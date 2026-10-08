"""KISPilot 웹 앱 — src/kispilot/app/ui 정적 화면을 서빙하고 src/kispilot/api 함수를 HTTP API 로 노출한다.

src/kispilot/mcp_server/server.py 와 같은 방식으로 src/kispilot/api 각 패키지의 공개 함수를 자동 등록하므로,
src/kispilot/api 에 함수를 추가하고 패키지 __init__ 에서 export 하면 엔드포인트가 자동으로 생긴다.

엔드포인트:
    GET  /                          정적 UI (src/kispilot/app/ui/index.html)
    GET  /api/health                서버 상태
    GET  /api/session               사용 가능한 모드, 계좌(마스킹), 토큰 만료 시각, 초당 호출 수
    GET  /api/functions             등록된 API 함수 목록과 인자
    GET  /api/{pkg}/{name}?...      조회 함수 호출 (쿼리스트링 → 함수 인자)
    POST /api/order/{name}          주문 함수 호출 (JSON 본문 → 함수 인자)
    GET  /api/search/stock?q=       종목명/코드 검색 (KIS 마스터 파일)
    GET  /api/search/sector?q=      업종/지수 코드 검색
    GET  /api/history?code=         yfinance 과거 시세
    GET  /api/chart?code=&tf=&kind= 차트 봉 (tf: 1m 5m 30m D W M Y, kind: stock/index) — utils/chart.py
    GET  /api/news?code=&count=     주식 관련 뉴스만 (code 있으면 그 종목 뉴스) + 제목 검색 링크 — utils/news.py
    GET  /api/fo/futures?session=   KOSPI200 선물 전광판 (session: day/night) — utils/fo_board.py
    GET  /api/fo/expiries?session=&product=        옵션 만기 목록 (product: regular mini weekly_thu weekly_mon)
    GET  /api/fo/board?session=&product=&expiry=&n= 옵션 전광판 (ATM ±n 행사가 콜·풋)
    GET  /api/stream?ccnl=&book=&member=&program=   실시간 시세 SSE (KIS 웹소켓 중계) — utils/realtime_hub.py
                                    선물·옵션: fut_ccnl fut_book opt_ccnl opt_book (주간), nfut_* nopt_* (야간)
    GET  /api/stream/status         실시간 구독 현황
    GET  /api/backtest/options      백테스트 화면 구성 (기본 전략, 지표 카탈로그, 저장된 전략) — utils/backtest.py
    POST /api/backtest/run          백테스트 실행 (JSON: code, start, end, capital, benchmark, strategy, risk, fee)
    POST /api/backtest/compare      같은 종목에 전략·파라미터 여러 개 비교 (JSON: run 과 같고 strategy 대신 variants, sort_by)
    POST /api/backtest/portfolio    여러 종목 비중 + 리밸런싱 (JSON: holdings[{code, weight}], rebalance, start, end, capital, benchmark, fee)
    GET  /api/backtest/strategies   저장된 커스텀 전략 목록 / POST 저장 (헤더 필요)
    GET  /api/backtest/strategies/{file}   불러오기 / DELETE 삭제 (헤더 필요)

응답 형식:
    성공  {"ok": true,  "data": ...}
    실패  {"ok": false, "error": "...", "code": "..."}   (KIS rt_cd != "0" 도 실패로 본다)

실행:
    kispilot ui                       # http://127.0.0.1:8000  (pip install -e . 또는 uvx 로 설치한 경우)
    kispilot ui --port 8080 --reload
    python -m kispilot.app.main       # 설치 없이 src/ 를 PYTHONPATH 에 두고 실행

주문 안전장치:
    - 주문은 POST + JSON + 헤더 "X-Requested-With: kispilot" 일 때만 받는다
      (다른 사이트가 브라우저로 로컬 서버에 주문을 보내는 것을 막기 위함).
    - 주문은 화면에서 고른 모드(real/paper)로 나간다. 본문에 mode 가 없으면 "paper".
    - 기본 바인드 주소는 127.0.0.1 (같은 PC 에서만 접속).
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import dataclasses
import importlib
import inspect
import json
import logging
import os
import re
import secrets
import signal
import socket
import sys
import threading
import time
import typing
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Literal

# 설치 없이 `python src/kispilot/app/main.py` 로 실행해도 `kispilot` import 가 되도록 src/ 를 경로에 추가.
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd  # noqa: E402
import requests  # noqa: E402
from starlette.applications import Starlette  # noqa: E402
from starlette.concurrency import run_in_threadpool  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

from kispilot.api import config  # noqa: E402
from kispilot.api.oauth import kis_token  # noqa: E402
from kispilot.api.utils.api_tracker import tracker  # noqa: E402

UI_DIR = Path(__file__).resolve().parent / "ui"
_log = logging.getLogger("uvicorn.error")  # uvicorn 콘솔에 같이 찍힌다

_PACKAGES = ["account", "info", "order", "price", "price_anal", "ranking_anal", "sector", "futureoption"]

# 계좌에 변화를 일으키는 주문 함수 (나머지는 모두 조회).
_ORDER_FUNCS = {
    "buy_cash", "sell_cash", "buy_credit", "sell_credit",
    "revise_order", "cancel_order",
    "reserve_buy_order", "reserve_sell_order", "revise_reservation", "cancel_reservation",
}

_TRUTHY = ("1", "true", "yes", "on")
_ORDER_HEADER = ("x-requested-with", "kispilot")


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "BAD_REQUEST"):
        super().__init__(message)
        self.status = status
        self.code = code


# ── 공통 유틸 ───────────────────────────────────────────────

def _to_plain(result: Any) -> Any:
    """dataclass / DataFrame 을 JSON 직렬화 가능한 형태로."""
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        return dataclasses.asdict(result)
    if isinstance(result, pd.DataFrame):
        return json.loads(result.to_json(orient="records", force_ascii=False, date_format="iso"))
    return result


def _ok(data: Any) -> JSONResponse:
    return JSONResponse({"ok": True, "data": data})


def _fail(message: str, status: int = 400, code: str = "BAD_REQUEST", data: Any = None) -> JSONResponse:
    body = {"ok": False, "error": message, "code": code}
    if data is not None:
        body["data"] = data
    return JSONResponse(body, status_code=status)


# KIS 초당 호출 한도(실전 20/s, 모의 1/s)를 넘지 않도록 요청 시작 간격을 벌린다.
# (함수 내부의 연속조회 페이지 호출까지는 제어하지 않는다.)
_MIN_INTERVAL = {"real": 0.06, "paper": 1.05}  # 모의투자 한도 1건/초 (여유 50ms)
_next_slot = {"real": 0.0, "paper": 0.0}
_throttle_lock = threading.Lock()


def _throttle(mode: str) -> None:
    mode = "paper" if mode == "paper" else "real"
    with _throttle_lock:
        now = time.monotonic()
        start = max(now, _next_slot[mode])
        _next_slot[mode] = start + _MIN_INTERVAL[mode]
    if start > now:
        time.sleep(start - now)


# 접근토큰 자동 갱신. src/kispilot/api 함수는 캐시 파일(load_token)만 읽으므로 호출 전에
# 만료 임박(6시간 미만) 토큰을 재발급해 둔다. 서버가 토큰을 거절하면(EGW00123/EGW00121)
# 캐시를 지우고 강제 재발급 후 1회 재시도. 발급은 KIS 제한(1분 1회)이 있어 모드별 락을 건다.
_TOKEN_INVALID_CODES = {"EGW00123", "EGW00121"}
_token_locks = {"real": threading.Lock(), "paper": threading.Lock()}


def _ensure_token(mode: str, force: bool = False) -> None:
    mode = "paper" if mode == "paper" else "real"
    with _token_locks[mode]:
        if force:
            try:
                os.remove(kis_token._token_file(mode))
            except FileNotFoundError:
                pass
        kis_token._issue_access_token(mode)


_RATE_LIMIT_CODE = "EGW00201"  # 초당 거래건수 초과
_RATE_LIMIT_RETRIES = 3


def _call_kis(fn: Callable, mode: str, kwargs: dict) -> Any:
    """토큰 확인 → 속도 제한 → 호출.

    토큰 거절 시 재발급 후 1회, 초당 한도 초과 시 잠시 쉬었다가 최대 3회 재시도한다.
    두 경우 모두 KIS 가 요청을 처리하지 않고 거절한 것이므로 주문도 재시도해도 안전하다.
    """
    kis_token.require_mode("paper" if mode == "paper" else "real")
    _ensure_token(mode)
    token_refreshed = False
    for attempt in range(_RATE_LIMIT_RETRIES + 1):
        _throttle(mode)
        result = fn(**kwargs)
        code = getattr(result, "msg_cd", None)
        if code in _TOKEN_INVALID_CODES and not token_refreshed:
            _ensure_token(mode, force=True)
            token_refreshed = True
            continue
        if code == _RATE_LIMIT_CODE and attempt < _RATE_LIMIT_RETRIES:
            time.sleep(0.6 * (attempt + 1))
            continue
        return result
    return result


# ── 인자 변환 (쿼리스트링/JSON → 함수 인자) ─────────────────

def _unwrap_optional(ann: Any) -> Any:
    if typing.get_origin(ann) is typing.Union or type(ann).__name__ == "UnionType":
        args = [a for a in typing.get_args(ann) if a is not type(None)]
        return args[0] if len(args) == 1 else str
    return ann


def _coerce(name: str, value: Any, ann: Any) -> Any:
    ann = _unwrap_optional(ann)
    if typing.get_origin(ann) is list:
        # 쿼리스트링은 "005930,000660" 처럼 쉼표로, JSON 은 배열로 받는다.
        items = value.split(",") if isinstance(value, str) else list(value)
        return [str(v).strip() for v in items if str(v).strip()]
    if typing.get_origin(ann) is Literal:
        allowed = typing.get_args(ann)
        if value not in allowed:
            raise ApiError(f"'{name}' 값은 {list(allowed)} 중 하나여야 합니다: {value!r}")
        return value
    if isinstance(value, str):
        try:
            if ann is bool:
                return value.strip().lower() in _TRUTHY
            if ann is int:
                return int(value)
            if ann is float:
                return float(value)
        except ValueError:
            raise ApiError(f"'{name}' 는 {ann.__name__} 형식이어야 합니다: {value!r}") from None
        return value
    # JSON 본문에서 숫자로 온 값을 문자열 인자(주문 수량/가격 등)로 받는 함수에 맞춘다.
    if ann in (str, inspect.Parameter.empty) and isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return value


@dataclasses.dataclass
class Endpoint:
    pkg: str
    name: str
    fn: Callable
    params: dict[str, inspect.Parameter]
    hints: dict[str, Any]
    is_order: bool
    has_mode: bool
    doc: str

    def build_kwargs(self, raw: dict[str, Any]) -> tuple[dict[str, Any], str]:
        unknown = set(raw) - set(self.params)
        if unknown:
            raise ApiError(f"알 수 없는 인자: {sorted(unknown)}")

        kwargs: dict[str, Any] = {}
        for pname, p in self.params.items():
            if pname in raw:
                kwargs[pname] = _coerce(pname, raw[pname], self.hints.get(pname, p.annotation))
            elif p.default is inspect.Parameter.empty:
                raise ApiError(f"필수 인자 누락: '{pname}'")

        if self.has_mode:
            # 주문은 명시하지 않으면 모의투자, 조회는 함수 기본값(보통 real)을 따른다.
            fn_default = self.params["mode"].default
            if fn_default is inspect.Parameter.empty:
                fn_default = "real"
            if not self.is_order and "mode" not in kwargs and fn_default == "real":
                # 모의투자 키만 등록한 사용자는 조회도 모의투자 서버로
                available = kis_token._available_modes()
                if "real" not in available and "paper" in available:
                    fn_default = "paper"
            kwargs.setdefault("mode", "paper" if self.is_order else fn_default)
            mode = kwargs["mode"]
        else:
            mode = "real"  # mode 인자가 없는 함수는 실전 키 전용
        return kwargs, mode

    def describe(self) -> dict:
        args = []
        for pname, p in self.params.items():
            ann = self.hints.get(pname, p.annotation)
            args.append({
                "name": pname,
                "type": "str" if ann is inspect.Parameter.empty else str(ann).replace("typing.", ""),
                "required": p.default is inspect.Parameter.empty,
                "default": None if p.default is inspect.Parameter.empty else p.default,
            })
        return {
            "path": f"/api/{self.pkg}/{self.name}",
            "method": "POST" if self.is_order else "GET",
            "order": self.is_order,
            "title": self.doc.splitlines()[0] if self.doc else self.name,
            "args": args,
        }


_REGISTRY: dict[tuple[str, str], Endpoint] = {}


def _register_endpoints() -> int:
    for pkg in _PACKAGES:
        module = importlib.import_module(f"kispilot.api.{pkg}")
        for name, fn in vars(module).items():
            if name.startswith("_") or not inspect.isfunction(fn):
                continue
            if not fn.__module__.startswith(f"kispilot.api.{pkg}."):
                continue  # 패키지 __init__ 에 섞여 들어온 외부 함수 제외
            try:
                hints = typing.get_type_hints(fn)
            except Exception:
                hints = {}
            params = dict(inspect.signature(fn).parameters)
            _REGISTRY[(pkg, name)] = Endpoint(
                pkg=pkg, name=name, fn=fn, params=params, hints=hints,
                is_order=pkg == "order" and name in _ORDER_FUNCS,
                has_mode="mode" in params,
                doc=inspect.getdoc(fn) or "",
            )
    return len(_REGISTRY)


# ── KIS 마스터 파일 검색 (api/data/master.py: 하루 한 번 갱신) ─────────

def _search_stock(query: str, market: str, limit: int) -> list[dict]:
    from kispilot.api.data import master
    return master.search_stocks(query, market, limit)


def _search_sector(query: str, limit: int) -> list[dict]:
    from kispilot.api.data import master
    return master.search_sectors(query, limit)


# ── 세션 정보 ────────────────────────────────────────────────

def _mask_account(cano: str | None, prdt: str | None) -> str | None:
    if not cano:
        return None
    return f"{cano[:4]}{'*' * max(0, len(cano) - 4)}-{prdt or '??'}"


def _token_status(mode: str) -> dict:
    """캐시된 토큰의 만료 시각만 읽는다 (발급 요청은 하지 않음)."""
    path = kis_token._token_file(mode)
    try:
        with open(path, encoding="utf-8") as f:
            expired_at = datetime.strptime(json.load(f)["access_token_token_expired"], "%Y-%m-%d %H:%M:%S")
    except (OSError, KeyError, ValueError, json.JSONDecodeError):
        return {"issued": False, "expires_at": None, "seconds_left": None}
    left = int((expired_at - datetime.now()).total_seconds())
    return {"issued": left > 0, "expires_at": expired_at.isoformat(), "seconds_left": max(0, left)}


def _session_info() -> dict:
    modes = kis_token._available_modes()
    accounts = {
        "real": _mask_account(config.CANO, config.ACNT_PRDT_CD),
        "paper": _mask_account(config.PAPER_CANO, config.PAPER_ACNT_PRDT_CD),
    }
    return {
        "modes": modes,
        "default_mode": "real" if "real" in modes else (modes[0] if modes else None),
        "accounts": {m: accounts[m] for m in modes},
        "tokens": {m: _token_status(m) for m in modes},
        "call_rate": tracker.rates(),
        "server_time": datetime.now().isoformat(timespec="seconds"),
    }


# ── 라우트 핸들러 ────────────────────────────────────────────

async def health(request: Request) -> JSONResponse:
    return _ok({"status": "up", "functions": len(_REGISTRY)})


async def session(request: Request) -> JSONResponse:
    return _ok(await run_in_threadpool(_session_info))


async def functions(request: Request) -> JSONResponse:
    return _ok([ep.describe() for ep in _REGISTRY.values()])


async def search_stock(request: Request) -> JSONResponse:
    q = request.query_params.get("q", "").strip()
    market = request.query_params.get("market", "all")
    if not q:
        raise ApiError("검색어 q 가 필요합니다.")
    if market not in ("all", "kospi", "kosdaq"):
        raise ApiError("market 은 all/kospi/kosdaq 중 하나입니다.")
    limit = _coerce("limit", request.query_params.get("limit", "20"), int)
    return _ok(await run_in_threadpool(_search_stock, q, market, limit))


async def search_sector(request: Request) -> JSONResponse:
    q = request.query_params.get("q", "")
    limit = _coerce("limit", request.query_params.get("limit", "30"), int)
    return _ok(await run_in_threadpool(_search_sector, q, limit))


_HISTORY_INTERVALS = ("1d", "1wk", "1mo", "1h", "30m", "15m", "5m", "1m")


def _history(code: str, start, end, period, interval: str, auto_adjust: bool) -> dict:
    from kispilot.app.utils.utils import get_history

    try:
        df = get_history(code, start=start, end=end, period=period, interval=interval, auto_adjust=auto_adjust)
    except ValueError as e:
        raise ApiError(str(e), status=404, code="NO_DATA") from e
    fmt = "%Y-%m-%d" if interval in ("1d", "1wk", "1mo") else "%Y-%m-%d %H:%M"
    out = df.round(2).reset_index()
    out["Date"] = out["Date"].dt.strftime(fmt)
    out = out.astype(object).where(out.notna(), None)  # NaN(당일 미확정 봉 등) → null
    return {"symbol": df.attrs.get("symbol"), "rows": out.to_dict(orient="records")}


async def history(request: Request) -> JSONResponse:
    qp = request.query_params
    code = qp.get("code", "").strip()
    if not code:
        raise ApiError("종목코드 code 가 필요합니다.")
    interval = qp.get("interval", "1d")
    if interval not in _HISTORY_INTERVALS:
        raise ApiError(f"interval 은 {list(_HISTORY_INTERVALS)} 중 하나입니다.")
    data = await run_in_threadpool(
        _history, code, qp.get("start"), qp.get("end"), qp.get("period"), interval,
        qp.get("auto_adjust", "true").lower() in _TRUTHY,
    )
    return _ok(data)


def _kis_network_error(e: requests.exceptions.RequestException, is_order: bool) -> ApiError:
    """KIS 서버 연결/응답 실패를 사용자에게 보여줄 오류로 바꾼다.

    주문에서 중요한 구분: 연결 자체를 못 했으면(ConnectTimeout) 주문은 전송되지 않았지만,
    보낸 뒤 응답만 못 받았으면(ReadTimeout 등) 접수됐을 수 있어 재전송하면 중복 주문이 될 수 있다.
    """
    server = "모의투자" if "openapivts" in str(e) else "실전"
    if isinstance(e, requests.exceptions.ConnectTimeout):
        msg = f"KIS {server} 서버에 연결하지 못했습니다 (10초 초과)."
        return ApiError(msg + (" 주문은 전송되지 않았습니다." if is_order else " 잠시 후 다시 시도하세요."),
                        status=504, code="KIS_CONNECT_TIMEOUT")
    if is_order:
        return ApiError(f"KIS {server} 서버 응답이 없어 주문 결과를 확인하지 못했습니다. "
                        "접수됐을 수 있으니 미체결·체결 내역을 확인한 뒤 다시 시도하세요.",
                        status=504, code="KIS_ORDER_UNKNOWN")
    if isinstance(e, requests.exceptions.Timeout):
        return ApiError(f"KIS {server} 서버 응답이 늦습니다 (10초 초과). 잠시 후 다시 시도하세요.",
                        status=504, code="KIS_TIMEOUT")
    return ApiError(f"KIS {server} 서버 연결 오류 ({type(e).__name__}). 잠시 후 다시 시도하세요.",
                    status=502, code="KIS_NETWORK")


def _kis_call(fn: Callable, **kwargs) -> dict:
    """차트 모듈용 KIS 호출 (실전 키, 토큰·속도 제한 처리)."""
    data = _to_plain(_call_kis(fn, "real", kwargs))
    return data if isinstance(data, dict) else {}


async def chart(request: Request) -> JSONResponse:
    from kispilot.app.utils import chart as chart_data

    qp = request.query_params
    code = qp.get("code", "").strip().upper()
    kind = qp.get("kind", "stock")
    if not code:
        raise ApiError("종목코드 code 가 필요합니다.")
    if kind not in ("stock", "index"):
        raise ApiError("kind 는 stock/index 중 하나입니다.")
    try:
        data = await run_in_threadpool(chart_data.build, code, qp.get("tf", "D"), kind, _kis_call)
    except chart_data.ChartError as e:
        raise ApiError(str(e), status=404, code="NO_DATA") from e
    except requests.exceptions.RequestException as e:
        _log.warning("[kis] chart %s %s 네트워크 오류: %s", code, qp.get("tf"), type(e).__name__)
        raise _kis_network_error(e, False) from None
    return _ok(data)


# ── KOSPI200 선물·옵션 전광판 (app/utils/fo_board.py) ────────

async def fo_futures(request: Request) -> JSONResponse:
    from kispilot.app.utils import fo_board

    try:
        data = await run_in_threadpool(fo_board.futures, request.query_params.get("session", "day"), _kis_call)
    except ValueError as e:
        raise ApiError(str(e)) from e
    except fo_board.BoardError as e:
        raise ApiError(str(e), status=404, code="NO_DATA") from e
    except requests.exceptions.RequestException as e:
        _log.warning("[kis] fo futures 네트워크 오류: %s", type(e).__name__)
        raise _kis_network_error(e, False) from None
    return _ok(data)


async def fo_expiries(request: Request) -> JSONResponse:
    from kispilot.app.utils import fo_board

    qp = request.query_params
    try:
        data = await run_in_threadpool(fo_board.expiries, qp.get("session", "day"), qp.get("product", "regular"))
    except ValueError as e:
        raise ApiError(str(e)) from e
    return _ok(data)


async def fo_board_view(request: Request) -> JSONResponse:
    from kispilot.app.utils import fo_board

    qp = request.query_params
    expiry = qp.get("expiry", "").strip().upper()
    if not expiry:
        raise ApiError("만기 expiry 가 필요합니다. 예: 202612, 2610W3 (/api/fo/expiries 참고)")
    try:
        n = int(qp.get("n", fo_board.DEFAULT_N))
    except ValueError:
        raise ApiError("n 은 정수입니다.") from None
    try:
        data = await run_in_threadpool(fo_board.build, qp.get("session", "day"), qp.get("product", "regular"),
                                       expiry, n, _kis_call)
    except ValueError as e:
        raise ApiError(str(e)) from e
    except fo_board.BoardError as e:
        raise ApiError(str(e), status=404, code="NO_DATA") from e
    except requests.exceptions.RequestException as e:
        _log.warning("[kis] fo board %s 네트워크 오류: %s", expiry, type(e).__name__)
        raise _kis_network_error(e, False) from None
    return _ok(data)


async def news(request: Request) -> JSONResponse:
    from kispilot.app.utils import news as news_data

    qp = request.query_params
    try:
        count = int(qp.get("count", "20"))
    except ValueError:
        raise ApiError("count 는 숫자입니다.") from None
    try:
        rows = await run_in_threadpool(news_data.fetch, _kis_call, qp.get("code", ""), count)
    except news_data.NewsError as e:
        raise ApiError(str(e), status=502, code="KIS_ERROR") from e
    except requests.exceptions.RequestException as e:
        _log.warning("[kis] news 네트워크 오류: %s", type(e).__name__)
        raise _kis_network_error(e, False) from None
    return _ok(rows)


# ── 백테스트 ─────────────────────────────────────────────────

async def _json_body(request: Request, need_header: bool = False) -> dict:
    if need_header and request.headers.get(_ORDER_HEADER[0]) != _ORDER_HEADER[1]:
        raise ApiError("요청 헤더가 없습니다.", status=403, code="FORBIDDEN")
    try:
        raw = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ApiError("본문은 JSON 이어야 합니다.") from None
    if not isinstance(raw, dict):
        raise ApiError("본문은 JSON 객체여야 합니다.")
    return raw


async def _backtest(fn: Callable, *args) -> JSONResponse:
    from kispilot.app.utils import backtest as bt

    try:
        return _ok(await run_in_threadpool(fn, *args))
    except bt.BacktestError as e:
        return _fail(str(e), status=e.status, code="BACKTEST", data={"errors": e.errors} if e.errors else None)
    except requests.exceptions.RequestException as e:
        _log.warning("[kis] backtest 네트워크 오류: %s", type(e).__name__)
        raise _kis_network_error(e, False) from None


async def backtest_options(request: Request) -> JSONResponse:
    from kispilot.app.utils import backtest as bt

    return await _backtest(bt.options)


async def backtest_run(request: Request) -> JSONResponse:
    from kispilot.app.utils import backtest as bt

    return await _backtest(bt.run, await _json_body(request), _kis_call)


async def backtest_compare(request: Request) -> JSONResponse:
    from kispilot.app.utils import backtest as bt

    return await _backtest(bt.compare, await _json_body(request), _kis_call)


async def backtest_portfolio(request: Request) -> JSONResponse:
    from kispilot.app.utils import backtest as bt

    return await _backtest(bt.portfolio, await _json_body(request), _kis_call)


async def backtest_strategies(request: Request) -> JSONResponse:
    """GET 목록 / POST 저장 {strategy, risk, fee}"""
    from kispilot.app.utils import backtest as bt

    if request.method == "GET":
        return await _backtest(bt.list_saved)
    body = await _json_body(request, need_header=True)
    return await _backtest(bt.save, body.get("strategy") or {}, body.get("risk"), body.get("fee"))


async def backtest_strategy(request: Request) -> JSONResponse:
    """GET 불러오기 / DELETE 삭제"""
    from kispilot.app.utils import backtest as bt

    file = request.path_params["file"]
    if request.method == "GET":
        return await _backtest(bt.load_saved, file)
    if request.headers.get(_ORDER_HEADER[0]) != _ORDER_HEADER[1]:
        raise ApiError("요청 헤더가 없습니다.", status=403, code="FORBIDDEN")
    return await _backtest(bt.delete, file)


async def call_function(request: Request) -> JSONResponse:
    pkg = request.path_params["pkg"]
    name = request.path_params["name"]
    ep = _REGISTRY.get((pkg, name))
    if ep is None:
        raise ApiError(f"없는 API 입니다: /api/{pkg}/{name}", status=404, code="NOT_FOUND")

    if ep.is_order:
        if request.method != "POST":
            raise ApiError("주문은 POST 로만 요청할 수 있습니다.", status=405, code="METHOD_NOT_ALLOWED")
        if request.headers.get(_ORDER_HEADER[0]) != _ORDER_HEADER[1]:
            raise ApiError("주문 요청 헤더가 없습니다.", status=403, code="FORBIDDEN")
        try:
            raw = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError("주문 본문은 JSON 이어야 합니다.") from None
        if not isinstance(raw, dict):
            raise ApiError("주문 본문은 JSON 객체여야 합니다.")
    else:
        if request.method != "GET":
            raise ApiError("조회는 GET 으로 요청하세요.", status=405, code="METHOD_NOT_ALLOWED")
        raw = dict(request.query_params)

    kwargs, mode = ep.build_kwargs(raw)
    try:
        result = await run_in_threadpool(_call_kis, ep.fn, mode, kwargs)
    except requests.exceptions.RequestException as e:
        _log.warning("[kis] %s %s/%s 네트워크 오류: %s", mode, pkg, name, type(e).__name__)
        raise _kis_network_error(e, ep.is_order) from None
    except Exception as e:
        if not ep.is_order:
            raise
        # 주문은 KIS 가 처리한 뒤 응답 해석에서 실패했을 수도 있으므로 '결과 불확실'로 알린다 (재전송 방지)
        _log.exception("[kis] %s %s/%s 주문 처리 중 오류", mode, pkg, name)
        raise ApiError(f"주문 처리 중 오류가 났습니다 ({type(e).__name__}). 접수됐을 수 있으니 "
                       "미체결·체결 내역을 확인한 뒤 다시 시도하세요.", status=500, code="KIS_ORDER_UNKNOWN") from None
    data = _to_plain(result)

    rt_cd = data.get("rt_cd") if isinstance(data, dict) else None
    if rt_cd not in (None, "0"):
        return _fail(data.get("msg1") or "KIS 요청 실패", status=502, code=data.get("msg_cd") or "KIS_ERROR", data=data)
    return _ok(data)


# ── 실시간 스트림 (SSE) ──────────────────────────────────────

_STREAM_CODE = re.compile(r"^[0-9A-Z]{6,9}$")  # 주식 6자리 · 선물 6자리 · 옵션 9자리


async def stream(request: Request) -> StreamingResponse:
    """실시간 시세를 SSE 로 보낸다. ?ccnl=005930,000660&book=005930&member=..&program=..

    브라우저가 연결을 닫으면(페이지 이동·탭 닫기) 제너레이터가 정리되며 구독 참조가 줄어든다.
    """
    from kispilot.app.utils.realtime_hub import CLOSE, KINDS, hub

    topics = set()
    for kind in KINDS:
        for code in request.query_params.get(kind, "").upper().split(","):
            if _STREAM_CODE.match(code.strip()):
                topics.add((kind, code.strip()))
    if not topics:
        raise ApiError(f"구독할 종목이 없습니다. 예: /api/stream?ccnl=005930 (종류: {', '.join(KINDS)})")
    if "real" not in kis_token._available_modes():
        raise ApiError("실시간 시세는 실전 앱키가 필요합니다. 터미널에서 kispilot setup 으로 등록하세요.", code="NO_REAL_KEY")

    client = hub.add(topics)

    async def events():
        try:
            yield "retry: 3000\n\n"
            while True:
                try:
                    event, data = await asyncio.wait_for(client.queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"  # 프록시·브라우저가 유휴 연결을 끊지 않도록
                    continue
                if event == CLOSE:  # 서버 종료 중 → 스트림을 정상적으로 끝낸다
                    return
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        finally:
            hub.remove(client)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


async def stream_status(request: Request) -> JSONResponse:
    from kispilot.app.utils.realtime_hub import hub

    return _ok(hub.snapshot())


def _hook_shutdown_signals(loop: asyncio.AbstractEventLoop, on_exit) -> None:
    """종료 신호(Ctrl+C, 재시작)를 받는 즉시 on_exit 를 예약한 뒤 uvicorn 의 원래 처리기로 넘긴다.

    uvicorn 은 열린 연결이 닫히기를(최대 timeout_graceful_shutdown) 기다린 뒤에야 lifespan 종료를
    부르므로, 실시간 허브를 그보다 먼저 정리해 KIS 웹소켓을 정상 종료하고 SSE 스트림도 바로 끝낸다.
    """
    sigs = [signal.SIGINT, signal.SIGTERM] + ([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])
    for sig in sigs:
        prev = signal.getsignal(sig)
        if not callable(prev) or getattr(prev, "_pykis_hooked", False):
            continue

        def handler(signum, frame, prev=prev):
            loop.call_soon_threadsafe(lambda: asyncio.ensure_future(on_exit()))
            prev(signum, frame)

        handler._pykis_hooked = True
        try:
            signal.signal(sig, handler)
        except ValueError:  # 메인 스레드가 아니면 설치 불가 → lifespan 종료에서 정리
            return


@contextlib.asynccontextmanager
async def _lifespan(app):
    from kispilot.app.utils.realtime_hub import hub

    _hook_shutdown_signals(asyncio.get_running_loop(), hub.close)
    yield
    await hub.close()  # 신호 없이 끝나는 경우의 대비 (이미 정리됐으면 아무 일도 안 함)


# ── 예외 처리 ────────────────────────────────────────────────

async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
    return _fail(str(exc), status=exc.status, code=exc.code)


async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, kis_token.CredentialsMissing):
        return _fail(str(exc), status=400, code="NO_CREDENTIALS")
    # KisApiError(토큰 발급 실패 등), 설정 누락(ValueError) 등을 JSON 으로 돌려준다.
    code = getattr(exc, "error_code", None) or type(exc).__name__
    return _fail(f"{type(exc).__name__}: {exc}", status=500, code=code)


# ── 앱 구성 ──────────────────────────────────────────────────

class _UIFiles(StaticFiles):
    """정적 UI. 코드를 고친 뒤 옛 JS/CSS 가 남지 않도록 매번 재검증(ETag → 304)하게 한다."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


# ── 외부 접속 키 (0.0.0.0 등으로 열 때만) ─────────────────────

_ACCESS_ENV = "KIS_UI_ACCESS_KEY"
_ACCESS_COOKIE = "kis_ui_key"
_LOOPBACK = ("127.0.0.1", "::1", "localhost")


class _AccessKeyGate:
    """외부로 열었을 때 접속 키가 있는 브라우저만 들여보낸다.

    이 화면에는 로그인이 없고 실전 주문까지 되므로, 같은 PC(127.0.0.1)가 아닌 곳에서 오는 요청은
    서버 시작 때 정한 키(?key=…)를 한 번 확인한 뒤 쿠키로 기억한다. 키는 환경변수 KIS_UI_ACCESS_KEY.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        key = os.environ.get(_ACCESS_ENV)
        if not key or scope["type"] != "http" or (scope.get("client") or ("",))[0] in _LOOPBACK:
            return await self.app(scope, receive, send)
        req = Request(scope)
        cookie = req.cookies.get(_ACCESS_COOKIE, "")
        if cookie and secrets.compare_digest(cookie, key):
            return await self.app(scope, receive, send)
        given = req.query_params.get("key", "")
        if given and secrets.compare_digest(given, key):
            # 키를 쿠키로 옮기고 주소창에서는 지운다
            rest = [(k, v) for k, v in req.query_params.multi_items() if k != "key"]
            target = req.url.path + ("?" + "&".join(f"{k}={v}" for k, v in rest) if rest else "")
            resp = RedirectResponse(target, status_code=303)
            resp.set_cookie(_ACCESS_COOKIE, key, max_age=7 * 86400, httponly=True, samesite="strict")
            return await resp(scope, receive, send)
        if req.url.path.startswith("/api/"):
            resp = JSONResponse({"ok": False, "error": "접속 키가 필요합니다. 서버를 켠 터미널에 나온 주소로 접속하세요.",
                                 "code": "ACCESS_KEY"}, status_code=401)
        else:
            resp = HTMLResponse("<!doctype html><meta charset=utf-8><title>접속 키 필요</title>"
                                "<body style='font-family:sans-serif;padding:40px'><h2>접속 키가 필요합니다</h2>"
                                "<p>서버를 켠 터미널에 나온 주소(<code>?key=…</code> 포함)로 접속하세요.</p></body>",
                                status_code=401)
        return await resp(scope, receive, send)


def _lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))  # 실제로 보내지 않음 (어느 랜카드로 나가는지만 확인)
            return s.getsockname()[0]
    except OSError:
        return None


def create_app() -> Starlette:
    if not _REGISTRY:
        _register_endpoints()

    routes = [
        Route("/api/health", health),
        Route("/api/session", session),
        Route("/api/functions", functions),
        Route("/api/search/stock", search_stock),
        Route("/api/search/sector", search_sector),
        Route("/api/history", history),
        Route("/api/chart", chart),
        Route("/api/fo/futures", fo_futures),
        Route("/api/fo/expiries", fo_expiries),
        Route("/api/fo/board", fo_board_view),
        Route("/api/news", news),
        Route("/api/stream", stream),
        Route("/api/stream/status", stream_status),  # /api/{pkg}/{name} 보다 먼저
        Route("/api/backtest/options", backtest_options),
        Route("/api/backtest/run", backtest_run, methods=["POST"]),
        Route("/api/backtest/compare", backtest_compare, methods=["POST"]),
        Route("/api/backtest/portfolio", backtest_portfolio, methods=["POST"]),
        Route("/api/backtest/strategies", backtest_strategies, methods=["GET", "POST"]),
        Route("/api/backtest/strategies/{file}", backtest_strategy, methods=["GET", "DELETE"]),
        Route("/api/{pkg}/{name}", call_function, methods=["GET", "POST"]),
        Mount("/", app=_UIFiles(directory=UI_DIR, html=True), name="ui"),
    ]
    from starlette.middleware import Middleware

    return Starlette(
        routes=routes,
        exception_handlers={ApiError: _api_error, Exception: _unexpected_error},
        lifespan=_lifespan,
        middleware=[Middleware(_AccessKeyGate)],
    )


app = create_app()


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="KISPilot 웹 앱 서버")
    parser.add_argument("--host", default="127.0.0.1", help="바인드 주소 (기본 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="코드 변경 시 자동 재시작 (개발용)")
    args = parser.parse_args()
    try:  # 출력이 파일·파이프로 갈 때도 안내 문구가 바로 보이게
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    if args.host in _LOOPBACK:
        print(f"KISPilot UI  →  http://{args.host}:{args.port}")
    else:
        # 외부 접속: 로그인이 없으므로 접속 키를 켠다 (같은 PC 의 127.0.0.1 접속은 키 없이)
        key = os.environ.get(_ACCESS_ENV) or secrets.token_urlsafe(18)
        os.environ[_ACCESS_ENV] = key  # --reload 로 뜨는 하위 프로세스도 같은 키를 쓴다
        ip = _lan_ip() if args.host in ("0.0.0.0", "::") else args.host
        print("[주의] 외부 접속 모드 — 이 주소를 아는 사람은 계좌 조회와 주문까지 할 수 있습니다.")
        print(f"   다른 기기에서:  http://{ip or '<이 PC의 IP>'}:{args.port}/?key={key}")
        print(f"   이 PC 에서:     http://127.0.0.1:{args.port}  (키 없이)")
        print("   HTTP(암호화 없음)이므로 믿을 수 있는 네트워크에서만, 쓰고 나면 바로 끄세요. 인터넷에 열려면 HTTPS 터널을 쓰세요.")
    print(f"API 함수 {len(_REGISTRY)}개 등록")
    # 실시간 스트림(SSE)은 브라우저가 열어 두는 한 끝나지 않으므로, 종료·재시작 때
    # 열린 연결을 무한정 기다리지 않도록 유예 시간을 둔다 (브라우저는 알아서 재접속한다).
    opts = dict(host=args.host, port=args.port, timeout_graceful_shutdown=3)
    if args.reload:
        uvicorn.run("kispilot.app.main:app", reload=True, reload_dirs=[str(_ROOT / "kispilot")], **opts)
    else:
        uvicorn.run(app, **opts)


if __name__ == "__main__":
    main()
