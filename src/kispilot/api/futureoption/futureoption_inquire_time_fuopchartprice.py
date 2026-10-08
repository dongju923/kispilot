# 선물옵션 분봉조회[v1_국내선물-012]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice"
# ※ 한 번의 호출에 최대 102건까지 확인 가능. 입력 일자·시간(FID_INPUT_DATE_1/FID_INPUT_HOUR_1) 이전 봉부터
#   최근 순으로 온다. 더 과거는 받은 봉 중 가장 이른 일자·시간을 다시 넣어 이어서 조회한다 (일자를 넘어서도 이어짐).
# ※ 야간(CM/EU) 봉의 체결 시간은 24시를 넘겨 표기된다 (ex 280500 = 다음 날 04:05, 300000 = 06:00).

_TR_ID = "FHKIF03020200"  # 실전/모의 동일


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    futs_prdy_vrss: Optional[str] = None                    # 선물 전일 대비
    prdy_vrss_sign: Optional[str] = None                    # 전일 대비 부호
    futs_prdy_ctrt: Optional[str] = None                    # 선물 전일 대비율
    futs_prdy_clpr: Optional[str] = None                    # 선물 전일 종가
    prdy_nmix: Optional[str] = None                         # 전일 지수
    acml_vol: Optional[str] = None                          # 누적 거래량
    acml_tr_pbmn: Optional[str] = None                      # 누적 거래 대금
    hts_kor_isnm: Optional[str] = None                      # HTS 한글 종목명
    futs_prpr: Optional[str] = None                         # 선물 현재가
    futs_shrn_iscd: Optional[str] = None                    # 선물 단축 종목코드
    prdy_vol: Optional[str] = None                          # 전일 거래량
    futs_mxpr: Optional[str] = None                         # 선물 상한가
    futs_llam: Optional[str] = None                         # 선물 하한가
    futs_oprc: Optional[str] = None                         # 선물 시가2
    futs_hgpr: Optional[str] = None                         # 선물 최고가
    futs_lwpr: Optional[str] = None                         # 선물 최저가
    futs_prdy_oprc: Optional[str] = None                    # 선물 전일 시가
    futs_prdy_hgpr: Optional[str] = None                    # 선물 전일 최고가
    futs_prdy_lwpr: Optional[str] = None                    # 선물 전일 최저가
    futs_askp: Optional[str] = None                         # 선물 매도호가
    futs_bidp: Optional[str] = None                         # 선물 매수호가
    basis: Optional[str] = None                             # 베이시스
    kospi200_nmix: Optional[str] = None                     # KOSPI200 지수
    hts_otst_stpl_qty: Optional[str] = None                 # HTS 미결제 약정 수량
    otst_stpl_qty_icdc: Optional[str] = None                # 미결제 약정 수량 증감
    tday_rltv: Optional[str] = None                         # 당일 체결강도
    hts_thpr: Optional[str] = None                          # HTS 이론가
    dprt: Optional[str] = None                              # 괴리율


@dataclass
class ResponseBodyOutput2:
    stck_bsop_date: Optional[str] = None                    # 영업 일자
    stck_cntg_hour: Optional[str] = None                    # 체결 시간 (봉 시각, HHMMSS. 야간은 24시 이상으로 표기)
    futs_prpr: Optional[str] = None                         # 선물 현재가 (종가)
    futs_oprc: Optional[str] = None                         # 선물 시가2
    futs_hgpr: Optional[str] = None                         # 선물 최고가
    futs_lwpr: Optional[str] = None                         # 선물 최저가
    cntg_vol: Optional[str] = None                          # 체결 거래량
    acml_tr_pbmn: Optional[str] = None                      # 누적 거래 대금


@dataclass
class ResponseBody:
    rt_cd: str                                                          # 성공 실패 여부
    msg_cd: str                                                         # 응답코드
    msg1: str                                                           # 응답메세지
    output1: ResponseBodyOutput1                                        # 종목 현재가 요약(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)    # 분봉 시세(배열, 최근 순 최대 102건)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_time_fuopchartprice(
    code: str,
    market_div: Literal["F", "O", "JF", "JO", "CF", "CM", "EU"],
    input_hour: str,
    input_date: str,
    hour_cls_code: Literal["30", "60", "300", "1800", "3600"] = "60",
    pw_data_incu_yn: Literal["Y", "N"] = "Y",
    fake_tick_incu_yn: Literal["Y", "N"] = "N",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """선물옵션 분봉을 조회한다. 한 번의 호출에 최대 102건까지 확인 가능하다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 선물옵션 단축코드(ex A01612 KOSPI200 선물 2026년 12월물).
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). F:지수선물, O:지수옵션, JF:주식선물,
            JO:주식옵션, CF:상품선물(금·국채·달러), CM:야간선물, EU:야간옵션.
        input_hour: 입력 시간1(FID_INPUT_HOUR_1). HHMMSS. 이 시각 이전 봉부터 조회. 최근부터는 "999999".
        input_date: 입력 날짜1(FID_INPUT_DATE_1). YYYYMMDD.
        hour_cls_code: 시간 구분 코드(FID_HOUR_CLS_CODE), 봉 간격(초). 30:30초, 60:1분, 300:5분,
            1800:30분, 3600:60분. 기본값 "60".
        pw_data_incu_yn: 과거 데이터 포함 여부(FID_PW_DATA_INCU_YN). Y:과거 포함, N:당일. 기본값 "Y".
        fake_tick_incu_yn: 허봉 포함 여부(FID_FAKE_TICK_INCU_YN). Y/N. 기본값 "N".
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
        "FID_HOUR_CLS_CODE": hour_cls_code,
        "FID_PW_DATA_INCU_YN": pw_data_incu_yn,
        "FID_FAKE_TICK_INCU_YN": fake_tick_incu_yn,
        "FID_INPUT_DATE_1": input_date,
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
    result = inquire_time_fuopchartprice(code="A01612", market_div="F", input_hour="999999", input_date="20261008")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
