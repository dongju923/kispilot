# 주식잔고조회[v1_국내주식-006]
import time
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import (
    DOMAIN,
    CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET,
    PAPER_CANO, PAPER_ACNT_PRDT_CD, PAPER_APPKEY, PAPER_APP_SECRET,
)
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/inquire-balance"
# ※ 실전: 1회 최대 50건 / 모의: 1회 최대 20건. 그 이상은 연속조회(tr_cont)로 이어받는다.
# ※ 제공 정보량이 많아 조회속도가 느린 API. 주문 준비용이면 "매수/매도가능수량 조회" TR을 권장.
# ※ 초당 120 TPS 제한(원장 유량정책, 전체 고객 합산)과 별개로 개인별 초당 호출 한도도 있다.
#   둘 다 "초당 거래건수 초과"로 뜨는 rate-limit 상황이라 잠깐 쉬었다가 재시도하면 되는 건 같지만,
#   구분 방법이 다르다: 원장 초과는 msg_cd(EGW00215)로 판별되고, 개인 유량 초과는 KIS 문서에
#   msg_cd가 안 나와 있어 msg1에 "원장" 없이 "초당 거래건수를 초과하였습니다."만 있는 경우로 판별한다.
#   → _is_rate_limited() / _fetch_page 참고.

_RATE_LIMIT_MSG_CD = "EGW00215"                        # 원장(전체 고객 합산) 유량 초과
_PERSONAL_RATE_LIMIT_TEXT = "초당 거래건수를 초과하였습니다"   # 개인 유량 초과 (msg_cd 미문서화, msg1 텍스트로 판별)
_MAX_RETRIES = 3
_RETRY_DELAY_SEC = 0.5

_TR_ID = {"real": "TTTC8434R", "paper": "VTTC8434R"}


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
    evlu_erng_rt: Optional[str] = None              # 평가수익율 (미사용항목, 0으로 출력)
    loan_dt: Optional[str] = None                   # 대출일자(INQR_DVSN=01 대출일별일 때만 값 존재)
    loan_amt: Optional[str] = None                  # 대출금액
    stln_slng_chgs: Optional[str] = None            # 대주매각대금
    expd_dt: Optional[str] = None                   # 만기일자
    fltt_rt: Optional[str] = None                   # 등락율
    bfdy_cprs_icdc: Optional[str] = None            # 전일대비증감
    item_mgna_rt_name: Optional[str] = None         # 종목증거금율명
    grta_rt_name: Optional[str] = None              # 보증금율명
    sbst_pric: Optional[str] = None                 # 대용가격(위탁보증금 대용 유가증권 가격)
    stck_loan_unpr: Optional[str] = None            # 주식대출단가


@dataclass
class ResponseBodyOutput2:
    dnca_tot_amt: Optional[str] = None              # 예수금총금액
    nxdy_excc_amt: Optional[str] = None             # 익일정산금액(D+1 예수금)
    prvs_rcdl_excc_amt: Optional[str] = None        # 가수도정산금액(D+2 예수금)
    cma_evlu_amt: Optional[str] = None              # CMA평가금액
    bfdy_buy_amt: Optional[str] = None              # 전일매수금액
    thdt_buy_amt: Optional[str] = None              # 금일매수금액
    nxdy_auto_rdpt_amt: Optional[str] = None        # 익일자동상환금액
    bfdy_sll_amt: Optional[str] = None              # 전일매도금액
    thdt_sll_amt: Optional[str] = None              # 금일매도금액
    d2_auto_rdpt_amt: Optional[str] = None          # D+2자동상환금액
    bfdy_tlex_amt: Optional[str] = None             # 전일제비용금액
    thdt_tlex_amt: Optional[str] = None             # 금일제비용금액
    tot_loan_amt: Optional[str] = None              # 총대출금액
    scts_evlu_amt: Optional[str] = None             # 유가평가금액
    tot_evlu_amt: Optional[str] = None              # 총평가금액(유가증권 평가금액 합계 + D+2 예수금)
    nass_amt: Optional[str] = None                  # 순자산금액
    fncg_gld_auto_rdpt_yn: Optional[str] = None     # 융자금자동상환여부(보유현금에 대한 융자금만 차감 여부)
    pchs_amt_smtl_amt: Optional[str] = None         # 매입금액합계금액
    evlu_amt_smtl_amt: Optional[str] = None         # 평가금액합계금액(유가증권 평가금액 합계)
    evlu_pfls_smtl_amt: Optional[str] = None        # 평가손익합계금액
    tot_stln_slng_chgs: Optional[str] = None        # 총대주매각대금
    bfdy_tot_asst_evlu_amt: Optional[str] = None    # 전일총자산평가금액
    asst_icdc_amt: Optional[str] = None             # 자산증감액
    asst_icdc_erng_rt: Optional[str] = None         # 자산증감수익율 (데이터 미제공)


@dataclass
class ResponseBody:
    rt_cd: str                                                        # 성공 실패 여부
    msg_cd: str                                                       # 응답코드
    msg1: str                                                         # 응답메세지
    ctx_area_fk100: str = ""                                          # 연속조회검색조건100
    ctx_area_nk100: str = ""                                          # 연속조회키100
    output1: List[ResponseBodyOutput1] = field(default_factory=list)  # 보유종목 목록(배열)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)  # 계좌 요약(배열, 보통 원소 1개)


# ── 요청 함수 ───────────────────────────────────────────────

def _get_account(mode: Literal["real", "paper"]) -> tuple[str, str, str, str, str]:
    """모드에 맞는 계좌번호, 상품코드, 앱키, 앱시크릿, 도메인을 반환한다."""
    if mode == "real":
        return CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET, DOMAIN["real"]
    return PAPER_CANO, PAPER_ACNT_PRDT_CD, PAPER_APPKEY, PAPER_APP_SECRET, DOMAIN["paper"]


def _is_rate_limited(raw: dict) -> bool:
    """원장(EGW00215) 유량 초과 또는 개인 초당 호출 한도 초과 응답인지 판별한다."""
    if raw.get("msg_cd") == _RATE_LIMIT_MSG_CD:
        return True
    msg1 = raw.get("msg1", "") or ""
    return _PERSONAL_RATE_LIMIT_TEXT in msg1 and "원장" not in msg1


def _get_with_retry(url: str, headers: dict, params: dict) -> tuple[object, dict]:
    """GET 요청 후 초당 거래건수 초과(원장 또는 개인) 응답이면 잠깐 쉬었다가 재시도한다.

    120 TPS 원장 유량 제한이든 개인 유량 제한이든 내 호출 횟수를 미리 줄일 필요는 없고,
    실제로 rate-limit 에러를 받았을 때만 대응하면 된다. 그 외 에러(rt_cd != "0")는 그대로
    반환해서 호출부가 평소처럼 처리하게 둔다.
    """
    response = None
    raw = {}
    for attempt in range(_MAX_RETRIES + 1):
        response = get_session().get(url, headers=headers, params=params, timeout=10)
        raw = response.json()
        if _is_rate_limited(raw) and attempt < _MAX_RETRIES:
            time.sleep(_RETRY_DELAY_SEC * (attempt + 1))  # 재시도할수록 대기시간 증가
            continue
        break
    return response, raw


def _fetch_page(
    mode: Literal["real", "paper"],
    afhr_flpr_yn: str,
    ofl_yn: str,
    inqr_dvsn: str,
    unpr_dvsn: str,
    fund_sttl_icld_yn: str,
    fncg_amt_auto_rdpt_yn: str,
    prcs_dvsn: str,
    ctx_area_fk100: str,
    ctx_area_nk100: str,
    tr_cont: str,
) -> tuple[ResponseBody, str, str, str]:
    """주식잔고를 한 페이지(실전 최대 50건/모의 최대 20건)만 조회한다.

    Args:
        mode: "real"(실전투자) 또는 "paper"(모의투자).
        afhr_flpr_yn: 시장 구분(AFHR_FLPR_YN). N KRX정규장종가 / X NXT / Y KRX+NXT 통합시세.
        ofl_yn: 오프라인여부(OFL_YN). 보통 공란.
        inqr_dvsn: 조회구분(INQR_DVSN). 01 대출일별.
        unpr_dvsn: 단가구분(UNPR_DVSN). 01 기본값.
        fund_sttl_icld_yn: 펀드결제분포함여부(FUND_STTL_ICLD_YN). N 포함하지 않음 / Y 포함.
        fncg_amt_auto_rdpt_yn: 융자금액자동상환여부(FNCG_AMT_AUTO_RDPT_YN). N 기본값.
        prcs_dvsn: 처리구분(PRCS_DVSN). 00 전일매매포함 / 01 전일매매미포함.
        ctx_area_fk100: 연속조회검색조건100(CTX_AREA_FK100). 최초 조회는 "".
        ctx_area_nk100: 연속조회키100(CTX_AREA_NK100). 최초 조회는 "".
        tr_cont: 요청 헤더의 연속 거래 여부. 최초 조회는 "", 다음 페이지는 "N".

    Returns:
        (이번 페이지 ResponseBody, 응답 헤더의 tr_cont, 다음 페이지용 ctx_area_fk100, ctx_area_nk100).
        응답 tr_cont가 "F" 또는 "M"이면 다음 페이지가 더 있다는 뜻이고, "D"/"E"면 마지막 페이지다.
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
        "tr_cont": tr_cont,
        "custtype": "P",
    }
    params = {
        "CANO": cano,
        "ACNT_PRDT_CD": acnt_prdt_cd,
        "AFHR_FLPR_YN": afhr_flpr_yn,
        "OFL_YN": ofl_yn,
        "INQR_DVSN": inqr_dvsn,
        "UNPR_DVSN": unpr_dvsn,
        "FUND_STTL_ICLD_YN": fund_sttl_icld_yn,
        "FNCG_AMT_AUTO_RDPT_YN": fncg_amt_auto_rdpt_yn,
        "PRCS_DVSN": prcs_dvsn,
        "CTX_AREA_FK100": ctx_area_fk100,
        "CTX_AREA_NK100": ctx_area_nk100,
    }
    response, raw = _get_with_retry(domain + URL, headers, params)

    # 에러 응답(rt_cd != "0")은 output1/output2 키가 없거나 null일 수 있어 안전 파싱.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or []
    output1 = [ResponseBodyOutput1(**{k: v for k, v in item.items() if k in fields1}) for item in raw_output1]

    fields2 = set(ResponseBodyOutput2.__dataclass_fields__)
    raw_output2 = raw.get("output2") or []
    output2 = [ResponseBodyOutput2(**{k: v for k, v in item.items() if k in fields2}) for item in raw_output2]

    body = ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        ctx_area_fk100=raw.get("ctx_area_fk100", "") or "",
        ctx_area_nk100=raw.get("ctx_area_nk100", "") or "",
        output1=output1,
        output2=output2,
    )

    next_tr_cont = response.headers.get("tr_cont", "")
    return body, next_tr_cont, body.ctx_area_fk100, body.ctx_area_nk100


def inquire_balance(
    afhr_flpr_yn: Literal["N", "X", "Y"] = "N",
    ofl_yn: str = "",
    inqr_dvsn: Literal["01"] = "01",
    unpr_dvsn: Literal["01"] = "01",
    fund_sttl_icld_yn: Literal["N", "Y"] = "N",
    fncg_amt_auto_rdpt_yn: Literal["N"] = "N",
    prcs_dvsn: Literal["00", "01"] = "00",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """주식잔고를 전부 조회한다(연속조회 자동 처리).

    1회 호출은 실전 최대 50건/모의 최대 20건까지만 돌아오므로, 응답 헤더의 tr_cont가
    "F"/"M"(다음 데이터 있음)인 동안 CTX_AREA_FK100/CTX_AREA_NK100을 이어받아 자동으로
    연속조회하며, "D"/"E"(마지막 데이터)가 되면 멈춘다.

    Args:
        afhr_flpr_yn: 시장 구분. N KRX정규장종가 / X NXT / Y KRX+NXT 통합시세. 기본값 "N".
        ofl_yn: 오프라인여부. 기본값 "" (공란).
        inqr_dvsn: 조회구분. 01 대출일별. 기본값 "01".
        unpr_dvsn: 단가구분. 01 기본값.
        fund_sttl_icld_yn: 펀드결제분포함여부. N 포함하지 않음 / Y 포함. 기본값 "N".
        fncg_amt_auto_rdpt_yn: 융자금액자동상환여부. 기본값 "N".
        prcs_dvsn: 처리구분. 00 전일매매포함 / 01 전일매매미포함. 기본값 "00".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1(마지막으로 받은 페이지 기준)과, 모든 페이지를 합친 보유종목(output1),
        계좌 요약(output2, 보통 원소 1개)을 담은 ResponseBody. 실패 여부는 반드시 rt_cd로 확인할 것 —
        중간에 에러가 나면 그 페이지의 rt_cd/msg_cd/msg1이 그대로 반환되고 output1은 그때까지 모은 값이다.
    """
    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    tr_cont = ""  # 공백: 최초 조회

    all_output1: List[ResponseBodyOutput1] = []
    body = ResponseBody(rt_cd="", msg_cd="", msg1="")

    while True:
        body, next_tr_cont, ctx_area_fk100, ctx_area_nk100 = _fetch_page(
            mode, afhr_flpr_yn, ofl_yn, inqr_dvsn, unpr_dvsn,
            fund_sttl_icld_yn, fncg_amt_auto_rdpt_yn, prcs_dvsn,
            ctx_area_fk100, ctx_area_nk100, tr_cont,
        )
        all_output1.extend(body.output1)

        if body.rt_cd != "0" or next_tr_cont not in ("F", "M"):
            break
        tr_cont = "N"  # 다음 페이지 조회

    return ResponseBody(
        rt_cd=body.rt_cd,
        msg_cd=body.msg_cd,
        msg1=body.msg1,
        output1=all_output1,
        output2=body.output2,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_balance(mode="paper")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output1:
            print(row)
        for row in result.output2:
            print(row)
