# 국내주식 매물대/거래비중[국내주식-196]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/pbar-tratio"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0113] 당일가격대별 매물대 화면의 데이터 일부.
# ※ output2는 당일 체결된 가격대 전체가 체결거래량 내림차순(data_rank 1부터)으로 내려온다(연속조회 불가).
#   건수는 당일 체결된 가격대 수에 따라 달라지고, cntg_vol 합계는 당일 누적거래량과 같으며
#   acml_vol_rlim(%) 합계는 약 100이다.
# ※ FID_COND_SCR_DIV_CODE(20113), FID_INPUT_HOUR_1(공백)은 문서상 고정값이라 파라미터로 노출하지 않는다.

_TR_ID = "FHPST01130000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    rprs_mrkt_kor_name: Optional[str] = None    # 대표시장한글명
    stck_shrn_iscd: Optional[str] = None        # 주식단축종목코드
    hts_kor_isnm: Optional[str] = None          # HTS한글종목명
    stck_prpr: Optional[str] = None             # 주식현재가
    prdy_vrss_sign: Optional[str] = None        # 전일대비부호
    prdy_vrss: Optional[str] = None             # 전일대비
    prdy_ctrt: Optional[str] = None             # 전일대비율
    acml_vol: Optional[str] = None              # 누적거래량
    prdy_vol: Optional[str] = None              # 전일거래량
    wghn_avrg_stck_prc: Optional[str] = None    # 가중평균주식가격
    lstn_stcn: Optional[str] = None             # 상장주수


@dataclass
class ResponseBodyOutput2:
    data_rank: Optional[str] = None             # 데이터순위(체결거래량 순)
    stck_prpr: Optional[str] = None             # 주식현재가(가격대)
    cntg_vol: Optional[str] = None              # 체결거래량
    acml_vol_rlim: Optional[str] = None         # 누적거래량비중(%)


@dataclass
class ResponseBody:
    rt_cd: str                                                                  # 성공 실패 여부
    msg_cd: str                                                                 # 응답코드
    msg1: str                                                                   # 응답메세지
    output1: ResponseBodyOutput1 = field(default_factory=ResponseBodyOutput1)   # 종목 현재 시세(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)            # 가격대별 매물대(배열, 체결거래량 순)


# ── 요청 함수 ───────────────────────────────────────────────

def pbar_tratio(
    code: str,
    market_div: Literal["J", "NX", "UN"] = "J",
) -> ResponseBody:
    """국내주식 당일 가격대별 매물대/거래비중을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0113] 당일가격대별 매물대 화면 데이터의 일부.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930).
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".

    Returns:
        rt_cd/msg_cd/msg1과 종목 현재 시세(output1), 가격대별 매물대(output2)를 담은 ResponseBody.
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
        "FID_COND_MRKT_DIV_CODE": market_div,
        "FID_INPUT_ISCD": code,
        "FID_COND_SCR_DIV_CODE": "20113",
        "FID_INPUT_HOUR_1": "",
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
    result = pbar_tratio(code="005930")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
