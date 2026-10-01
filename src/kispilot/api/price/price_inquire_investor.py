# 주식현재가 투자자[v1_국내주식-012]
from dataclasses import dataclass, field
from typing import List, Literal

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-investor"
# ※ 외국인은 외국인(외국인투자등록 고유번호가 있는 경우)+기타 외국인을 지칭.
# ※ 당일 데이터는 장 종료 후 제공됨.

_TR_ID = "FHKST01010900"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stck_bsop_date: str          # 주식 영업 일자
    stck_clpr: str                # 주식 종가
    prdy_vrss: str                  # 전일 대비
    prdy_vrss_sign: str               # 전일 대비 부호
    prsn_ntby_qty: str                 # 개인 순매수 수량
    frgn_ntby_qty: str                   # 외국인 순매수 수량
    orgn_ntby_qty: str                     # 기관계 순매수 수량
    prsn_ntby_tr_pbmn: str                   # 개인 순매수 거래 대금
    frgn_ntby_tr_pbmn: str                     # 외국인 순매수 거래 대금
    orgn_ntby_tr_pbmn: str                       # 기관계 순매수 거래 대금
    prsn_shnu_vol: str                             # 개인 매수2 거래량
    frgn_shnu_vol: str                               # 외국인 매수2 거래량
    orgn_shnu_vol: str                                 # 기관계 매수2 거래량
    prsn_shnu_tr_pbmn: str                               # 개인 매수2 거래 대금
    frgn_shnu_tr_pbmn: str                                 # 외국인 매수2 거래 대금
    orgn_shnu_tr_pbmn: str                                   # 기관계 매수2 거래 대금
    prsn_seln_vol: str                                         # 개인 매도 거래량
    frgn_seln_vol: str                                           # 외국인 매도 거래량
    orgn_seln_vol: str                                             # 기관계 매도 거래량
    prsn_seln_tr_pbmn: str                                           # 개인 매도 거래 대금
    frgn_seln_tr_pbmn: str                                             # 외국인 매도 거래 대금
    orgn_seln_tr_pbmn: str                                               # 기관계 매도 거래 대금


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 투자자별 매매동향(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_investor(
    code: str,
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """주식현재가 투자자(개인/외국인/기관계 매매동향)를 조회한다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930 삼성전자).
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 투자자별 매매동향(output)을 담은 ResponseBody.
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
    result = inquire_investor(code="005930")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
