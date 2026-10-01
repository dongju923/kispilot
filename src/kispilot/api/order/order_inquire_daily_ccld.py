# 주식일별주문체결조회[v1_국내주식-005]
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Literal, Optional

from kispilot.api.config import (
    DOMAIN,
    CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET,
    PAPER_CANO, PAPER_ACNT_PRDT_CD, PAPER_APPKEY, PAPER_APP_SECRET,
)
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/inquire-daily-ccld"
# ※ 실전: 1회 최대 100건 / 모의: 1회 최대 15건. 그 이상은 연속조회(tr_cont)로 이어받는다.
# ※ 3개월 이전 체결내역(CTSC9215R/VTSC9215R) 조회는 장중 지연이 있을 수 있어
#    가급적 장 종료(15:30) 이후, 조회기간을 짧게 해서 조회할 것을 KIS가 권장함.

# (mode, period)별 tr_id — period는 조회시작일자가 최근 3개월 이내(recent)인지 이전(old)인지로 결정
_TR_ID = {
    ("real", "recent"): "TTTC0081R",
    ("real", "old"): "CTSC9215R",
    ("paper", "recent"): "VTTC0081R",
    ("paper", "old"): "VTSC9215R",
}


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    ord_dt: Optional[str] = None                          # 주문일자
    ord_gno_brno: Optional[str] = None                    # 주문채번지점번호
    odno: Optional[str] = None                             # 주문번호
    orgn_odno: Optional[str] = None                         # 원주문번호
    ord_dvsn_name: Optional[str] = None                     # 주문구분명
    sll_buy_dvsn_cd: Optional[str] = None                   # 매도매수구분코드
    sll_buy_dvsn_cd_name: Optional[str] = None              # 매도매수구분코드명
    pdno: Optional[str] = None                              # 상품번호
    prdt_name: Optional[str] = None                         # 상품명
    ord_qty: Optional[str] = None                           # 주문수량
    ord_unpr: Optional[str] = None                          # 주문단가
    ord_tmd: Optional[str] = None                           # 주문시각
    tot_ccld_qty: Optional[str] = None                      # 총체결수량
    avg_prvs: Optional[str] = None                          # 평균가
    cncl_yn: Optional[str] = None                           # 취소여부
    tot_ccld_amt: Optional[str] = None                      # 총체결금액
    loan_dt: Optional[str] = None                           # 대출일자
    ordr_empno: Optional[str] = None                        # 주문자사번
    ord_dvsn_cd: Optional[str] = None                       # 주문구분코드
    cncl_cfrm_qty: Optional[str] = None                     # 취소확인수량
    rmn_qty: Optional[str] = None                           # 잔여수량
    rjct_qty: Optional[str] = None                          # 거부수량
    ccld_cndt_name: Optional[str] = None                    # 체결조건명
    inqr_ip_addr: Optional[str] = None                      # 조회IP주소
    cpbc_ordp_ord_rcit_dvsn_cd: Optional[str] = None        # 전산주문표주문접수구분코드
    cpbc_ordp_infm_mthd_dvsn_cd: Optional[str] = None       # 전산주문표통보방법구분코드
    infm_tmd: Optional[str] = None                          # 통보시각
    ctac_tlno: Optional[str] = None                         # 연락전화번호
    prdt_type_cd: Optional[str] = None                      # 상품유형코드
    excg_dvsn_cd: Optional[str] = None                      # 거래소구분코드
    cpbc_ordp_mtrl_dvsn_cd: Optional[str] = None            # 전산주문표자료구분코드
    ord_orgno: Optional[str] = None                         # 주문조직번호
    rsvn_ord_end_dt: Optional[str] = None                   # 예약주문종료일자
    excg_id_dvsn_cd: Optional[str] = None                   # 거래소ID구분코드
    stpm_cndt_pric: Optional[str] = None                    # 스톱지정가조건가격
    stpm_efct_occr_dtmd: Optional[str] = None               # 스톱지정가효력발생상세시각


@dataclass
class ResponseBodyOutput2:
    tot_ord_qty: Optional[str] = None       # 총주문수량
    tot_ccld_qty: Optional[str] = None      # 총체결수량
    tot_ccld_amt: Optional[str] = None      # 총체결금액
    pchs_avg_pric: Optional[str] = None     # 매입평균가격
    prsm_tlex_smtl: Optional[str] = None    # 추정제비용합계


@dataclass
class ResponseBody:
    rt_cd: str                                                        # 성공 실패 여부
    msg_cd: str                                                       # 응답코드
    msg1: str                                                         # 응답메세지
    output1: List[ResponseBodyOutput1] = field(default_factory=list)  # 일별 주문체결 내역(배열)
    output2: ResponseBodyOutput2 = field(default_factory=ResponseBodyOutput2)   # 조회기간 합계(단일)


# ── 요청 함수 ───────────────────────────────────────────────

def _get_account(mode: Literal["real", "paper"]) -> tuple[str, str, str, str, str]:
    """모드에 맞는 계좌번호, 상품코드, 앱키, 앱시크릿, 도메인을 반환한다."""
    if mode == "real":
        return CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET, DOMAIN["real"]
    return PAPER_CANO, PAPER_ACNT_PRDT_CD, PAPER_APPKEY, PAPER_APP_SECRET, DOMAIN["paper"]


def _select_period(inqr_strt_dt: str) -> Literal["recent", "old"]:
    """조회시작일자가 최근 3개월 이내인지에 따라 사용할 tr_id 종류를 고른다. (3개월은 90일로 근사)"""
    strt = datetime.strptime(inqr_strt_dt, "%Y%m%d")
    cutoff = datetime.now() - timedelta(days=90)
    return "recent" if strt >= cutoff else "old"


def _fetch_page(
    mode: Literal["real", "paper"],
    inqr_strt_dt: str,
    inqr_end_dt: str,
    sll_buy_dvsn_cd: str,
    pdno: str,
    ord_gno_brno: str,
    odno: str,
    ccld_dvsn: str,
    inqr_dvsn: str,
    inqr_dvsn_1: str,
    inqr_dvsn_3: str,
    market: str,
    ctx_area_fk100: str,
    ctx_area_nk100: str,
    tr_cont: str,
) -> tuple[ResponseBody, str, str, str]:
    """일별 주문체결내역을 한 페이지(실전 최대 100건/모의 최대 15건)만 조회한다.

    Args:
        mode: "real"(실전투자) 또는 "paper"(모의투자). 조회기간과 함께 tr_id를 결정.
        inqr_strt_dt: 조회시작일자(INQR_STRT_DT), YYYYMMDD.
        inqr_end_dt: 조회종료일자(INQR_END_DT), YYYYMMDD.
        sll_buy_dvsn_cd: 매도매수구분코드(SLL_BUY_DVSN_CD). 00 전체/01 매도/02 매수.
        pdno: 상품번호(PDNO). 특정 종목만 조회할 때, 아니면 "".
        ord_gno_brno: 주문채번지점번호(ORD_GNO_BRNO). 특정 주문 조회가 아니면 "".
        odno: 주문번호(ODNO). 특정 주문만 조회할 때, 아니면 "".
        ccld_dvsn: 체결구분(CCLD_DVSN). 00 전체/01 체결/02 미체결.
        inqr_dvsn: 조회구분(INQR_DVSN). 00 역순(최신순)/01 정순.
        inqr_dvsn_1: 조회구분1(INQR_DVSN_1). "" 전체/1 ELW/2 프리보드.
        inqr_dvsn_3: 조회구분3(INQR_DVSN_3). 00 전체/01 현금/02 신용/03 담보/04 대주/05 대여/06 자기융자/07 유통융자.
        market: 거래소ID구분코드(EXCG_ID_DVSN_CD). KRX/NXT/SOR/ALL. 모의투자는 KRX만 지원.
        ctx_area_fk100: 연속조회검색조건100(CTX_AREA_FK100). 최초 조회는 "".
        ctx_area_nk100: 연속조회키100(CTX_AREA_NK100). 최초 조회는 "".
        tr_cont: 요청 헤더의 연속 거래 여부. 최초 조회는 "", 다음 페이지는 "N".

    Returns:
        (이번 페이지 ResponseBody, 응답 헤더의 tr_cont, 다음 페이지용 ctx_area_fk100, ctx_area_nk100).
        응답 tr_cont가 "F" 또는 "M"이면 다음 페이지가 더 있다는 뜻이고, "D"/"E"면 마지막 페이지다.
    """
    token = load_token(mode)
    cano, acnt_prdt_cd, app_key, app_secret, domain = _get_account(mode)
    tr_id = _TR_ID[(mode, _select_period(inqr_strt_dt))]

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
        "INQR_STRT_DT": inqr_strt_dt,
        "INQR_END_DT": inqr_end_dt,
        "SLL_BUY_DVSN_CD": sll_buy_dvsn_cd,
        "PDNO": pdno,
        "ORD_GNO_BRNO": ord_gno_brno,
        "ODNO": odno,
        "CCLD_DVSN": ccld_dvsn,
        "INQR_DVSN": inqr_dvsn,
        "INQR_DVSN_1": inqr_dvsn_1,
        "INQR_DVSN_3": inqr_dvsn_3,
        "EXCG_ID_DVSN_CD": market,
        "CTX_AREA_FK100": ctx_area_fk100,
        "CTX_AREA_NK100": ctx_area_nk100,
    }
    response = get_session().get(domain + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1/output2 키가 없거나 null일 수 있어 안전 파싱.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or []
    output1 = [ResponseBodyOutput1(**{k: v for k, v in item.items() if k in fields1}) for item in raw_output1]

    fields2 = set(ResponseBodyOutput2.__dataclass_fields__)
    raw_output2 = raw.get("output2") or {}
    output2 = ResponseBodyOutput2(**{k: v for k, v in raw_output2.items() if k in fields2})

    body = ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
        output2=output2,
    )

    next_tr_cont = response.headers.get("tr_cont", "")
    next_fk100 = raw.get("ctx_area_fk100", "") or ""
    next_nk100 = raw.get("ctx_area_nk100", "") or ""

    return body, next_tr_cont, next_fk100, next_nk100


def inquire_daily_ccld(
    inqr_strt_dt: str,
    inqr_end_dt: str,
    sll_buy_dvsn_cd: Literal["00", "01", "02"] = "00",
    pdno: str = "",
    ord_gno_brno: str = "",
    odno: str = "",
    ccld_dvsn: Literal["00", "01", "02"] = "00",
    inqr_dvsn: Literal["00", "01"] = "00",
    inqr_dvsn_1: Literal["", "1", "2"] = "",
    inqr_dvsn_3: Literal["00", "01", "02", "03", "04", "05", "06", "07"] = "00",
    mode: Literal["real", "paper"] = "real",
    market: Literal["KRX", "NXT", "SOR", "ALL"] = "KRX",
) -> ResponseBody:
    """기간 내 일별 주문체결내역을 전부 조회한다(연속조회 자동 처리).

    1회 호출은 실전 최대 100건/모의 최대 15건까지만 돌아오므로, 응답 헤더의 tr_cont가
    "F"/"M"(다음 데이터 있음)인 동안 CTX_AREA_FK100/CTX_AREA_NK100을 이어받아 자동으로
    연속조회하며, "D"/"E"(마지막 데이터)가 되면 멈춘다.

    Args:
        inqr_strt_dt: 조회시작일자, YYYYMMDD. 오늘로부터 3개월 이전이면 자동으로 다른 tr_id(3개월이전용)를 사용.
        inqr_end_dt: 조회종료일자, YYYYMMDD.
        sll_buy_dvsn_cd: 매도매수구분코드. 00 전체/01 매도/02 매수. 기본값 "00".
        pdno: 특정 종목코드만 조회할 때 지정. 기본값 "".
        ord_gno_brno: 특정 주문의 주문채번지점번호. 기본값 "".
        odno: 특정 주문번호만 조회할 때 지정. 기본값 "".
        ccld_dvsn: 체결구분. 00 전체/01 체결/02 미체결. 기본값 "00".
        inqr_dvsn: 조회구분. 00 역순(최신순)/01 정순. 기본값 "00".
        inqr_dvsn_1: 조회구분1. "" 전체/1 ELW/2 프리보드. 기본값 "".
        inqr_dvsn_3: 조회구분3(신용/담보/대주 등 구분). 기본값 "00"(전체).
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".
        market: 거래소ID구분코드. KRX/NXT/SOR/ALL. 모의투자는 KRX만 지원. 기본값 "KRX".

    Returns:
        rt_cd/msg_cd/msg1(마지막으로 받은 페이지 기준)과, 모든 페이지를 합친 일별 주문체결 내역(output1),
        조회기간 합계(output2)를 담은 ResponseBody. 실패 여부는 반드시 rt_cd로 확인할 것.
    """
    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    tr_cont = ""  # 공백: 최초 조회

    all_output1: List[ResponseBodyOutput1] = []
    body = ResponseBody(rt_cd="", msg_cd="", msg1="")

    while True:
        body, next_tr_cont, ctx_area_fk100, ctx_area_nk100 = _fetch_page(
            mode, inqr_strt_dt, inqr_end_dt, sll_buy_dvsn_cd, pdno, ord_gno_brno, odno,
            ccld_dvsn, inqr_dvsn, inqr_dvsn_1, inqr_dvsn_3, market,
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
    today = datetime.now().strftime("%Y%m%d")
    result = inquire_daily_ccld(inqr_strt_dt=today, inqr_end_dt=today, mode="paper")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output1:
            print(row)
        print(result.output2)
