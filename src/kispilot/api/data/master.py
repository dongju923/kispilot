"""KIS 종목·업종 마스터 파일 — 내려받기, 하루 한 번 갱신, 검색.

한투가 매일 갱신하는 마스터(.mst.zip)를 받아 CSV 로 바꿔 사용자 데이터 폴더에 둔다.
    <데이터 폴더>/data/kospi_code.csv · kosdaq_code.csv · idxcode.csv

갱신 규칙
    - 하루에 한 번. 하루의 경계는 오전 7시 (장 시작 전 갱신분을 받도록).
      파일이 그 시각 이전에 만들어졌으면 다음 조회 때 새로 받는다.
    - 받기에 실패하면 예전 파일을 그대로 쓰고, 10분 동안은 다시 시도하지 않는다.
    - SSL 인증서 검증을 끄지 않는다. 임시 폴더에서 풀고, 다 만든 CSV 만 원자적으로 교체한다
      (웹 서버와 MCP 서버가 동시에 읽어도 반쯤 쓴 파일을 보지 않게).
"""
from __future__ import annotations

import io
import logging
import os
import tempfile
import threading
import time
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Literal

import pandas as pd
import requests

from kispilot.paths import data_dir

Kind = Literal["kospi", "kosdaq", "sector"]

_BASE_URL = "https://new.real.download.dws.co.kr/common/master/"
_DAY_STARTS_AT = 7          # 이 시각(로컬) 이전에 받은 파일은 하루 지난 것으로 본다
_RETRY_AFTER = 600          # 받기 실패 후 재시도까지 (초)
_log = logging.getLogger("kispilot.master")


def _parsers() -> dict[str, tuple[str, str, Callable[[Path], pd.DataFrame]]]:
    from kispilot.api.data import kosdaq, kospi, sector
    return {
        "kospi": ("kospi_code.mst.zip", "kospi_code.csv", kospi.parse),
        "kosdaq": ("kosdaq_code.mst.zip", "kosdaq_code.csv", kosdaq.parse),
        "sector": ("idxcode.mst.zip", "idxcode.csv", sector.parse),
    }


def csv_path(kind: Kind) -> Path:
    return data_dir() / "data" / _parsers()[kind][1]


def _day_start(now: datetime) -> datetime:
    start = now.replace(hour=_DAY_STARTS_AT, minute=0, second=0, microsecond=0)
    return start if now >= start else start - timedelta(days=1)


def is_fresh(kind: Kind, now: datetime | None = None) -> bool:
    p = csv_path(kind)
    return p.exists() and datetime.fromtimestamp(p.stat().st_mtime) >= _day_start(now or datetime.now())


def refresh(kind: Kind) -> Path:
    """마스터를 내려받아 CSV 를 새로 만든다 (실패하면 예외, 기존 파일은 그대로)."""
    zip_name, csv_name, parse = _parsers()[kind]
    r = requests.get(_BASE_URL + zip_name, timeout=30)  # SSL 인증서 검증은 기본값(켜짐)
    r.raise_for_status()
    out = csv_path(kind)
    out.parent.mkdir(parents=True, exist_ok=True)
    # 임시 폴더를 같은 폴더 안에 만들어야 os.replace 가 같은 드라이브 안에서 원자적으로 동작한다
    with tempfile.TemporaryDirectory(dir=out.parent, prefix=".tmp-") as tmp:
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            member = next((n for n in z.namelist() if n.lower().endswith(".mst")), None)
            if member is None:
                raise ValueError(f"{zip_name} 안에 .mst 파일이 없습니다.")
            mst = Path(z.extract(member, tmp))
        df = parse(mst)
        if df.empty:
            raise ValueError(f"{zip_name} 를 읽었지만 종목이 없습니다.")
        part = Path(tmp) / csv_name
        df.to_csv(part, index=False)
        os.replace(part, out)
    return out


# ── 읽기 (메모리 캐시) ────────────────────────────────────────

_cache: dict[str, tuple[datetime, pd.DataFrame]] = {}
_fail_until: dict[str, float] = {}
_locks = {k: threading.Lock() for k in ("kospi", "kosdaq", "sector")}


def load(kind: Kind) -> pd.DataFrame:
    """마스터 DataFrame (모든 값은 문자열). 하루가 지났으면 새로 받는다."""
    with _locks[kind]:
        now = datetime.now()
        hit = _cache.get(kind)
        if hit and hit[0] >= _day_start(now) and is_fresh(kind, now):
            return hit[1]
        path = csv_path(kind)
        if not is_fresh(kind, now) and time.time() >= _fail_until.get(kind, 0):
            try:
                refresh(kind)
            except Exception as e:
                _fail_until[kind] = time.time() + _RETRY_AFTER
                if not path.exists():
                    raise RuntimeError(f"{kind} 마스터 파일을 받지 못했습니다 ({type(e).__name__}: {e})") from e
                _log.warning("%s 마스터 갱신 실패 — 예전 파일을 씁니다: %s", kind, e)
        df = pd.read_csv(path, dtype=str)
        _cache[kind] = (now, df)
        return df


# ── 검색 ─────────────────────────────────────────────────────

def search_stocks(query: str, market: str = "all", limit: int = 20) -> list[dict]:
    """종목명(부분 일치) 또는 6자리 코드로 검색. 정확히 일치 → 짧은 이름 순."""
    q = query.strip()
    results = []
    for kind in (["kospi", "kosdaq"] if market == "all" else [market]):
        df = load(kind)
        name_col = "한글명" if "한글명" in df.columns else "한글종목명"
        names = df[name_col].fillna("").str.strip()
        codes = df["단축코드"].fillna("").str.strip()
        hit = names.str.contains(q, case=False, regex=False) | (codes == q)
        for code, name in zip(codes[hit], names[hit]):
            results.append({"code": code, "name": name, "market": kind.upper()})
    results.sort(key=lambda r: (r["name"] != q and r["code"] != q, len(r["name"])))
    return results[:limit]


def stock_names() -> dict[str, str]:
    """{6자리 코드: 종목명} (코스피 + 코스닥)."""
    out: dict[str, str] = {}
    for kind in ("kospi", "kosdaq"):
        df = load(kind)
        name_col = "한글명" if "한글명" in df.columns else "한글종목명"
        out.update(zip(df["단축코드"].fillna("").str.strip(), df[name_col].fillna("").str.strip()))
    return out


def search_sectors(query: str, limit: int = 30) -> list[dict]:
    """업종/지수명(부분 일치) 또는 4자리 업종코드로 검색."""
    df = load("sector")
    q = query.strip()
    codes = df["업종코드"].fillna("").str.strip().str.zfill(4)
    names = df["업종명"].fillna("").str.strip()
    hit = names.str.contains(q, case=False, regex=False) | (codes == q)
    return [{"code": c, "name": n} for c, n in zip(codes[hit], names[hit])][:limit]
