# ETF 구성종목시세[국내주식-073]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/etfetn/v1/quotations/inquire-component-stock-price"
# ※ 한국투자 HTS(eFriend Plus) [0245] ETF/ETN 구성종목시세 화면 기능에 해당.

_TR_ID = "FHKST121600C0"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    stck_prpr: Optional[str] = None                     # 주식 현재가
    prdy_vrss: Optional[str] = None                       # 전일 대비
    prdy_vrss_sign: Optional[str] = None                    # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                          # 전일 대비율
    acml_vol: Optional[str] = None                             # 누적 거래량
    acml_tr_pbmn: Optional[str] = None                           # 누적 거래 대금
    stck_prdy_clpr: Optional[str] = None                          # 주식 전일 종가
    stck_oprc: Optional[str] = None                                 # 주식 시가2
    stck_hgpr: Optional[str] = None                                   # 주식 최고가
    stck_lwpr: Optional[str] = None                                    # 주식 최저가
    stck_mxpr: Optional[str] = None                                     # 주식 상한가
    stck_llam: Optional[str] = None                                      # 주식 하한가
    nav: Optional[str] = None                                             # NAV
    nav_prdy_vrss_sign: Optional[str] = None                               # NAV 전일 대비 부호
    nav_prdy_vrss: Optional[str] = None                                     # NAV 전일 대비
    nav_prdy_ctrt: Optional[str] = None                                      # NAV 전일 대비율
    prdy_clpr_nav: Optional[str] = None                                       # NAV 전일 종가
    oprc_nav: Optional[str] = None                                             # NAV 시가
    hprc_nav: Optional[str] = None                                              # NAV 고가
    lprc_nav: Optional[str] = None                                               # NAV 저가
    etf_cu_unit_scrt_cnt: Optional[str] = None                                    # ETF CU 단위 증권 수
    etf_cnfg_issu_cnt: Optional[str] = None                                        # ETF 구성 종목 수


@dataclass
class ResponseBodyOutput2:
    stck_shrn_iscd: str      # 주식 단축 종목코드
    hts_kor_isnm: str          # HTS 한글 종목명
    acml_vol: str                # 누적 거래량
    acml_tr_pbmn: str              # 누적 거래 대금
    tday_rsfl_rate: str              # 당일 등락 비율
    prdy_vrss_vol: str                 # 전일 대비 거래량
    tr_pbmn_tnrt: str                    # 거래대금회전율
    hts_avls: str                          # HTS 시가총액
    etf_vltn_amt: str                        # ETF 구성종목 평가금액
    etf_cnfg_issu_rlim: str                    # ETF 구성종목 비중


@dataclass
class ResponseBody:
    rt_cd: str                                                          # 성공 실패 여부
    msg_cd: str                                                         # 응답코드
    msg1: str                                                           # 응답메세지
    output1: ResponseBodyOutput1                                        # ETF 기본/NAV 정보(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)    # 구성종목별 시세(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_etf_component_stock_price(
    code: str,
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """ETF 구성종목시세를 조회한다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 069500 KODEX 200).
        market_div: 조건시장분류코드(FID_COND_MRKT_DIV_CODE). J:주식/ETF/ETN. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 ETF 기본/NAV 정보(output1), 구성종목별 시세(output2)를 담은 ResponseBody.
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
        "FID_COND_SCR_DIV_CODE": "11216",
    }
    response = get_session().get(DOMAIN[mode] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1/output2 키가 없거나 null일 수 있어 안전 파싱.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or {}
    output1 = ResponseBodyOutput1(**{k: v for k, v in raw_output1.items() if k in fields1})

    fields2 = set(ResponseBodyOutput2.__dataclass_fields__)
    raw_output2 = raw.get("output2") or []
    output2 = [ResponseBodyOutput2(**{k: v for k, v in item.items() if k in fields2}) for item in raw_output2]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
        output2=output2,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_etf_component_stock_price(code="069500")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
