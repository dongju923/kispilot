# 주식주문(정정취소)[v1_국내주식-003]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import (
    DOMAIN,
    CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET,
    PAPER_CANO, PAPER_ACNT_PRDT_CD, PAPER_APPKEY, PAPER_APP_SECRET,
)
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/order-rvsecncl"

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

# RVSE_CNCL_DVSN_CD(정정취소구분코드): 01 정정 / 02 취소
# ※ 이 API 호출 전에 반드시 "주식정정취소가능주문조회"로 정정취소가능수량(output > psbl_qty)을 먼저 확인해야 함.
# ※ 이미 체결된 주문은 정정/취소 불가.

_TR_ID = {"real": "TTTC0013U", "paper": "VTTC0013U"}


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    krx_fwdg_ord_orgno: Optional[str] = None   # 한국거래소전송주문조직번호
    odno: Optional[str] = None                 # 주문번호
    ord_tmd: Optional[str] = None               # 주문시각


@dataclass
class ResponseBody:
    rt_cd: str                                              # 성공 실패 여부
    msg_cd: str                                             # 응답코드
    msg1: str                                               # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 주문 결과 데이터(배열)


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
    rvse_cncl_dvsn_cd: Literal["01", "02"],
    krx_fwdg_ord_orgno: str,
    orgn_odno: str,
    ord_dvsn: str,
    ord_qty: str,
    ord_unpr: str,
    qty_all_ord_yn: Literal["Y", "N"],
    cndt_pric: str,
    mode: Literal["real", "paper"],
    market: Literal["KRX", "NXT", "SOR"],
) -> ResponseBody:
    """주문 정정/취소 공통 처리.

    Args:
        rvse_cncl_dvsn_cd: 정정취소구분코드(RVSE_CNCL_DVSN_CD). 01 정정 / 02 취소.
        krx_fwdg_ord_orgno: 한국거래소전송주문조직번호(KRX_FWDG_ORD_ORGNO). 원주문 응답의 output 값 그대로.
        orgn_odno: 원주문번호(ORGN_ODNO). 정정/취소할 원주문의 odno.
        ord_dvsn: 주문구분(ORD_DVSN). 00 지정가/01 시장가 등 — 파일 상단 코드표 참고.
        ord_qty: 주문수량(ORD_QTY). 정정 시 새 수량, 취소 시 취소 수량.
        ord_unpr: 주문단가(ORD_UNPR). 시장가 등 가격 미지정 주문은 빈 문자열이면 자동으로 "0" 처리.
        qty_all_ord_yn: 잔량전부주문여부(QTY_ALL_ORD_YN). "Y" 잔량 전부 / "N" 일부만.
        cndt_pric: 조건가격(CNDT_PRIC). 스탑지정가호가에서만 사용.
        mode: "real"(실전투자) 또는 "paper"(모의투자).
        market: 거래소ID구분코드(EXCG_ID_DVSN_CD). KRX/NXT/SOR.

    Returns:
        rt_cd/msg_cd/msg1과 주문 결과 배열(output)을 담은 ResponseBody.
    """
    ord_unpr = ord_unpr or "0"  # 시장가 등 가격 미지정 주문은 빈 문자열이 아니라 "0"으로 보내야 함

    token = load_token(mode)
    cano, acnt_prdt_cd, app_key, app_secret, domain = _get_account(mode)
    tr_id = _TR_ID[mode]

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
            "KRX_FWDG_ORD_ORGNO": krx_fwdg_ord_orgno,
            "ORGN_ODNO": orgn_odno,
            "ORD_DVSN": ord_dvsn,
            "RVSE_CNCL_DVSN_CD": rvse_cncl_dvsn_cd,
            "ORD_QTY": ord_qty,
            "ORD_UNPR": ord_unpr,
            "QTY_ALL_ORD_YN": qty_all_ord_yn,
            "CNDT_PRIC": cndt_pric,
            "EXCG_ID_DVSN_CD": market,
        },
        timeout=10,
    )
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
        msg1=raw.get("msg1", ""),
        output=outputs,
    )


def revise_order(
    krx_fwdg_ord_orgno, orgn_odno, ord_dvsn, ord_qty, ord_unpr,
    qty_all_ord_yn: Literal["Y", "N"] = "N",
    cndt_pric="",
    mode: Literal["real", "paper"] = "real",
    market: Literal["KRX", "NXT", "SOR"] = "KRX",
) -> ResponseBody:
    """주문 정정: 원주문의 주문단가/주문구분을 변경. 정정 가능 수량은 원주문수량을 초과할 수 없음.

    Args:
        krx_fwdg_ord_orgno: 한국거래소전송주문조직번호(KRX_FWDG_ORD_ORGNO). 원주문 응답의 output 값 그대로.
        orgn_odno: 원주문번호(ORGN_ODNO). 정정할 원주문의 odno.
        ord_dvsn: 주문구분(ORD_DVSN). 바꿀 주문구분. 00 지정가/01 시장가 등 — 파일 상단 코드표 참고.
        ord_qty: 주문수량(ORD_QTY). 정정 후 수량.
        ord_unpr: 주문단가(ORD_UNPR). 정정 후 가격. 시장가 등은 ""로 넘기면 자동으로 "0" 처리.
        qty_all_ord_yn: 잔량전부주문여부(QTY_ALL_ORD_YN). "Y" 잔량 전부 / "N" 일부만. 기본값 "N".
        cndt_pric: 조건가격(CNDT_PRIC). 스탑지정가호가에서만 사용.
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".
        market: 거래소ID구분코드(EXCG_ID_DVSN_CD). KRX/NXT/SOR. 기본값 "KRX".

    Returns:
        rt_cd/msg_cd/msg1과 주문 결과 배열(output)을 담은 ResponseBody.
    """
    return _place_order("01", krx_fwdg_ord_orgno, orgn_odno, ord_dvsn, ord_qty, ord_unpr, qty_all_ord_yn, cndt_pric, mode, market)


def cancel_order(
    krx_fwdg_ord_orgno, orgn_odno, ord_dvsn, ord_qty, ord_unpr="0",
    qty_all_ord_yn: Literal["Y", "N"] = "Y",
    cndt_pric="",
    mode: Literal["real", "paper"] = "real",
    market: Literal["KRX", "NXT", "SOR"] = "KRX",
) -> ResponseBody:
    """주문 취소. qty_all_ord_yn="Y"(기본값)면 잔량 전부 취소.

    Args:
        krx_fwdg_ord_orgno: 한국거래소전송주문조직번호(KRX_FWDG_ORD_ORGNO). 원주문 응답의 output 값 그대로.
        orgn_odno: 원주문번호(ORGN_ODNO). 취소할 원주문의 odno.
        ord_dvsn: 주문구분(ORD_DVSN). 원주문의 주문구분 — 파일 상단 코드표 참고.
        ord_qty: 주문수량(ORD_QTY). 취소할 수량(잔량 전부 취소면 원주문 잔량과 동일하게).
        ord_unpr: 주문단가(ORD_UNPR). 취소이므로 의미 없음 — 기본값 "0".
        qty_all_ord_yn: 잔량전부주문여부(QTY_ALL_ORD_YN). "Y" 잔량 전부 / "N" 일부만. 기본값 "Y".
        cndt_pric: 조건가격(CNDT_PRIC). 스탑지정가호가에서만 사용.
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".
        market: 거래소ID구분코드(EXCG_ID_DVSN_CD). KRX/NXT/SOR. 기본값 "KRX".

    Returns:
        rt_cd/msg_cd/msg1과 주문 결과 배열(output)을 담은 ResponseBody.
    """
    return _place_order("02", krx_fwdg_ord_orgno, orgn_odno, ord_dvsn, ord_qty, ord_unpr, qty_all_ord_yn, cndt_pric, mode, market)


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = cancel_order(
        krx_fwdg_ord_orgno="00000",
        orgn_odno="0000000000",
        ord_dvsn="00",
        ord_qty="1",
        mode="paper",
    )
    print(result)
