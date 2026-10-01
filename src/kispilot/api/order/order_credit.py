# 주식주문(신용)[v1_국내주식-002]
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/order-credit"
# ※ 모의투자 미지원 (실전투자 전용)

# ORD_DVSN(주문구분) 코드표
# [KRX]
#   00 지정가            01 시장가            02 조건부지정가       03 최유리지정가
#   04 최우선지정가       05 장전 시간외        06 장후 시간외
#   11 IOC지정가(즉시체결,잔량취소)          12 FOK지정가(즉시체결,전량취소)
#   13 IOC시장가(즉시체결,잔량취소)          14 FOK시장가(즉시체결,전량취소)
#   15 IOC최유리(즉시체결,잔량취소)          16 FOK최유리(즉시체결,전량취소)
#   21 중간가             22 스톱지정가         23 중간가IOC          24 중간가FOK
#   41 KRX애프터마켓지정가                   42 KRX애프터마켓지정가IOC
#   43 KRX애프터마켓지정가FOK                44 KRX애프터마켓최유리지정가
#   45 KRX애프터마켓최유리지정가IOC          46 KRX애프터마켓최유리지정가FOK
#   47 KRX애프터마켓최우선지정가
# [NXT]
#   00 지정가  03 최유리지정가  04 최우선지정가
#   11 IOC지정가  12 FOK지정가  13 IOC시장가  14 FOK시장가  15 IOC최유리  16 FOK최유리
#   21 중간가  22 스톱지정가  23 중간가IOC  24 중간가FOK
#   27 NXT GTP지정가  28 NXT GTP최유리  29 NXT GTP최우선
# [SOR]
#   00 지정가  01 시장가  03 최유리지정가  04 최우선지정가
#   11 IOC지정가  12 FOK지정가  13 IOC시장가  14 FOK시장가  15 IOC최유리  16 FOK최유리

# CRDT_TYPE(신용유형) 코드표
#   [매도] 22 유통대주신규   24 자기대주신규   25 자기융자상환   27 유통융자상환
#   [매수] 21 자기융자신규   23 유통융자신규   26 유통대주상환   28 자기대주상환

_TR_ID = {"buy": "TTTC0052U", "sell": "TTTC0051U"}


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    krx_fwdg_ord_orgno: Optional[str] = None   # 한국거래소전송주문조직번호
    odno: Optional[str] = None                 # 주문번호
    ord_tmd: Optional[str] = None               # 주문시간


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output: ResponseBodyOutput          # 주문 결과 데이터


# ── 요청 함수 ───────────────────────────────────────────────

def _place_order(
    side: Literal["buy", "sell"],
    code: str,
    ord_qty: str,
    ord_dvsn: str,
    ord_unpr: str,
    crdt_type: str,
    loan_dt: str,
    cndt_pric: str,
    market: Literal["KRX", "NXT", "SOR"],
) -> ResponseBody:
    """신용 매수/매도 주문 공통 처리. (모의투자 미지원, 실전 계좌 전용)

    Args:
        side: "buy"(매수) 또는 "sell"(매도) — tr_id 선택에 사용.
        code: 종목코드(PDNO), 6자리.
        ord_qty: 주문수량(ORD_QTY).
        ord_dvsn: 주문구분(ORD_DVSN). 00 지정가/01 시장가 등 — 파일 상단 코드표 참고.
        ord_unpr: 주문단가(ORD_UNPR). 시장가 등 가격 미지정 주문은 빈 문자열이면 자동으로 "0" 처리.
        crdt_type: 신용유형(CRDT_TYPE). 매수/매도별로 허용 코드가 다름 — 파일 상단 코드표 참고.
        loan_dt: 대출일자(LOAN_DT). 매수는 신규 대출일(오늘), 매도는 상환 대상 종목의 원래 대출일(YYYYMMDD).
        cndt_pric: 조건가격(CNDT_PRIC). 스탑지정가호가(ORD_DVSN=22) 주문 시에만 필요.
        market: 거래소ID구분코드(EXCG_ID_DVSN_CD). KRX/NXT/SOR.

    Returns:
        rt_cd/msg_cd/msg1과 주문 결과(output)를 담은 ResponseBody.
    """
    ord_unpr = ord_unpr or "0"  # 시장가 등 가격 미지정 주문은 빈 문자열이 아니라 "0"으로 보내야 함

    token = load_token("real")
    tr_id = _TR_ID[side]

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": REAL_APPKEY,
        "appsecret": REAL_APP_SECRET,
        "tr_id": tr_id,
        "custtype": "P",
    }
    response = get_session().post(
        DOMAIN["real"] + URL,
        headers=headers,
        json={
            "CANO": CANO,
            "ACNT_PRDT_CD": ACNT_PRDT_CD,
            "PDNO": code,
            "SLL_TYPE": "",   # 문서상 공란 입력
            "CRDT_TYPE": crdt_type,
            "LOAN_DT": loan_dt,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": ord_qty,
            "ORD_UNPR": ord_unpr,
            "EXCG_ID_DVSN_CD": market,
            "CNDT_PRIC": cndt_pric,
        },
        timeout=10,
    )
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output 키가 없거나 null일 수 있어 안전 파싱.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_output = raw.get("output") or {}
    # 응답 키가 대문자(ODNO 등)로 와도 받도록 소문자로 맞춘다
    output = ResponseBodyOutput(**{k.lower(): v for k, v in raw_output.items() if k.lower() in fields})

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output=output,
    )


def buy_credit(
    code, ord_qty, ord_dvsn, ord_unpr,
    crdt_type: Literal["21", "23"],   # 21:자기융자신규 / 23:유통융자신규
    loan_dt: Optional[str] = None,    # 생략 시 오늘 날짜(YYYYMMDD)로 신규 대출
    cndt_pric="",
    market: Literal["KRX", "NXT", "SOR"] = "KRX",
) -> ResponseBody:
    """신용 매수(융자) 주문.

    Args:
        code: 종목코드(PDNO), 6자리.
        ord_qty: 주문수량(ORD_QTY).
        ord_dvsn: 주문구분(ORD_DVSN). 00 지정가/01 시장가 등 — 파일 상단 코드표 참고.
        ord_unpr: 주문단가(ORD_UNPR). 시장가 등 가격 미지정 주문은 ""로 넘기면 자동으로 "0" 처리.
        crdt_type: 신용유형(CRDT_TYPE). 21 자기융자신규 / 23 유통융자신규.
        loan_dt: 대출일자(LOAN_DT), YYYYMMDD. 생략 시 오늘 날짜로 신규 대출 처리.
        cndt_pric: 조건가격(CNDT_PRIC). 스탑지정가호가(ORD_DVSN=22) 주문 시에만 필요.
        market: 거래소ID구분코드(EXCG_ID_DVSN_CD). KRX/NXT/SOR. 기본값 "KRX".

    Returns:
        rt_cd/msg_cd/msg1과 주문 결과(output)를 담은 ResponseBody.
    """
    loan_dt = loan_dt or datetime.now().strftime("%Y%m%d")
    return _place_order("buy", code, ord_qty, ord_dvsn, ord_unpr, crdt_type, loan_dt, cndt_pric, market)


def sell_credit(
    code, ord_qty, ord_dvsn, ord_unpr,
    crdt_type: Literal["22", "24", "25", "27"],   # 22:유통대주신규 24:자기대주신규 25:자기융자상환 27:유통융자상환
    loan_dt: str,                                  # 상환/매도할 종목의 원래 대출일자(YYYYMMDD)
    cndt_pric="",
    market: Literal["KRX", "NXT", "SOR"] = "KRX",
) -> ResponseBody:
    """신용 매도(대주/상환) 주문.

    Args:
        code: 종목코드(PDNO), 6자리.
        ord_qty: 주문수량(ORD_QTY).
        ord_dvsn: 주문구분(ORD_DVSN). 00 지정가/01 시장가 등 — 파일 상단 코드표 참고.
        ord_unpr: 주문단가(ORD_UNPR). 시장가 등 가격 미지정 주문은 ""로 넘기면 자동으로 "0" 처리.
        crdt_type: 신용유형(CRDT_TYPE). 22 유통대주신규 / 24 자기대주신규 / 25 자기융자상환 / 27 유통융자상환.
        loan_dt: 대출일자(LOAN_DT), YYYYMMDD. 상환/매도할 종목의 원래 대출일자.
        cndt_pric: 조건가격(CNDT_PRIC). 스탑지정가호가(ORD_DVSN=22) 주문 시에만 필요.
        market: 거래소ID구분코드(EXCG_ID_DVSN_CD). KRX/NXT/SOR. 기본값 "KRX".

    Returns:
        rt_cd/msg_cd/msg1과 주문 결과(output)를 담은 ResponseBody.
    """
    return _place_order("sell", code, ord_qty, ord_dvsn, ord_unpr, crdt_type, loan_dt, cndt_pric, market)


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = buy_credit(code="005930", ord_qty="1", ord_dvsn="01", ord_unpr="", crdt_type="23")
    print(result)
