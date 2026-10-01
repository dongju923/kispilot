# 기간별손익일별합산조회[v1_국내주식-052]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/inquire-period-profit"
# ※ 모의투자 미지원 (실전투자 전용).
# ※ HTS(eFriend Plus) [0856] 기간별 매매손익 화면에서 "일별" 클릭 시와 동일한 데이터.
# ※ output2의 총손익률(우측 하단 표시값)은 이 API가 아니라 기간별매매손익현황조회(TTTC8715R)의
#   output2.tot_pftrt(총수익률)로 확인해야 한다 — 이 파일에는 없음(문서에 명시된 주의사항).
# ※ 연속조회 지원: CTX_AREA_FK100/CTX_AREA_NK100이 실제 쿼리 파라미터에 있음(다른 계좌 API와 다름).

_TR_ID = "TTTC8708R"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    trad_dt: Optional[str] = None       # 매매일자
    buy_amt: Optional[str] = None       # 매수금액
    sll_amt: Optional[str] = None       # 매도금액
    rlzt_pfls: Optional[str] = None     # 실현손익
    fee: Optional[str] = None           # 수수료
    loan_int: Optional[str] = None      # 대출이자
    tl_tax: Optional[str] = None        # 제세금
    pfls_rt: Optional[str] = None       # 손익률
    sll_qty1: Optional[str] = None      # 매도수량1
    buy_qty1: Optional[str] = None      # 매수수량1


@dataclass
class ResponseBodyOutput2:
    sll_qty_smtl: Optional[str] = None          # 매도수량합계
    sll_tr_amt_smtl: Optional[str] = None       # 매도거래금액합계
    sll_fee_smtl: Optional[str] = None          # 매도수수료합계
    sll_tltx_smtl: Optional[str] = None         # 매도제세금합계
    sll_excc_amt_smtl: Optional[str] = None     # 매도정산금액합계
    buy_qty_smtl: Optional[str] = None          # 매수수량합계
    buy_tr_amt_smtl: Optional[str] = None       # 매수거래금액합계
    buy_fee_smtl: Optional[str] = None          # 매수수수료합계
    buy_tax_smtl: Optional[str] = None          # 매수제세금합계
    buy_excc_amt_smtl: Optional[str] = None     # 매수정산금액합계
    tot_qty: Optional[str] = None               # 총수량
    tot_tr_amt: Optional[str] = None            # 총거래금액
    tot_fee: Optional[str] = None               # 총수수료
    tot_tltx: Optional[str] = None              # 총제세금
    tot_excc_amt: Optional[str] = None          # 총정산금액
    tot_rlzt_pfls: Optional[str] = None         # 총실현손익
    loan_int: Optional[str] = None              # 대출이자


@dataclass
class ResponseBody:
    rt_cd: str                                                        # 성공 실패 여부
    msg_cd: str                                                       # 응답코드
    msg1: str                                                         # 응답메세지
    output1: List[ResponseBodyOutput1] = field(default_factory=list)  # 매매일자별 손익(배열)
    output2: ResponseBodyOutput2 = field(default_factory=ResponseBodyOutput2)  # 기간 합계(단일)


# ── 요청 함수 ───────────────────────────────────────────────

def _fetch_page(
    inqr_strt_dt: str,
    inqr_end_dt: str,
    pdno: str,
    sort_dvsn: str,
    ctx_area_fk100: str,
    ctx_area_nk100: str,
    tr_cont: str,
) -> tuple[ResponseBody, str, str, str]:
    """기간별손익 일별합산 내역을 한 페이지만 조회한다.

    Args:
        inqr_strt_dt: 조회시작일자(INQR_STRT_DT), YYYYMMDD.
        inqr_end_dt: 조회종료일자(INQR_END_DT), YYYYMMDD.
        pdno: 상품번호(PDNO). 특정 종목만, 공란이면 전체.
        sort_dvsn: 정렬구분(SORT_DVSN). 00/02 최근 순, 01 과거 순.
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
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "CANO": CANO,
        "INQR_STRT_DT": inqr_strt_dt,
        "PDNO": pdno,
        "CTX_AREA_NK100": ctx_area_nk100,
        "INQR_END_DT": inqr_end_dt,
        "SORT_DVSN": sort_dvsn,
        "INQR_DVSN": "00",
        "CBLC_DVSN": "00",
        "CTX_AREA_FK100": ctx_area_fk100,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
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


def inquire_period_profit(
    inqr_strt_dt: str,
    inqr_end_dt: str,
    pdno: str = "",
    sort_dvsn: Literal["00", "01", "02"] = "00",
) -> ResponseBody:
    """기간 내 매매일자별 손익 합산 내역을 전부 조회한다(연속조회 자동 처리). (모의투자 미지원, 실전 계좌 전용)

    HTS(eFriend Plus) [0856] 기간별 매매손익 화면의 "일별" 탭과 동일한 데이터.

    Args:
        inqr_strt_dt: 조회시작일자, YYYYMMDD.
        inqr_end_dt: 조회종료일자, YYYYMMDD.
        pdno: 특정 종목코드만 조회할 때 지정. 기본값 "" (전체).
        sort_dvsn: 정렬구분. "00"/"02" 최근 순, "01" 과거 순. 기본값 "00".

    Returns:
        rt_cd/msg_cd/msg1(마지막으로 받은 페이지 기준)과, 모든 페이지를 합친 매매일자별
        손익(output1), 기간 합계(output2)를 담은 ResponseBody. 실패 여부는 반드시 rt_cd로 확인할 것.
        (참고: 화면 우측 하단의 "총손익률"은 이 API가 아니라 기간별매매손익현황조회의
        output2.tot_pftrt로 확인해야 한다.)
    """
    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    tr_cont = ""  # 공백: 최초 조회

    all_output1: List[ResponseBodyOutput1] = []
    body = ResponseBody(rt_cd="", msg_cd="", msg1="")

    while True:
        body, next_tr_cont, ctx_area_fk100, ctx_area_nk100 = _fetch_page(
            inqr_strt_dt, inqr_end_dt, pdno, sort_dvsn,
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
    result = inquire_period_profit(inqr_strt_dt="20260101", inqr_end_dt="20261231")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output1:
            print(row)
        print(result.output2)
