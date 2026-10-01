# 매도가능수량조회[국내주식-165]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/inquire-psbl-sell"
# ※ 모의투자 미지원 (실전투자 전용). 1회 호출에 최대 1건만 조회됨(연속조회 불가, tr_cont 없음).
# ※ 특정 종목 매도가능수량 확인 시 매도주문 내려는 종목코드(PDNO)로 호출 후 output.ord_psbl_qty(주문가능수량) 확인.

_TR_ID = "TTTC8408R"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    pdno: Optional[str] = None              # 상품번호
    prdt_name: Optional[str] = None          # 상품명
    buy_qty: Optional[str] = None            # 매수수량
    sll_qty: Optional[str] = None            # 매도수량
    cblc_qty: Optional[str] = None           # 잔고수량
    nsvg_qty: Optional[str] = None           # 비저축수량
    ord_psbl_qty: Optional[str] = None       # 주문가능수량
    pchs_avg_pric: Optional[str] = None      # 매입평균가격
    pchs_amt: Optional[str] = None           # 매입금액
    now_pric: Optional[str] = None           # 현재가
    evlu_amt: Optional[str] = None           # 평가금액
    evlu_pfls_amt: Optional[str] = None      # 평가손익금액
    evlu_pfls_rt: Optional[str] = None       # 평가손익율


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output1: ResponseBodyOutput1        # 매도가능수량 조회 결과(단일)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_psbl_sell(pdno: str) -> ResponseBody:
    """특정 종목의 매도가능수량을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    Args:
        pdno: 종목코드(PDNO), 보유종목 6자리. ex) "000660".

    Returns:
        rt_cd/msg_cd/msg1과 조회 결과(output1)를 담은 ResponseBody.
        매도가능수량은 output1.ord_psbl_qty(주문가능수량)로 확인.
    """
    token = load_token("real")

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": REAL_APPKEY,
        "appsecret": REAL_APP_SECRET,
        "tr_id": _TR_ID,
        "custtype": "P",
    }
    params = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "PDNO": pdno,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1 키가 없거나 null일 수 있어 안전 파싱.
    fields = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or {}
    output1 = ResponseBodyOutput1(**{k: v for k, v in raw_output1.items() if k in fields})

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_psbl_sell(pdno="066570")
    print(result)
