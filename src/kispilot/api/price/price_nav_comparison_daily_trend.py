# NAV 비교추이(일)[v1_국내주식-071]
from dataclasses import dataclass, field
from typing import List, Literal

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/etfetn/v1/quotations/nav-comparison-daily-trend"
# ※ 한국투자 HTS(eFriend Plus) [0244] ETF/ETN 비교추이(NAV/IIV) "일별" 비교추이 기능에 해당.
# ※ 한 번의 호출에 최대 100건까지 확인 가능.

_TR_ID = "FHPST02440200"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stck_bsop_date: str      # 주식 영업 일자
    stck_clpr: str             # 주식 종가
    prdy_vrss: str                # 전일 대비
    prdy_vrss_sign: str              # 전일 대비 부호
    prdy_ctrt: str                     # 전일 대비율
    acml_vol: str                         # 누적 거래량
    cntg_vol: str                            # 체결 거래량
    dprt: str                                   # 괴리율
    nav_vrss_prpr: str                             # NAV 대비 현재가
    nav: str                                          # NAV
    nav_prdy_vrss_sign: str                              # NAV 전일 대비 부호
    nav_prdy_vrss: str                                      # NAV 전일 대비
    nav_prdy_ctrt: str                                         # NAV 전일 대비율


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 일자별 주가/NAV 비교(배열, 최대 100건)


# ── 요청 함수 ───────────────────────────────────────────────

def nav_comparison_daily_trend(
    code: str,
    start_date: str,
    end_date: str,
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """NAV 비교추이(일)를 조회한다. 한 번의 호출에 최대 100건까지 확인 가능하다.

    Args:
        code: 입력종목코드(FID_INPUT_ISCD), 6자리(ex 069500 KODEX 200).
        start_date: 조회시작일자(FID_INPUT_DATE_1). YYYYMMDD.
        end_date: 조회종료일자(FID_INPUT_DATE_2). YYYYMMDD.
        market_div: 조건시장분류코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 일자별 주가/NAV 비교(output)를 담은 ResponseBody.
    """
    token = load_token(mode)
    if mode == "real":
        app_key, app_secret = REAL_APPKEY, REAL_APP_SECRET
    else:
        app_key, app_secret = PAPER_APPKEY, PAPER_APP_SECRET

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": _TR_ID,
        "custtype": "P",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": market_div,
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
    }
    response = get_session().get(DOMAIN[mode] + URL, headers=headers, params=params, timeout=10)
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
    result = nav_comparison_daily_trend(code="069500", start_date="20240101", end_date="20240220")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
