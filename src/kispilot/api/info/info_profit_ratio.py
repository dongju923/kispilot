# 국내주식 수익성비율[v1_국내주식-081]
from dataclasses import dataclass, field
from typing import List, Literal

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/finance/profit-ratio"
# ※ 모의투자 미지원 (실전투자 전용).

_TR_ID = "FHKST66430400"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stac_yymm: str              # 결산 년월
    cptl_ntin_rate: str         # 총자본 순이익율
    self_cptl_ntin_inrt: str    # 자기자본 순이익율
    sale_ntin_rate: str         # 매출액 순이익율
    sale_totl_rate: str         # 매출액 총이익율


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 수익성비율(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def profit_ratio(
    code: str,
    div_cls: Literal["0", "1"] = "0",
) -> ResponseBody:
    """국내주식 수익성비율을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0635] 재무분석종합 화면의 하단 '4. 수익성비율' 기능과 동일.

    Args:
        code: 입력 종목코드(fid_input_iscd), 6자리(ex 000660).
        div_cls: 분류 구분 코드(FID_DIV_CLS_CODE). 0:년, 1:분기. 기본값 "0".

    Returns:
        rt_cd/msg_cd/msg1과 결산 년월별 수익성비율(output)을 담은 ResponseBody.
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
        "fid_input_iscd": code,
        "FID_DIV_CLS_CODE": div_cls,
        "fid_cond_mrkt_div_code": "J",
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
    result = profit_ratio(code="000660")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
