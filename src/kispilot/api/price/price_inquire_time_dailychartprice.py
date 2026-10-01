# 주식일별분봉조회[국내주식-213]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-time-dailychartprice"
# ※ 한 번의 호출에 최대 120건까지 확인 가능. FID_INPUT_DATE_1/FID_INPUT_HOUR_1로 과거일자 분봉 조회 가능
#   (당사 서버 보관 기간인 최대 1년치까지만 조회 가능).

_TR_ID = "FHKST03010230"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    prdy_vrss: Optional[str] = None          # 전일 대비
    prdy_vrss_sign: Optional[str] = None      # 전일 대비 부호
    prdy_ctrt: Optional[str] = None            # 전일 대비율
    stck_prdy_clpr: Optional[str] = None        # 주식 전일 종가
    acml_vol: Optional[str] = None               # 누적 거래량
    acml_tr_pbmn: Optional[str] = None            # 누적 거래 대금
    hts_kor_isnm: Optional[str] = None             # HTS 한글 종목명
    stck_prpr: Optional[str] = None                 # 주식 현재가


@dataclass
class ResponseBodyOutput2:
    stck_bsop_date: str    # 주식 영업 일자
    stck_cntg_hour: str      # 주식 체결 시간
    stck_prpr: str            # 주식 현재가
    stck_oprc: str              # 주식 시가2
    stck_hgpr: str                # 주식 최고가
    stck_lwpr: str                  # 주식 최저가
    cntg_vol: str                     # 체결 거래량
    acml_tr_pbmn: str                   # 누적 거래 대금


@dataclass
class ResponseBody:
    rt_cd: str                                                          # 성공 실패 여부
    msg_cd: str                                                         # 응답코드
    msg1: str                                                           # 응답메세지
    output1: ResponseBodyOutput1                                        # 종목 현재가 요약(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)    # 분봉 시세(배열, 최대 120건)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_time_dailychartprice(
    code: str,
    input_hour: str,
    input_date: str,
    pw_data_incu_yn: Literal["Y", "N"] = "N",
    fake_tick_incu_yn: str = "",
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """주식일별분봉조회(특정 과거 일자의 분봉)를 조회한다. 한 번의 호출에 최대 120건까지 확인 가능하다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930 삼성전자).
        input_hour: 입력 시간1(FID_INPUT_HOUR_1). HHMMSS.
        input_date: 입력 날짜1(FID_INPUT_DATE_1). YYYYMMDD. 조회할 과거 영업일자.
        pw_data_incu_yn: 과거 데이터 포함 여부(FID_PW_DATA_INCU_YN). Y/N. 기본값 "N".
        fake_tick_incu_yn: 허봉 포함 여부(FID_FAKE_TICK_INCU_YN). 기본값 "".
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 종목 현재가 요약(output1), 분봉 시세(output2)를 담은 ResponseBody.
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
        "FID_INPUT_DATE_1": input_date,
        "FID_PW_DATA_INCU_YN": pw_data_incu_yn,
        "FID_FAKE_TICK_INCU_YN": fake_tick_incu_yn,
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
    result = inquire_time_dailychartprice(code="005930", input_hour="130000", input_date="20241023")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
