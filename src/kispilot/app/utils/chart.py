"""차트용 봉(OHLCV) 데이터.

과거 구간은 yfinance 로 한 번에 받고, 최근 구간은 KIS 로 보강한다.

    일·주·월·년  yfinance 전체 일봉(period="max") → 주/월/년은 일봉을 합쳐서 만든다.
                 마지막(당일) 봉은 KIS 일별 시세로 덮어쓴다.
                 yfinance 에 없는 종목(신규 상장 등)과 KOSPI200 은 KIS 기간별 시세로 대신 받는다.
    1분·5분·30분 yfinance 분봉(1분 7일, 5분·30분 60일) + 최근 거래일은 KIS 당일 1분봉으로 교체.
                 yfinance 분봉은 약 15분 지연되고 종가 단일가(15:20~15:30)가 빠지기 때문이다.
                 5분·30분은 KIS 1분봉을 묶어서 만든다. 지수 분봉은 KIS API 가 없어 yfinance 만 쓴다.
    선물·옵션    (kind="fo", KOSPI200) yfinance 에 없어 KIS 기간별 시세·분봉만 쓴다. session 으로 주간/야간을 고른다.

KIS 호출은 build() 의 call 인자(토큰·속도 제한을 처리하는 함수)로 한다:
    call(fn, **kwargs) -> dict (KIS 응답 본문)
"""
from __future__ import annotations

import calendar
import threading
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Literal, Optional

import pandas as pd

from kispilot.api import futureoption, price, sector
from kispilot.app.utils.utils import get_history

Timeframe = Literal["1m", "5m", "30m", "D", "W", "M", "Y"]
TIMEFRAMES = ("1m", "5m", "30m", "D", "W", "M", "Y")
Call = Callable[..., dict]

_COLS = ["Open", "High", "Low", "Close", "Volume"]
_INTRADAY = {"1m": ("1m", "7d", 1), "5m": ("5m", "60d", 5), "30m": ("30m", "60d", 30)}
_RESAMPLE = {"W": "W-FRI", "M": "ME", "Y": "YE"}

# 지수: 업종코드 → yfinance 티커 (KOSPI200 은 yfinance 일봉이 없어 KIS 로 받는다)
INDEX_SYMBOL = {"0001": "^KS11", "1001": "^KQ11", "2001": "^KS200"}
_KIS_ONLY_DAILY = {"2001"}

_DAILY_TTL = 6 * 3600
_INTRADAY_TTL = 300
_KIS_FULL_TTL = 600  # 당일 분봉 전체 재조회 주기 (그 사이에는 최근 30개만 갱신)

_cache: dict[tuple, tuple[float, Any]] = {}
_cache_lock = threading.Lock()
_kis_minutes: dict[str, dict] = {}
_kis_locks: dict[str, threading.Lock] = {}


class ChartError(Exception):
    pass


# ── 공통 ─────────────────────────────────────────────────────

def _cached(key: tuple, ttl: float, loader: Callable[[], Any]) -> Any:
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
    value = loader()
    with _cache_lock:
        _cache[key] = (time.time(), value)
    return value


def _num(v: Any) -> Optional[float]:
    try:
        x = float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return x


def _frame(rows: list[dict], index: list) -> pd.DataFrame:
    df = pd.DataFrame(rows, index=pd.DatetimeIndex(index), columns=_COLS)
    return df[~df.index.duplicated(keep="last")].sort_index()


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df[_COLS].copy()
    return df[df["Close"].notna() & (df["Close"] > 0)]


def _resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """일봉 → 주/월/년봉. 봉의 날짜는 그 구간의 첫 거래일."""
    if tf == "D" or df.empty:
        return df
    x = df.copy()
    x["_d"] = x.index
    g = x.resample(_RESAMPLE[tf]).agg(
        {"_d": "first", "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    ).dropna(subset=["Close"])
    g.index = pd.DatetimeIndex(g.pop("_d"))
    return g


def _bucket(df1m: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """1분봉 → N분봉 (09:00 기준으로 나눠짐)."""
    if minutes == 1 or df1m.empty:
        return df1m
    key = df1m.index.floor(f"{minutes}min")
    return df1m.groupby(key).agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})


# ── yfinance ─────────────────────────────────────────────────

def _yf(symbol: str, interval: str, period: str) -> pd.DataFrame:
    def load() -> pd.DataFrame:
        try:
            # auto_adjust=False: 배당 조정 없이 분할만 반영된 가격 (HTS 수정주가와 같은 기준)
            df = get_history(symbol, period=period, interval=interval, auto_adjust=False)
        except Exception:
            return pd.DataFrame(columns=_COLS)
        return _clean(df)

    ttl = _DAILY_TTL if interval == "1d" else _INTRADAY_TTL
    return _cached(("yf", symbol, interval, period), ttl, load)


# ── KIS: 일봉 계열 ───────────────────────────────────────────

def _kis_daily(kind: str, code: str, tf: str, call: Call) -> pd.DataFrame:
    """KIS 기간별 시세를 뒤로 이어 조회 (주식 100건/호출, 지수 50건/호출)."""
    pages = {"D": 6, "W": 3, "M": 3, "Y": 1}[tf]
    per_page = 100 if kind == "stock" else 50
    end = datetime.now()
    rows: dict[str, dict] = {}
    for _ in range(pages):
        if kind == "stock":
            d = call(price.inquire_daily_itemchartprice, code=code, start_date="19800101",
                     end_date=end.strftime("%Y%m%d"), period_div=tf)
            fields = ("stck_oprc", "stck_hgpr", "stck_lwpr", "stck_clpr")
        else:
            d = call(sector.inquire_daily_indexchartprice, iscd=code, start_date="19800101",
                     end_date=end.strftime("%Y%m%d"), period_div=tf)
            fields = ("bstp_nmix_oprc", "bstp_nmix_hgpr", "bstp_nmix_lwpr", "bstp_nmix_prpr")
        out = [r for r in (d.get("output2") or []) if r.get("stck_bsop_date")]
        for r in out:
            o, h, lo, c = (_num(r.get(f)) for f in fields)
            if c:
                rows[r["stck_bsop_date"]] = {"Open": o or c, "High": h or c, "Low": lo or c, "Close": c,
                                             "Volume": _num(r.get("acml_vol")) or 0}
        if len(out) < per_page:
            break
        oldest = min(r["stck_bsop_date"] for r in out)
        end = datetime.strptime(oldest, "%Y%m%d") - timedelta(days=1)
    dates = sorted(rows)
    return _frame([rows[k] for k in dates], [pd.Timestamp(k) for k in dates])


def _kis_last_day(kind: str, code: str, call: Call) -> Optional[tuple[pd.Timestamp, dict]]:
    """가장 최근 거래일의 일봉 (당일 장중이면 현재까지)."""
    try:
        if kind == "stock":
            r = (call(price.inquire_daily_price, code=code).get("output") or [{}])[0]
            vals = (r.get("stck_oprc"), r.get("stck_hgpr"), r.get("stck_lwpr"), r.get("stck_clpr"))
        else:
            r = (call(sector.inquire_index_daily_price, iscd=code,
                      date=datetime.now().strftime("%Y%m%d")).get("output2") or [{}])[0]
            vals = (r.get("bstp_nmix_oprc"), r.get("bstp_nmix_hgpr"), r.get("bstp_nmix_lwpr"), r.get("bstp_nmix_prpr"))
    except Exception:
        return None
    o, h, lo, c = (_num(v) for v in vals)
    if not r.get("stck_bsop_date") or not c:
        return None
    return pd.Timestamp(r["stck_bsop_date"]), {"Open": o or c, "High": h or c, "Low": lo or c, "Close": c,
                                               "Volume": _num(r.get("acml_vol")) or 0}


# ── KIS: 당일 1분봉 ──────────────────────────────────────────

def _kis_today_minutes(code: str, call: Call) -> pd.DataFrame:
    """최근 거래일 1분봉. 처음(또는 10분마다)은 09:00 까지 전부, 그 사이에는 최근 30개만 받아 합친다."""
    lock = _kis_locks.setdefault(code, threading.Lock())
    with lock:
        now = datetime.now()
        hhmmss = now.strftime("%H%M%S")
        start_hour = hhmmss if "090000" <= hhmmss <= "153000" else "153000"

        entry = _kis_minutes.get(code)
        full = entry is None or time.time() - entry["full_at"] > _KIS_FULL_TTL
        bars: dict[str, dict] = {} if full else dict(entry["bars"])
        day = None if full else entry["date"]
        hour = start_hour
        max_pages = 15 if full else 1
        page = 0
        while page < max_pages:
            page += 1
            d = call(price.inquire_time_itemchartprice, code=code, input_hour=hour)
            out = [r for r in (d.get("output2") or []) if r.get("stck_cntg_hour") and r.get("stck_bsop_date")]
            if not out:
                break
            if day is None or out[0]["stck_bsop_date"] != day:
                if day is not None:  # 거래일이 바뀜 → 처음부터 다시
                    bars, max_pages, full = {}, 15, True
                day = out[0]["stck_bsop_date"]
            out = [r for r in out if r["stck_bsop_date"] == day]
            for r in out:
                vol = _num(r.get("cntg_vol")) or 0
                c = _num(r.get("stck_prpr"))
                if not c or vol <= 0:
                    continue  # 체결 없는 분(15:21~15:29 등)은 봉을 만들지 않는다
                bars[r["stck_cntg_hour"]] = {"Open": _num(r.get("stck_oprc")) or c, "High": _num(r.get("stck_hgpr")) or c,
                                             "Low": _num(r.get("stck_lwpr")) or c, "Close": c, "Volume": vol}
            earliest = min(r["stck_cntg_hour"] for r in out)
            if len(out) < 30 or earliest <= "090000":
                break
            hour = (datetime.strptime(earliest, "%H%M%S") - timedelta(minutes=1)).strftime("%H%M%S")

        if day is None:
            return pd.DataFrame(columns=_COLS)
        _kis_minutes[code] = {"date": day, "bars": bars,
                              "full_at": time.time() if full else entry["full_at"]}
        keys = sorted(bars)
        return _frame([bars[k] for k in keys], [datetime.strptime(day + k, "%Y%m%d%H%M%S") for k in keys])


# ── KIS: 선물·옵션 (KOSPI200) ────────────────────────────────
# yfinance 에는 국내 선물옵션이 없어 KIS 만 쓴다. 분봉 API 가 봉 간격을 직접 받으므로 1분봉을 묶지 않는다.
_FO_MINUTE = {"1m": ("60", 4), "5m": ("300", 3), "30m": ("1800", 2)}  # (봉 간격 초, 최대 호출 수 — 호출당 102봉)
_FO_DAILY_PAGES = {"D": 3, "W": 2, "M": 1}                             # 호출당 100봉
_FO_TTL = 15
FO_TIMEFRAMES = ("1m", "5m", "30m", "D", "W", "M")


def fo_market_div(code: str, session: str) -> str:
    """KOSPI200 선물 코드는 A…, 옵션은 B…(콜)·C…(풋). 주간 F/O, 야간 CM/EU."""
    futures = code.startswith("A")
    if session == "night":
        return "CM" if futures else "EU"
    return "F" if futures else "O"


def _fo_time(day: str, hhmmss: str) -> datetime:
    """봉 시각. 야간 봉은 장 시작일 + 24시를 넘긴 시간으로 온다 (20261007 280500 = 10/08 04:05)."""
    return datetime.strptime(day, "%Y%m%d") + timedelta(
        hours=int(hhmmss[:2]), minutes=int(hhmmss[2:4]), seconds=int(hhmmss[4:6]))


def _fo_bar(r: dict, volume_key: str) -> Optional[dict]:
    c = _num(r.get("futs_prpr"))
    if not c:
        return None
    return {"Open": _num(r.get("futs_oprc")) or c, "High": _num(r.get("futs_hgpr")) or c,
            "Low": _num(r.get("futs_lwpr")) or c, "Close": c, "Volume": _num(r.get(volume_key)) or 0}


def _fo_daily(code: str, market_div: str, tf: str, call: Call) -> pd.DataFrame:
    """선물옵션 기간별 시세를 뒤로 이어 조회. 야간 일봉의 날짜는 그 야간장이 시작한 날."""
    end = datetime.now()
    rows: dict[str, dict] = {}
    for _ in range(_FO_DAILY_PAGES[tf]):
        d = call(futureoption.inquire_daily_fuopchartprice, code=code, market_div=market_div,
                 start_date="20000101", end_date=end.strftime("%Y%m%d"), period_div=tf)
        out = [r for r in (d.get("output2") or []) if r.get("stck_bsop_date")]
        for r in out:
            bar = _fo_bar(r, "acml_vol")
            if bar:
                rows[r["stck_bsop_date"]] = bar
        if len(out) < 100:
            break
        end = datetime.strptime(min(r["stck_bsop_date"] for r in out), "%Y%m%d") - timedelta(days=1)
    dates = sorted(rows)
    return _frame([rows[k] for k in dates], [pd.Timestamp(k) for k in dates])


def _fo_minutes(code: str, market_div: str, tf: str, call: Call) -> pd.DataFrame:
    """선물옵션 분봉을 최근부터 뒤로 이어 조회. 체결 없는 분은 봉이 없다 (거래 없는 옵션은 빈 차트)."""
    cls, pages = _FO_MINUTE[tf]
    date, hour = datetime.now().strftime("%Y%m%d"), "999999"
    bars: dict[datetime, dict] = {}
    for _ in range(pages):
        d = call(futureoption.inquire_time_fuopchartprice, code=code, market_div=market_div,
                 input_hour=hour, input_date=date, hour_cls_code=cls)
        out = [r for r in (d.get("output2") or []) if r.get("stck_bsop_date") and r.get("stck_cntg_hour")]
        for r in out:
            bar = _fo_bar(r, "cntg_vol")
            if bar and bar["Volume"] > 0:
                bars[_fo_time(r["stck_bsop_date"], r["stck_cntg_hour"])] = bar
        if len(out) < 102:
            break
        # 최근 순으로 오므로 마지막이 가장 이른 봉. 그 일자·시간(야간은 24시+ 그대로)부터 이어 받는다 (겹치는 봉은 덮어씀)
        date, hour = out[-1]["stck_bsop_date"], out[-1]["stck_cntg_hour"]
    keys = sorted(bars)
    return _frame([bars[k] for k in keys], keys)


def _fo(code: str, tf: str, session: str, call: Call, sources: list[str]) -> pd.DataFrame:
    market_div = fo_market_div(code, session)
    label = "야간" if session == "night" else "주간"
    if tf in _FO_MINUTE:
        sources.append(f"KIS 선물옵션 분봉 ({label} {market_div})")
        return _cached(("fo", code, market_div, tf), _FO_TTL, lambda: _fo_minutes(code, market_div, tf, call))
    sources.append(f"KIS 선물옵션 기간별 시세 ({label} {market_div})")
    return _cached(("fo", code, market_div, tf), _FO_TTL, lambda: _fo_daily(code, market_div, tf, call))


# ── 조립 ─────────────────────────────────────────────────────

def _daily(kind: str, code: str, tf: str, call: Call, sources: list[str]) -> pd.DataFrame:
    if kind == "index" and code in _KIS_ONLY_DAILY:
        sources.append("KIS 기간별 시세")
        return _kis_daily(kind, code, tf, call)

    symbol = INDEX_SYMBOL[code] if kind == "index" else code
    df = _yf(symbol, "1d", "max")
    if df.empty:
        sources.append("KIS 기간별 시세 (yfinance 없음)")
        return _kis_daily(kind, code, tf, call)
    sources.append("yfinance 일봉")

    last = _kis_last_day(kind, code, call)
    if last is not None:
        ts, bar = last
        df = pd.concat([df.drop(index=ts, errors="ignore"), pd.DataFrame([bar], index=pd.DatetimeIndex([ts]))]).sort_index()
        sources.append(f"KIS {ts:%m/%d} 일봉")
    return _resample(df, tf)


def _intraday(kind: str, code: str, tf: str, call: Call, sources: list[str]) -> pd.DataFrame:
    interval, period, minutes = _INTRADAY[tf]
    symbol = INDEX_SYMBOL[code] if kind == "index" else code
    df = _yf(symbol, interval, period)
    if not df.empty:
        sources.append(f"yfinance {interval} ({period})")

    if kind == "stock":
        try:
            kis = _kis_today_minutes(code, call)
        except Exception:
            kis = pd.DataFrame(columns=_COLS)
        if not kis.empty:
            day = kis.index[0].normalize()
            df = pd.concat([df[df.index.normalize() != day], _bucket(kis, minutes)]).sort_index()
            sources.append(f"KIS {day:%m/%d} 1분봉")
    return df


def _to_bars(df: pd.DataFrame, intraday: bool) -> list[dict]:
    out = []
    for ts, r in df.iterrows():
        if pd.isna(r["Close"]):
            continue
        # 분봉: KST 시각을 그대로 UTC 로 취급한 유닉스 초 (차트가 UTC 로 그리므로 화면에 KST 로 보인다)
        t = calendar.timegm(ts.timetuple()) if intraday else ts.strftime("%Y-%m-%d")
        c = round(float(r["Close"]), 2)
        px = lambda k: round(float(r[k]), 2) if pd.notna(r[k]) else c  # noqa: E731
        out.append({
            "time": t,
            "open": px("Open"),
            "high": px("High"),
            "low": px("Low"),
            "close": c,
            "volume": int(r["Volume"]) if pd.notna(r["Volume"]) else 0,
        })
    return out


def daily_frame(code: str, kind: Literal["stock", "index"], call: Call) -> tuple[pd.DataFrame, list[str]]:
    """전체 일봉 DataFrame(Open·High·Low·Close·Volume, 날짜 인덱스)과 출처 — 백테스트용."""
    if kind == "index" and code not in INDEX_SYMBOL:
        raise ChartError(f"지원하는 지수 코드: {list(INDEX_SYMBOL)}")
    sources: list[str] = []
    df = _daily(kind, code, "D", call, sources)
    df = df[df["Close"].notna()]
    if df.empty:
        raise ChartError("일봉 데이터가 없습니다.")
    return df, sources


def build(code: str, tf: str, kind: Literal["stock", "index", "fo"], call: Call, session: str = "day") -> dict:
    if kind == "fo":
        if tf not in FO_TIMEFRAMES:
            raise ChartError(f"선물·옵션 tf 는 {list(FO_TIMEFRAMES)} 중 하나입니다.")
        sources: list[str] = []
        intraday = tf in _FO_MINUTE
        bars = _to_bars(_fo(code, tf, session, call, sources), intraday)
        if not bars:
            raise ChartError("차트 데이터가 없습니다 (이 장에서 체결이 없는 종목).")
        return {"code": code, "kind": kind, "tf": tf, "session": session, "intraday": intraday,
                "sources": sources, "bars": bars}
    if tf not in TIMEFRAMES:
        raise ChartError(f"tf 는 {list(TIMEFRAMES)} 중 하나입니다.")
    if kind == "index" and code not in INDEX_SYMBOL:
        raise ChartError(f"지원하는 지수 코드: {list(INDEX_SYMBOL)}")

    sources: list[str] = []
    intraday = tf in _INTRADAY
    df = _intraday(kind, code, tf, call, sources) if intraday else _daily(kind, code, tf, call, sources)
    bars = _to_bars(df, intraday)
    if not bars:
        raise ChartError("차트 데이터가 없습니다.")
    return {"code": code, "kind": kind, "tf": tf, "intraday": intraday, "sources": sources, "bars": bars}
