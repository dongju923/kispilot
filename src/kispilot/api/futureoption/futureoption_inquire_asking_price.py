# 선물옵션 시세호가[v1_국내선물-007]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-futureoption/v1/quotations/inquire-asking-price"
# ※ 실시간 데이터가 필요하면 웹소켓 API를 이용할 것.

_TR_ID = "FHMIF10010000"  # 실전/모의 동일


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    hts_kor_isnm: Optional[str] = None                      # HTS 한글 종목명
    futs_prpr: Optional[str] = None                         # 선물 현재가
    prdy_vrss_sign: Optional[str] = None                    # 전일 대비 부호 (1 상한, 2 상승, 3 보합, 4 하한, 5 하락)
    futs_prdy_vrss: Optional[str] = None                    # 선물 전일 대비
    futs_prdy_ctrt: Optional[str] = None                    # 선물 전일 대비율
    acml_vol: Optional[str] = None                          # 누적 거래량
    futs_prdy_clpr: Optional[str] = None                    # 선물 전일 종가
    futs_shrn_iscd: Optional[str] = None                    # 선물 단축 종목코드


@dataclass
class ResponseBodyOutput2:
    futs_askp1: Optional[str] = None                        # 선물 매도호가1
    futs_askp2: Optional[str] = None                        # 선물 매도호가2
    futs_askp3: Optional[str] = None                        # 선물 매도호가3
    futs_askp4: Optional[str] = None                        # 선물 매도호가4
    futs_askp5: Optional[str] = None                        # 선물 매도호가5
    futs_bidp1: Optional[str] = None                        # 선물 매수호가1
    futs_bidp2: Optional[str] = None                        # 선물 매수호가2
    futs_bidp3: Optional[str] = None                        # 선물 매수호가3
    futs_bidp4: Optional[str] = None                        # 선물 매수호가4
    futs_bidp5: Optional[str] = None                        # 선물 매수호가5
    askp_rsqn1: Optional[str] = None                        # 매도호가 잔량1
    askp_rsqn2: Optional[str] = None                        # 매도호가 잔량2
    askp_rsqn3: Optional[str] = None                        # 매도호가 잔량3
    askp_rsqn4: Optional[str] = None                        # 매도호가 잔량4
    askp_rsqn5: Optional[str] = None                        # 매도호가 잔량5
    bidp_rsqn1: Optional[str] = None                        # 매수호가 잔량1
    bidp_rsqn2: Optional[str] = None                        # 매수호가 잔량2
    bidp_rsqn3: Optional[str] = None                        # 매수호가 잔량3
    bidp_rsqn4: Optional[str] = None                        # 매수호가 잔량4
    bidp_rsqn5: Optional[str] = None                        # 매수호가 잔량5
    askp_csnu1: Optional[str] = None                        # 매도호가 건수1
    askp_csnu2: Optional[str] = None                        # 매도호가 건수2
    askp_csnu3: Optional[str] = None                        # 매도호가 건수3
    askp_csnu4: Optional[str] = None                        # 매도호가 건수4
    askp_csnu5: Optional[str] = None                        # 매도호가 건수5
    bidp_csnu1: Optional[str] = None                        # 매수호가 건수1
    bidp_csnu2: Optional[str] = None                        # 매수호가 건수2
    bidp_csnu3: Optional[str] = None                        # 매수호가 건수3
    bidp_csnu4: Optional[str] = None                        # 매수호가 건수4
    bidp_csnu5: Optional[str] = None                        # 매수호가 건수5
    total_askp_rsqn: Optional[str] = None                   # 총 매도호가 잔량
    total_bidp_rsqn: Optional[str] = None                   # 총 매수호가 잔량
    total_askp_csnu: Optional[str] = None                   # 총 매도호가 건수
    total_bidp_csnu: Optional[str] = None                   # 총 매수호가 건수
    aspr_acpt_hour: Optional[str] = None                    # 호가 접수 시간 (HHMMSS)


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output1: ResponseBodyOutput1        # 시세 요약
    output2: ResponseBodyOutput2        # 매도/매수 5단계 호가 (문서는 배열이라 하지만 실제 응답은 객체 하나)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_asking_price(
    code: str,
    market_div: Literal["F", "O", "JF", "JO", "CF", "CM", "EU"],
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """선물옵션 시세호가(매도/매수 5단계 호가·잔량·건수)를 조회한다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 선물옵션 단축코드(ex A01612 KOSPI200 선물 2026년 12월물).
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). F:지수선물, O:지수옵션, JF:주식선물,
            JO:주식옵션, CF:상품선물(금·국채·달러), CM:야간선물, EU:야간옵션.
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 시세 요약(output1), 매도/매수 호가(output2)를 담은 ResponseBody.
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

    # 에러 응답(rt_cd != "0")은 output1/output2 키가 없거나 null일 수 있어 안전 파싱.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or {}
    output1 = ResponseBodyOutput1(**{k: v for k, v in raw_output1.items() if k in fields1})

    fields2 = set(ResponseBodyOutput2.__dataclass_fields__)
    raw_output2 = raw.get("output2") or {}
    output2 = ResponseBodyOutput2(**{k: v for k, v in raw_output2.items() if k in fields2})

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
        output2=output2,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_asking_price(code="A01612", market_div="F")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        print(result.output2)
