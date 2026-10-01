# 주식예약주문[v1_국내주식-017]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/order-resv"
# ※ 모의투자 미지원 (실전투자 전용).
# ※ 예약주문 가능시간: 15:40 ~ 익영업일 07:30 (단, 서버 초기화 시간 23:40~00:10은 불가).
# ※ RSVN_ORD_END_DT를 안 넣으면 "일반예약주문"으로 다음 영업일에 1회만 주문 전송되고 예약은 종료됨.
#   넣으면 "기간예약주문"으로, 미체결 잔량에 대해 예약종료일까지 매 영업일 주문이 실행됨
#   (예약종료일은 익영업일 기준 공휴일 포함 최대 30일 후까지 입력 가능, 계좌당 최대 1,000건).
# ※ 예약주문 처리내역은 별도로 통보되지 않으므로, 주문처리일 장 시작 전 반드시 처리결과를 직접 확인해야 함
#   (매수가능금액/매도가능수량 부족, 상하한가 변경 등으로 거부될 수 있음).
# ※ 응답 메시지 필드명이 다른 API들과 달리 msg1이 아니라 msg 로 내려온다(KIS 문서 원문 그대로).

_TR_ID = "CTSC0008U"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    rsvn_ord_seq: Optional[str] = None      # 예약주문 순번


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg: str                                                         # 응답메세지 (다른 API의 msg1에 해당)
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 예약주문 결과(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def _place_reservation(
    sll_buy_dvsn_cd: Literal["01", "02"],
    pdno: str,
    ord_qty: str,
    ord_unpr: str,
    ord_dvsn_cd: str,
    ord_objt_cblc_dvsn_cd: str,
    loan_dt: str,
    rsvn_ord_end_dt: str,
    ldng_dt: str,
) -> ResponseBody:
    """예약매수/매도 주문 공통 처리. (모의투자 미지원, 실전 계좌 전용)

    Args:
        sll_buy_dvsn_cd: 매도매수구분코드(SLL_BUY_DVSN_CD). 01 매도 / 02 매수.
        pdno: 종목코드(PDNO), 6자리.
        ord_qty: 주문수량(ORD_QTY).
        ord_unpr: 주문단가(ORD_UNPR). 장전 시간외/시장가는 빈 문자열이면 자동으로 "0" 처리.
        ord_dvsn_cd: 주문구분코드(ORD_DVSN_CD). 00 지정가/01 시장가/02 조건부지정가/05 장전 시간외.
        ord_objt_cblc_dvsn_cd: 주문대상잔고구분코드(ORD_OBJT_CBLC_DVSN_CD).
            매수/매도 공통 10 현금. 매도 전용: 12 주식담보대출/14 대여상환/21~28 신용 관련.
        loan_dt: 대출일자(LOAN_DT), YYYYMMDD. 신용 관련 매도가 아니면 "".
        rsvn_ord_end_dt: 예약주문종료일자(RSVN_ORD_END_DT), YYYYMMDD. 비우면 일반예약주문(다음 영업일 1회).
            채우면 기간예약주문(그 날짜까지 매 영업일 재시도, 익영업일 기준 최대 30일 후까지).
        ldng_dt: 대여일자(LDNG_DT), YYYYMMDD. 대여상환이 아니면 "".

    Returns:
        rt_cd/msg_cd/msg와 예약주문 결과(output, rsvn_ord_seq 포함)를 담은 ResponseBody.
    """
    ord_unpr = ord_unpr or "0"  # 시장가/장전 시간외 등 가격 미지정 주문은 "0"으로 보내야 함

    token = load_token("real")

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": REAL_APPKEY,
        "appsecret": REAL_APP_SECRET,
        "tr_id": _TR_ID,
        "custtype": "P",
    }
    body = {
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "PDNO": pdno,
        "ORD_QTY": ord_qty,
        "ORD_UNPR": ord_unpr,
        "SLL_BUY_DVSN_CD": sll_buy_dvsn_cd,
        "ORD_DVSN_CD": ord_dvsn_cd,
        "ORD_OBJT_CBLC_DVSN_CD": ord_objt_cblc_dvsn_cd,
        "LOAN_DT": loan_dt,
        "RSVN_ORD_END_DT": rsvn_ord_end_dt,
        "LDNG_DT": ldng_dt,
    }
    response = get_session().post(DOMAIN["real"] + URL, headers=headers, json=body, timeout=10)
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


def reserve_buy_order(
    pdno: str,
    ord_qty: str,
    ord_dvsn_cd: Literal["00", "01", "02", "05"],
    ord_unpr: str = "0",
    rsvn_ord_end_dt: str = "",
) -> ResponseBody:
    """예약매수주문. 현금매수만 지원(주문대상잔고구분코드는 10 현금으로 고정)."""
    return _place_reservation(
        "02", pdno, ord_qty, ord_unpr, ord_dvsn_cd, "10",
        loan_dt="", rsvn_ord_end_dt=rsvn_ord_end_dt, ldng_dt="",
    )


def reserve_sell_order(
    pdno: str,
    ord_qty: str,
    ord_dvsn_cd: Literal["00", "01", "02", "05"],
    ord_unpr: str = "0",
    ord_objt_cblc_dvsn_cd: Literal["10", "12", "14", "21", "22", "23", "24", "25", "26", "27", "28"] = "10",
    loan_dt: str = "",
    rsvn_ord_end_dt: str = "",
    ldng_dt: str = "",
) -> ResponseBody:
    """예약매도주문. ord_objt_cblc_dvsn_cd로 현금/신용/대여상환 등 매도 대상 잔고를 지정한다.

    10 현금 / 12 주식담보대출 / 14 대여상환 / 21 자기융자신규 / 22 유통대주신규 / 23 유통융자신규 /
    24 자기대주신규 / 25 자기융자상환 / 26 유통대주상환 / 27 유통융자상환 / 28 자기대주상환.
    """
    return _place_reservation(
        "01", pdno, ord_qty, ord_unpr, ord_dvsn_cd, ord_objt_cblc_dvsn_cd,
        loan_dt=loan_dt, rsvn_ord_end_dt=rsvn_ord_end_dt, ldng_dt=ldng_dt,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = reserve_buy_order(pdno="005930", ord_qty="1", ord_dvsn_cd="00", ord_unpr="70000")
    print(result)
