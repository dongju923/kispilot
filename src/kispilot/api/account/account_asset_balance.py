# 투자계좌자산현황조회[v1_국내주식-048]
from dataclasses import dataclass, field
from typing import List, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/inquire-account-balance"
# ※ 모의투자 미지원 (실전투자 전용).
# ※ output1은 HTS(eFriend Plus) [0891] 계좌 자산비중(결제기준) 화면 아래 테이블과 동일.
#   자산종류별로 고정된 순서(주식/펀드/채권/... /예수금/합계 등 최대 20개, 21번 계좌는 17개)로 내려온다.
# ※ 응답 헤더에 tr_cont(F/M/D/E)가 있긴 하지만, 다음 페이지 요청에 필요한 CTX_AREA_FK100/NK100 같은
#   연속조회 키 파라미터 자체가 Query Parameter에 없다. output1이 최대 20개로 고정된 목록이라
#   실질적으로 연속조회가 필요 없는 것으로 보고, 페이지네이션 없이 1회 호출로 구현했다.
# ※ INQR_DVSN_1, BSPR_BF_DT_APLY_YN은 문서상 "공란입력"이 고정값이라 파라미터로 노출하지 않는다.

_TR_ID = "CTRP6548R"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    pchs_amt: Optional[str] = None          # 매입금액
    evlu_amt: Optional[str] = None          # 평가금액
    evlu_pfls_amt: Optional[str] = None     # 평가손익금액
    crdt_lnd_amt: Optional[str] = None      # 신용대출금액
    real_nass_amt: Optional[str] = None     # 실제순자산금액
    whol_weit_rt: Optional[str] = None      # 전체비중율


@dataclass
class ResponseBodyOutput2:
    pchs_amt_smtl: Optional[str] = None                     # 매입금액합계(유가매입금액)
    nass_tot_amt: Optional[str] = None                       # 순자산총금액
    loan_amt_smtl: Optional[str] = None                      # 대출금액합계
    evlu_pfls_amt_smtl: Optional[str] = None                 # 평가손익금액합계
    evlu_amt_smtl: Optional[str] = None                      # 평가금액합계(유가평가금액)
    tot_asst_amt: Optional[str] = None                       # 총자산금액
    tot_lnda_tot_ulst_lnda: Optional[str] = None              # 총대출금액총융자대출금액
    cma_auto_loan_amt: Optional[str] = None                   # CMA자동대출금액
    tot_mgln_amt: Optional[str] = None                        # 총담보대출금액
    stln_evlu_amt: Optional[str] = None                       # 대주평가금액
    crdt_fncg_amt: Optional[str] = None                       # 신용융자금액
    ocl_apl_loan_amt: Optional[str] = None                    # OCL_APL대출금액
    pldg_stup_amt: Optional[str] = None                       # 질권설정금액
    frcr_evlu_tota: Optional[str] = None                      # 외화평가총액
    tot_dncl_amt: Optional[str] = None                        # 총예수금액
    cma_evlu_amt: Optional[str] = None                        # CMA평가금액
    dncl_amt: Optional[str] = None                            # 예수금액
    tot_sbst_amt: Optional[str] = None                        # 총대용금액
    thdt_rcvb_amt: Optional[str] = None                       # 당일미수금액
    ovrs_stck_evlu_amt1: Optional[str] = None                 # 해외주식평가금액1
    ovrs_bond_evlu_amt: Optional[str] = None                  # 해외채권평가금액
    mmf_cma_mgge_loan_amt: Optional[str] = None               # MMF·CMA담보대출금액
    sbsc_dncl_amt: Optional[str] = None                       # 청약예수금액
    pbst_sbsc_fnds_loan_use_amt: Optional[str] = None         # 공모주청약자금대출사용금액
    etpr_crdt_grnt_loan_amt: Optional[str] = None             # 기업신용공여대출금액


@dataclass
class ResponseBody:
    rt_cd: str                                                        # 성공 실패 여부
    msg_cd: str                                                       # 응답코드
    msg1: str                                                         # 응답메세지
    output1: List[ResponseBodyOutput1] = field(default_factory=list)  # 자산종류별 현황(배열, 최대 20개)
    output2: ResponseBodyOutput2 = field(default_factory=ResponseBodyOutput2)  # 계좌 자산 요약(단일)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_account_balance() -> ResponseBody:
    """투자계좌 자산현황을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    HTS(eFriend Plus) [0891] 계좌 자산비중(결제기준) 화면과 동일한 데이터.
    output1은 주식/펀드/채권/... /예수금/합계 등 자산종류별 현황이 고정된 순서로 최대 20개
    (21번 계좌는 17개) 내려오고, output2는 계좌 전체의 자산/대출 요약이다.

    Returns:
        rt_cd/msg_cd/msg1과 자산종류별 현황(output1), 계좌 자산 요약(output2)을 담은 ResponseBody.
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
        "INQR_DVSN_1": "",
        "BSPR_BF_DT_APLY_YN": "",
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1/output2 키가 없거나 null일 수 있어 안전 파싱.
    # 문서 표기가 Output1/Output2(대문자)라 실제 JSON 키가 소문자일 가능성을 대비해 둘 다 확인한다.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or raw.get("Output1") or []
    output1 = [ResponseBodyOutput1(**{k: v for k, v in item.items() if k in fields1}) for item in raw_output1]

    fields2 = set(ResponseBodyOutput2.__dataclass_fields__)
    raw_output2 = raw.get("output2") or raw.get("Output2") or {}
    output2 = ResponseBodyOutput2(**{k: v for k, v in raw_output2.items() if k in fields2})

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
        output2=output2,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_account_balance()
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output1:
            print(row)
        print(result.output2)
