# 국내기관_외국인 매매종목가집계[국내주식-037]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/foreign-institution-total"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0440] 외국인/기관 매매종목 가집계 화면과 동일한 기능.
# ※ 증권사 직원이 장중에 집계/입력한 자료를 단순 누계한 수치다.
#   입력시간: 외국인 09:30, 11:20, 13:20, 14:30 / 기관종합 10:00, 11:20, 13:20, 14:30 (±10분 차이 가능).
# ※ FID_COND_MRKT_DIV_CODE(V), FID_COND_SCR_DIV_CODE(16449)는 문서상 고정값이라 파라미터로 노출하지 않는다.
# ※ 문서 표기가 Output(대문자)이라 실제 JSON 키가 소문자일 가능성을 대비해 둘 다 확인한다.

_TR_ID = "FHPTJ04400000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    hts_kor_isnm: Optional[str] = None                      # HTS 한글 종목명
    mksc_shrn_iscd: Optional[str] = None                    # 유가증권 단축 종목코드
    ntby_qty: Optional[str] = None                          # 순매수 수량
    stck_prpr: Optional[str] = None                         # 주식 현재가
    prdy_vrss_sign: Optional[str] = None                    # 전일 대비 부호
    prdy_vrss: Optional[str] = None                         # 전일 대비
    prdy_ctrt: Optional[str] = None                         # 전일 대비율
    acml_vol: Optional[str] = None                          # 누적 거래량
    frgn_ntby_qty: Optional[str] = None                     # 외국인 순매수 수량
    orgn_ntby_qty: Optional[str] = None                     # 기관계 순매수 수량
    ivtr_ntby_qty: Optional[str] = None                     # 투자신탁 순매수 수량
    bank_ntby_qty: Optional[str] = None                     # 은행 순매수 수량
    insu_ntby_qty: Optional[str] = None                     # 보험 순매수 수량
    mrbn_ntby_qty: Optional[str] = None                     # 종금 순매수 수량
    fund_ntby_qty: Optional[str] = None                     # 기금 순매수 수량
    etc_orgt_ntby_vol: Optional[str] = None                 # 기타 단체 순매수 거래량
    etc_corp_ntby_vol: Optional[str] = None                 # 기타 법인 순매수 거래량
    frgn_ntby_tr_pbmn: Optional[str] = None                 # 외국인 순매수 거래 대금(백만원, 수량*현재가)
    orgn_ntby_tr_pbmn: Optional[str] = None                 # 기관계 순매수 거래 대금(백만원)
    ivtr_ntby_tr_pbmn: Optional[str] = None                 # 투자신탁 순매수 거래 대금(백만원)
    bank_ntby_tr_pbmn: Optional[str] = None                 # 은행 순매수 거래 대금(백만원)
    insu_ntby_tr_pbmn: Optional[str] = None                 # 보험 순매수 거래 대금(백만원)
    mrbn_ntby_tr_pbmn: Optional[str] = None                 # 종금 순매수 거래 대금(백만원)
    fund_ntby_tr_pbmn: Optional[str] = None                 # 기금 순매수 거래 대금(백만원)
    etc_orgt_ntby_tr_pbmn: Optional[str] = None             # 기타 단체 순매수 거래 대금(백만원)
    etc_corp_ntby_tr_pbmn: Optional[str] = None             # 기타 법인 순매수 거래 대금(백만원)


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 매매종목 가집계(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def foreign_institution_total(
    sector_code: str,
    div_cls: Literal["0", "1"] = "0",
    rank_sort_cls: Literal["0", "1"] = "0",
    etc_cls: Literal["0", "1", "2", "3"] = "0",
) -> ResponseBody:
    """국내기관/외국인 매매종목 가집계를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0440] 외국인/기관 매매종목 가집계 화면 기능과 동일.

    Args:
        sector_code: 입력 종목코드(FID_INPUT_ISCD). 0000:전체, 0001:코스피, 1001:코스닥 등 업종코드.
        div_cls: 분류 구분 코드(FID_DIV_CLS_CODE). 0:수량정렬, 1:금액정렬. 기본값 "0".
        rank_sort_cls: 순위 정렬 구분 코드(FID_RANK_SORT_CLS_CODE). 0:순매수상위, 1:순매도상위. 기본값 "0".
        etc_cls: 기타 구분 정렬(FID_ETC_CLS_CODE). 0:전체, 1:외국인, 2:기관계, 3:기타. 기본값 "0".

    Returns:
        rt_cd/msg_cd/msg1과 종목별 가집계(output)를 담은 ResponseBody.
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
        "FID_COND_MRKT_DIV_CODE": "V",
        "FID_COND_SCR_DIV_CODE": "16449",
        "FID_INPUT_ISCD": sector_code,
        "FID_DIV_CLS_CODE": div_cls,
        "FID_RANK_SORT_CLS_CODE": rank_sort_cls,
        "FID_ETC_CLS_CODE": etc_cls,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output 키가 없거나 null일 수 있어 안전 파싱.
    # 단일 객체로 내려오는 경우에도 리스트로 감싸 동일하게 처리한다.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_output = raw.get("output") or raw.get("Output") or []
    if isinstance(raw_output, dict):
        raw_output = [raw_output]
    output = [ResponseBodyOutput(**{k: v for k, v in item.items() if k in fields}) for item in raw_output]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output=output,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = foreign_institution_total(sector_code="0001")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
