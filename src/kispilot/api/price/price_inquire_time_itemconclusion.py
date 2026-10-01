# 주식현재가 당일시간대별체결[v1_국내주식-023]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-time-itemconclusion"
# ※ 주식현재가 체결[FHKST01010300] 대비 더 많은 체결데이터가 필요할 때 사용.
#   FID_INPUT_HOUR_1로 과거 시간대 체결데이터 확인 가능.

_TR_ID = "FHPST01060000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    stck_prpr: Optional[str] = None              # 주식 현재가
    prdy_vrss: Optional[str] = None               # 전일 대비
    prdy_vrss_sign: Optional[str] = None            # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                  # 전일 대비율
    acml_vol: Optional[str] = None                     # 누적 거래량
    prdy_vol: Optional[str] = None                       # 전일 거래량
    rprs_mrkt_kor_name: Optional[str] = None               # 대표 시장 한글 명


@dataclass
class ResponseBodyOutput2:
    stck_cntg_hour: str    # 주식 체결 시간
    stck_prpr: str           # 주식 현재가
    prdy_vrss: str             # 전일 대비
    prdy_vrss_sign: str          # 전일 대비 부호
    prdy_ctrt: str                 # 전일 대비율
    askp: str                        # 매도호가
    bidp: str                          # 매수호가
    tday_rltv: str                       # 당일 체결강도
    acml_vol: str                          # 누적 거래량
    cnqn: str                                # 체결량


@dataclass
class ResponseBody:
    rt_cd: str                                                          # 성공 실패 여부
    msg_cd: str                                                         # 응답코드
    msg1: str                                                           # 응답메세지
    output1: ResponseBodyOutput1                                        # 종목 현재가 요약(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)    # 시간대별 체결(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_time_itemconclusion(
    code: str,
    input_hour: str,
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """주식현재가 당일시간대별체결을 조회한다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930 삼성전자).
        input_hour: 입력 시간1(FID_INPUT_HOUR_1). HHMMSS. 과거 시간대 체결데이터 조회에 사용.
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 종목 현재가 요약(output1), 시간대별 체결(output2)을 담은 ResponseBody.
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
        "FID_INPUT_HOUR_1": input_hour,
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
    result = inquire_time_itemconclusion(code="005930", input_hour="115959")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
