"""뉴스 제목 정리 — 웹 콘솔 뉴스 카드(/api/news)와 MCP stock_news 가 같이 쓴다.

KIS 종합 시황/공시(news_title)는 시장 전체를 조회하면 정치·사회·연예 기사까지 섞여 오고,
종목코드로 조회해도 그 종목이 본문에만 나오는 시황 기사가 많이 섞인다. 여기서 주식 관련 기사만 고른다.

    시장 뉴스 (code 없음)  제목에 증시 용어(코스피·특징주·목표가 …)가 있거나, KIS 가 연결한 종목의 이름이 제목에 있는 기사
    종목 뉴스 (code 있음)  제목에 종목 이름(약칭 포함)이 있거나, KIS 가 그 종목을 첫 번째로 연결했고(iscd1)
                           시장 전체 시황 기사(코스피·마감·상위종목 …)가 아닌 기사

한 번 조회에 40건(시장 전체는 약 5분 치)이라, 모자라면 마지막 기사 시각부터 이어서 최대 3번 더 받는다.
KIS 는 기사 주소를 주지 않으므로 링크는 제목 검색 주소로 만든다.
"""
from __future__ import annotations

import re
from typing import Callable
from urllib.parse import quote

MAX_PAGES = 3

_MARKET_RE = re.compile(
    r"코스피|코스닥|증시|특징주|주가|주식|株|종목|상장|공시|시총|시가총액|목표가|목표주가|투자의견|증권사|리포트|"
    r"순매수|순매도|상한가|하한가|신고가|신저가|52주|거래대금|거래량|매수우위|매도우위|"
    r"ETF|ETN|IPO|공모주|자사주|배당|실적|영업이익|어닝|밸류업|공매도"
)

# 종목 뉴스에서 뺄 시장 전체 시황 기사 (KIS 가 종목을 연결해 두지만 제목에 그 종목이 없는 것)
_WRAP_RE = re.compile(r"코스피|코스닥|증시|시황|개장|장마감|마감|상위\s*\d*\s*종목|순매수,도|인기검색|기술적 분석")

# 제목에 자주 쓰는 약칭 (종목명 앞 4글자로 못 잡는 것)
_ALIASES = {
    "005930": ("삼전", "삼전닉스"),
    "000660": ("하이닉스", "삼전닉스"),
    "373220": ("LG엔솔", "엔솔", "엘지에너지솔루션"),
    "207940": ("삼바",),
    "005380": ("현대자동차",),
    "035420": ("네이버",),
    "035720": ("카카오",),
}


class NewsError(RuntimeError):
    pass


def search_url(title: str) -> str:
    """KIS 뉴스 API 는 기사 주소를 주지 않으므로 제목 검색으로 연결한다."""
    return "https://www.google.com/search?q=" + quote(title or "")


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "").upper()


def _name_keys(code: str, name: str) -> set[str]:
    """제목에서 찾을 종목 이름들: 전체 이름, 긴 이름은 앞 4글자(SK이노베이션 → SK이노), 약칭."""
    n = _norm(re.sub(r"\(.*?\)", "", name or ""))
    keys = {n} if n else set()
    if len(n) >= 5:
        keys.add(n[:4])
    keys.update(_norm(a) for a in _ALIASES.get(code, ()))
    return keys


def _names() -> dict[str, str]:
    try:
        from kispilot.api.data import master
        return master.stock_names()
    except Exception:
        return {}


def _row(x: dict, names: dict[str, str]) -> dict:
    title = (x.get("hts_pbnt_titl_cntt") or "").strip()
    code = (x.get("iscd1") or "").strip()
    return {
        "date": x.get("data_dt") or "",
        "time": x.get("data_tm") or "",
        "title": title,
        "source": (x.get("dorg") or "").strip(),
        "code": code,
        "name": names.get(code, ""),
        "url": search_url(title),
    }


def _is_market_news(row: dict) -> bool:
    if _MARKET_RE.search(row["title"]):
        return True
    t = _norm(row["title"])
    return bool(row["name"]) and any(k in t for k in _name_keys(row["code"], row["name"]))


def fetch(kis_call: Callable[..., dict], code: str = "", count: int = 20) -> list[dict]:
    """주식 관련 뉴스 최신순 count 건. kis_call(fn, **kwargs) 는 KIS 함수를 불러 응답 dict 를 돌려준다."""
    from kispilot.api.sector import news_title

    code = (code or "").strip().upper()
    count = max(1, min(int(count), 100))
    names = _names()
    keys = _name_keys(code, names.get(code, "")) if code else set()

    out: list[dict] = []
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    kwargs = {"iscd": code}
    for page in range(MAX_PAGES + 1):
        raw = kis_call(news_title, **kwargs) or {}
        if raw.get("rt_cd") not in (None, "0"):
            if page == 0:
                raise NewsError(raw.get("msg1") or "뉴스를 가져오지 못했습니다.")
            break
        items = [x for x in raw.get("output") or [] if isinstance(x, dict) and x.get("hts_pbnt_titl_cntt")]
        fresh = [x for x in items if x.get("cntt_usiq_srno") not in seen_ids]
        if not fresh:
            break
        for x in fresh:
            seen_ids.add(x.get("cntt_usiq_srno"))
            row = _row(x, names)
            title_key = _norm(row["title"])
            if title_key in seen_titles:  # 같은 기사를 여러 번 송고한 것
                continue
            if code:
                keep = any(k in title_key for k in keys) or (row["code"] == code and not _WRAP_RE.search(row["title"]))
            else:
                keep = _is_market_news(row)
            if keep:
                seen_titles.add(title_key)
                out.append(row)
        if len(out) >= count:
            break
        last = items[-1]
        kwargs = {"iscd": code, "date": "00" + (last.get("data_dt") or ""), "hour": "0000" + (last.get("data_tm") or "")}
    return out[:count]
