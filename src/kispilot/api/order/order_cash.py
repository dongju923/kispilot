# 주식주문(현금)[v1_국내주식-001]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import (
    DOMAIN,
    CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET,
    PAPER_CANO, PAPER_ACNT_PRDT_CD, PAPER_APPKEY, PAPER_APP_SECRET,
)
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/order-cash"

# ORD_DVSN(주문구분) 코드표
# [KRX]
#   00 지정가            01 시장가            02 조건부지정가       03 최유리지정가
#   04 최우선지정가       05 장전 시간외        06 장후 시간외        07 시간외 단일가
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

# (mode, side)별 tr_id
_TR_ID = {
    ("real", "buy"): "TTTC0012U",
    ("real", "sell"): "TTTC0011U",
    ("paper", "buy"): "VTTC0012U",
    ("paper", "sell"): "VTTC0011U",
}


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    KRX_FWDG_ORD_ORGNO: Optional[str] = None   # 계좌관리점코드
    ODNO: Optional[str] = None                 # 주문번호
    ORD_TMD: Optional[str] = None              # 주문시간


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output: ResponseBodyOutput          # 주문 결과 데이터


# ── 요청 함수 ───────────────────────────────────────────────

def _get_account(mode: Literal["real", "paper"]) -> tuple[str, str, str, str, str]:
    """모드에 맞는 계좌번호, 상품코드, 앱키, 앱시크릿, 도메인을 반환한다.

    Args:
        mode: "real"(실전투자) 또는 "paper"(모의투자).

    Returns:
        (CANO, ACNT_PRDT_CD, appkey, appsecret, domain) 튜플.
    """
    if mode == "real":
        return CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET, DOMAIN["real"]
    return PAPER_CANO, PAPER_ACNT_PRDT_CD, PAPER_APPKEY, PAPER_APP_SECRET, DOMAIN["paper"]


def _place_order(
    side: Literal["buy", "sell"],
    code: str,
    ord_qty: str,
    ord_dvsn: str,
    ord_unpr: str,
    cndt_pric: str,
    mode: Literal["real", "paper"],
    market: Literal["KRX", "NXT", "SOR"],
    sll_type: str,
) -> ResponseBody:
    """현금 매수/매도 주문 공통 처리.

    Args:
        side: "buy"(매수) 또는 "sell"(매도) — tr_id 선택에 사용.
        code: 종목코드(PDNO), 6자리.
        ord_qty: 주문수량(ORD_QTY).
        ord_dvsn: 주문구분(ORD_DVSN). 00 지정가/01 시장가 등 — 파일 상단 코드표 참고.
        ord_unpr: 주문단가(ORD_UNPR). 시장가 등 가격 미지정 주문은 빈 문자열이면 자동으로 "0" 처리.
        cndt_pric: 조건가격(CNDT_PRIC). 스탑지정가호가(ORD_DVSN=22) 주문 시에만 필요.
        mode: "real"(실전투자) 또는 "paper"(모의투자).
        market: 거래소ID구분코드(EXCG_ID_DVSN_CD). KRX/NXT/SOR.
        sll_type: 매도유형(SLL_TYPE). 매수 주문은 "", 매도 주문은 01/02/03.

    Returns:
        rt_cd/msg_cd/msg1과 주문 결과(output)를 담은 ResponseBody.
    """
    ord_unpr = ord_unpr or "0"  # 시장가 등 가격 미지정 주문은 빈 문자열이 아니라 "0"으로 보내야 함

    token = load_token(mode)
    cano, acnt_prdt_cd, app_key, app_secret, domain = _get_account(mode)
    tr_id = _TR_ID[(mode, side)]

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": tr_id,
        "custtype": "P",
    }
    response = get_session().post(
        domain + URL,
        headers=headers,
        json={
            "CANO": cano,
            "ACNT_PRDT_CD": acnt_prdt_cd,
            "PDNO": code,
            "SLL_TYPE": sll_type,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": ord_qty,
            "ORD_UNPR": ord_unpr,
            "CNDT_PRIC": cndt_pric,
            "EXCG_ID_DVSN_CD": market,
        },
        timeout=10,
    )
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output 키가 없거나 null일 수 있어 안전 파싱.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_output = raw.get("output") or {}
    output = ResponseBodyOutput(**{k: v for k, v in raw_output.items() if k in fields})

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output=output,
    )


def buy_cash(
    code, ord_qty, ord_dvsn, ord_unpr, cndt_pric="",
    mode: Literal["real", "paper"] = "real",
    market: Literal["KRX", "NXT", "SOR"] = "KRX",
) -> ResponseBody:
    """현금 매수 주문.

    Args:
        code: 종목코드(PDNO), 6자리.
        ord_qty: 주문수량(ORD_QTY).
        ord_dvsn: 주문구분(ORD_DVSN). 00 지정가/01 시장가 등 — 파일 상단 코드표 참고.
        ord_unpr: 주문단가(ORD_UNPR). 시장가 등 가격 미지정 주문은 ""로 넘기면 자동으로 "0" 처리.
        cndt_pric: 조건가격(CNDT_PRIC). 스탑지정가호가(ORD_DVSN=22) 주문 시에만 필요.
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".
        market: 거래소ID구분코드(EXCG_ID_DVSN_CD). KRX/NXT/SOR. 기본값 "KRX".

    Returns:
        rt_cd/msg_cd/msg1과 주문 결과(output)를 담은 ResponseBody.
    """
    return _place_order("buy", code, ord_qty, ord_dvsn, ord_unpr, cndt_pric, mode, market, sll_type="")


def sell_cash(
    code, ord_qty, ord_dvsn, ord_unpr, cndt_pric="",
    mode: Literal["real", "paper"] = "real",
    market: Literal["KRX", "NXT", "SOR"] = "KRX",
    sll_type="01",  # 01:일반매도/02:임의매매/03:대차매도
) -> ResponseBody:
    """현금 매도 주문.

    Args:
        code: 종목코드(PDNO), 6자리.
        ord_qty: 주문수량(ORD_QTY).
        ord_dvsn: 주문구분(ORD_DVSN). 00 지정가/01 시장가 등 — 파일 상단 코드표 참고.
        ord_unpr: 주문단가(ORD_UNPR). 시장가 등 가격 미지정 주문은 ""로 넘기면 자동으로 "0" 처리.
        cndt_pric: 조건가격(CNDT_PRIC). 스탑지정가호가(ORD_DVSN=22) 주문 시에만 필요.
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".
        market: 거래소ID구분코드(EXCG_ID_DVSN_CD). KRX/NXT/SOR. 기본값 "KRX".
        sll_type: 매도유형(SLL_TYPE). 01 일반매도/02 임의매매/03 대차매도. 기본값 "01".

    Returns:
        rt_cd/msg_cd/msg1과 주문 결과(output)를 담은 ResponseBody.
    """
    return _place_order("sell", code, ord_qty, ord_dvsn, ord_unpr, cndt_pric, mode, market, sll_type=sll_type)


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = sell_cash(code="005930", ord_qty="1", ord_dvsn="01", ord_unpr="", mode="real")
    print(result)
