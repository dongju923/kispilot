# 주식예약주문정정취소[v1_국내주식-018,019]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/order-resv-rvsecncl"
# ※ 모의투자 미지원 (실전투자 전용).
# ※ 정정은 취소보다 필수 입력값이 많다 — 취소는 RSVN_ORD_SEQ(예약주문순번)만 있으면 되고,
#   정정은 PDNO/ORD_QTY/ORD_UNPR/SLL_BUY_DVSN_CD/ORD_DVSN_CD/ORD_OBJT_CBLC_DVSN_CD(order_reserve.py와 동일)를
#   RSVN_ORD_SEQ와 함께 보내야 한다.
# ※ 응답 메시지 필드명이 msg1이 아니라 msg (order_reserve.py와 동일한 KIS 문서 표기).

_TR_ID = {"revise": "CTSC0013U", "cancel": "CTSC0009U"}


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    nrml_prcs_yn: Optional[str] = None      # 정상처리여부


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg: str                                                         # 응답메세지 (다른 API의 msg1에 해당)
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 처리 결과(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def _post_reservation_edit(op: Literal["revise", "cancel"], body: dict) -> ResponseBody:
    """예약주문 정정/취소 공통 POST 처리."""
    token = load_token("real")

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": REAL_APPKEY,
        "appsecret": REAL_APP_SECRET,
        "tr_id": _TR_ID[op],
        "custtype": "P",
    }
    full_body = {"CANO": CANO, "ACNT_PRDT_CD": ACNT_PRDT_CD, **body}

    response = get_session().post(DOMAIN["real"] + URL, headers=headers, json=full_body, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output 키가 없거나 null일 수 있어 안전 파싱.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_outputs = raw.get("output") or []
    if isinstance(raw_outputs, dict):  # 성공 응답의 output 은 배열이 아니라 객체 하나로 온다
        raw_outputs = [raw_outputs]
    # 응답 키가 대문자(ODNO 등)로 와도 받도록 소문자로 맞춘다
    outputs = [ResponseBodyOutput(**{k.lower(): v for k, v in item.items() if k.lower() in fields}) for item in raw_outputs]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg=raw.get("msg", ""),
        output=outputs,
    )


def revise_reservation(
    rsvn_ord_seq: str,
    pdno: str,
    ord_qty: str,
    sll_buy_dvsn_cd: Literal["01", "02"],
    ord_dvsn_cd: Literal["00", "01", "02", "05"],
    ord_objt_cblc_dvsn_cd: Literal["10", "12", "14", "21", "22", "23", "24", "25", "26", "27", "28"] = "10",
    ord_unpr: str = "0",
    loan_dt: str = "",
    rsvn_ord_end_dt: str = "",
    ctal_tlno: str = "",
    rsvn_ord_orgno: str = "",
    rsvn_ord_ord_dt: str = "",
) -> ResponseBody:
    """예약주문을 정정한다. (모의투자 미지원, 실전 계좌 전용)

    Args:
        rsvn_ord_seq: 예약주문순번(RSVN_ORD_SEQ). order_reserve.py 호출 결과 output의 rsvn_ord_seq.
        pdno: 종목코드(PDNO), 6자리.
        ord_qty: 주문수량(ORD_QTY). 정정 후 수량.
        sll_buy_dvsn_cd: 매도매수구분코드(SLL_BUY_DVSN_CD). 01 매도 / 02 매수.
        ord_dvsn_cd: 주문구분코드(ORD_DVSN_CD). 00 지정가/01 시장가/02 조건부지정가/05 장전 시간외.
        ord_objt_cblc_dvsn_cd: 주문대상잔고구분코드(ORD_OBJT_CBLC_DVSN_CD). order_reserve.py와 동일한 코드표.
            기본값 "10"(현금).
        ord_unpr: 주문단가(ORD_UNPR). 정정 후 가격. 시장가/장전 시간외는 빈 문자열이면 자동으로 "0" 처리.
        loan_dt: 대출일자(LOAN_DT), YYYYMMDD. 신용 관련이 아니면 "".
        rsvn_ord_end_dt: 예약주문종료일자(RSVN_ORD_END_DT), YYYYMMDD. 기간예약주문 종료일을 바꿀 때만.
        ctal_tlno: 연락전화번호(CTAL_TLNO).
        rsvn_ord_orgno: 예약주문조직번호(RSVN_ORD_ORGNO).
        rsvn_ord_ord_dt: 예약주문주문일자(RSVN_ORD_ORD_DT), YYYYMMDD.

    Returns:
        rt_cd/msg_cd/msg와 처리 결과(output.nrml_prcs_yn)를 담은 ResponseBody.
    """
    ord_unpr = ord_unpr or "0"  # 시장가/장전 시간외 등 가격 미지정 주문은 "0"으로 보내야 함

    body = {
        "PDNO": pdno,
        "ORD_QTY": ord_qty,
        "ORD_UNPR": ord_unpr,
        "SLL_BUY_DVSN_CD": sll_buy_dvsn_cd,
        "ORD_DVSN_CD": ord_dvsn_cd,
        "ORD_OBJT_CBLC_DVSN_CD": ord_objt_cblc_dvsn_cd,
        "LOAN_DT": loan_dt,
        "RSVN_ORD_END_DT": rsvn_ord_end_dt,
        "CTAL_TLNO": ctal_tlno,
        "RSVN_ORD_SEQ": rsvn_ord_seq,
        "RSVN_ORD_ORGNO": rsvn_ord_orgno,
        "RSVN_ORD_ORD_DT": rsvn_ord_ord_dt,
    }
    return _post_reservation_edit("revise", body)


def cancel_reservation(
    rsvn_ord_seq: str,
    rsvn_ord_orgno: str = "",
    rsvn_ord_ord_dt: str = "",
) -> ResponseBody:
    """예약주문을 취소한다. (모의투자 미지원, 실전 계좌 전용)

    정정과 달리 종목/수량/가격 등은 필요 없고 어떤 예약주문인지 식별하는 값만 있으면 된다.

    Args:
        rsvn_ord_seq: 예약주문순번(RSVN_ORD_SEQ). order_reserve.py 호출 결과 output의 rsvn_ord_seq.
        rsvn_ord_orgno: 예약주문조직번호(RSVN_ORD_ORGNO).
        rsvn_ord_ord_dt: 예약주문주문일자(RSVN_ORD_ORD_DT), YYYYMMDD.

    Returns:
        rt_cd/msg_cd/msg와 처리 결과(output.nrml_prcs_yn)를 담은 ResponseBody.
    """
    body = {
        "RSVN_ORD_SEQ": rsvn_ord_seq,
        "RSVN_ORD_ORGNO": rsvn_ord_orgno,
        "RSVN_ORD_ORD_DT": rsvn_ord_ord_dt,
    }
    return _post_reservation_edit("cancel", body)


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = cancel_reservation(rsvn_ord_seq="1")
    print(result)
