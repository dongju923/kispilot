# NAV 비교추이(분)[v1_국내주식-070]
from dataclasses import dataclass, field
from typing import List, Literal

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/etfetn/v1/quotations/nav-comparison-time-trend"
# ※ 한국투자 HTS(eFriend Plus) [0244] ETF/ETN 비교추이(NAV/IIV) "분별" 비교추이 기능에 해당.
# ※ 한 번의 호출에 최근 30건까지 확인 가능.

_TR_ID = "FHPST02440100"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    bsop_hour: str            # 영업 시간
    nav: str                    # NAV
    nav_prdy_vrss_sign: str        # NAV 전일 대비 부호
    nav_prdy_vrss: str                # NAV 전일 대비
    nav_prdy_ctrt: str                   # NAV 전일 대비율
    nav_vrss_prpr: str                      # NAV 대비 현재가
    dprt: str                                  # 괴리율
    stck_prpr: str                                # 주식 현재가
    prdy_vrss: str                                   # 전일 대비
    prdy_vrss_sign: str                                 # 전일 대비 부호
    prdy_ctrt: str                                         # 전일 대비율
    acml_vol: str                                             # 누적 거래량
    cntg_vol: str                                                # 체결 거래량


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 시간대별 주가/NAV 비교(배열, 최근 30건)


# ── 요청 함수 ───────────────────────────────────────────────

def nav_comparison_time_trend(
    code: str,
    hour_cls_code: str = "60",
    market_div: str = "E",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """NAV 비교추이(분)를 조회한다. 한 번의 호출에 최근 30건까지 확인 가능하다.

    Args:
        code: 입력종목코드(FID_INPUT_ISCD), 6자리(ex 069500 KODEX 200).
        hour_cls_code: 시간구분코드(FID_HOUR_CLS_CODE). 60:1분/180:3분/... /7200:120분. 기본값 "60".
        market_div: 조건시장분류코드(FID_COND_MRKT_DIV_CODE). 공식 예제 기준 "E". 기본값 "E".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 시간대별 주가/NAV 비교(output)를 담은 ResponseBody.
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
        "FID_HOUR_CLS_CODE": hour_cls_code,
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
    result = nav_comparison_time_trend(code="069500")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
