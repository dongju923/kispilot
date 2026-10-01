# 종합 시황/공시(제목)[국내주식-141]
from dataclasses import dataclass, field
from typing import List

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/news-title"
# ※ 모의투자 미지원 (실전투자 전용).

_TR_ID = "FHKST01011800"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    cntt_usiq_srno: str        # 내용 조회용 일련번호
    news_ofer_entp_code: str   # 뉴스 제공 업체 코드
    data_dt: str               # 작성일자
    data_tm: str               # 작성시간
    hts_pbnt_titl_cntt: str    # HTS 공시 제목 내용
    news_lrdv_code: str        # 뉴스 대구분
    dorg: str                  # 자료원
    iscd1: str                 # 종목 코드1
    iscd2: str                 # 종목 코드2
    iscd3: str                 # 종목 코드3
    iscd4: str                 # 종목 코드4
    iscd5: str                 # 종목 코드5


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 종합 시황/공시 제목(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def news_title(
    news_ofer_entp_code: str = "",
    cond_mrkt_cls_code: str = "",
    iscd: str = "",
    titl_cntt: str = "",
    date: str = "",
    hour: str = "",
    rank_sort_cls_code: str = "",
    input_srno: str = "",
) -> ResponseBody:
    """종합 시황/공시(제목)를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0601] 종합 시황/공시 화면의 "우측 상단 리스트" 기능과 동일.

    Args:
        news_ofer_entp_code: 뉴스 제공 업체 코드(FID_NEWS_OFER_ENTP_CODE). 공백 필수 입력.
        cond_mrkt_cls_code: 조건 시장 구분 코드(FID_COND_MRKT_CLS_CODE). 공백 필수 입력.
        iscd: 입력 종목코드(FID_INPUT_ISCD). 공백:전체, 종목코드:해당코드가 등록된 뉴스.
        titl_cntt: 제목 내용(FID_TITL_CNTT). 공백 필수 입력.
        date: 입력 날짜(FID_INPUT_DATE_1). 공백:현재기준, 조회일자(ex 00YYYYMMDD).
        hour: 입력 시간(FID_INPUT_HOUR_1). 공백:현재기준, 조회시간(ex 0000HHMMSS).
        rank_sort_cls_code: 순위 정렬 구분 코드(FID_RANK_SORT_CLS_CODE). 공백 필수 입력.
        input_srno: 입력 일련번호(FID_INPUT_SRNO). 공백 필수 입력.

    Returns:
        rt_cd/msg_cd/msg1과 종합 시황/공시 제목 상세(output)를 담은 ResponseBody.
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
        "FID_NEWS_OFER_ENTP_CODE": news_ofer_entp_code,
        "FID_COND_MRKT_CLS_CODE": cond_mrkt_cls_code,
        "FID_INPUT_ISCD": iscd,
        "FID_TITL_CNTT": titl_cntt,
        "FID_INPUT_DATE_1": date,
        "FID_INPUT_HOUR_1": hour,
        "FID_RANK_SORT_CLS_CODE": rank_sort_cls_code,
        "FID_INPUT_SRNO": input_srno,
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
    result = news_title(iscd="005930")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
