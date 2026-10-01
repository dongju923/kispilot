# 국내주식 실시간회원사 (통합)[H0UNMBC0]
import asyncio
import contextlib
import inspect
import json
from dataclasses import dataclass, fields
from typing import Any, Callable, Literal, Optional

import websockets

from kispilot.api.config import WS_DOMAIN
from kispilot.api.oauth import kis_token
from kispilot.api.oauth.kis_token import KisApiError, load_websocket_token

URL = "/tryitout/H0UNMBC0"
# ※ 모의투자 미지원 (실전투자 전용). KRX + NXT 통합 매도/매수 상위 5개 회원사(거래원)와 외국계 합계.
# ※ 웹소켓 1세션당 구독 가능 건수는 실시간 체결가/호가/회원사 등을 합쳐 최대 41건.
# ※ 수신 데이터는 "0|TR_ID|데이터건수|값^값^..." 형식이며, 데이터건수가 2 이상이면 값이 필드 수 단위로 이어서 온다.
# ※ PINGPONG 메시지는 받은 그대로 되돌려 보내야 서버가 세션을 끊지 않는다.

_TR_ID = "H0UNMBC0"

_MAX_SUBSCRIPTIONS = 41


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBody:
    mksc_shrn_iscd: Optional[str] = None             # 유가증권 단축 종목코드
    seln2_mbcr_name1: Optional[str] = None           # 매도2 회원사명1
    seln2_mbcr_name2: Optional[str] = None           # 매도2 회원사명2
    seln2_mbcr_name3: Optional[str] = None           # 매도2 회원사명3
    seln2_mbcr_name4: Optional[str] = None           # 매도2 회원사명4
    seln2_mbcr_name5: Optional[str] = None           # 매도2 회원사명5
    byov_mbcr_name1: Optional[str] = None            # 매수 회원사명1
    byov_mbcr_name2: Optional[str] = None            # 매수 회원사명2
    byov_mbcr_name3: Optional[str] = None            # 매수 회원사명3
    byov_mbcr_name4: Optional[str] = None            # 매수 회원사명4
    byov_mbcr_name5: Optional[str] = None            # 매수 회원사명5
    total_seln_qty1: Optional[str] = None            # 총 매도 수량1
    total_seln_qty2: Optional[str] = None            # 총 매도 수량2
    total_seln_qty3: Optional[str] = None            # 총 매도 수량3
    total_seln_qty4: Optional[str] = None            # 총 매도 수량4
    total_seln_qty5: Optional[str] = None            # 총 매도 수량5
    total_shnu_qty1: Optional[str] = None            # 총 매수2 수량1
    total_shnu_qty2: Optional[str] = None            # 총 매수2 수량2
    total_shnu_qty3: Optional[str] = None            # 총 매수2 수량3
    total_shnu_qty4: Optional[str] = None            # 총 매수2 수량4
    total_shnu_qty5: Optional[str] = None            # 총 매수2 수량5
    seln_mbcr_glob_yn_1: Optional[str] = None        # 매도거래원구분1
    seln_mbcr_glob_yn_2: Optional[str] = None        # 매도거래원구분2
    seln_mbcr_glob_yn_3: Optional[str] = None        # 매도거래원구분3
    seln_mbcr_glob_yn_4: Optional[str] = None        # 매도거래원구분4
    seln_mbcr_glob_yn_5: Optional[str] = None        # 매도거래원구분5
    shnu_mbcr_glob_yn_1: Optional[str] = None        # 매수거래원구분1
    shnu_mbcr_glob_yn_2: Optional[str] = None        # 매수거래원구분2
    shnu_mbcr_glob_yn_3: Optional[str] = None        # 매수거래원구분3
    shnu_mbcr_glob_yn_4: Optional[str] = None        # 매수거래원구분4
    shnu_mbcr_glob_yn_5: Optional[str] = None        # 매수거래원구분5
    seln_mbcr_no1: Optional[str] = None              # 매도거래원코드1
    seln_mbcr_no2: Optional[str] = None              # 매도거래원코드2
    seln_mbcr_no3: Optional[str] = None              # 매도거래원코드3
    seln_mbcr_no4: Optional[str] = None              # 매도거래원코드4
    seln_mbcr_no5: Optional[str] = None              # 매도거래원코드5
    shnu_mbcr_no1: Optional[str] = None              # 매수거래원코드1
    shnu_mbcr_no2: Optional[str] = None              # 매수거래원코드2
    shnu_mbcr_no3: Optional[str] = None              # 매수거래원코드3
    shnu_mbcr_no4: Optional[str] = None              # 매수거래원코드4
    shnu_mbcr_no5: Optional[str] = None              # 매수거래원코드5
    seln_mbcr_rlim1: Optional[str] = None            # 매도 회원사 비중1
    seln_mbcr_rlim2: Optional[str] = None            # 매도 회원사 비중2
    seln_mbcr_rlim3: Optional[str] = None            # 매도 회원사 비중3
    seln_mbcr_rlim4: Optional[str] = None            # 매도 회원사 비중4
    seln_mbcr_rlim5: Optional[str] = None            # 매도 회원사 비중5
    shnu_mbcr_rlim1: Optional[str] = None            # 매수2 회원사 비중1
    shnu_mbcr_rlim2: Optional[str] = None            # 매수2 회원사 비중2
    shnu_mbcr_rlim3: Optional[str] = None            # 매수2 회원사 비중3
    shnu_mbcr_rlim4: Optional[str] = None            # 매수2 회원사 비중4
    shnu_mbcr_rlim5: Optional[str] = None            # 매수2 회원사 비중5
    seln_qty_icdc1: Optional[str] = None             # 매도 수량 증감1
    seln_qty_icdc2: Optional[str] = None             # 매도 수량 증감2
    seln_qty_icdc3: Optional[str] = None             # 매도 수량 증감3
    seln_qty_icdc4: Optional[str] = None             # 매도 수량 증감4
    seln_qty_icdc5: Optional[str] = None             # 매도 수량 증감5
    shnu_qty_icdc1: Optional[str] = None             # 매수2 수량 증감1
    shnu_qty_icdc2: Optional[str] = None             # 매수2 수량 증감2
    shnu_qty_icdc3: Optional[str] = None             # 매수2 수량 증감3
    shnu_qty_icdc4: Optional[str] = None             # 매수2 수량 증감4
    shnu_qty_icdc5: Optional[str] = None             # 매수2 수량 증감5
    glob_total_seln_qty: Optional[str] = None        # 외국계 총 매도 수량
    glob_total_shnu_qty: Optional[str] = None        # 외국계 총 매수2 수량
    glob_total_seln_qty_icdc: Optional[str] = None   # 외국계 총 매도 수량 증감
    glob_total_shnu_qty_icdc: Optional[str] = None   # 외국계 총 매수2 수량 증감
    glob_ntby_qty: Optional[str] = None              # 외국계 순매수 수량
    glob_seln_rlim: Optional[str] = None             # 외국계 매도 비중
    glob_shnu_rlim: Optional[str] = None             # 외국계 매수2 비중
    seln2_mbcr_eng_name1: Optional[str] = None       # 매도2 영문회원사명1
    seln2_mbcr_eng_name2: Optional[str] = None       # 매도2 영문회원사명2
    seln2_mbcr_eng_name3: Optional[str] = None       # 매도2 영문회원사명3
    seln2_mbcr_eng_name4: Optional[str] = None       # 매도2 영문회원사명4
    seln2_mbcr_eng_name5: Optional[str] = None       # 매도2 영문회원사명5
    byov_mbcr_eng_name1: Optional[str] = None        # 매수 영문회원사명1
    byov_mbcr_eng_name2: Optional[str] = None        # 매수 영문회원사명2
    byov_mbcr_eng_name3: Optional[str] = None        # 매수 영문회원사명3
    byov_mbcr_eng_name4: Optional[str] = None        # 매수 영문회원사명4
    byov_mbcr_eng_name5: Optional[str] = None        # 매수 영문회원사명5


_FIELD_NAMES = [f.name for f in fields(ResponseBody)]


# ── 요청 함수 ───────────────────────────────────────────────

def _subscribe_msg(approval_key: str, code: str, tr_type: Literal["1", "2"]) -> str:
    """구독 등록(tr_type="1")/해제(tr_type="2") 요청 메시지를 만든다."""
    return json.dumps({
        "header": {
            "approval_key": approval_key,
            "custtype": "P",
            "tr_type": tr_type,
            "content-type": "utf-8",
        },
        "body": {"input": {"tr_id": _TR_ID, "tr_key": code}},
    })


def _parse(data_cnt: int, payload: str) -> list[ResponseBody]:
    """"값^값^..." 본문을 데이터건수만큼 ResponseBody 로 나눈다."""
    values = payload.split("^")
    n = len(_FIELD_NAMES)
    return [ResponseBody(**dict(zip(_FIELD_NAMES, values[i * n:(i + 1) * n]))) for i in range(data_cnt)]


async def member_total(
    codes: list[str],
    callback: Callable[[ResponseBody], Any],
    stop_event: Optional[asyncio.Event] = None,
    refresh_key: bool = False,
) -> None:
    """국내주식 실시간회원사(통합, KRX+NXT)를 구독해 회원사 매매 변동마다 callback 을 호출한다. (모의투자 미지원, 실전 계좌 전용)

    stop_event 가 set 되면 구독을 해제하고 접속을 끊은 뒤 반환한다. 태스크가 취소(cancel)되거나
    예외가 나도 async with 블록을 빠져나가며 웹소켓 접속은 닫힌다.

    Args:
        codes: 구독 종목코드(tr_key) 목록, 6자리(ex ["005930", "000660"]). 최대 41개.
        callback: 회원사 데이터 1건(ResponseBody)마다 호출할 함수. 일반 함수와 async 함수 모두 가능.
        stop_event: set() 되면 구독 해제 후 종료. None 이면 취소될 때까지 계속 수신.
        refresh_key: True 면 접속 전에 웹소켓 접속키(approval_key)를 새로 발급받는다. 기본값 False.

    Raises:
        ValueError: 구독 종목이 없거나 41개를 넘을 때.
        KisApiError: 구독 요청이 거부됐을 때(rt_cd != "0").
        websockets.exceptions.ConnectionClosed: 서버가 접속을 끊었을 때.
    """
    if not codes:
        raise ValueError("구독할 종목코드를 1개 이상 입력하세요.")
    if len(codes) > _MAX_SUBSCRIPTIONS:
        raise ValueError(f"웹소켓 1세션당 구독은 최대 {_MAX_SUBSCRIPTIONS}건입니다. (입력 {len(codes)}건)")

    if refresh_key:
        kis_token._issue_websocket_key("real")
    approval_key = load_websocket_token("real")
    stop = stop_event or asyncio.Event()

    # KIS 는 웹소켓 표준 ping 대신 PINGPONG 메시지를 쓰므로 라이브러리 ping 은 끈다.
    async with websockets.connect(WS_DOMAIN["real"] + URL, ping_interval=None) as ws:
        for code in codes:
            await ws.send(_subscribe_msg(approval_key, code, "1"))

        # 수신 대기와 stop_event 대기를 동시에 걸어, stop_event 가 set 되는 즉시 루프를 빠져나온다.
        stop_task = asyncio.create_task(stop.wait())
        recv_task: Optional[asyncio.Task] = None
        try:
            while True:
                recv_task = asyncio.create_task(ws.recv())
                await asyncio.wait({recv_task, stop_task}, return_when=asyncio.FIRST_COMPLETED)
                if stop_task.done():
                    recv_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await recv_task
                    break
                data = recv_task.result()

                if not data:
                    continue

                # 실시간 데이터: "0|TR_ID|데이터건수|본문" (0: 평문, 1: 암호화 — 회원사는 평문)
                if data[0] in ("0", "1"):
                    parts = data.split("|", 3)
                    if len(parts) < 4 or parts[1] != _TR_ID:
                        continue
                    for body in _parse(int(parts[2]), parts[3]):
                        result = callback(body)
                        if inspect.isawaitable(result):
                            await result
                    continue

                # 제어 메시지(JSON): PINGPONG 응답, 구독 등록/해제 결과
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue

                header = obj.get("header", {})
                if header.get("tr_id") == "PINGPONG":
                    await ws.send(data)
                    continue

                body = obj.get("body", {})
                if body.get("rt_cd") not in (None, "0"):
                    raise KisApiError(body.get("msg_cd", ""), f"[{header.get('tr_key', '')}] {body.get('msg1', '')}")
        finally:
            # 외부에서 태스크가 취소돼도 대기 중인 recv/stop 태스크가 남지 않도록 정리한다.
            for task in (stop_task, recv_task):
                if task is not None and not task.done():
                    task.cancel()

        for code in codes:
            await ws.send(_subscribe_msg(approval_key, code, "2"))


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    # Ctrl+C 를 누를 때까지 계속 수신한다.
    async def _main() -> None:
        def on_member(mb: ResponseBody) -> None:
            print(mb.mksc_shrn_iscd,
                  f"매도1 {mb.seln2_mbcr_name1}({mb.total_seln_qty1})", f"매수1 {mb.byov_mbcr_name1}({mb.total_shnu_qty1})",
                  f"외국계 순매수 {mb.glob_ntby_qty}")

        await member_total(codes=["005930", "000660"], callback=on_member, refresh_key=True)

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
