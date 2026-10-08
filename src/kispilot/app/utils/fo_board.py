"""KOSPI200 선물·옵션 전광판 — 마스터에서 종목을 골라 시세를 모은다.

선물 (futures)  KOSPI200 선물 월물(일반 7 · 미니 6, 야간은 일반만)마다 선물옵션 시세(inquire_price)를 부른다.

옵션 (build)    마스터에서 ATM 근처 행사가를 골라 콜·풋 시세를 모은다.

KIS 옵션 전광판 API(display_board_callput)를 쓰지 않는 이유
    - 콜·풋 각각 행사가 높은 순 100건까지만 오고 연속조회가 안 된다. 일반 월물은 행사가가 300~500개라
      거래가 몰리는 ATM 부근이 잘린다 (위클리는 100개 안쪽이라 다 들어온다).
    - 야간(EU)은 지원하지 않는다 (OPSQ2001 INVALID FID_COND_MRKT_DIV_CODE).
그래서 마스터에서 기준가(ATM)에 가까운 행사가 2n+1개를 고르고, 종목마다 선물옵션 시세(inquire_price)를 부른다.
n=10 이면 기준가 1회 + 콜·풋 42회. 4개씩 겹쳐 보내 서버 속도 제한(실전 0.06초 간격) 근처까지 줄인다.
같은 조회는 BOARD_TTL 초 동안 캐시한다.

    상품(product)   regular 일반 · mini 미니 · weekly_thu 위클리(목) · weekly_mon 위클리(월)
    세션(session)   day 주간(F/O, 지수선물옵션 마스터) · night 야간(CM/EU, 야간선물·야간옵션 마스터)
    기준가          주간은 KOSPI200 지수, 야간은 지수가 멈춰 있으므로 야간 최근월 선물 현재가

KIS 호출은 build() 의 call 인자(토큰·속도 제한을 처리하는 함수)로 한다:
    call(fn, **kwargs) -> dict (KIS 응답 본문)
"""
from __future__ import annotations

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any, Callable, Literal, Optional

import pandas as pd

from kispilot.api import futureoption
from kispilot.api.data import master

Session = Literal["day", "night"]
Product = Literal["regular", "mini", "weekly_thu", "weekly_mon"]
Call = Callable[..., dict]

# 상품 → (이름, 콜 상품종류, 풋 상품종류). 상품종류는 마스터의 첫 필드.
PRODUCTS: dict[str, tuple[str, str, str]] = {
    "regular": ("일반", "5", "6"),
    "mini": ("미니", "D", "E"),
    "weekly_thu": ("위클리(목)", "L", "M"),
    "weekly_mon": ("위클리(월)", "N", "O"),
}
SESSIONS = ("day", "night")
_MASTER = {"day": ("index_fo", "index_fo"), "night": ("night_option", "night_future")}  # (옵션, 선물)
_MARKET_DIV = {"day": ("O", "F"), "night": ("EU", "CM")}  # (옵션, 선물)
_KOSPI200 = "2001"
_FUTURES_TYPE = "1"
# 선물 상품종류 → 이름 (스프레드 2·C 는 뺀다). 야간 마스터에는 미니선물이 없다.
FUTURES_PRODUCTS = {"1": "일반", "B": "미니"}

BOARD_TTL = 10
DEFAULT_N = 10
MAX_N = 15
_WORKERS = 4
_EXPIRY_RE = re.compile(r"\b(\d{6}|\d{4}W\d)\b")  # "C 202610 1,060.0" → 202610, "위클리C 2610W3 …" → 2610W3

_cache: dict[tuple, tuple[float, Any]] = {}
_cache_lock = threading.Lock()


class BoardError(Exception):
    pass


# ── 마스터 ───────────────────────────────────────────────────

def _expiry_key(expiry: str) -> tuple[int, int, int]:
    """만기 정렬 키. 202610 → (2026, 10, 9), 2610W3 → (2026, 10, 3) (같은 달이면 위클리가 앞)."""
    if "W" in expiry:
        yymm, week = expiry.split("W")
        return 2000 + int(yymm[:2]), int(yymm[2:]), int(week)
    return int(expiry[:4]), int(expiry[4:]), 9


def _expiry_label(expiry: str) -> str:
    year, month, week = _expiry_key(expiry)
    return f"{year}년 {month}월 {week}주" if "W" in expiry else f"{year}년 {month}월물"


_MONDAY, _THURSDAY = 0, 3


def _expiry_date(expiry: str, weekday: int = _THURSDAY) -> date:
    """만기일. 월물 202612 → 그 달 둘째 목요일, 위클리 2610W3 → 그 달 셋째 목요일 (월요일 위클리는 weekday=월).

    공휴일은 반영하지 않는다. 만기일이 공휴일이면 실제 만기는 그 전 영업일이라, 끝난 종목이 하루 늦게
    빠질 뿐 거래 중인 종목을 빼지는 않는다.
    """
    if "W" in expiry:
        yymm, nth = expiry.split("W")
        year, month, nth = 2000 + int(yymm[:2]), int(yymm[2:]), int(nth)
    else:
        year, month, nth = int(expiry[:4]), int(expiry[4:]), 2
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))


def _closed_through(session: Session, now: Optional[datetime] = None) -> date:
    """이 날짜까지 만기인 종목은 이 장에서 거래되지 않는다 (마스터는 다음 날 오전 7시에야 빠진다).

    주간: 어제까지 만기 (오늘 만기물은 장 마감 뒤에도 최종 가격을 보여준다).
    야간: 그 야간장이 시작한 날까지 만기 (수요일 18시에 시작한 야간장은 목요일 만기물을 거래한다).
    """
    now = now or datetime.now()
    if session == "day":
        return now.date() - timedelta(days=1)
    return now.date() if now.hour >= 18 else now.date() - timedelta(days=1)


def _live(expiries: pd.Series, session: Session, weekday: int = _THURSDAY) -> pd.Series:
    cutoff = _closed_through(session)
    return expiries.map(lambda e: _expiry_date(e, weekday) > cutoff)


def _options(session: Session, product: Product) -> pd.DataFrame:
    """KOSPI200 옵션 목록 (code, cp, expiry, strike, name)."""
    _, call_type, put_type = PRODUCTS[product]
    df = master.load(_MASTER[session][0])
    df = df[(df["기초자산단축코드"] == _KOSPI200) & df["상품종류"].isin([call_type, put_type])]
    out = pd.DataFrame({
        "code": df["단축코드"],
        "cp": df["상품종류"].map({call_type: "C", put_type: "P"}),
        "expiry": df["한글종목명"].str.extract(_EXPIRY_RE, expand=False),
        "strike": pd.to_numeric(df["행사가"], errors="coerce"),
        "name": df["한글종목명"],
    })
    out = out.dropna(subset=["expiry", "strike"])
    return out[_live(out["expiry"], session, _MONDAY if product == "weekly_mon" else _THURSDAY)]


def expiries(session: Session, product: Product) -> list[dict]:
    """상품의 만기 목록 (가까운 순). [{expiry, label, strikes}]"""
    _check(session, product)
    df = _options(session, product)
    counts = df[df["cp"] == "C"].groupby("expiry").size()
    return [{"expiry": e, "label": _expiry_label(e), "strikes": int(counts[e])}
            for e in sorted(counts.index, key=_expiry_key)]


def _near_futures(session: Session) -> Optional[str]:
    """최근월 KOSPI200 선물 코드 (미니·스프레드 제외)."""
    df = master.load(_MASTER[session][1])
    df = df[(df["기초자산단축코드"] == _KOSPI200) & (df["상품종류"] == _FUTURES_TYPE)]
    expiry = df["한글종목명"].str.extract(_EXPIRY_RE, expand=False)
    df = df.assign(expiry=expiry).dropna(subset=["expiry"])
    df = df[_live(df["expiry"], session)]
    if df.empty:
        return None
    return df.sort_values("expiry", key=lambda s: s.map(_expiry_key)).iloc[0]["단축코드"]


# ── 시세 ─────────────────────────────────────────────────────

def _num(v: Any) -> Optional[float]:
    try:
        return float(str(v).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _reference(session: Session, call: Call) -> dict:
    """기준가. 주간은 KOSPI200 지수, 야간은 야간 최근월 선물 현재가."""
    code = _near_futures(session)
    if code is None:
        raise BoardError("KOSPI200 선물 종목을 마스터에서 찾지 못했습니다.")
    data = call(futureoption.inquire_price, code=code, market_div=_MARKET_DIV[session][1])
    if data.get("rt_cd") != "0":
        raise BoardError(f"기준가 조회 실패: {data.get('msg1') or data.get('msg_cd')}")
    fut = data.get("output1") or {}
    idx = data.get("output3") or {}
    index, futures = _num(idx.get("bstp_nmix_prpr")), _num(fut.get("futs_prpr"))
    price = futures if session == "night" else index
    if not price:
        raise BoardError("기준가(KOSPI200 지수·선물 현재가)를 받지 못했습니다.")
    return {
        "price": price,
        "source": "야간 선물" if session == "night" else "KOSPI200 지수",
        "index": index,
        "futures": futures,
        "futures_code": code,
    }


def _quote(code: str, market_div: str, call: Call, futures: bool = False) -> dict:
    """종목 하나의 시세. 선물이면 베이시스·고저가·잔존일과 KOSPI200 지수(index)도 담는다."""
    data = call(futureoption.inquire_price, code=code, market_div=market_div)
    if data.get("rt_cd") != "0":
        return {"code": code, "error": data.get("msg1") or data.get("msg_cd") or "조회 실패"}
    o = data.get("output1") or {}
    q = {
        "code": code,
        "price": _num(o.get("futs_prpr")),
        "change": _num(o.get("futs_prdy_vrss")),
        "change_rate": _num(o.get("futs_prdy_ctrt")),
        "sign": o.get("prdy_vrss_sign"),
        "volume": _num(o.get("acml_vol")),
        "open_interest": _num(o.get("hts_otst_stpl_qty")),
        "oi_change": _num(o.get("otst_stpl_qty_icdc")),
        "theory": _num(o.get("hts_thpr")),
    }
    if not futures:
        return q | {"iv": _num(o.get("hts_ints_vltl")), "delta": _num(o.get("delta_val"))}
    idx = data.get("output3") or {}
    return q | {
        "open": _num(o.get("futs_oprc")),
        "high": _num(o.get("futs_hgpr")),
        "low": _num(o.get("futs_lwpr")),
        "basis": _num(o.get("basis")),
        "market_basis": _num(o.get("mrkt_basis")),
        "days_left": _num(o.get("hts_rmnn_dynu")),
        "last_trade_date": o.get("futs_last_tr_date"),
        "index": {
            "price": _num(idx.get("bstp_nmix_prpr")),
            "change": _num(idx.get("bstp_nmix_prdy_vrss")),
            "change_rate": _num(idx.get("bstp_nmix_prdy_ctrt")),
            "sign": idx.get("prdy_vrss_sign"),
        },
    }


def _check(session: str, product: str) -> None:
    """잘못된 인자는 ValueError (데이터가 없는 경우의 BoardError 와 구분)."""
    if session not in SESSIONS:
        raise ValueError(f"session 은 {'/'.join(SESSIONS)} 중 하나입니다.")
    if product not in PRODUCTS:
        raise ValueError(f"product 는 {'/'.join(PRODUCTS)} 중 하나입니다.")


def _load(session: Session, product: Product, expiry: str, n: int, call: Call) -> dict:
    df = _options(session, product)
    df = df[df["expiry"] == expiry]
    if df.empty:
        raise BoardError(f"{PRODUCTS[product][0]} 옵션 만기 {expiry} 를 찾지 못했습니다.")
    ref = _reference(session, call)
    strikes = sorted(df["strike"].unique())
    atm = min(strikes, key=lambda s: abs(s - ref["price"]))
    near = sorted(sorted(strikes, key=lambda s: abs(s - atm))[: 2 * n + 1], reverse=True)

    market_div = _MARKET_DIV[session][0]
    codes = {(r.strike, r.cp): r.code for r in df.itertuples()}
    cells = [(strike, cp) for strike in near for cp in ("C", "P") if (strike, cp) in codes]
    # 호출 시작 간격은 call 쪽 속도 제한이 지키고, 여기서는 응답 대기만 겹친다 (MCP batch_query 와 같은 4개)
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        quotes = dict(zip(cells, pool.map(lambda c: _quote(codes[c], market_div, call), cells)))
    rows = [{"strike": s, "call": quotes.get((s, "C")), "put": quotes.get((s, "P"))} for s in near]
    return {
        "session": session,
        "product": product,
        "product_label": PRODUCTS[product][0],
        "expiry": expiry,
        "expiry_label": _expiry_label(expiry),
        "market_div": market_div,
        "reference": ref,
        "atm": atm,
        "strikes_total": len(strikes),
        "rows": rows,
        "as_of": time.strftime("%H:%M:%S"),
    }


def _cached(key: tuple, loader: Callable[[], dict]) -> dict:
    with _cache_lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < BOARD_TTL:
            return hit[1]
    value = loader()
    with _cache_lock:
        _cache[key] = (time.time(), value)
    return value


def build(session: Session, product: Product, expiry: str, n: int, call: Call) -> dict:
    """옵션 전광판 표. rows 는 행사가 높은 순, 각 행에 call/put 시세 (해당 종목이 없으면 None)."""
    _check(session, product)
    n = max(1, min(int(n), MAX_N))
    return _cached(("options", session, product, expiry, n), lambda: _load(session, product, expiry, n, call))


# ── 선물 ─────────────────────────────────────────────────────

def _futures_list(session: Session) -> pd.DataFrame:
    """KOSPI200 선물 월물 목록 (code, product, expiry). 일반 먼저, 같은 상품은 가까운 만기 순."""
    df = master.load(_MASTER[session][1])
    df = df[(df["기초자산단축코드"] == _KOSPI200) & df["상품종류"].isin(list(FUTURES_PRODUCTS))]
    out = pd.DataFrame({
        "code": df["단축코드"],
        "product": df["상품종류"],
        "expiry": df["한글종목명"].str.extract(_EXPIRY_RE, expand=False),
    }).dropna(subset=["expiry"])
    out = out[_live(out["expiry"], session)]
    order = {t: i for i, t in enumerate(FUTURES_PRODUCTS)}
    return out.sort_values(["product", "expiry"], key=lambda s: s.map(order) if s.name == "product" else s.map(_expiry_key))


def _load_futures(session: Session, call: Call) -> dict:
    df = _futures_list(session)
    if df.empty:
        raise BoardError("KOSPI200 선물 종목을 마스터에서 찾지 못했습니다.")
    market_div = _MARKET_DIV[session][1]
    with ThreadPoolExecutor(max_workers=_WORKERS) as pool:
        quotes = list(pool.map(lambda c: _quote(c, market_div, call, futures=True), df["code"]))
    index = next((q["index"] for q in quotes if q.get("index")), None)
    rows = []
    for r, q in zip(df.itertuples(), quotes):
        q.pop("index", None)
        rows.append({"product": "mini" if r.product == "B" else "regular", "product_label": FUTURES_PRODUCTS[r.product],
                     "expiry": r.expiry, "expiry_label": _expiry_label(r.expiry)} | q)
    return {"session": session, "market_div": market_div, "index": index, "rows": rows,
            "as_of": time.strftime("%H:%M:%S")}


def futures(session: Session, call: Call) -> dict:
    """선물 전광판. rows 는 일반 → 미니, 같은 상품은 가까운 만기 순. index 는 KOSPI200 지수."""
    if session not in SESSIONS:
        raise ValueError(f"session 은 {'/'.join(SESSIONS)} 중 하나입니다.")
    return _cached(("futures", session), lambda: _load_futures(session, call))
