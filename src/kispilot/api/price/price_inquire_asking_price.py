# 주식현재가 호가/예상체결[v1_국내주식-011]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
# ※ 실시간 데이터가 필요하면 웹소켓 API를 이용할 것.

_TR_ID = "FHKST01010200"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    aspr_acpt_hour: Optional[str] = None              # 호가 접수 시간
    askp1: Optional[str] = None                        # 매도호가1
    askp2: Optional[str] = None                        # 매도호가2
    askp3: Optional[str] = None                        # 매도호가3
    askp4: Optional[str] = None                        # 매도호가4
    askp5: Optional[str] = None                        # 매도호가5
    askp6: Optional[str] = None                        # 매도호가6
    askp7: Optional[str] = None                        # 매도호가7
    askp8: Optional[str] = None                        # 매도호가8
    askp9: Optional[str] = None                        # 매도호가9
    askp10: Optional[str] = None                       # 매도호가10
    bidp1: Optional[str] = None                        # 매수호가1
    bidp2: Optional[str] = None                        # 매수호가2
    bidp3: Optional[str] = None                        # 매수호가3
    bidp4: Optional[str] = None                        # 매수호가4
    bidp5: Optional[str] = None                        # 매수호가5
    bidp6: Optional[str] = None                        # 매수호가6
    bidp7: Optional[str] = None                        # 매수호가7
    bidp8: Optional[str] = None                        # 매수호가8
    bidp9: Optional[str] = None                        # 매수호가9
    bidp10: Optional[str] = None                       # 매수호가10
    askp_rsqn1: Optional[str] = None                   # 매도호가 잔량1
    askp_rsqn2: Optional[str] = None                   # 매도호가 잔량2
    askp_rsqn3: Optional[str] = None                   # 매도호가 잔량3
    askp_rsqn4: Optional[str] = None                   # 매도호가 잔량4
    askp_rsqn5: Optional[str] = None                   # 매도호가 잔량5
    askp_rsqn6: Optional[str] = None                   # 매도호가 잔량6
    askp_rsqn7: Optional[str] = None                   # 매도호가 잔량7
    askp_rsqn8: Optional[str] = None                   # 매도호가 잔량8
    askp_rsqn9: Optional[str] = None                   # 매도호가 잔량9
    askp_rsqn10: Optional[str] = None                  # 매도호가 잔량10
    bidp_rsqn1: Optional[str] = None                   # 매수호가 잔량1
    bidp_rsqn2: Optional[str] = None                   # 매수호가 잔량2
    bidp_rsqn3: Optional[str] = None                   # 매수호가 잔량3
    bidp_rsqn4: Optional[str] = None                   # 매수호가 잔량4
    bidp_rsqn5: Optional[str] = None                   # 매수호가 잔량5
    bidp_rsqn6: Optional[str] = None                   # 매수호가 잔량6
    bidp_rsqn7: Optional[str] = None                   # 매수호가 잔량7
    bidp_rsqn8: Optional[str] = None                   # 매수호가 잔량8
    bidp_rsqn9: Optional[str] = None                   # 매수호가 잔량9
    bidp_rsqn10: Optional[str] = None                  # 매수호가 잔량10
    askp_rsqn_icdc1: Optional[str] = None              # 매도호가 잔량 증감1
    askp_rsqn_icdc2: Optional[str] = None              # 매도호가 잔량 증감2
    askp_rsqn_icdc3: Optional[str] = None              # 매도호가 잔량 증감3
    askp_rsqn_icdc4: Optional[str] = None              # 매도호가 잔량 증감4
    askp_rsqn_icdc5: Optional[str] = None              # 매도호가 잔량 증감5
    askp_rsqn_icdc6: Optional[str] = None              # 매도호가 잔량 증감6
    askp_rsqn_icdc7: Optional[str] = None              # 매도호가 잔량 증감7
    askp_rsqn_icdc8: Optional[str] = None              # 매도호가 잔량 증감8
    askp_rsqn_icdc9: Optional[str] = None              # 매도호가 잔량 증감9
    askp_rsqn_icdc10: Optional[str] = None             # 매도호가 잔량 증감10
    bidp_rsqn_icdc1: Optional[str] = None              # 매수호가 잔량 증감1
    bidp_rsqn_icdc2: Optional[str] = None              # 매수호가 잔량 증감2
    bidp_rsqn_icdc3: Optional[str] = None              # 매수호가 잔량 증감3
    bidp_rsqn_icdc4: Optional[str] = None              # 매수호가 잔량 증감4
    bidp_rsqn_icdc5: Optional[str] = None              # 매수호가 잔량 증감5
    bidp_rsqn_icdc6: Optional[str] = None              # 매수호가 잔량 증감6
    bidp_rsqn_icdc7: Optional[str] = None              # 매수호가 잔량 증감7
    bidp_rsqn_icdc8: Optional[str] = None              # 매수호가 잔량 증감8
    bidp_rsqn_icdc9: Optional[str] = None              # 매수호가 잔량 증감9
    bidp_rsqn_icdc10: Optional[str] = None             # 매수호가 잔량 증감10
    total_askp_rsqn: Optional[str] = None              # 총 매도호가 잔량
    total_bidp_rsqn: Optional[str] = None              # 총 매수호가 잔량
    total_askp_rsqn_icdc: Optional[str] = None         # 총 매도호가 잔량 증감
    total_bidp_rsqn_icdc: Optional[str] = None         # 총 매수호가 잔량 증감
    ovtm_total_askp_icdc: Optional[str] = None         # 시간외 총 매도호가 증감
    ovtm_total_bidp_icdc: Optional[str] = None         # 시간외 총 매수호가 증감
    ovtm_total_askp_rsqn: Optional[str] = None         # 시간외 총 매도호가 잔량
    ovtm_total_bidp_rsqn: Optional[str] = None         # 시간외 총 매수호가 잔량
    ntby_aspr_rsqn: Optional[str] = None                # 순매수 호가 잔량
    new_mkop_cls_code: Optional[str] = None             # 신 장운영 구분 코드


@dataclass
class ResponseBodyOutput2:
    antc_mkop_cls_code: Optional[str] = None        # 예상 장운영 구분 코드
    stck_prpr: Optional[str] = None                  # 주식 현재가
    stck_oprc: Optional[str] = None                   # 주식 시가2
    stck_hgpr: Optional[str] = None                    # 주식 최고가
    stck_lwpr: Optional[str] = None                     # 주식 최저가
    stck_sdpr: Optional[str] = None                      # 주식 기준가
    antc_cnpr: Optional[str] = None                       # 예상 체결가
    antc_cntg_vrss_sign: Optional[str] = None              # 예상 체결 대비 부호
    antc_cntg_vrss: Optional[str] = None                    # 예상 체결 대비
    antc_cntg_prdy_ctrt: Optional[str] = None                # 예상 체결 전일 대비율
    antc_vol: Optional[str] = None                             # 예상 거래량
    stck_shrn_iscd: Optional[str] = None                        # 주식 단축 종목코드
    vi_cls_code: Optional[str] = None                             # VI적용구분코드


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output1: ResponseBodyOutput1        # 호가 상세
    output2: ResponseBodyOutput2        # 예상체결 상세


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_asking_price(
    code: str,
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """주식현재가 호가/예상체결을 조회한다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930 삼성전자).
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 매수/매도 호가(output1), 예상체결 정보(output2)를 담은 ResponseBody.
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
    result = inquire_asking_price(code="005930")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        print(result.output2)
