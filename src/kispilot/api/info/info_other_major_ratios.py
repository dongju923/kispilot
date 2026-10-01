# 국내주식 기타주요비율[v1_국내주식-082]
from dataclasses import dataclass, field
from typing import List, Literal

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/finance/other-major-ratios"
# ※ 모의투자 미지원 (실전투자 전용).

_TR_ID = "FHKST66430500"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stac_yymm: str      # 결산 년월
    payout_rate: str    # 배당 성향 (비정상 출력되는 데이터로 무시)
    eva: str            # EVA
    ebitda: str         # EBITDA
    ev_ebitda: str      # EV_EBITDA


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 기타주요비율(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def other_major_ratios(
    code: str,
    div_cls: Literal["0", "1"] = "0",
) -> ResponseBody:
    """국내주식 기타주요비율을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0635] 재무분석종합 화면의 하단 '9. 기타주요비율' 기능과 동일.

    Args:
        code: 입력 종목코드(fid_input_iscd), 6자리(ex 000660).
        div_cls: 분류 구분 코드(fid_div_cls_code). 0:년, 1:분기. 기본값 "0".

    Returns:
        rt_cd/msg_cd/msg1과 결산 년월별 기타주요비율(output)을 담은 ResponseBody.
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
        "fid_div_cls_code": div_cls,
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
    result = other_major_ratios(code="000660")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
