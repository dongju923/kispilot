# 국내주식업종기간별시세(일/주/월/년)[v1_국내주식-021]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-daily-indexchartprice"
# ※ 실전계좌/모의계좌 모두 한 번의 호출에 최대 50건까지 확인 가능.

_TR_ID = "FHKUP03500100"
_FID_COND_MRKT_DIV_CODE = "U"  # 업종 고정값


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    prdy_vrss_sign: Optional[str] = None                     # 전일 대비 부호
    bstp_nmix_prdy_ctrt: Optional[str] = None                # 업종 지수 전일 대비율
    prdy_nmix: Optional[str] = None                          # 전일 지수
    acml_vol: Optional[str] = None                           # 누적 거래량
    acml_tr_pbmn: Optional[str] = None                       # 누적 거래 대금
    hts_kor_isnm: Optional[str] = None                       # HTS 한글 종목명
    bstp_nmix_prpr: Optional[str] = None                     # 업종 지수 현재가
    bstp_cls_code: Optional[str] = None                      # 업종 구분 코드
    prdy_vol: Optional[str] = None                           # 전일 거래량
    bstp_nmix_oprc: Optional[str] = None                     # 업종 지수 시가2
    bstp_nmix_hgpr: Optional[str] = None                     # 업종 지수 최고가
    bstp_nmix_lwpr: Optional[str] = None                     # 업종 지수 최저가
    futs_prdy_oprc: Optional[str] = None                     # 선물 전일 시가
    futs_prdy_hgpr: Optional[str] = None                     # 선물 전일 최고가
    futs_prdy_lwpr: Optional[str] = None                     # 선물 전일 최저가


@dataclass
class ResponseBodyOutput2:
    stck_bsop_date: str    # 주식 영업 일자
    bstp_nmix_prpr: str    # 업종 지수 현재가
    bstp_nmix_oprc: str    # 업종 지수 시가2
    bstp_nmix_hgpr: str    # 업종 지수 최고가
    bstp_nmix_lwpr: str    # 업종 지수 최저가
    acml_vol: str          # 누적 거래량
    acml_tr_pbmn: str      # 누적 거래 대금
    mod_yn: str            # 변경 여부


@dataclass
class ResponseBody:
    rt_cd: str                                                          # 성공 실패 여부
    msg_cd: str                                                         # 응답코드
    msg1: str                                                           # 응답메세지
    output1: ResponseBodyOutput1                                        # 업종 지수 요약(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)    # 기간별 시세(배열, 최대 50건)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_daily_indexchartprice(
    iscd: str,
    start_date: str,
    end_date: str,
    period_div: Literal["D", "W", "M", "Y"] = "D",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """국내주식 업종기간별시세(일/주/월/년봉)를 조회한다. 한 번의 호출에 최대 50건까지 확인 가능하다.

    Args:
        iscd: 업종 상세코드(FID_INPUT_ISCD). 0001:종합, 0002:대형주 등 업종코드.
            (포탈 FAQ : 종목정보 다운로드(국내) - 업종코드 참조)
        start_date: 조회 시작일자(FID_INPUT_DATE_1). YYYYMMDD.
        end_date: 조회 종료일자(FID_INPUT_DATE_2). YYYYMMDD. 시작일자와의 사이에서 최대 50건.
        period_div: 기간분류코드(FID_PERIOD_DIV_CODE). D:일봉/W:주봉/M:월봉/Y:년봉. 기본값 "D".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 업종 지수 요약(output1), 기간별 시세(output2)를 담은 ResponseBody.
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
        "FID_COND_MRKT_DIV_CODE": _FID_COND_MRKT_DIV_CODE,
        "FID_INPUT_ISCD": iscd,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": period_div,
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
    result = inquire_daily_indexchartprice(iscd="0001", start_date="20220501", end_date="20220530")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
