# 국내주식 예상체결지수 추이[국내주식-121]
from dataclasses import dataclass, field
from typing import List, Literal

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/exp-index-trend"
# ※ 모의투자 미지원 (실전투자 전용).

_TR_ID = "FHPST01840000"
_FID_COND_MRKT_DIV_CODE = "U"  # 업종 고정값


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stck_cntg_hour: str        # 주식 체결 시간
    bstp_nmix_prpr: str        # 업종 지수 현재가
    prdy_vrss_sign: str        # 전일 대비 부호
    bstp_nmix_prdy_vrss: str   # 업종 지수 전일 대비
    prdy_ctrt: str             # 전일 대비율
    acml_vol: str              # 누적 거래량
    acml_tr_pbmn: str          # 누적 거래 대금


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 예상체결지수 추이(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def exp_index_trend(
    iscd: str,
    mkop_cls_code: Literal["1", "2"],
    hour: Literal["10", "30", "60", "600"] = "60",
) -> ResponseBody:
    """국내주식 예상체결지수 추이를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0184] 예상체결지수 추이 화면과 동일한 기능.

    Args:
        iscd: 입력 종목코드(FID_INPUT_ISCD). 0000:전체, 0001:코스피, 1001:코스닥, 2001:코스피200,
            4001:KRX100.
        mkop_cls_code: 장운영 구분 코드(FID_MKOP_CLS_CODE). 1:장시작전, 2:장마감.
        hour: 입력 시간1(FID_INPUT_HOUR_1). 10(10초)/30(30초)/60(1분)/600(10분). 기본값 "60".

    Returns:
        rt_cd/msg_cd/msg1과 예상체결지수 추이(output)를 담은 ResponseBody.
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
        "FID_MKOP_CLS_CODE": mkop_cls_code,
        "FID_INPUT_HOUR_1": hour,
        "FID_INPUT_ISCD": iscd,
        "FID_COND_MRKT_DIV_CODE": _FID_COND_MRKT_DIV_CODE,
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
    result = exp_index_trend(iscd="0001", mkop_cls_code="1")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
