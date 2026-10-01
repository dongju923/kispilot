# 프로그램매매 투자자매매동향(당일)[국내주식-116]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/investor-program-trade-today"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0466] 프로그램매매 투자자별 동향 화면의 "당일동향" 표.
# ※ output1은 시장 전체의 당일 프로그램 매매를 투자자 구분별로 11건 돌려준다(연속조회 불가).
#   투자자코드: 1000 금융투자, 2000 보험, 3000 투신, 3100 사모, 4000 은행, 5000 기타금융,
#   6000 연기금등, 7100 기타, 8000 개인, 8888 기관(합계), 9100 외국인.
#   invr_cls_name은 "기 타", "보 험"처럼 글자 사이에 공백이 섞여 내려온다.
# ※ 구TR(HHPPG046600C0)은 사전고지 없이 막힐 수 있어 신TR(HHPPG046600C1)을 사용한다.

_TR_ID = "HHPPG046600C1"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    invr_cls_code: Optional[str] = None     # 투자자코드
    invr_cls_name: Optional[str] = None     # 투자자 구분 명
    all_seln_qty: Optional[str] = None      # 전체매도수량
    all_shnu_qty: Optional[str] = None      # 전체매수수량
    all_ntby_qty: Optional[str] = None      # 전체순매수수량
    all_seln_amt: Optional[str] = None      # 전체매도대금
    all_shnu_amt: Optional[str] = None      # 전체매수대금
    all_ntby_amt: Optional[str] = None      # 전체순매수대금
    arbt_seln_qty: Optional[str] = None     # 차익매도수량
    arbt_shnu_qty: Optional[str] = None     # 차익매수수량
    arbt_ntby_qty: Optional[str] = None     # 차익순매수수량
    arbt_seln_amt: Optional[str] = None     # 차익매도대금
    arbt_shnu_amt: Optional[str] = None     # 차익매수대금
    arbt_ntby_amt: Optional[str] = None     # 차익순매수대금
    nabt_seln_qty: Optional[str] = None     # 비차익매도수량
    nabt_shnu_qty: Optional[str] = None     # 비차익매수수량
    nabt_ntby_qty: Optional[str] = None     # 비차익순매수수량
    nabt_seln_amt: Optional[str] = None     # 비차익매도대금
    nabt_shnu_amt: Optional[str] = None     # 비차익매수대금
    nabt_ntby_amt: Optional[str] = None     # 비차익순매수대금


@dataclass
class ResponseBody:
    rt_cd: str                                                         # 성공 실패 여부
    msg_cd: str                                                        # 응답코드
    msg1: str                                                          # 응답메세지
    output1: List[ResponseBodyOutput1] = field(default_factory=list)   # 투자자별 프로그램 매매동향(배열, 11건)


# ── 요청 함수 ───────────────────────────────────────────────

def investor_program_trade_today(
    market: Literal["1", "4"],
    exch_div: Literal["J", "NX", "UN"] = "J",
) -> ResponseBody:
    """프로그램매매 투자자매매동향(당일)을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0466] 프로그램매매 투자자별 동향 화면의 "당일동향" 표와 동일.
    시장 전체의 당일 프로그램 매매(전체/차익/비차익)를 투자자 구분별로 돌려준다.

    Args:
        market: 시장 구분 코드(MRKT_DIV_CLS_CODE). 1:코스피, 4:코스닥.
        exch_div: 거래소 구분 코드(EXCH_DIV_CLS_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".

    Returns:
        rt_cd/msg_cd/msg1과 투자자별 프로그램 매매동향(output1)을 담은 ResponseBody.
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
        "EXCH_DIV_CLS_CODE": exch_div,
        "MRKT_DIV_CLS_CODE": market,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1 키가 없거나 null일 수 있어 안전 파싱.
    fields = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or []
    output1 = [ResponseBodyOutput1(**{k: v for k, v in item.items() if k in fields}) for item in raw_output1]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = investor_program_trade_today(market="1")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output1:
            print(row)
