# 주식잔고조회_실현손익[v1_국내주식-041]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/inquire-balance-rlz-pl"
# ※ 모의투자 미지원 (실전투자 전용).
# ※ order_inquire_balance.py(주식잔고조회)와 거의 같지만, output2에 실현손익 관련 필드
#   (rlzt_pfls/rlzt_erng_rt/real_evlu_pfls/real_evlu_pfls_erng_rt)가 추가된 버전이다.
# ※ CTX_AREA_FK100/NK100 쿼리 파라미터는 있지만, 응답 헤더 설명상 tr_cont로 다음 페이지를 이어받는
#   연속조회는 지원하지 않는 API라서(항상 공란으로 보냄) 페이지네이션 없이 1회 호출로 끝난다.
#   (요청 헤더 표에는 F/M/D/E 설명이 있지만, 응답 헤더 표는 "다음조회 불가 API"라고 명시돼 있어 후자를 따름.)

_TR_ID = "TTTC8494R"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    pdno: Optional[str] = None                    # 상품번호(종목번호 뒤 6자리)
    prdt_name: Optional[str] = None                # 상품명(종목명)
    trad_dvsn_name: Optional[str] = None            # 매매구분명(매수/매도구분)
    bfdy_buy_qty: Optional[str] = None              # 전일매수수량
    bfdy_sll_qty: Optional[str] = None              # 전일매도수량
    thdt_buyqty: Optional[str] = None               # 금일매수수량
    thdt_sll_qty: Optional[str] = None              # 금일매도수량
    hldg_qty: Optional[str] = None                  # 보유수량
    ord_psbl_qty: Optional[str] = None              # 주문가능수량
    pchs_avg_pric: Optional[str] = None             # 매입평균가격(매입금액/보유수량)
    pchs_amt: Optional[str] = None                  # 매입금액
    prpr: Optional[str] = None                      # 현재가
    evlu_amt: Optional[str] = None                  # 평가금액
    evlu_pfls_amt: Optional[str] = None             # 평가손익금액(평가금액-매입금액)
    evlu_pfls_rt: Optional[str] = None              # 평가손익율
    evlu_erng_rt: Optional[str] = None              # 평가수익율
    loan_dt: Optional[str] = None                   # 대출일자
    loan_amt: Optional[str] = None                  # 대출금액
    stln_slng_chgs: Optional[str] = None            # 대주매각대금(신용거래 시 대부받은 주식의 매각대금)
    expd_dt: Optional[str] = None                   # 만기일자
    stck_loan_unpr: Optional[str] = None            # 주식대출단가
    bfdy_cprs_icdc: Optional[str] = None            # 전일대비증감
    fltt_rt: Optional[str] = None                   # 등락율


@dataclass
class ResponseBodyOutput2:
    dnca_tot_amt: Optional[str] = None              # 예수금총금액
    nxdy_excc_amt: Optional[str] = None             # 익일정산금액(D+1 예수금)
    prvs_rcdl_excc_amt: Optional[str] = None        # 가수도정산금액(D+2 예수금)
    cma_evlu_amt: Optional[str] = None               # CMA평가금액
    bfdy_buy_amt: Optional[str] = None               # 전일매수금액
    thdt_buy_amt: Optional[str] = None               # 금일매수금액
    nxdy_auto_rdpt_amt: Optional[str] = None         # 익일자동상환금액
    bfdy_sll_amt: Optional[str] = None               # 전일매도금액
    thdt_sll_amt: Optional[str] = None               # 금일매도금액
    d2_auto_rdpt_amt: Optional[str] = None           # D+2자동상환금액
    bfdy_tlex_amt: Optional[str] = None              # 전일제비용금액
    thdt_tlex_amt: Optional[str] = None              # 금일제비용금액
    tot_loan_amt: Optional[str] = None               # 총대출금액
    scts_evlu_amt: Optional[str] = None              # 유가평가금액
    tot_evlu_amt: Optional[str] = None               # 총평가금액
    nass_amt: Optional[str] = None                   # 순자산금액
    fncg_gld_auto_rdpt_yn: Optional[str] = None      # 융자금자동상환여부
    pchs_amt_smtl_amt: Optional[str] = None          # 매입금액합계금액
    evlu_amt_smtl_amt: Optional[str] = None          # 평가금액합계금액
    evlu_pfls_smtl_amt: Optional[str] = None         # 평가손익합계금액
    tot_stln_slng_chgs: Optional[str] = None         # 총대주매각대금
    bfdy_tot_asst_evlu_amt: Optional[str] = None     # 전일총자산평가금액
    asst_icdc_amt: Optional[str] = None              # 자산증감액
    asst_icdc_erng_rt: Optional[str] = None          # 자산증감수익율
    rlzt_pfls: Optional[str] = None                  # 실현손익
    rlzt_erng_rt: Optional[str] = None               # 실현수익율
    real_evlu_pfls: Optional[str] = None             # 실평가손익
    real_evlu_pfls_erng_rt: Optional[str] = None     # 실평가손익수익율


@dataclass
class ResponseBody:
    rt_cd: str                                                        # 성공 실패 여부
    msg_cd: str                                                       # 응답코드
    msg1: str                                                         # 응답메세지
    output1: List[ResponseBodyOutput1] = field(default_factory=list)  # 보유종목 목록(배열)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)  # 계좌 요약 + 실현손익(배열, 보통 원소 1개)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_balance_rlz_pl(
    afhr_flpr_yn: Literal["N", "X", "Y"] = "N",
    inqr_dvsn: Literal["00"] = "00",
    fund_sttl_icld_yn: Literal["N", "Y"] = "N",
    prcs_dvsn: Literal["00", "01"] = "00",
    cost_icld_yn: Literal["Y", "N"] = "N",
) -> ResponseBody:
    """주식잔고(실현손익 포함)를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0800] 국내 체결기준잔고 화면과 동일한 데이터.
    order_inquire_balance.py와 달리 output2에 실현손익(rlzt_pfls 등) 필드가 있다.

    Args:
        afhr_flpr_yn: 시장 구분(AFHR_FLPR_YN). N KRX정규장종가 / X NXT / Y KRX+NXT 통합시세. 기본값 "N".
        inqr_dvsn: 조회구분(INQR_DVSN). 00 전체(문서상 유일한 값).
        fund_sttl_icld_yn: 펀드결제포함여부(FUND_STTL_ICLD_YN). N 포함하지 않음 / Y 포함. 기본값 "N".
        prcs_dvsn: 처리구분(PRCS_DVSN). 00 전일매매포함 / 01 전일매매미포함. 기본값 "00".
        cost_icld_yn: 비용포함여부(COST_ICLD_YN). Y 포함 / N 미포함. 기본값 "N".

    Returns:
        rt_cd/msg_cd/msg1과 보유종목 목록(output1), 계좌 요약+실현손익(output2)을 담은 ResponseBody.
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
        "AFHR_FLPR_YN": afhr_flpr_yn,
        "OFL_YN": "",
        "INQR_DVSN": inqr_dvsn,
        "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": fund_sttl_icld_yn,
        "FNCG_AMT_AUTO_RDPT_YN": "N",
        "PRCS_DVSN": prcs_dvsn,
        "COST_ICLD_YN": cost_icld_yn,
        "CTX_AREA_FK100": "",
        "CTX_AREA_NK100": "",
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1/output2 키가 없거나 null일 수 있어 안전 파싱.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or []
    output1 = [ResponseBodyOutput1(**{k: v for k, v in item.items() if k in fields1}) for item in raw_output1]

    fields2 = set(ResponseBodyOutput2.__dataclass_fields__)
    raw_output2 = raw.get("output2") or []
    output2 = [ResponseBodyOutput2(**{k: v for k, v in item.items() if k in fields2}) for item in raw_output2]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
        output2=output2,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_balance_rlz_pl()
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output1:
            print(row)
        for row in result.output2:
            print(row)
