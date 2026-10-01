# 국내업종 구분별전체시세[v1_국내주식-066]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-index-category-price"
# ※ 모의투자 미지원 (실전투자 전용).

_TR_ID = "FHPUP02140000"
_FID_COND_MRKT_DIV_CODE = "U"      # 업종 고정값
_FID_COND_SCR_DIV_CODE = "20214"   # 화면 분류 코드 고정값


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    bstp_nmix_prpr: Optional[str] = None                     # 업종 지수 현재가
    bstp_nmix_prdy_vrss: Optional[str] = None                # 업종 지수 전일 대비
    prdy_vrss_sign: Optional[str] = None                     # 전일 대비 부호
    bstp_nmix_prdy_ctrt: Optional[str] = None                # 업종 지수 전일 대비율
    acml_vol: Optional[str] = None                           # 누적 거래량
    acml_tr_pbmn: Optional[str] = None                       # 누적 거래 대금
    bstp_nmix_oprc: Optional[str] = None                     # 업종 지수 시가2
    bstp_nmix_hgpr: Optional[str] = None                     # 업종 지수 최고가
    bstp_nmix_lwpr: Optional[str] = None                     # 업종 지수 최저가
    prdy_vol: Optional[str] = None                           # 전일 거래량
    ascn_issu_cnt: Optional[str] = None                      # 상승 종목 수
    down_issu_cnt: Optional[str] = None                      # 하락 종목 수
    stnr_issu_cnt: Optional[str] = None                      # 보합 종목 수
    uplm_issu_cnt: Optional[str] = None                      # 상한 종목 수
    lslm_issu_cnt: Optional[str] = None                      # 하한 종목 수
    prdy_tr_pbmn: Optional[str] = None                       # 전일 거래 대금
    dryy_bstp_nmix_hgpr_date: Optional[str] = None           # 연중업종지수최고가일자
    dryy_bstp_nmix_hgpr: Optional[str] = None                # 연중업종지수최고가
    dryy_bstp_nmix_lwpr: Optional[str] = None                # 연중업종지수최저가
    dryy_bstp_nmix_lwpr_date: Optional[str] = None           # 연중업종지수최저가일자


@dataclass
class ResponseBodyOutput2:
    bstp_cls_code: str         # 업종 구분 코드
    hts_kor_isnm: str          # HTS 한글 종목명
    bstp_nmix_prpr: str        # 업종 지수 현재가
    bstp_nmix_prdy_vrss: str   # 업종 지수 전일 대비
    prdy_vrss_sign: str        # 전일 대비 부호
    bstp_nmix_prdy_ctrt: str   # 업종 지수 전일 대비율
    acml_vol: str              # 누적 거래량
    acml_tr_pbmn: str          # 누적 거래 대금
    acml_vol_rlim: str         # 누적 거래량 비중
    acml_tr_pbmn_rlim: str     # 누적 거래 대금 비중


@dataclass
class ResponseBody:
    rt_cd: str                                                          # 성공 실패 여부
    msg_cd: str                                                         # 응답코드
    msg1: str                                                           # 응답메세지
    output1: ResponseBodyOutput1                                        # 업종 지수 요약(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)    # 구분별 전체시세(배열)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_index_category_price(
    iscd: str,
    mrkt_cls_code: Literal["K", "Q", "K2"],
    blng_cls_code: str,
) -> ResponseBody:
    """국내업종 구분별전체시세를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0214] 업종 전체시세 화면과 동일한 기능.

    Args:
        iscd: 입력 종목코드(FID_INPUT_ISCD). 코스피(0001), 코스닥(1001), 코스피200(2001) 등
            업종코드. (포탈 FAQ : 종목정보 다운로드(국내) - 업종코드 참조)
        mrkt_cls_code: 시장 구분 코드(FID_MRKT_CLS_CODE). K:거래소, Q:코스닥, K2:코스피200.
        blng_cls_code: 소속 구분 코드(FID_BLNG_CLS_CODE). mrkt_cls_code에 따라 의미가 다름.
            K(거래소): 0:전업종, 1:기타구분, 2:자본금구분, 3:산업별구분
            Q(코스닥): 0:전업종, 1:기타구분, 2:벤처구분, 3:일반구분
            K2(코스피200): 0:전업종

    Returns:
        rt_cd/msg_cd/msg1과 업종 지수 요약(output1), 구분별 전체시세(output2)를 담은 ResponseBody.
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
        "FID_COND_SCR_DIV_CODE": _FID_COND_SCR_DIV_CODE,
        "FID_MRKT_CLS_CODE": mrkt_cls_code,
        "FID_BLNG_CLS_CODE": blng_cls_code,
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
    result = inquire_index_category_price(iscd="0001", mrkt_cls_code="K", blng_cls_code="0")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
