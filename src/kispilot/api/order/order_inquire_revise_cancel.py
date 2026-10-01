# 주식정정취소가능주문조회[v1_국내주식-004]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, CANO, ACNT_PRDT_CD, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/trading/inquire-psbl-rvsecncl"
# ※ 모의투자 미지원 (실전투자 전용). 한 번에 최대 50건, 그 이상은 연속조회(tr_cont)로 이어받는다.
# ※ 주문 정정/취소(order_revise_cancel.py) 호출 전에 반드시 이 API로 정정취소가능수량(output.psbl_qty)을 먼저 확인할 것.

# ord_dvsn_cd(주문구분코드) 코드표는 order_cash.py 상단 ORD_DVSN 코드표와 동일.

_TR_ID = "TTTC0084R"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    ord_gno_brno: Optional[str] = None           # 주문채번지점번호
    odno: Optional[str] = None                   # 주문번호
    orgn_odno: Optional[str] = None               # 원주문번호(정정/취소주문인 경우)
    ord_dvsn_name: Optional[str] = None           # 주문구분명
    pdno: Optional[str] = None                    # 상품번호(종목번호 뒤 6자리)
    prdt_name: Optional[str] = None               # 상품명(종목명)
    rvse_cncl_dvsn_name: Optional[str] = None      # 정정취소구분명
    ord_qty: Optional[str] = None                  # 주문수량
    ord_unpr: Optional[str] = None                 # 주문단가(1주당 주문가격)
    ord_tmd: Optional[str] = None                  # 주문시각(HHMMSS)
    tot_ccld_qty: Optional[str] = None             # 총체결수량(주문 수량 중 체결된 수량)
    tot_ccld_amt: Optional[str] = None             # 총체결금액(주문금액 중 체결금액)
    psbl_qty: Optional[str] = None                 # 정정/취소 주문 가능수량
    sll_buy_dvsn_cd: Optional[str] = None          # 매도매수구분코드(01:매도, 02:매수)
    ord_dvsn_cd: Optional[str] = None              # 주문구분코드
    mgco_aptm_odno: Optional[str] = None           # 운용사지정주문번호
    excg_dvsn_cd: Optional[str] = None             # 거래소구분코드
    excg_id_dvsn_cd: Optional[str] = None          # 거래소ID구분코드(KRX/NXT/SOR)
    excg_id_dvsn_name: Optional[str] = None        # 거래소ID구분명
    stpm_cndt_pric: Optional[str] = None           # 스톱지정가조건가격
    stpm_efct_occr_yn: Optional[str] = None        # 스톱지정가효력발생여부


@dataclass
class ResponseBody:
    rt_cd: str                                              # 성공 실패 여부
    msg_cd: str                                             # 응답코드
    msg1: str                                               # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 정정취소가능주문 목록(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def _fetch_page(
    inqr_dvsn_1: str,
    inqr_dvsn_2: str,
    ctx_area_fk100: str,
    ctx_area_nk100: str,
    tr_cont: str,
) -> tuple[ResponseBody, str, str, str]:
    """정정취소가능주문을 한 페이지(최대 50건)만 조회한다.

    Args:
        inqr_dvsn_1: 조회구분1(INQR_DVSN_1). 0 주문 / 1 종목.
        inqr_dvsn_2: 조회구분2(INQR_DVSN_2). 0 전체 / 1 매도 / 2 매수.
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
        "CANO": CANO,
        "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "CTX_AREA_FK100": ctx_area_fk100,
        "CTX_AREA_NK100": ctx_area_nk100,
        "INQR_DVSN_1": inqr_dvsn_1,
        "INQR_DVSN_2": inqr_dvsn_2,
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
    next_fk100 = raw.get("ctx_area_fk100", "") or ""
    next_nk100 = raw.get("ctx_area_nk100", "") or ""

    return body, next_tr_cont, next_fk100, next_nk100


def inquire_psbl_rvsecncl(
    inqr_dvsn_1: Literal["0", "1"] = "0",   # 0:주문 1:종목
    inqr_dvsn_2: Literal["0", "1", "2"] = "0",   # 0:전체 1:매도 2:매수
) -> ResponseBody:
    """정정취소 가능한 주문을 전부 조회한다.

    1회 호출은 최대 50건까지만 돌아오므로, 응답 헤더의 tr_cont가 "F"/"M"(다음 데이터 있음)인 동안
    CTX_AREA_FK100/CTX_AREA_NK100을 이어받아 자동으로 연속조회하며, "D"/"E"(마지막 데이터)가 되면 멈춘다.

    Args:
        inqr_dvsn_1: 조회구분1. "0"(주문 단위) 또는 "1"(종목 단위). 기본값 "0".
        inqr_dvsn_2: 조회구분2. "0"(전체)/"1"(매도)/"2"(매수). 기본값 "0".

    Returns:
        rt_cd/msg_cd/msg1(마지막으로 받은 페이지 기준)과, 모든 페이지를 합친 정정취소가능주문
        목록(output, 정정취소가능수량은 각 항목의 psbl_qty)을 담은 ResponseBody.
        실패 여부는 반드시 rt_cd로 확인할 것.
    """
    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    tr_cont = ""  # 공백: 최초 조회

    results: List[ResponseBodyOutput] = []
    body = ResponseBody(rt_cd="", msg_cd="", msg1="")

    while True:
        body, next_tr_cont, ctx_area_fk100, ctx_area_nk100 = _fetch_page(
            inqr_dvsn_1, inqr_dvsn_2, ctx_area_fk100, ctx_area_nk100, tr_cont
        )
        results.extend(body.output)

        if body.rt_cd != "0" or next_tr_cont not in ("F", "M"):
            break
        tr_cont = "N"  # 다음 페이지 조회

    return ResponseBody(rt_cd=body.rt_cd, msg_cd=body.msg_cd, msg1=body.msg1, output=results)


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_psbl_rvsecncl()
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
