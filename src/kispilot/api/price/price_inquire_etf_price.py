# ETF/ETN 현재가[v1_국내주식-068]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/etfetn/v1/quotations/inquire-price"
# ※ 한국투자 HTS(eFriend Plus) [0240] ETF/ETN 현재가 화면 기능에 해당.

_TR_ID = "FHPST02400000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stck_prpr: Optional[str] = None                        # 주식 현재가
    prdy_vrss_sign: Optional[str] = None                     # 전일 대비 부호
    prdy_vrss: Optional[str] = None                           # 전일 대비
    prdy_ctrt: Optional[str] = None                             # 전일 대비율
    acml_vol: Optional[str] = None                               # 누적 거래량
    prdy_vol: Optional[str] = None                                # 전일 거래량
    stck_mxpr: Optional[str] = None                                 # 주식 상한가
    stck_llam: Optional[str] = None                                  # 주식 하한가
    stck_prdy_clpr: Optional[str] = None                              # 주식 전일 종가
    stck_oprc: Optional[str] = None                                    # 주식 시가2
    prdy_clpr_vrss_oprc_rate: Optional[str] = None                      # 전일 종가 대비 시가2 비율
    stck_hgpr: Optional[str] = None                                       # 주식 최고가
    prdy_clpr_vrss_hgpr_rate: Optional[str] = None                        # 전일 종가 대비 최고가 비율
    stck_lwpr: Optional[str] = None                                         # 주식 최저가
    prdy_clpr_vrss_lwpr_rate: Optional[str] = None                          # 전일 종가 대비 최저가 비율
    prdy_last_nav: Optional[str] = None                                      # 전일 최종 NAV
    nav: Optional[str] = None                                                 # NAV
    nav_prdy_vrss: Optional[str] = None                                       # NAV 전일 대비
    nav_prdy_vrss_sign: Optional[str] = None                                   # NAV 전일 대비 부호
    nav_prdy_ctrt: Optional[str] = None                                        # NAV 전일 대비율
    trc_errt: Optional[str] = None                                             # 추적 오차율
    stck_sdpr: Optional[str] = None                                             # 주식 기준가
    stck_sspr: Optional[str] = None                                              # 주식 대용가
    nmix_ctrt: Optional[str] = None                                              # 지수 대비율
    etf_crcl_stcn: Optional[str] = None                                          # ETF 유통 주수
    etf_ntas_ttam: Optional[str] = None                                          # ETF 순자산 총액
    etf_frcr_ntas_ttam: Optional[str] = None                                     # ETF 외화 순자산 총액
    frgn_limt_rate: Optional[str] = None                                         # 외국인 한도 비율
    frgn_oder_able_qty: Optional[str] = None                                     # 외국인 주문 가능 수량
    etf_cu_unit_scrt_cnt: Optional[str] = None                                   # ETF CU 단위 증권 수
    etf_cnfg_issu_cnt: Optional[str] = None                                      # ETF 구성 종목 수
    etf_dvdn_cycl: Optional[str] = None                                          # ETF 배당 주기
    crcd: Optional[str] = None                                                   # 통화 코드
    etf_crcl_ntas_ttam: Optional[str] = None                                     # ETF 유통 순자산 총액
    etf_frcr_crcl_ntas_ttam: Optional[str] = None                                # ETF 외화 유통 순자산 총액
    etf_frcr_last_ntas_wrth_val: Optional[str] = None                            # ETF 외화 최종 순자산 가치 값
    lp_oder_able_cls_code: Optional[str] = None                                  # LP 주문 가능 구분 코드
    stck_dryy_hgpr: Optional[str] = None                                        # 주식 연중 최고가
    dryy_hgpr_vrss_prpr_rate: Optional[str] = None                              # 연중 최고가 대비 현재가 비율
    dryy_hgpr_date: Optional[str] = None                                        # 연중 최고가 일자
    stck_dryy_lwpr: Optional[str] = None                                        # 주식 연중 최저가
    dryy_lwpr_vrss_prpr_rate: Optional[str] = None                              # 연중 최저가 대비 현재가 비율
    dryy_lwpr_date: Optional[str] = None                                        # 연중 최저가 일자
    bstp_kor_isnm: Optional[str] = None                                         # 업종 한글 종목명
    vi_cls_code: Optional[str] = None                                           # VI적용구분코드
    lstn_stcn: Optional[str] = None                                             # 상장 주수
    frgn_hldn_qty: Optional[str] = None                                         # 외국인 보유 수량
    frgn_hldn_qty_rate: Optional[str] = None                                    # 외국인 보유 수량 비율
    etf_trc_ert_mltp: Optional[str] = None                                      # ETF 추적 수익률 배수
    dprt: Optional[str] = None                                                  # 괴리율
    mbcr_name: Optional[str] = None                                             # 회원사 명
    stck_lstn_date: Optional[str] = None                                        # 주식 상장 일자
    mtrt_date: Optional[str] = None                                             # 만기 일자
    shrg_type_code: Optional[str] = None                                        # 분배금형태코드
    lp_hldn_rate: Optional[str] = None                                          # LP 보유 비율
    etf_trgt_nmix_bstp_code: Optional[str] = None                               # ETF대상지수업종코드
    etf_div_name: Optional[str] = None                                          # ETF 분류 명
    etf_rprs_bstp_kor_isnm: Optional[str] = None                                # ETF 대표 업종 한글 종목명
    lp_hldn_vol: Optional[str] = None                                           # ETN LP 보유량


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output: ResponseBodyOutput          # ETF/ETN 현재가 상세


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_etf_price(
    code: str,
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """ETF/ETN 현재가를 조회한다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 069500 KODEX 200).
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 ETF/ETN 현재가 상세(output)를 담은 ResponseBody.
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
    result = inquire_etf_price(code="069500")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output)
