# 주식현재가 일자별[v1_국내주식-010]
from dataclasses import dataclass, field
from typing import List, Literal

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
# ※ 일/주/월별 주가를 조회하며, 최근 30건(거래일/주/개월)으로 제한된다.

_TR_ID = "FHKST01010400"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stck_bsop_date: str        # 주식 영업 일자
    stck_oprc: str              # 주식 시가2
    stck_hgpr: str                # 주식 최고가
    stck_lwpr: str                 # 주식 최저가
    stck_clpr: str                  # 주식 종가
    acml_vol: str                    # 누적 거래량
    prdy_vrss_vol_rate: str            # 전일 대비 거래량 비율
    prdy_vrss: str                      # 전일 대비
    prdy_vrss_sign: str                  # 전일 대비 부호
    prdy_ctrt: str                        # 전일 대비율
    hts_frgn_ehrt: str                     # HTS 외국인 소진율
    frgn_ntby_qty: str                      # 외국인 순매수 수량
    flng_cls_code: str                       # 락 구분 코드
    acml_prtt_rate: str                       # 누적 분할 비율


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 일/주/월별 시세(배열, 최근 30건)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_daily_price(
    code: str,
    period_div: Literal["D", "W", "M"] = "D",
    org_adj_prc: Literal["0", "1"] = "0",
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """주식현재가 일자별(일/주/월별 최근 30건) 시세를 조회한다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930 삼성전자).
        period_div: 기간 분류 코드(FID_PERIOD_DIV_CODE). D:일(최근 30거래일)/W:주(최근 30주)/M:월(최근 30개월). 기본값 "D".
        org_adj_prc: 수정주가 원주가 가격(FID_ORG_ADJ_PRC). 0:수정주가미반영/1:수정주가반영. 기본값 "0".
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 일/주/월별 시세(output)를 담은 ResponseBody.
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
        "FID_PERIOD_DIV_CODE": period_div,
        "FID_ORG_ADJ_PRC": org_adj_prc,
    }
    response = get_session().get(DOMAIN[mode] + URL, headers=headers, params=params, timeout=10)
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
    result = inquire_daily_price(code="005930")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
