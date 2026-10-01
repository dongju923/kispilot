# 국내주식 손익계산서[v1_국내주식-079]
from dataclasses import dataclass, field
from typing import List, Literal

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/finance/income-statement"
# ※ 모의투자 미지원 (실전투자 전용).

_TR_ID = "FHKST66430200"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stac_yymm: str         # 결산 년월
    sale_account: str      # 매출액
    sale_cost: str         # 매출 원가
    sale_totl_prfi: str    # 매출 총 이익
    depr_cost: str         # 감가상각비 (출력되지 않는 데이터, 99.99로 표시)
    sell_mang: str         # 판매 및 관리비 (출력되지 않는 데이터, 99.99로 표시)
    bsop_prti: str         # 영업 이익
    bsop_non_ernn: str     # 영업 외 수익 (출력되지 않는 데이터, 99.99로 표시)
    bsop_non_expn: str     # 영업 외 비용 (출력되지 않는 데이터, 99.99로 표시)
    op_prfi: str           # 경상 이익
    spec_prfi: str         # 특별 이익
    spec_loss: str         # 특별 손실
    thtr_ntin: str         # 당기순이익


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 손익계산서(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def income_statement(
    code: str,
    div_cls: Literal["0", "1"] = "0",
) -> ResponseBody:
    """국내주식 손익계산서를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0635] 재무분석종합 화면의 하단 '2. 손익계산서' 기능과 동일.

    Args:
        code: 입력 종목코드(fid_input_iscd), 6자리(ex 000660).
        div_cls: 분류 구분 코드(FID_DIV_CLS_CODE). 0:년, 1:분기. 기본값 "0".
            ※ 분기 데이터는 연단위 누적합산 값.

    Returns:
        rt_cd/msg_cd/msg1과 결산 년월별 손익계산서(output)를 담은 ResponseBody.
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
        "FID_DIV_CLS_CODE": div_cls,
        "fid_cond_mrkt_div_code": "J",
        "fid_input_iscd": code,
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
    result = income_statement(code="000660")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
