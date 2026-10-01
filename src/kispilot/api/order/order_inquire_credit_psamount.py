# 신용매수가능조회[v1_국내주식-042]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/inquire-credit-psamount"
# ※ 모의투자 미지원 (실전투자 전용). 1회 호출에 최대 1건만 조회됨(연속조회 불가, tr_cont 없음).
# ※ 미수 미사용 시 output.nrcvb_buy_amt/nrcvb_buy_qty, 미수 사용 시 output.max_buy_amt/max_buy_qty 확인.

_TR_ID = "TTTC8909R"

# CRDT_TYPE(신용유형) 코드표 — order_credit.py 상단 코드표와 동일
#   [매도] 22 유통대주신규   24 자기대주신규   25 자기융자상환   27 유통융자상환
#   [매수] 21 자기융자신규   23 유통융자신규   26 유통대주상환   28 자기대주상환


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    ord_psbl_cash: Optional[str] = None            # 주문가능현금
    ord_psbl_sbst: Optional[str] = None            # 주문가능대용
    ruse_psbl_amt: Optional[str] = None            # 재사용가능금액
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
    output: ResponseBodyOutput          # 신용매수가능 조회 결과(단일)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_credit_psamount(
    pdno: str,
    ord_unpr: str,
    ord_dvsn: str,
    crdt_type: Literal["21", "22", "23", "24", "25", "26", "27", "28"],
    cma_evlu_amt_icld_yn: Literal["Y", "N"] = "N",
    ovrs_icld_yn: Literal["Y", "N"] = "N",
) -> ResponseBody:
    """신용매수 가능 금액/수량을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    Args:
        pdno: 종목코드(PDNO), 6자리.
        ord_unpr: 주문단가(ORD_UNPR). 시장가/장전·장후 시간외 등은 공란 대신 "0" 입력 권장
            (빈 문자열로 넘기면 자동으로 "0" 처리).
        ord_dvsn: 주문구분(ORD_DVSN). 00 지정가/01 시장가/02 조건부지정가/03 최유리지정가/
            04 최우선지정가/05 장전 시간외/06 장후 시간외/07 시간외 단일가 등.
        crdt_type: 신용유형(CRDT_TYPE). 파일 상단 코드표 참고 (21/23/26/28 매수측, 22/24/25/27 매도측).
        cma_evlu_amt_icld_yn: CMA평가금액포함여부. Y 포함/N 미포함. 기본값 "N".
        ovrs_icld_yn: 해외포함여부. Y 포함/N 미포함. 기본값 "N".

    Returns:
        rt_cd/msg_cd/msg1과 신용매수가능 조회 결과(output)를 담은 ResponseBody.
        미수 미사용 시 output.nrcvb_buy_amt/nrcvb_buy_qty, 미수 사용 시 output.max_buy_amt/max_buy_qty를 본다.
    """
    ord_unpr = ord_unpr or "0"

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
        "ORD_UNPR": ord_unpr,
        "ORD_DVSN": ord_dvsn,
        "CRDT_TYPE": crdt_type,
        "CMA_EVLU_AMT_ICLD_YN": cma_evlu_amt_icld_yn,
        "OVRS_ICLD_YN": ovrs_icld_yn,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
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
    result = inquire_credit_psamount(pdno="005930", ord_unpr="", ord_dvsn="01", crdt_type="23")
    print(result)
