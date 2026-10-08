# 선물옵션 시세[v1_국내선물-006]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-futureoption/v1/quotations/inquire-price"

_TR_ID = "FHMIF10000000"  # 실전/모의 동일


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    hts_kor_isnm: Optional[str] = None                      # HTS 한글 종목명
    futs_prpr: Optional[str] = None                         # 선물 현재가
    futs_prdy_vrss: Optional[str] = None                    # 선물 전일 대비
    prdy_vrss_sign: Optional[str] = None                    # 전일 대비 부호 (1 상한, 2 상승, 3 보합, 4 하한, 5 하락)
    futs_prdy_clpr: Optional[str] = None                    # 선물 전일 종가
    futs_prdy_ctrt: Optional[str] = None                    # 선물 전일 대비율
    acml_vol: Optional[str] = None                          # 누적 거래량
    acml_tr_pbmn: Optional[str] = None                      # 누적 거래 대금
    hts_otst_stpl_qty: Optional[str] = None                 # HTS 미결제 약정 수량
    otst_stpl_qty_icdc: Optional[str] = None                # 미결제 약정 수량 증감
    futs_oprc: Optional[str] = None                         # 선물 시가2
    futs_hgpr: Optional[str] = None                         # 선물 최고가
    futs_lwpr: Optional[str] = None                         # 선물 최저가
    futs_mxpr: Optional[str] = None                         # 선물 상한가
    futs_llam: Optional[str] = None                         # 선물 하한가
    basis: Optional[str] = None                             # 베이시스 (이론베이시스)
    futs_sdpr: Optional[str] = None                         # 선물 기준가
    hts_thpr: Optional[str] = None                          # HTS 이론가
    dprt: Optional[str] = None                              # 괴리율
    crbr_aply_mxpr: Optional[str] = None                    # 서킷브레이커 적용 상한가
    crbr_aply_llam: Optional[str] = None                    # 서킷브레이커 적용 하한가
    futs_last_tr_date: Optional[str] = None                 # 선물 최종 거래 일자
    hts_rmnn_dynu: Optional[str] = None                     # HTS 잔존 일수
    futs_lstn_medm_hgpr: Optional[str] = None               # 선물 상장 중 최고가
    futs_lstn_medm_lwpr: Optional[str] = None               # 선물 상장 중 최저가
    delta_val: Optional[str] = None                         # 델타 값
    gama: Optional[str] = None                              # 감마
    theta: Optional[str] = None                             # 세타
    vega: Optional[str] = None                              # 베가
    rho: Optional[str] = None                               # 로우
    hist_vltl: Optional[str] = None                         # 역사적 변동성
    hts_ints_vltl: Optional[str] = None                     # HTS 내재 변동성
    mrkt_basis: Optional[str] = None                        # 시장 베이시스
    acpr: Optional[str] = None                              # 행사가


@dataclass
class ResponseBodyOutput2:
    bstp_cls_code: Optional[str] = None                     # 업종 구분 코드
    hts_kor_isnm: Optional[str] = None                      # HTS 한글 종목명
    bstp_nmix_prpr: Optional[str] = None                    # 업종 지수 현재가
    prdy_vrss_sign: Optional[str] = None                    # 전일 대비 부호
    bstp_nmix_prdy_vrss: Optional[str] = None               # 업종 지수 전일 대비
    bstp_nmix_prdy_ctrt: Optional[str] = None               # 업종 지수 전일 대비율


@dataclass
class ResponseBodyOutput3:
    bstp_cls_code: Optional[str] = None                     # 업종 구분 코드
    hts_kor_isnm: Optional[str] = None                      # HTS 한글 종목명
    bstp_nmix_prpr: Optional[str] = None                    # 업종 지수 현재가
    prdy_vrss_sign: Optional[str] = None                    # 전일 대비 부호
    bstp_nmix_prdy_vrss: Optional[str] = None               # 업종 지수 전일 대비
    bstp_nmix_prdy_ctrt: Optional[str] = None               # 업종 지수 전일 대비율


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output1: ResponseBodyOutput1        # 선물옵션 시세 상세
    output2: ResponseBodyOutput2        # 업종 지수 — 종합(0001). 상품과 관계없이 같다
    output3: ResponseBodyOutput3        # 업종 지수 — KOSPI200(2001). 상품과 관계없이 같다


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_price(
    code: str,
    market_div: Literal["F", "O", "JF", "JO", "CF", "CM", "EU"],
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """선물옵션 시세를 조회한다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 선물옵션 단축코드(ex A01612 KOSPI200 선물 2026년 12월물).
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). F:지수선물, O:지수옵션, JF:주식선물,
            JO:주식옵션, CF:상품선물(금·국채·달러), CM:야간선물, EU:야간옵션.
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 시세 상세(output1), 종합 지수(output2), KOSPI200 지수(output3)를 담은 ResponseBody.
    """
    token = load_token(mode)
    if mode == "real":
        app_key, app_secret = REAL_APPKEY, REAL_APP_SECRET
    else:
        app_key, app_secret = PAPER_APPKEY, PAPER_APP_SECRET

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": _TR_ID,
        "custtype": "P",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": market_div,
        "FID_INPUT_ISCD": code,
    }
    response = get_session().get(DOMAIN[mode] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1/output2/output3 키가 없거나 null일 수 있어 안전 파싱.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or {}
    output1 = ResponseBodyOutput1(**{k: v for k, v in raw_output1.items() if k in fields1})

    fields2 = set(ResponseBodyOutput2.__dataclass_fields__)
    raw_output2 = raw.get("output2") or {}
    output2 = ResponseBodyOutput2(**{k: v for k, v in raw_output2.items() if k in fields2})

    fields3 = set(ResponseBodyOutput3.__dataclass_fields__)
    raw_output3 = raw.get("output3") or {}
    output3 = ResponseBodyOutput3(**{k: v for k, v in raw_output3.items() if k in fields3})

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
        output2=output2,
        output3=output3,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_price(code="A01612", market_div="F")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        print(result.output2)
        print(result.output3)
