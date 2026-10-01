# 국내주식기간별시세(일/주/월/년)[v1_국내주식-016]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
# ※ 한 번의 호출에 최대 100건(일/주/월/년봉)까지 확인 가능.

_TR_ID = "FHKST03010100"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    prdy_vrss: Optional[str] = None                # 전일 대비
    prdy_vrss_sign: Optional[str] = None            # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                  # 전일 대비율
    stck_prdy_clpr: Optional[str] = None              # 주식 전일 종가
    acml_vol: Optional[str] = None                     # 누적 거래량
    acml_tr_pbmn: Optional[str] = None                   # 누적 거래 대금
    hts_kor_isnm: Optional[str] = None                    # HTS 한글 종목명
    stck_prpr: Optional[str] = None                         # 주식 현재가
    stck_shrn_iscd: Optional[str] = None                     # 주식 단축 종목코드
    prdy_vol: Optional[str] = None                            # 전일 거래량
    stck_mxpr: Optional[str] = None                            # 주식 상한가
    stck_llam: Optional[str] = None                             # 주식 하한가
    stck_oprc: Optional[str] = None                              # 주식 시가2
    stck_hgpr: Optional[str] = None                               # 주식 최고가
    stck_lwpr: Optional[str] = None                                # 주식 최저가
    stck_prdy_oprc: Optional[str] = None                            # 주식 전일 시가
    stck_prdy_hgpr: Optional[str] = None                             # 주식 전일 최고가
    stck_prdy_lwpr: Optional[str] = None                              # 주식 전일 최저가
    askp: Optional[str] = None                                        # 매도호가
    bidp: Optional[str] = None                                         # 매수호가
    prdy_vrss_vol: Optional[str] = None                                  # 전일 대비 거래량
    vol_tnrt: Optional[str] = None                                        # 거래량 회전율
    stck_fcam: Optional[str] = None                                        # 주식 액면가
    lstn_stcn: Optional[str] = None                                         # 상장 주수
    cpfn: Optional[str] = None                                               # 자본금
    hts_avls: Optional[str] = None                                           # HTS 시가총액
    per: Optional[str] = None                                                 # PER
    eps: Optional[str] = None                                                  # EPS
    pbr: Optional[str] = None                                                   # PBR
    itewhol_loan_rmnd_ratem: Optional[str] = None                               # 전체 융자 잔고 비율


@dataclass
class ResponseBodyOutput2:
    stck_bsop_date: str      # 주식 영업 일자
    stck_clpr: str            # 주식 종가
    stck_oprc: str              # 주식 시가2
    stck_hgpr: str                # 주식 최고가
    stck_lwpr: str                  # 주식 최저가
    acml_vol: str                     # 누적 거래량
    acml_tr_pbmn: str                   # 누적 거래 대금
    flng_cls_code: str                    # 락 구분 코드
    prtt_rate: str                          # 분할 비율
    mod_yn: str                               # 변경 여부
    prdy_vrss_sign: str                         # 전일 대비 부호
    prdy_vrss: str                                # 전일 대비
    revl_issu_reas: str                             # 재평가사유코드


@dataclass
class ResponseBody:
    rt_cd: str                                                          # 성공 실패 여부
    msg_cd: str                                                         # 응답코드
    msg1: str                                                           # 응답메세지
    output1: ResponseBodyOutput1                                        # 종목 현재가 요약(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)    # 기간별 시세(배열, 최대 100건)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_daily_itemchartprice(
    code: str,
    start_date: str,
    end_date: str,
    period_div: Literal["D", "W", "M", "Y"] = "D",
    org_adj_prc: Literal["0", "1"] = "0",
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """국내주식기간별시세(일/주/월/년봉)를 조회한다. 한 번의 호출에 최대 100건까지 확인 가능하다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930 삼성전자).
        start_date: 조회 시작일자(FID_INPUT_DATE_1). YYYYMMDD.
        end_date: 조회 종료일자(FID_INPUT_DATE_2). YYYYMMDD. 시작일자와의 사이에서 최대 100건.
        period_div: 기간분류코드(FID_PERIOD_DIV_CODE). D:일봉/W:주봉/M:월봉/Y:년봉. 기본값 "D".
        org_adj_prc: 수정주가 원주가 가격 여부(FID_ORG_ADJ_PRC). 0:수정주가/1:원주가. 기본값 "0".
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 종목 현재가 요약(output1), 기간별 시세(output2)를 담은 ResponseBody.
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
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
        "FID_PERIOD_DIV_CODE": period_div,
        "FID_ORG_ADJ_PRC": org_adj_prc,
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
    result = inquire_daily_itemchartprice(code="005930", start_date="20240101", end_date="20240110")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
