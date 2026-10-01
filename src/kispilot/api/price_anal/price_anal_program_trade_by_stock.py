# 종목별 프로그램매매추이(체결)[v1_국내주식-044]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/program-trade-by-stock"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0465] 종목별 프로그램 매매추이 화면과 동일한 기능.
# ※ output은 당일 체결 시각별 프로그램 매매 추이가 최신순으로 최대 30건 내려온다(연속조회 불가).
#   whol_smtn_*는 해당 시각까지의 누적값이며, 거래 대금 단위는 원이다.
# ※ 구TR(FHPPG04650100)은 사전고지 없이 막힐 수 있어 신TR(FHPPG04650101)을 사용한다.

_TR_ID = "FHPPG04650101"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    bsop_hour: Optional[str] = None                 # 영업 시간(HHMMSS)
    stck_prpr: Optional[str] = None                 # 주식 현재가
    prdy_vrss: Optional[str] = None                 # 전일 대비
    prdy_vrss_sign: Optional[str] = None            # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                 # 전일 대비율
    acml_vol: Optional[str] = None                  # 누적 거래량
    whol_smtn_seln_vol: Optional[str] = None        # 전체 합계 매도 거래량
    whol_smtn_shnu_vol: Optional[str] = None        # 전체 합계 매수2 거래량
    whol_smtn_ntby_qty: Optional[str] = None        # 전체 합계 순매수 수량
    whol_smtn_seln_tr_pbmn: Optional[str] = None    # 전체 합계 매도 거래 대금(원)
    whol_smtn_shnu_tr_pbmn: Optional[str] = None    # 전체 합계 매수2 거래 대금(원)
    whol_smtn_ntby_tr_pbmn: Optional[str] = None    # 전체 합계 순매수 거래 대금(원)
    whol_ntby_vol_icdc: Optional[str] = None        # 전체 순매수 거래량 증감
    whol_ntby_tr_pbmn_icdc: Optional[str] = None    # 전체 순매수 거래 대금 증감


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 시각별 프로그램 매매추이(배열, 최신순, 최대 30건)


# ── 요청 함수 ───────────────────────────────────────────────

def program_trade_by_stock(
    code: str,
    market_div: Literal["J", "NX", "UN"] = "J",
) -> ResponseBody:
    """종목별 프로그램매매추이(체결)를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0465] 종목별 프로그램 매매추이 화면 기능과 동일.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930).
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".

    Returns:
        rt_cd/msg_cd/msg1과 시각별 프로그램 매매추이(output)를 담은 ResponseBody.
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
    result = program_trade_by_stock(code="005930")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
