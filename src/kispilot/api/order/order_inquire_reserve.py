# 주식예약주문조회[v1_국내주식-020]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/order-resv-ccnl"
# ※ 모의투자 미지원 (실전투자 전용). 1회 최대 20건, 그 이상은 연속조회(tr_cont)로 이어받는다.
# ※ 다른 조회 API들과 달리 연속조회 키가 CTX_AREA_FK200/CTX_AREA_NK200(100이 아니라 200)이다.

_TR_ID = "CTSC0004R"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    rsvn_ord_seq: Optional[str] = None          # 예약주문 순번
    rsvn_ord_ord_dt: Optional[str] = None        # 예약주문주문일자
    rsvn_ord_rcit_dt: Optional[str] = None       # 예약주문접수일자
    pdno: Optional[str] = None                   # 상품번호
    ord_dvsn_cd: Optional[str] = None            # 주문구분코드
    ord_rsvn_qty: Optional[str] = None           # 주문예약수량
    tot_ccld_qty: Optional[str] = None           # 총체결수량
    cncl_ord_dt: Optional[str] = None            # 취소주문일자
    ord_tmd: Optional[str] = None                # 주문시각
    ctac_tlno: Optional[str] = None              # 연락전화번호
    rjct_rson2: Optional[str] = None             # 거부사유2
    odno: Optional[str] = None                   # 주문번호
    rsvn_ord_rcit_tmd: Optional[str] = None      # 예약주문접수시각
    kor_item_shtn_name: Optional[str] = None     # 한글종목단축명
    sll_buy_dvsn_cd: Optional[str] = None        # 매도매수구분코드
    ord_rsvn_unpr: Optional[str] = None          # 주문예약단가
    tot_ccld_amt: Optional[str] = None           # 총체결금액
    loan_dt: Optional[str] = None                # 대출일자
    cncl_rcit_tmd: Optional[str] = None          # 취소접수시각
    prcs_rslt: Optional[str] = None              # 처리결과
    ord_dvsn_name: Optional[str] = None          # 주문구분명
    tmnl_mdia_kind_cd: Optional[str] = None      # 단말매체종류코드
    rsvn_end_dt: Optional[str] = None            # 예약종료일자


@dataclass
class ResponseBody:
    rt_cd: str                                                        # 성공 실패 여부
    msg_cd: str                                                       # 응답코드
    msg1: str                                                         # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)    # 예약주문 처리내역(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def _fetch_page(
    rsvn_ord_ord_dt: str,
    rsvn_ord_end_dt: str,
    rsvn_ord_seq: str,
    prcs_dvsn_cd: str,
    cncl_yn: str,
    pdno: str,
    sll_buy_dvsn_cd: str,
    ctx_area_fk200: str,
    ctx_area_nk200: str,
    tr_cont: str,
) -> tuple[ResponseBody, str, str, str]:
    """예약주문 처리내역을 한 페이지(최대 20건)만 조회한다.

    Args:
        rsvn_ord_ord_dt: 예약주문시작일자(RSVN_ORD_ORD_DT), YYYYMMDD.
        rsvn_ord_end_dt: 예약주문종료일자(RSVN_ORD_END_DT), YYYYMMDD.
        rsvn_ord_seq: 예약주문순번(RSVN_ORD_SEQ). 특정 건만 조회할 때, 아니면 "".
        prcs_dvsn_cd: 처리구분코드(PRCS_DVSN_CD). 0 전체/1 처리내역/2 미처리내역.
        cncl_yn: 취소여부(CNCL_YN). "Y"면 유효한(취소 안 된) 주문만 조회, ""면 전체.
        pdno: 상품번호(PDNO). 특정 종목만, 공란이면 전체.
        sll_buy_dvsn_cd: 매도매수구분코드(SLL_BUY_DVSN_CD). "01" 매도/"02" 매수, ""면 전체.
        ctx_area_fk200: 연속조회검색조건200(CTX_AREA_FK200). 최초 조회는 "".
        ctx_area_nk200: 연속조회키200(CTX_AREA_NK200). 최초 조회는 "".
        tr_cont: 요청 헤더의 연속 거래 여부. 최초 조회는 "", 다음 페이지는 "N".

    Returns:
        (이번 페이지 ResponseBody, 응답 헤더의 tr_cont, 다음 페이지용 ctx_area_fk200, ctx_area_nk200).
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
        "RSVN_ORD_ORD_DT": rsvn_ord_ord_dt,
        "RSVN_ORD_END_DT": rsvn_ord_end_dt,
        "RSVN_ORD_SEQ": rsvn_ord_seq,
        "TMNL_MDIA_KIND_CD": "00",
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "PRCS_DVSN_CD": prcs_dvsn_cd,
        "CNCL_YN": cncl_yn,
        "PDNO": pdno,
        "SLL_BUY_DVSN_CD": sll_buy_dvsn_cd,
        "CTX_AREA_FK200": ctx_area_fk200,
        "CTX_AREA_NK200": ctx_area_nk200,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output 키가 없거나 null일 수 있어 안전 파싱.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_outputs = raw.get("output") or []
    outputs = [ResponseBodyOutput(**{k: v for k, v in item.items() if k in fields}) for item in raw_outputs]

    body = ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output=outputs,
    )

    next_tr_cont = response.headers.get("tr_cont", "")
    next_fk200 = raw.get("ctx_area_fk200", "") or ""
    next_nk200 = raw.get("ctx_area_nk200", "") or ""

    return body, next_tr_cont, next_fk200, next_nk200


def inquire_order_resv_ccnl(
    rsvn_ord_ord_dt: str,
    rsvn_ord_end_dt: str,
    rsvn_ord_seq: str = "",
    prcs_dvsn_cd: Literal["0", "1", "2"] = "0",
    cncl_yn: Literal["", "Y"] = "",
    pdno: str = "",
    sll_buy_dvsn_cd: Literal["", "01", "02"] = "",
) -> ResponseBody:
    """기간 내 예약주문 처리내역을 전부 조회한다(연속조회 자동 처리). (모의투자 미지원, 실전 계좌 전용)

    1회 호출은 최대 20건까지만 돌아오므로, 응답 헤더의 tr_cont가 "F"/"M"(다음 데이터 있음)인 동안
    CTX_AREA_FK200/CTX_AREA_NK200을 이어받아 자동으로 연속조회하며, "D"/"E"(마지막 데이터)가 되면 멈춘다.

    Args:
        rsvn_ord_ord_dt: 예약주문시작일자, YYYYMMDD.
        rsvn_ord_end_dt: 예약주문종료일자, YYYYMMDD.
        rsvn_ord_seq: 특정 예약주문순번만 조회할 때 지정. 기본값 "" (전체).
        prcs_dvsn_cd: 처리구분코드. 0 전체/1 처리내역/2 미처리내역. 기본값 "0".
        cncl_yn: 취소여부. "Y"면 유효한(취소 안 된) 주문만, ""면 전체. 기본값 "".
        pdno: 특정 종목코드만 조회할 때 지정. 기본값 "" (전체).
        sll_buy_dvsn_cd: 매도매수구분코드. "01" 매도/"02" 매수, ""면 전체. 기본값 "".

    Returns:
        rt_cd/msg_cd/msg1(마지막으로 받은 페이지 기준)과, 모든 페이지를 합친 예약주문
        처리내역(output)을 담은 ResponseBody. 실패 여부는 반드시 rt_cd로 확인할 것.
    """
    ctx_area_fk200 = ""
    ctx_area_nk200 = ""
    tr_cont = ""  # 공백: 최초 조회

    results: List[ResponseBodyOutput] = []
    body = ResponseBody(rt_cd="", msg_cd="", msg1="")

    while True:
        body, next_tr_cont, ctx_area_fk200, ctx_area_nk200 = _fetch_page(
            rsvn_ord_ord_dt, rsvn_ord_end_dt, rsvn_ord_seq,
            prcs_dvsn_cd, cncl_yn, pdno, sll_buy_dvsn_cd,
            ctx_area_fk200, ctx_area_nk200, tr_cont,
        )
        results.extend(body.output)

        if body.rt_cd != "0" or next_tr_cont not in ("F", "M"):
            break
        tr_cont = "N"  # 다음 페이지 조회

    return ResponseBody(rt_cd=body.rt_cd, msg_cd=body.msg_cd, msg1=body.msg1, output=results)


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_order_resv_ccnl(rsvn_ord_ord_dt="20260101", rsvn_ord_end_dt="20261231")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
