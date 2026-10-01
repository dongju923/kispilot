# 국내주식 실시간호가 (통합)[H0UNASP0]
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

URL = "/tryitout/H0UNASP0"
# ※ 모의투자 미지원 (실전투자 전용). KRX + NXT 통합 10단계 호가.
# ※ 웹소켓 1세션당 구독 가능 건수는 실시간 체결가/호가/회원사 등을 합쳐 최대 41건.
# ※ 수신 데이터는 "0|TR_ID|데이터건수|값^값^..." 형식이며, 데이터건수가 2 이상이면 값이 필드 수 단위로 이어서 온다.
# ※ PINGPONG 메시지는 받은 그대로 되돌려 보내야 서버가 세션을 끊지 않는다.

_TR_ID = "H0UNASP0"

_MAX_SUBSCRIPTIONS = 41


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBody:
    mksc_shrn_iscd: Optional[str] = None         # 유가증권 단축 종목코드
    bsop_hour: Optional[str] = None              # 영업 시간
    hour_cls_code: Optional[str] = None          # 시간 구분 코드
    askp1: Optional[str] = None                  # 매도호가1
    askp2: Optional[str] = None                  # 매도호가2
    askp3: Optional[str] = None                  # 매도호가3
    askp4: Optional[str] = None                  # 매도호가4
    askp5: Optional[str] = None                  # 매도호가5
    askp6: Optional[str] = None                  # 매도호가6
    askp7: Optional[str] = None                  # 매도호가7
    askp8: Optional[str] = None                  # 매도호가8
    askp9: Optional[str] = None                  # 매도호가9
    askp10: Optional[str] = None                 # 매도호가10
    bidp1: Optional[str] = None                  # 매수호가1
    bidp2: Optional[str] = None                  # 매수호가2
    bidp3: Optional[str] = None                  # 매수호가3
    bidp4: Optional[str] = None                  # 매수호가4
    bidp5: Optional[str] = None                  # 매수호가5
    bidp6: Optional[str] = None                  # 매수호가6
    bidp7: Optional[str] = None                  # 매수호가7
    bidp8: Optional[str] = None                  # 매수호가8
    bidp9: Optional[str] = None                  # 매수호가9
    bidp10: Optional[str] = None                 # 매수호가10
    askp_rsqn1: Optional[str] = None             # 매도호가 잔량1
    askp_rsqn2: Optional[str] = None             # 매도호가 잔량2
    askp_rsqn3: Optional[str] = None             # 매도호가 잔량3
    askp_rsqn4: Optional[str] = None             # 매도호가 잔량4
    askp_rsqn5: Optional[str] = None             # 매도호가 잔량5
    askp_rsqn6: Optional[str] = None             # 매도호가 잔량6
    askp_rsqn7: Optional[str] = None             # 매도호가 잔량7
    askp_rsqn8: Optional[str] = None             # 매도호가 잔량8
    askp_rsqn9: Optional[str] = None             # 매도호가 잔량9
    askp_rsqn10: Optional[str] = None            # 매도호가 잔량10
    bidp_rsqn1: Optional[str] = None             # 매수호가 잔량1
    bidp_rsqn2: Optional[str] = None             # 매수호가 잔량2
    bidp_rsqn3: Optional[str] = None             # 매수호가 잔량3
    bidp_rsqn4: Optional[str] = None             # 매수호가 잔량4
    bidp_rsqn5: Optional[str] = None             # 매수호가 잔량5
    bidp_rsqn6: Optional[str] = None             # 매수호가 잔량6
    bidp_rsqn7: Optional[str] = None             # 매수호가 잔량7
    bidp_rsqn8: Optional[str] = None             # 매수호가 잔량8
    bidp_rsqn9: Optional[str] = None             # 매수호가 잔량9
    bidp_rsqn10: Optional[str] = None            # 매수호가 잔량10
    total_askp_rsqn: Optional[str] = None        # 총 매도호가 잔량
    total_bidp_rsqn: Optional[str] = None        # 총 매수호가 잔량
    ovtm_total_askp_rsqn: Optional[str] = None   # 시간외 총 매도호가 잔량
    ovtm_total_bidp_rsqn: Optional[str] = None   # 시간외 총 매수호가 잔량
    antc_cnpr: Optional[str] = None              # 예상 체결가
    antc_cnqn: Optional[str] = None              # 예상 체결량
    antc_vol: Optional[str] = None               # 예상 거래량
    antc_cntg_vrss: Optional[str] = None         # 예상 체결 대비
    antc_cntg_vrss_sign: Optional[str] = None    # 예상 체결 대비 부호
    antc_cntg_prdy_ctrt: Optional[str] = None    # 예상 체결 전일 대비율
    acml_vol: Optional[str] = None               # 누적 거래량
    total_askp_rsqn_icdc: Optional[str] = None   # 총 매도호가 잔량 증감
    total_bidp_rsqn_icdc: Optional[str] = None   # 총 매수호가 잔량 증감
    ovtm_total_askp_icdc: Optional[str] = None   # 시간외 총 매도호가 증감
    ovtm_total_bidp_icdc: Optional[str] = None   # 시간외 총 매수호가 증감
    stck_deal_cls_code: Optional[str] = None     # 주식 매매 구분 코드
    kmid_prc: Optional[str] = None               # KRX 중간가
    kmid_total_rsqn: Optional[str] = None        # KRX 중간가잔량합계수량
    kmid_cls_code: Optional[str] = None          # KRX 중간가 매수매도 구분
    nmid_prc: Optional[str] = None               # NXT 중간가
    nmid_total_rsqn: Optional[str] = None        # NXT 중간가잔량합계수량
    nmid_cls_code: Optional[str] = None          # NXT 중간가 매수매도 구분
    antc_exch_cls_code: Optional[str] = None     # 예상체결 거래소구분 (1:KRX 2:NXT)


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


async def asking_price_total(
    codes: list[str],
    callback: Callable[[ResponseBody], Any],
    stop_event: Optional[asyncio.Event] = None,
    refresh_key: bool = False,
) -> None:
    """국내주식 실시간호가(통합, KRX+NXT)를 구독해 호가 변경마다 callback 을 호출한다. (모의투자 미지원, 실전 계좌 전용)

    stop_event 가 set 되면 구독을 해제하고 접속을 끊은 뒤 반환한다. 태스크가 취소(cancel)되거나
    예외가 나도 async with 블록을 빠져나가며 웹소켓 접속은 닫힌다.

    Args:
        codes: 구독 종목코드(tr_key) 목록, 6자리(ex ["005930", "000660"]). 최대 41개.
        callback: 호가 1건(ResponseBody)마다 호출할 함수. 일반 함수와 async 함수 모두 가능.
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

                # 실시간 데이터: "0|TR_ID|데이터건수|본문" (0: 평문, 1: 암호화 — 호가는 평문)
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
        def on_orderbook(ob: ResponseBody) -> None:
            print(ob.bsop_hour, ob.mksc_shrn_iscd,
                  f"매도1 {ob.askp1}({ob.askp_rsqn1})", f"매수1 {ob.bidp1}({ob.bidp_rsqn1})",
                  f"총잔량 {ob.total_askp_rsqn}/{ob.total_bidp_rsqn}")

        await asking_price_total(codes=["005930", "000660"], callback=on_orderbook, refresh_key=True)

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
