# 국내주식 예상체결 전체지수[국내주식-122]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/exp-total-index"
# ※ 모의투자 미지원 (실전투자 전용).

_TR_ID = "FHKUP11750000"
_FID_COND_MRKT_DIV_CODE = "U"      # 업종 고정값
_FID_COND_SCR_DIV_CODE = "11175"   # 화면 분류 코드 고정값


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    bstp_nmix_prpr: Optional[str] = None                     # 업종 지수 현재가
    bstp_nmix_prdy_vrss: Optional[str] = None                # 업종 지수 전일 대비
    prdy_vrss_sign: Optional[str] = None                     # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                          # 전일 대비율
    acml_vol: Optional[str] = None                           # 누적 거래량
    ascn_issu_cnt: Optional[str] = None                      # 상승 종목 수
    down_issu_cnt: Optional[str] = None                      # 하락 종목 수
    stnr_issu_cnt: Optional[str] = None                      # 보합 종목 수
    bstp_cls_code: Optional[str] = None                      # 업종 구분 코드


@dataclass
class ResponseBodyOutput2:
    hts_kor_isnm: str          # HTS 한글 종목명
    bstp_nmix_prpr: str        # 업종 지수 현재가
    bstp_nmix_prdy_vrss: str   # 업종 지수 전일 대비
    prdy_vrss_sign: str        # 전일 대비 부호
    bstp_nmix_prdy_ctrt: str   # 업종 지수 전일 대비율
    acml_vol: str              # 누적 거래량
    nmix_sdpr: str             # 지수 기준가
    ascn_issu_cnt: str         # 상승 종목 수
    stnr_issu_cnt: str         # 보합 종목 수
    down_issu_cnt: str         # 하락 종목 수


@dataclass
class ResponseBody:
    rt_cd: str                                                          # 성공 실패 여부
    msg_cd: str                                                         # 응답코드
    msg1: str                                                           # 응답메세지
    output1: ResponseBodyOutput1                                        # 업종 지수 요약(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)    # 구분별 예상체결지수(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def exp_total_index(
    iscd: str,
    mkop_cls_code: Literal["1", "2"],
    mrkt_cls_code: Literal["0", "K", "Q"] = "0",
) -> ResponseBody:
    """국내주식 예상체결 전체지수를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0185] 예상체결 전체지수 화면과 동일한 기능.

    Args:
        iscd: 입력 종목코드(FID_INPUT_ISCD). 0000:전체, 0001:거래소, 1001:코스닥, 2001:코스피200,
            4001:KRX100.
        mkop_cls_code: 장운영 구분 코드(FID_MKOP_CLS_CODE). 1:장시작전, 2:장마감.
        mrkt_cls_code: 시장 구분 코드(FID_MRKT_CLS_CODE). 0:전체, K:거래소, Q:코스닥. 기본값 "0".

    Returns:
        rt_cd/msg_cd/msg1과 업종 지수 요약(output1), 구분별 예상체결지수(output2)를 담은 ResponseBody.
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
        "fid_mrkt_cls_code": mrkt_cls_code,
        "fid_cond_mrkt_div_code": _FID_COND_MRKT_DIV_CODE,
        "fid_cond_scr_div_code": _FID_COND_SCR_DIV_CODE,
        "fid_input_iscd": iscd,
        "fid_mkop_cls_code": mkop_cls_code,
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
    result = exp_total_index(iscd="0000", mkop_cls_code="1")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
