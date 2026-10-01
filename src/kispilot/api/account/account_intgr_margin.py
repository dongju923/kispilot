# 주식통합증거금 현황[국내주식-191]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/intgr-margin"
# ※ 모의투자 미지원 (실전투자 전용). 1회 호출에 최대 1건만 조회됨(연속조회 불가, tr_cont 없음).
# ※ HTS(eFriend Plus) [0867] 통합증거금조회 화면과 동일한 데이터 — 일반계좌/통합증거금 신청계좌의
#   국내·해외 주문가능금액을 한 번에 조회하는 용도.
# ※ 해외 국가별 상세 증거금현황은 이 API가 아니라 [해외주식] 해외증거금 통화별조회 API를 쓸 것.

_TR_ID = "TTTC0869R"
_CMA_EVLU_AMT_ICLD_YN = "N"  # 문서 고정값


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    acmga_rt: Optional[str] = None                          # 계좌증거금율
    acmga_pct100_aptm_rson: Optional[str] = None             # 계좌증거금100퍼센트지정사유
    stck_cash_objt_amt: Optional[str] = None                 # 주식현금대상금액
    stck_sbst_objt_amt: Optional[str] = None                 # 주식대용대상금액
    stck_evlu_objt_amt: Optional[str] = None                 # 주식평가대상금액
    stck_ruse_psbl_objt_amt: Optional[str] = None            # 주식재사용가능대상금액
    stck_fund_rpch_chgs_objt_amt: Optional[str] = None       # 주식펀드환매대금대상금액
    stck_fncg_rdpt_objt_atm: Optional[str] = None             # 주식융자상환금대상금액
    bond_ruse_psbl_objt_amt: Optional[str] = None             # 채권재사용가능대상금액
    stck_cash_use_amt: Optional[str] = None                   # 주식현금사용금액
    stck_sbst_use_amt: Optional[str] = None                   # 주식대용사용금액
    stck_evlu_use_amt: Optional[str] = None                   # 주식평가사용금액
    stck_ruse_psbl_amt_use_amt: Optional[str] = None          # 주식재사용가능금사용금액
    stck_fund_rpch_chgs_use_amt: Optional[str] = None         # 주식펀드환매대금사용금액
    stck_fncg_rdpt_amt_use_amt: Optional[str] = None          # 주식융자상환금사용금액
    bond_ruse_psbl_amt_use_amt: Optional[str] = None          # 채권재사용가능금사용금액
    stck_cash_ord_psbl_amt: Optional[str] = None              # 주식현금주문가능금액
    stck_sbst_ord_psbl_amt: Optional[str] = None              # 주식대용주문가능금액
    stck_evlu_ord_psbl_amt: Optional[str] = None              # 주식평가주문가능금액
    stck_ruse_psbl_ord_psbl_amt: Optional[str] = None         # 주식재사용가능주문가능금액
    stck_fund_rpch_ord_psbl_amt: Optional[str] = None         # 주식펀드환매주문가능금액
    bond_ruse_psbl_ord_psbl_amt: Optional[str] = None         # 채권재사용가능주문가능금액
    rcvb_amt: Optional[str] = None                            # 미수금액
    stck_loan_grta_ruse_psbl_amt: Optional[str] = None        # 주식대출보증금재사용가능금액
    stck_cash20_max_ord_psbl_amt: Optional[str] = None        # 주식현금20최대주문가능금액
    stck_cash30_max_ord_psbl_amt: Optional[str] = None        # 주식현금30최대주문가능금액
    stck_cash40_max_ord_psbl_amt: Optional[str] = None        # 주식현금40최대주문가능금액
    stck_cash50_max_ord_psbl_amt: Optional[str] = None        # 주식현금50최대주문가능금액
    stck_cash60_max_ord_psbl_amt: Optional[str] = None        # 주식현금60최대주문가능금액
    stck_cash100_max_ord_psbl_amt: Optional[str] = None       # 주식현금100최대주문가능금액
    stck_rsip100_max_ord_psbl_amt: Optional[str] = None       # 주식재사용불가100최대주문가능
    bond_max_ord_psbl_amt: Optional[str] = None                # 채권최대주문가능금액
    stck_fncg45_max_ord_psbl_amt: Optional[str] = None         # 주식융자45최대주문가능금액
    stck_fncg50_max_ord_psbl_amt: Optional[str] = None         # 주식융자50최대주문가능금액
    stck_fncg60_max_ord_psbl_amt: Optional[str] = None         # 주식융자60최대주문가능금액
    stck_fncg70_max_ord_psbl_amt: Optional[str] = None         # 주식융자70최대주문가능금액
    stck_stln_max_ord_psbl_amt: Optional[str] = None           # 주식대주최대주문가능금액
    lmt_amt: Optional[str] = None                              # 한도금액
    ovrs_stck_itgr_mgna_dvsn_name: Optional[str] = None        # 해외주식통합증거금구분명
    usd_objt_amt: Optional[str] = None                         # 미화대상금액
    usd_use_amt: Optional[str] = None                          # 미화사용금액
    usd_ord_psbl_amt: Optional[str] = None                     # 미화주문가능금액
    hkd_objt_amt: Optional[str] = None                         # 홍콩달러대상금액
    hkd_use_amt: Optional[str] = None                          # 홍콩달러사용금액
    hkd_ord_psbl_amt: Optional[str] = None                     # 홍콩달러주문가능금액
    jpy_objt_amt: Optional[str] = None                         # 엔화대상금액
    jpy_use_amt: Optional[str] = None                          # 엔화사용금액
    jpy_ord_psbl_amt: Optional[str] = None                     # 엔화주문가능금액
    cny_objt_amt: Optional[str] = None                         # 위안화대상금액
    cny_use_amt: Optional[str] = None                          # 위안화사용금액
    cny_ord_psbl_amt: Optional[str] = None                     # 위안화주문가능금액
    usd_ruse_objt_amt: Optional[str] = None                    # 미화재사용대상금액
    usd_ruse_amt: Optional[str] = None                         # 미화재사용금액
    usd_ruse_ord_psbl_amt: Optional[str] = None                # 미화재사용주문가능금액
    hkd_ruse_objt_amt: Optional[str] = None                    # 홍콩달러재사용대상금액
    hkd_ruse_amt: Optional[str] = None                         # 홍콩달러재사용금액
    hkd_ruse_ord_psbl_amt: Optional[str] = None                # 홍콩달러재사용주문가능금액
    jpy_ruse_objt_amt: Optional[str] = None                    # 엔화재사용대상금액
    jpy_ruse_amt: Optional[str] = None                         # 엔화재사용금액
    jpy_ruse_ord_psbl_amt: Optional[str] = None                # 엔화재사용주문가능금액
    cny_ruse_objt_amt: Optional[str] = None                    # 위안화재사용대상금액
    cny_ruse_amt: Optional[str] = None                         # 위안화재사용금액
    cny_ruse_ord_psbl_amt: Optional[str] = None                # 위안화재사용주문가능금액
    usd_gnrl_ord_psbl_amt: Optional[str] = None                # 미화일반주문가능금액
    usd_itgr_ord_psbl_amt: Optional[str] = None                # 미화통합주문가능금액
    hkd_gnrl_ord_psbl_amt: Optional[str] = None                # 홍콩달러일반주문가능금액
    hkd_itgr_ord_psbl_amt: Optional[str] = None                # 홍콩달러통합주문가능금액
    jpy_gnrl_ord_psbl_amt: Optional[str] = None                # 엔화일반주문가능금액
    jpy_itgr_ord_psbl_amt: Optional[str] = None                # 엔화통합주문가능금액
    cny_gnrl_ord_psbl_amt: Optional[str] = None                # 위안화일반주문가능금액
    cny_itgr_ord_psbl_amt: Optional[str] = None                # 위안화통합주문가능금액
    stck_itgr_cash20_ord_psbl_amt: Optional[str] = None        # 주식통합현금20주문가능금액
    stck_itgr_cash30_ord_psbl_amt: Optional[str] = None        # 주식통합현금30주문가능금액
    stck_itgr_cash40_ord_psbl_amt: Optional[str] = None        # 주식통합현금40주문가능금액
    stck_itgr_cash50_ord_psbl_amt: Optional[str] = None        # 주식통합현금50주문가능금액
    stck_itgr_cash60_ord_psbl_amt: Optional[str] = None        # 주식통합현금60주문가능금액
    stck_itgr_cash100_ord_psbl_amt: Optional[str] = None       # 주식통합현금100주문가능금액
    stck_itgr_100_ord_psbl_amt: Optional[str] = None           # 주식통합100주문가능금액
    stck_itgr_fncg45_ord_psbl_amt: Optional[str] = None        # 주식통합융자45주문가능금액
    stck_itgr_fncg50_ord_psbl_amt: Optional[str] = None        # 주식통합융자50주문가능금액
    stck_itgr_fncg60_ord_psbl_amt: Optional[str] = None        # 주식통합융자60주문가능금액
    stck_itgr_fncg70_ord_psbl_amt: Optional[str] = None        # 주식통합융자70주문가능금액
    stck_itgr_stln_ord_psbl_amt: Optional[str] = None          # 주식통합대주주문가능금액
    bond_itgr_ord_psbl_amt: Optional[str] = None               # 채권통합주문가능금액
    stck_cash_ovrs_use_amt: Optional[str] = None               # 주식현금해외사용금액
    stck_sbst_ovrs_use_amt: Optional[str] = None               # 주식대용해외사용금액
    stck_evlu_ovrs_use_amt: Optional[str] = None               # 주식평가해외사용금액
    stck_re_use_amt_ovrs_use_amt: Optional[str] = None         # 주식재사용금액해외사용금액
    stck_fund_rpch_ovrs_use_amt: Optional[str] = None          # 주식펀드환매해외사용금액
    stck_fncg_rdpt_ovrs_use_amt: Optional[str] = None          # 주식융자상환해외사용금액
    bond_re_use_ovrs_use_amt: Optional[str] = None             # 채권재사용해외사용금액
    usd_oth_mket_use_amt: Optional[str] = None                 # 미화타시장사용금액
    jpy_oth_mket_use_amt: Optional[str] = None                 # 엔화타시장사용금액
    cny_oth_mket_use_amt: Optional[str] = None                 # 위안화타시장사용금액
    hkd_oth_mket_use_amt: Optional[str] = None                 # 홍콩달러타시장사용금액
    usd_re_use_oth_mket_use_amt: Optional[str] = None          # 미화재사용타시장사용금액
    jpy_re_use_oth_mket_use_amt: Optional[str] = None          # 엔화재사용타시장사용금액
    cny_re_use_oth_mket_use_amt: Optional[str] = None          # 위안화재사용타시장사용금액
    hkd_re_use_oth_mket_use_amt: Optional[str] = None          # 홍콩달러재사용타시장사용금액
    hgkg_cny_re_use_amt: Optional[str] = None                  # 홍콩위안화재사용금액
    usd_frst_bltn_exrt: Optional[str] = None                   # 미국달러최초고시환율
    hkd_frst_bltn_exrt: Optional[str] = None                   # 홍콩달러최초고시환율
    jpy_frst_bltn_exrt: Optional[str] = None                   # 일본엔화최초고시환율
    cny_frst_bltn_exrt: Optional[str] = None                   # 중국위안화최초고시환율


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output: ResponseBodyOutput          # 통합증거금 현황(단일)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_intgr_margin(
    wcrc_frcr_dvsn_cd: Literal["01", "02"] = "02",
    fwex_ctrt_frcr_dvsn_cd: Literal["01", "02"] = "02",
) -> ResponseBody:
    """주식통합증거금 현황을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    일반계좌/통합증거금 신청계좌의 국내·해외 주문가능금액을 한 번에 확인한다.
    해외 국가별 상세 증거금현황은 [해외주식] 해외증거금 통화별조회 API를 쓸 것.

    Args:
        wcrc_frcr_dvsn_cd: 원화외화구분코드(WCRC_FRCR_DVSN_CD). "01" 외화기준 / "02" 원화기준. 기본값 "02".
        fwex_ctrt_frcr_dvsn_cd: 선도환계약외화구분코드(FWEX_CTRT_FRCR_DVSN_CD). "01" 외화기준 / "02" 원화기준.
            기본값 "02".

    Returns:
        rt_cd/msg_cd/msg1과 통합증거금 현황(output)을 담은 ResponseBody.
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
        "CMA_EVLU_AMT_ICLD_YN": _CMA_EVLU_AMT_ICLD_YN,
        "WCRC_FRCR_DVSN_CD": wcrc_frcr_dvsn_cd,
        "FWEX_CTRT_FRCR_DVSN_CD": fwex_ctrt_frcr_dvsn_cd,
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
    result = inquire_intgr_margin()
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output)
