"""공유 HTTP 세션 — 한국투자증권 REST 호출의 커넥션 재사용(keep-alive).

매 호출마다 새 TCP+TLS 핸드셰이크를 여는 대신 커넥션 풀을 재사용해 주문/조회의
왕복 지연을 줄인다(시장가 주문의 체결 지연·슬리피지 완화 목적).

urllib3 커넥션 풀은 스레드세이프하므로 asyncio.to_thread로 여러 스레드에서 동시에
호출해도 안전하다 — 헤더는 요청마다 전달하고 세션 상태(쿠키 등)는 변경하지 않는다.
풀 크기는 자동투자 엔진의 스레드풀(32)과 동시 호출량에 맞춰 키운다(풀 부족 시
keep-alive가 깨지고 throwaway 커넥션이 생긴다).
"""
import aiohttp
import requests
from requests.adapters import HTTPAdapter

from kispilot.api.utils.api_tracker import tracker as _kis_tracker

_session = requests.Session()
_adapter = HTTPAdapter(pool_connections=8, pool_maxsize=32)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)


def _record_kis_call(response, *args, **kwargs):
    # KIS 호스트만 카운트. 그 외 도메인(예: 헬스체크) 은 제외.
    try:
        url = response.url or ""
    except Exception:
        return
    if "openapivts.koreainvestment" in url:
        _kis_tracker.record("paper")
    elif "openapi.koreainvestment" in url:
        _kis_tracker.record("real")


_session.hooks["response"] = [_record_kis_call]


def get_session() -> requests.Session:
    """프로세스 전역에서 공유하는 requests.Session 반환."""
    return _session


# ── aiohttp 호출 추적 ──────────────────────────────────────────
# aiohttp 는 requests 의 response hook 을 거치지 않으므로 TraceConfig 로 동일하게 집계.

async def _record_kis_call_async(session, trace_config_ctx, params) -> None:
    url = str(params.url)
    if "openapivts.koreainvestment" in url:
        _kis_tracker.record("paper")
    elif "openapi.koreainvestment" in url:
        _kis_tracker.record("real")


def create_async_session(**kwargs) -> aiohttp.ClientSession:
    """KIS 호출 추적(TraceConfig)이 연결된 aiohttp.ClientSession 생성.

    aiohttp.ClientSession() 직접 생성 대신 이 팩토리를 쓰면 비동기 호출도
    대시보드 호출량 집계(api_tracker)에 포함된다. async with 로 사용.
    """
    trace = aiohttp.TraceConfig()
    trace.on_request_end.append(_record_kis_call_async)
    trace_configs = kwargs.pop("trace_configs", [])
    # 기본 타임아웃 30초 — aiohttp 기본값(total 300초)은 KIS 무응답 시
    # 대시보드 요청이 5분간 커넥션을 점유해 무한 로딩의 원인이 된다.
    kwargs.setdefault("timeout", aiohttp.ClientTimeout(total=30))
    return aiohttp.ClientSession(trace_configs=[trace, *trace_configs], **kwargs)
