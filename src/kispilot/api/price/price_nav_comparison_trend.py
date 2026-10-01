# NAV 비교추이(종목)[v1_국내주식-069]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/etfetn/v1/quotations/nav-comparison-trend"
# ※ 한국투자 HTS(eFriend Plus) [0244] ETF/ETN 비교추이(NAV/IIV) 좌측 화면 기능에 해당.

_TR_ID = "FHPST02440000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    stck_prpr: Optional[str] = None          # 주식 현재가
    prdy_vrss: Optional[str] = None            # 전일 대비
    prdy_vrss_sign: Optional[str] = None         # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                # 전일 대비율
    acml_vol: Optional[str] = None                   # 누적 거래량
    acml_tr_pbmn: Optional[str] = None                 # 누적 거래 대금
    stck_prdy_clpr: Optional[str] = None                 # 주식 전일 종가
    stck_oprc: Optional[str] = None                        # 주식 시가2
    stck_hgpr: Optional[str] = None                          # 주식 최고가
    stck_lwpr: Optional[str] = None                            # 주식 최저가
    stck_mxpr: Optional[str] = None                             # 주식 상한가
    stck_llam: Optional[str] = None                              # 주식 하한가


@dataclass
class ResponseBodyOutput2:
    nav: Optional[str] = None                        # NAV
    nav_prdy_vrss_sign: Optional[str] = None           # NAV 전일 대비 부호
    nav_prdy_vrss: Optional[str] = None                  # NAV 전일 대비
    nav_prdy_ctrt: Optional[str] = None                    # NAV 전일 대비율
    prdy_clpr_nav: Optional[str] = None                      # NAV 전일 종가
    oprc_nav: Optional[str] = None                             # NAV 시가
    hprc_nav: Optional[str] = None                               # NAV 고가
    lprc_nav: Optional[str] = None                                # NAV 저가


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output1: ResponseBodyOutput1        # 주가 시세(단일)
    output2: ResponseBodyOutput2        # NAV 시세(단일)


# ── 요청 함수 ───────────────────────────────────────────────

def nav_comparison_trend(
    code: str,
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """NAV 비교추이(종목) — 주가와 NAV 시세를 함께 조회한다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 069500 KODEX 200).
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 주가 시세(output1), NAV 시세(output2)를 담은 ResponseBody.
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
    }
    response = get_session().get(DOMAIN[mode] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1/output2 키가 없거나 null일 수 있어 안전 파싱.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or {}
    output1 = ResponseBodyOutput1(**{k: v for k, v in raw_output1.items() if k in fields1})

    fields2 = set(ResponseBodyOutput2.__dataclass_fields__)
    raw_output2 = raw.get("output2") or {}
    output2 = ResponseBodyOutput2(**{k: v for k, v in raw_output2.items() if k in fields2})

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
        output2=output2,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = nav_comparison_trend(code="069500")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        print(result.output2)
