# 종목별 프로그램매매추이(일별)[국내주식-113]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/program-trade-by-stock-daily"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0465] 종목별 프로그램 매매추이 화면의 "일자별" 기능.
# ※ output은 기준일부터 과거로 30영업일이 최신순으로 내려온다(연속조회 불가).
#   거래 대금(acml_tr_pbmn, whol_smtn_*_tr_pbmn, whol_ntby_tr_pbmn_icdc2) 단위는 원이다.
# ※ 기준일은 문서 예시(0020240308)와 달리 YYYYMMDD 8자리로 줘도 동일하게 조회된다. 공란이면 당일부터 조회.
# ※ 구TR(FHPPG04650200)은 사전고지 없이 막힐 수 있어 신TR(FHPPG04650201)을 사용한다.

_TR_ID = "FHPPG04650201"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stck_bsop_date: Optional[str] = None            # 주식 영업 일자
    stck_clpr: Optional[str] = None                 # 주식 종가
    prdy_vrss: Optional[str] = None                 # 전일 대비
    prdy_vrss_sign: Optional[str] = None            # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                 # 전일 대비율
    acml_vol: Optional[str] = None                  # 누적 거래량
    acml_tr_pbmn: Optional[str] = None              # 누적 거래 대금(원)
    whol_smtn_seln_vol: Optional[str] = None        # 전체 합계 매도 거래량
    whol_smtn_shnu_vol: Optional[str] = None        # 전체 합계 매수2 거래량
    whol_smtn_ntby_qty: Optional[str] = None        # 전체 합계 순매수 수량
    whol_smtn_seln_tr_pbmn: Optional[str] = None    # 전체 합계 매도 거래 대금(원)
    whol_smtn_shnu_tr_pbmn: Optional[str] = None    # 전체 합계 매수2 거래 대금(원)
    whol_smtn_ntby_tr_pbmn: Optional[str] = None    # 전체 합계 순매수 거래 대금(원)
    whol_ntby_vol_icdc: Optional[str] = None        # 전체 순매수 거래량 증감(전일 대비)
    whol_ntby_tr_pbmn_icdc2: Optional[str] = None   # 전체 순매수 거래 대금 증감2(전일 대비, 원)


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 일별 프로그램 매매추이(배열, 최신순, 30영업일)


# ── 요청 함수 ───────────────────────────────────────────────

def program_trade_by_stock_daily(
    code: str,
    date: str = "",
    market_div: Literal["J", "NX", "UN"] = "J",
) -> ResponseBody:
    """종목별 프로그램매매추이(일별)를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0465] 종목별 프로그램 매매추이 화면의 "일자별" 기능과 동일.
    기준일부터 과거로 30영업일의 일별 프로그램 매매 합계가 내려온다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930).
        date: 기준일(FID_INPUT_DATE_1), YYYYMMDD(ex 20240308). 공란이면 당일부터 조회. 기본값 "".
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".

    Returns:
        rt_cd/msg_cd/msg1과 일별 프로그램 매매추이(output)를 담은 ResponseBody.
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
        "FID_COND_MRKT_DIV_CODE": market_div,
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": date,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output 키가 없거나 null일 수 있어 안전 파싱.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_output = raw.get("output") or []
    output = [ResponseBodyOutput(**{k: v for k, v in item.items() if k in fields}) for item in raw_output]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output=output,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = program_trade_by_stock_daily(code="005930")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
