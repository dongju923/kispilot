# 종목별 외국계 순매수추이[국내주식-164]
from dataclasses import dataclass, field
from typing import List, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/frgnmem-pchs-trend"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0433] 종목별 외국계 순매수추이 화면과 동일한 기능.
# ※ output은 당일 장중 시간대별 외국계 매매 추이가 최신순으로 최대 100건 내려온다.
#   glob_ntby_qty(외국계 순매수 수량)는 해당 시각까지의 누적값이다.
# ※ FID_INPUT_ISCD_2(외국계 전체 "99999"), FID_COND_MRKT_DIV_CODE(KRX만 지원 "J")는
#   문서상 고정값이라 파라미터로 노출하지 않는다.

_TR_ID = "FHKST644400C0"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    bsop_hour: Optional[str] = None             # 영업시간(HHMMSS)
    stck_prpr: Optional[str] = None             # 주식현재가
    prdy_vrss: Optional[str] = None             # 전일대비
    prdy_vrss_sign: Optional[str] = None        # 전일대비부호
    prdy_ctrt: Optional[str] = None             # 전일대비율
    acml_vol: Optional[str] = None              # 누적거래량
    frgn_seln_vol: Optional[str] = None         # 외국인매도거래량
    frgn_shnu_vol: Optional[str] = None         # 외국인매수2거래량
    glob_ntby_qty: Optional[str] = None         # 외국계순매수수량
    frgn_ntby_qty_icdc: Optional[str] = None    # 외국인순매수수량증감


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 시간대별 외국계 순매수추이(배열, 최신순, 최대 100건)


# ── 요청 함수 ───────────────────────────────────────────────

def frgnmem_pchs_trend(
    code: str,
) -> ResponseBody:
    """종목별 외국계 순매수추이(당일 장중 시간대별)를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0433] 종목별 외국계 순매수추이 화면 기능과 동일.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930). KRX만 지원.

    Returns:
        rt_cd/msg_cd/msg1과 시간대별 외국계 순매수추이(output)를 담은 ResponseBody.
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
        "FID_INPUT_ISCD": code,
        "FID_INPUT_ISCD_2": "99999",
        "FID_COND_MRKT_DIV_CODE": "J",
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
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
    result = frgnmem_pchs_trend(code="005930")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
