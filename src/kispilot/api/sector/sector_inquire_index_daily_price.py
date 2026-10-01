# 국내업종 일자별지수[v1_국내주식-065]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-index-daily-price"
# ※ 모의투자 미지원 (실전투자 전용). 한 번의 호출에 최대 100건까지 확인 가능.

_TR_ID = "FHPUP02120000"
_FID_COND_MRKT_DIV_CODE = "U"  # 업종 고정값


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    bstp_nmix_prpr: Optional[str] = None                     # 업종 지수 현재가
    bstp_nmix_prdy_vrss: Optional[str] = None                # 업종 지수 전일 대비
    prdy_vrss_sign: Optional[str] = None                     # 전일 대비 부호
    bstp_nmix_prdy_ctrt: Optional[str] = None                # 업종 지수 전일 대비율
    acml_vol: Optional[str] = None                           # 누적 거래량
    acml_tr_pbmn: Optional[str] = None                       # 누적 거래 대금
    bstp_nmix_oprc: Optional[str] = None                     # 업종 지수 시가2
    bstp_nmix_hgpr: Optional[str] = None                     # 업종 지수 최고가
    bstp_nmix_lwpr: Optional[str] = None                     # 업종 지수 최저가
    prdy_vol: Optional[str] = None                           # 전일 거래량
    ascn_issu_cnt: Optional[str] = None                      # 상승 종목 수
    down_issu_cnt: Optional[str] = None                      # 하락 종목 수
    stnr_issu_cnt: Optional[str] = None                      # 보합 종목 수
    uplm_issu_cnt: Optional[str] = None                      # 상한 종목 수
    lslm_issu_cnt: Optional[str] = None                      # 하한 종목 수
    prdy_tr_pbmn: Optional[str] = None                       # 전일 거래 대금
    dryy_bstp_nmix_hgpr_date: Optional[str] = None           # 연중업종지수최고가일자
    dryy_bstp_nmix_hgpr: Optional[str] = None                # 연중업종지수최고가
    dryy_bstp_nmix_lwpr: Optional[str] = None                # 연중업종지수최저가
    dryy_bstp_nmix_lwpr_date: Optional[str] = None           # 연중업종지수최저가일자


@dataclass
class ResponseBodyOutput2:
    stck_bsop_date: str      # 주식 영업 일자
    bstp_nmix_prpr: str      # 업종 지수 현재가
    prdy_vrss_sign: str      # 전일 대비 부호
    bstp_nmix_prdy_vrss: str # 업종 지수 전일 대비
    bstp_nmix_prdy_ctrt: str # 업종 지수 전일 대비율
    bstp_nmix_oprc: str      # 업종 지수 시가2
    bstp_nmix_hgpr: str      # 업종 지수 최고가
    bstp_nmix_lwpr: str      # 업종 지수 최저가
    acml_vol_rlim: str       # 누적 거래량 비중
    acml_vol: str            # 누적 거래량
    acml_tr_pbmn: str        # 누적 거래 대금
    invt_new_psdg: str       # 투자 신 심리도
    d20_dsrt: str            # 20일 이격도


@dataclass
class ResponseBody:
    rt_cd: str                                                          # 성공 실패 여부
    msg_cd: str                                                         # 응답코드
    msg1: str                                                           # 응답메세지
    output1: ResponseBodyOutput1                                        # 업종 지수 요약(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)    # 일자별지수(배열, 최대 100건)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_index_daily_price(
    iscd: str,
    date: str,
    period_div: Literal["D", "W", "M"] = "D",
) -> ResponseBody:
    """국내업종 일자별지수를 조회한다. 한 번의 호출에 최대 100건까지 확인 가능하다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0212] 업종 일자별지수 화면과 동일한 기능.

    Args:
        iscd: 입력 종목코드(FID_INPUT_ISCD). 코스피(0001), 코스닥(1001), 코스피200(2001) 등
            업종코드. (포탈 FAQ : 종목정보 다운로드(국내) - 업종코드 참조)
        date: 입력 날짜1(FID_INPUT_DATE_1). YYYYMMDD.
        period_div: 기간분류코드(FID_PERIOD_DIV_CODE). D:일별/W:주별/M:월별. 기본값 "D".

    Returns:
        rt_cd/msg_cd/msg1과 업종 지수 요약(output1), 일자별지수(output2)를 담은 ResponseBody.
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
        "FID_PERIOD_DIV_CODE": period_div,
        "FID_COND_MRKT_DIV_CODE": _FID_COND_MRKT_DIV_CODE,
        "FID_INPUT_ISCD": iscd,
        "FID_INPUT_DATE_1": date,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
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
    result = inquire_index_daily_price(iscd="0001", date="20240223")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
