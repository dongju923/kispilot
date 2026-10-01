# 기간별계좌권리현황조회[국내주식-211]
from dataclasses import dataclass, field
from typing import List, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/period-rights"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [7344] 권리유형별 현황조회 화면과 동일한 데이터.
# ※ 연속조회 지원: CTX_AREA_NK100/CTX_AREA_FK100 쿼리 파라미터 + 응답 헤더 tr_cont(F/M/D/E).
# ※ INQR_DVSN="03", CUST_RNCNO25/HMID는 문서상 고정 공란값이라 파라미터로 노출하지 않는다.

_TR_ID = "CTRGA011R"
_INQR_DVSN = "03"  # 문서 고정값

# RGHT_TYPE_CD(권리유형코드) 코드표 (일부만 발췌, 전체는 KIS 문서 참고)
# ※ 1~9번은 앞에 0을 붙이지 않는다(길이는 2지만 값은 "1"~"9" 그대로, 11번부터 두 자리).
#   1 유상   2 무상   3 배당       4 매수청구   5 공개매수   6 주주총회
#   7 신주인수권증서   8 반대의사   9 신주인수권증권
#   11 합병   12 회사분할   13 주식교환   14 액면분할   15 액면병합
#   16 종목변경   17 감자   18 신구주합병
#   21~28: 11~18과 동일 항목의 "후"(사후) 버전
#   31 뮤츄얼펀드   32 ETF   41 ELW만기   42 ELS분배   43 DLS분배   45 ETN
#   51 전환청구   52 교환청구   61 원리금상환   62 스트립채권
#   91 공모주   92 청약   93 환매   99 기타권리사유


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    acno10: Optional[str] = None                # 계좌번호10
    rght_type_cd: Optional[str] = None           # 권리유형코드 (파일 상단 코드표 참고)
    bass_dt: Optional[str] = None                # 기준일자
    rght_cblc_type_cd: Optional[str] = None      # 권리잔고유형코드
    rptt_pdno: Optional[str] = None              # 대표상품번호
    pdno: Optional[str] = None                   # 상품번호
    prdt_type_cd: Optional[str] = None           # 상품유형코드
    shtn_pdno: Optional[str] = None              # 단축상품번호
    prdt_name: Optional[str] = None              # 상품명
    cblc_qty: Optional[str] = None               # 잔고수량
    last_alct_qty: Optional[str] = None          # 최종배정수량
    excs_alct_qty: Optional[str] = None          # 초과배정수량
    tot_alct_qty: Optional[str] = None           # 총배정수량
    last_ftsk_qty: Optional[str] = None          # 최종단수주수량
    last_alct_amt: Optional[str] = None          # 최종배정금액
    last_ftsk_chgs: Optional[str] = None         # 최종단수주대금
    rdpt_prca: Optional[str] = None              # 상환원금
    dlay_int_amt: Optional[str] = None           # 지연이자금액
    lstg_dt: Optional[str] = None                # 상장일자
    sbsc_end_dt: Optional[str] = None            # 청약종료일자
    cash_dfrm_dt: Optional[str] = None           # 현금지급일자
    rqst_qty: Optional[str] = None               # 신청수량
    rqst_amt: Optional[str] = None               # 신청금액
    rqst_dt: Optional[str] = None                # 신청일자
    rfnd_dt: Optional[str] = None                # 환불일자
    rfnd_amt: Optional[str] = None               # 환불금액
    lstg_stqt: Optional[str] = None              # 상장주수
    tax_amt: Optional[str] = None                # 세금금액
    sbsc_unpr: Optional[str] = None              # 청약단가


@dataclass
class ResponseBody:
    rt_cd: str                                                        # 성공 실패 여부
    msg_cd: str                                                       # 응답코드
    msg1: str                                                         # 응답메세지
    output1: List[ResponseBodyOutput1] = field(default_factory=list)  # 권리 발생 내역(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def _fetch_page(
    inqr_strt_dt: str,
    inqr_end_dt: str,
    rght_type_cd: str,
    pdno: str,
    prdt_type_cd: str,
    ctx_area_fk100: str,
    ctx_area_nk100: str,
    tr_cont: str,
) -> tuple[ResponseBody, str, str, str]:
    """기간별계좌권리현황을 한 페이지만 조회한다.

    Args:
        inqr_strt_dt: 조회시작일자(INQR_STRT_DT), YYYYMMDD.
        inqr_end_dt: 조회종료일자(INQR_END_DT), YYYYMMDD.
        rght_type_cd: 권리유형코드(RGHT_TYPE_CD). 특정 권리유형만, 공란이면 전체.
        pdno: 상품번호(PDNO). 특정 종목만, 공란이면 전체.
        prdt_type_cd: 상품유형코드(PRDT_TYPE_CD). 특정 상품유형만, 공란이면 전체.
        ctx_area_fk100: 연속조회검색조건100(CTX_AREA_FK100). 최초 조회는 "".
        ctx_area_nk100: 연속조회키100(CTX_AREA_NK100). 최초 조회는 "".
        tr_cont: 요청 헤더의 연속 거래 여부. 최초 조회는 "", 다음 페이지는 "N".

    Returns:
        (이번 페이지 ResponseBody, 응답 헤더의 tr_cont, 다음 페이지용 ctx_area_fk100, ctx_area_nk100).
        응답 tr_cont가 "F" 또는 "M"이면 다음 페이지가 더 있다는 뜻이고, "D"/"E"면 마지막 페이지다.
    """
    token = load_token("real")
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": REAL_APPKEY,
        "appsecret": REAL_APP_SECRET,
        "tr_id": _TR_ID,
        "tr_cont": tr_cont,
        "custtype": "P",
    }
    params = {
        "INQR_DVSN": _INQR_DVSN,
        "CUST_RNCNO25": "",
        "HMID": "",
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "INQR_STRT_DT": inqr_strt_dt,
        "INQR_END_DT": inqr_end_dt,
        "RGHT_TYPE_CD": rght_type_cd,
        "PDNO": pdno,
        "PRDT_TYPE_CD": prdt_type_cd,
        "CTX_AREA_NK100": ctx_area_nk100,
        "CTX_AREA_FK100": ctx_area_fk100,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1 키가 없거나 null일 수 있어 안전 파싱.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or []
    output1 = [ResponseBodyOutput1(**{k: v for k, v in item.items() if k in fields1}) for item in raw_output1]

    body = ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
    )

    next_tr_cont = response.headers.get("tr_cont", "")
    next_fk100 = raw.get("ctx_area_fk100", "") or ""
    next_nk100 = raw.get("ctx_area_nk100", "") or ""

    return body, next_tr_cont, next_fk100, next_nk100


def inquire_period_rights(
    inqr_strt_dt: str,
    inqr_end_dt: str,
    rght_type_cd: str = "",
    pdno: str = "",
    prdt_type_cd: str = "",
) -> ResponseBody:
    """기간 내 계좌 권리(유상/무상/배당/합병 등) 발생 내역을 전부 조회한다(연속조회 자동 처리).

    (모의투자 미지원, 실전 계좌 전용) HTS(eFriend Plus) [7344] 권리유형별 현황조회 화면과 동일한 데이터.

    Args:
        inqr_strt_dt: 조회시작일자, YYYYMMDD.
        inqr_end_dt: 조회종료일자, YYYYMMDD.
        rght_type_cd: 특정 권리유형코드만 조회할 때 지정(파일 상단 코드표 참고). 기본값 "" (전체).
        pdno: 특정 종목코드만 조회할 때 지정. 기본값 "" (전체).
        prdt_type_cd: 특정 상품유형코드만 조회할 때 지정. 기본값 "" (전체).

    Returns:
        rt_cd/msg_cd/msg1(마지막으로 받은 페이지 기준)과, 모든 페이지를 합친 권리 발생
        내역(output1)을 담은 ResponseBody. 실패 여부는 반드시 rt_cd로 확인할 것.
    """
    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    tr_cont = ""  # 공백: 최초 조회

    all_output1: List[ResponseBodyOutput1] = []
    body = ResponseBody(rt_cd="", msg_cd="", msg1="")

    while True:
        body, next_tr_cont, ctx_area_fk100, ctx_area_nk100 = _fetch_page(
            inqr_strt_dt, inqr_end_dt, rght_type_cd, pdno, prdt_type_cd,
            ctx_area_fk100, ctx_area_nk100, tr_cont,
        )
        all_output1.extend(body.output1)

        if body.rt_cd != "0" or next_tr_cont not in ("F", "M"):
            break
        tr_cont = "N"  # 다음 페이지 조회

    return ResponseBody(rt_cd=body.rt_cd, msg_cd=body.msg_cd, msg1=body.msg1, output1=all_output1)


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_period_rights(inqr_strt_dt="20260101", inqr_end_dt="20261231")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output1:
            print(row)
