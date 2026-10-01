# 매수가능조회[v1_국내주식-007]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import (
    DOMAIN,
    CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET,
    PAPER_CANO, PAPER_ACNT_PRDT_CD, PAPER_APPKEY, PAPER_APP_SECRET,
)
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/inquire-psbl-order"
# ※ 1회 호출에 최대 1건만 조회됨(연속조회 불가, tr_cont 없음).
# ※ 매수가능금액: 미수 미사용 시 output.nrcvb_buy_amt(미수없는매수금액), 미수 사용 시 output.max_buy_amt(최대매수금액).
# ※ 매수가능수량: 특정 종목 전량매수 가능수량 확인 시 반드시 ORD_DVSN을 01(시장가)로 지정해야 증거금율이 반영됨
#   (00 지정가는 증거금율 미반영). 조건부지정가/IOC 등으로 주문할 계획이면 그 주문구분을 그대로 입력해서 조회.
#   - 미수 미사용: output.nrcvb_buy_qty(미수없는매수수량)
#   - 미수 사용: output.max_buy_qty(최대매수수량)
# ※ PDNO/ORD_UNPR을 공란으로 입력하면 매수수량 없이 매수금액만 조회됨.

_TR_ID = {"real": "TTTC8908R", "paper": "VTTC8908R"}


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    ord_psbl_cash: Optional[str] = None            # 주문가능현금(예수금으로 계산된 주문가능금액)
    ord_psbl_sbst: Optional[str] = None            # 주문가능대용
    ruse_psbl_amt: Optional[str] = None            # 재사용가능금액(전일/금일 매도대금으로 계산된 주문가능금액)
    fund_rpch_chgs: Optional[str] = None           # 펀드환매대금
    psbl_qty_calc_unpr: Optional[str] = None       # 가능수량계산단가
    nrcvb_buy_amt: Optional[str] = None            # 미수없는매수금액 (미수 미사용 시 확인)
    nrcvb_buy_qty: Optional[str] = None            # 미수없는매수수량 (미수 미사용 시 확인)
    max_buy_amt: Optional[str] = None              # 최대매수금액 (미수 사용 시 확인)
    max_buy_qty: Optional[str] = None              # 최대매수수량 (미수 사용 시 확인)
    cma_evlu_amt: Optional[str] = None             # CMA평가금액
    ovrs_re_use_amt_wcrc: Optional[str] = None     # 해외재사용금액원화
    ord_psbl_frcr_amt_wcrc: Optional[str] = None   # 주문가능외화금액원화


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output: ResponseBodyOutput          # 매수가능 조회 결과(단일)


# ── 요청 함수 ───────────────────────────────────────────────

def _get_account(mode: Literal["real", "paper"]) -> tuple[str, str, str, str, str]:
    """모드에 맞는 계좌번호, 상품코드, 앱키, 앱시크릿, 도메인을 반환한다."""
    if mode == "real":
        return CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET, DOMAIN["real"]
    return PAPER_CANO, PAPER_ACNT_PRDT_CD, PAPER_APPKEY, PAPER_APP_SECRET, DOMAIN["paper"]


def inquire_psbl_order(
    pdno: str = "",
    ord_unpr: str = "",
    ord_dvsn: str = "01",
    cma_evlu_amt_icld_yn: Literal["Y", "N"] = "N",
    ovrs_icld_yn: Literal["Y", "N"] = "N",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """매수 가능 금액/수량을 조회한다.

    Args:
        pdno: 종목코드(PDNO), 6자리. ""로 두면(ORD_UNPR도 "") 매수수량 없이 매수금액만 조회됨.
        ord_unpr: 주문단가(ORD_UNPR). 시장가(ord_dvsn="01")로 조회할 때는 ""로 둔다.
        ord_dvsn: 주문구분(ORD_DVSN). 특정 종목 전량매수 가능수량을 확인하려면 반드시 "01"(시장가)을
            써야 증거금율이 반영된다("00" 지정가는 반영 안 됨). 조건부지정가/IOC 등으로 주문할 계획이면
            그 주문구분을 그대로 입력. 종목별 수량 조회 없이 금액만 조회할 거면 임의값 "00"도 무방.
        cma_evlu_amt_icld_yn: CMA평가금액포함여부(CMA_EVLU_AMT_ICLD_YN). Y 포함/N 미포함. 기본값 "N".
        ovrs_icld_yn: 해외포함여부(OVRS_ICLD_YN). Y 포함/N 미포함. 기본값 "N".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 매수가능 조회 결과(output)를 담은 ResponseBody.
        미수 미사용 시 output.nrcvb_buy_amt/nrcvb_buy_qty, 미수 사용 시 output.max_buy_amt/max_buy_qty를 본다.
    """
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
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "PDNO": pdno,
        "ORD_UNPR": ord_unpr,
        "ORD_DVSN": ord_dvsn,
        "CMA_EVLU_AMT_ICLD_YN": cma_evlu_amt_icld_yn,
        "OVRS_ICLD_YN": ovrs_icld_yn,
    }
    response = get_session().get(domain + URL, headers=headers, params=params, timeout=10)
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


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_psbl_order(pdno="005930", ord_dvsn="01", mode="paper")
    print(result)
