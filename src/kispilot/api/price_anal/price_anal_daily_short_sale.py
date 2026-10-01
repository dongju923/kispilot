# 국내주식 공매도 일별추이[국내주식-134]
from dataclasses import dataclass, field
from typing import List, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/daily-short-sale"
# ※ 모의투자 미지원 (실전투자 전용).
# ※ output2는 종료일(FID_INPUT_DATE_2)부터 과거로 최신순, 최대 100영업일까지 내려온다(연속조회 불가).
#   시작일(FID_INPUT_DATE_1)이 공란이거나 100영업일보다 이전이어도 100건에서 잘린다.
# ※ acml_*(누적) 필드는 시작일부터 해당 일자까지의 누적값이라, 시작일에 따라 같은 날짜라도 값이 달라진다.
#   stnd_*_smtn(기준 합계)도 같은 누적 구간의 거래량/거래대금 합계다. 거래 대금 단위는 원이다.
# ※ 시작일이 종료일보다 늦으면 에러 없이 빈 객체({})들이 내려와서, 영업일자가 없는 행은 제외한다.
# ※ FID_COND_MRKT_DIV_CODE는 문서상 주식 "J" 고정값이라 파라미터로 노출하지 않는다.

_TR_ID = "FHPST04830000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    stck_prpr: Optional[str] = None             # 주식 현재가
    prdy_vrss: Optional[str] = None             # 전일 대비
    prdy_vrss_sign: Optional[str] = None        # 전일 대비 부호
    prdy_ctrt: Optional[str] = None             # 전일 대비율
    acml_vol: Optional[str] = None              # 누적 거래량
    prdy_vol: Optional[str] = None              # 전일 거래량


@dataclass
class ResponseBodyOutput2:
    stck_bsop_date: Optional[str] = None            # 주식 영업 일자
    stck_clpr: Optional[str] = None                 # 주식 종가
    prdy_vrss: Optional[str] = None                 # 전일 대비
    prdy_vrss_sign: Optional[str] = None            # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                 # 전일 대비율
    acml_vol: Optional[str] = None                  # 누적 거래량(당일)
    stnd_vol_smtn: Optional[str] = None             # 기준 거래량 합계(시작일~해당일)
    ssts_cntg_qty: Optional[str] = None             # 공매도 체결 수량(당일)
    ssts_vol_rlim: Optional[str] = None             # 공매도 거래량 비중(당일, %)
    acml_ssts_cntg_qty: Optional[str] = None        # 누적 공매도 체결 수량(시작일~해당일)
    acml_ssts_cntg_qty_rlim: Optional[str] = None   # 누적 공매도 체결 수량 비중(%)
    acml_tr_pbmn: Optional[str] = None              # 누적 거래 대금(당일, 원)
    stnd_tr_pbmn_smtn: Optional[str] = None         # 기준 거래대금 합계(시작일~해당일, 원)
    ssts_tr_pbmn: Optional[str] = None              # 공매도 거래 대금(당일, 원)
    ssts_tr_pbmn_rlim: Optional[str] = None         # 공매도 거래대금 비중(당일, %)
    acml_ssts_tr_pbmn: Optional[str] = None         # 누적 공매도 거래 대금(시작일~해당일, 원)
    acml_ssts_tr_pbmn_rlim: Optional[str] = None    # 누적 공매도 거래 대금 비중(%)
    stck_oprc: Optional[str] = None                 # 주식 시가2
    stck_hgpr: Optional[str] = None                 # 주식 최고가
    stck_lwpr: Optional[str] = None                 # 주식 최저가
    avrg_prc: Optional[str] = None                  # 평균가격


@dataclass
class ResponseBody:
    rt_cd: str                                                                  # 성공 실패 여부
    msg_cd: str                                                                 # 응답코드
    msg1: str                                                                   # 응답메세지
    output1: ResponseBodyOutput1 = field(default_factory=ResponseBodyOutput1)   # 종목 현재 시세(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)            # 일별 공매도 추이(배열, 최신순, 최대 100건)


# ── 요청 함수 ───────────────────────────────────────────────

def daily_short_sale(
    code: str,
    end_date: str,
    start_date: str = "",
) -> ResponseBody:
    """국내주식 공매도 일별추이를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    종료일부터 과거로 최대 100영업일의 일별 공매도 체결 수량/대금과 비중이 내려온다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930).
        end_date: 조회 종료일(FID_INPUT_DATE_2), YYYYMMDD.
        start_date: 조회 시작일(FID_INPUT_DATE_1), YYYYMMDD. 공란이면 전체(최대 100건). 누적(acml_*)
            필드의 기준 시작일이 된다. 기본값 "".

    Returns:
        rt_cd/msg_cd/msg1과 종목 현재 시세(output1), 일별 공매도 추이(output2)를 담은 ResponseBody.
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
        "FID_INPUT_DATE_2": end_date,
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": start_date,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1/output2 키가 없거나 null일 수 있어 안전 파싱.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or {}
    output1 = ResponseBodyOutput1(**{k: v for k, v in raw_output1.items() if k in fields1})

    # 시작일 > 종료일이면 빈 객체({})가 섞여 내려오므로 영업일자가 없는 행은 제외한다.
    fields2 = set(ResponseBodyOutput2.__dataclass_fields__)
    raw_output2 = raw.get("output2") or []
    output2 = [
        ResponseBodyOutput2(**{k: v for k, v in item.items() if k in fields2})
        for item in raw_output2
        if item.get("stck_bsop_date")
    ]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
        output2=output2,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = daily_short_sale(code="005930", end_date="20260921", start_date="20260921")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
