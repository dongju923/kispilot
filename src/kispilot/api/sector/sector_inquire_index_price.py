# 국내업종 현재지수[v1_국내주식-063]
from dataclasses import dataclass
from typing import Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-index-price"
# ※ 모의투자 미지원 (실전투자 전용).

_TR_ID = "FHPUP02100000"
_FID_COND_MRKT_DIV_CODE = "U"  # 업종 고정값


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    bstp_nmix_prpr: Optional[str] = None                     # 업종 지수 현재가
    bstp_nmix_prdy_vrss: Optional[str] = None                # 업종 지수 전일 대비
    prdy_vrss_sign: Optional[str] = None                     # 전일 대비 부호
    bstp_nmix_prdy_ctrt: Optional[str] = None                # 업종 지수 전일 대비율
    acml_vol: Optional[str] = None                           # 누적 거래량
    prdy_vol: Optional[str] = None                           # 전일 거래량
    acml_tr_pbmn: Optional[str] = None                       # 누적 거래 대금
    prdy_tr_pbmn: Optional[str] = None                       # 전일 거래 대금
    bstp_nmix_oprc: Optional[str] = None                     # 업종 지수 시가2
    prdy_nmix_vrss_nmix_oprc: Optional[str] = None           # 전일 지수 대비 지수 시가2
    oprc_vrss_prpr_sign: Optional[str] = None                # 시가2 대비 현재가 부호
    bstp_nmix_oprc_prdy_ctrt: Optional[str] = None           # 업종 지수 시가2 전일 대비율
    bstp_nmix_hgpr: Optional[str] = None                     # 업종 지수 최고가
    prdy_nmix_vrss_nmix_hgpr: Optional[str] = None           # 전일 지수 대비 지수 최고가
    hgpr_vrss_prpr_sign: Optional[str] = None                # 최고가 대비 현재가 부호
    bstp_nmix_hgpr_prdy_ctrt: Optional[str] = None           # 업종 지수 최고가 전일 대비율
    bstp_nmix_lwpr: Optional[str] = None                     # 업종 지수 최저가
    prdy_clpr_vrss_lwpr: Optional[str] = None                # 전일 종가 대비 최저가
    lwpr_vrss_prpr_sign: Optional[str] = None                # 최저가 대비 현재가 부호
    prdy_clpr_vrss_lwpr_rate: Optional[str] = None           # 전일 종가 대비 최저가 비율
    ascn_issu_cnt: Optional[str] = None                      # 상승 종목 수
    uplm_issu_cnt: Optional[str] = None                      # 상한 종목 수
    stnr_issu_cnt: Optional[str] = None                      # 보합 종목 수
    down_issu_cnt: Optional[str] = None                      # 하락 종목 수
    lslm_issu_cnt: Optional[str] = None                      # 하한 종목 수
    dryy_bstp_nmix_hgpr: Optional[str] = None                # 연중업종지수최고가
    dryy_hgpr_vrss_prpr_rate: Optional[str] = None           # 연중 최고가 대비 현재가 비율
    dryy_bstp_nmix_hgpr_date: Optional[str] = None           # 연중업종지수최고가일자
    dryy_bstp_nmix_lwpr: Optional[str] = None                # 연중업종지수최저가
    dryy_lwpr_vrss_prpr_rate: Optional[str] = None           # 연중 최저가 대비 현재가 비율
    dryy_bstp_nmix_lwpr_date: Optional[str] = None           # 연중업종지수최저가일자
    total_askp_rsqn: Optional[str] = None                    # 총 매도호가 잔량
    total_bidp_rsqn: Optional[str] = None                    # 총 매수호가 잔량
    seln_rsqn_rate: Optional[str] = None                     # 매도 잔량 비율
    shnu_rsqn_rate: Optional[str] = None                     # 매수2 잔량 비율
    ntby_rsqn: Optional[str] = None                          # 순매수 잔량


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output: ResponseBodyOutput          # 업종 현재지수 상세


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_index_price(iscd: str) -> ResponseBody:
    """국내업종 현재지수를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0210] 업종 현재지수 화면과 동일한 기능.

    Args:
        iscd: 입력 종목코드(FID_INPUT_ISCD). 코스피(0001), 코스닥(1001), 코스피200(2001) 등
            업종코드. (포탈 FAQ : 종목정보 다운로드(국내) - 업종코드 참조)

    Returns:
        rt_cd/msg_cd/msg1과 업종 현재지수 상세(output)를 담은 ResponseBody.
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
        "FID_COND_MRKT_DIV_CODE": _FID_COND_MRKT_DIV_CODE,
        "FID_INPUT_ISCD": iscd,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output 키가 없거나 null일 수 있어 안전 파싱.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_output = raw.get("output") or {}
    output = ResponseBodyOutput(**{k: v for k, v in raw_output.items() if k in fields})

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output=output,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_index_price(iscd="0002")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output)
