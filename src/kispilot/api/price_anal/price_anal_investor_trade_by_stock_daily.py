# 종목별 투자자매매동향(일별)
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/investor-trade-by-stock-daily"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0416] 종목별 일별동향 화면과 동일한 기능.
# ※ 단위: 금액(백만원), 수량(주).
# ※ 당일 데이터는 15:40 이후 가집계/산출되어 조회 가능하다(산출 시간은 일정하지 않을 수 있음).
# ※ output2는 입력 날짜부터 과거로 30영업일이 내려온다. 문서상 tr_cont 연속조회가 있지만
#   실제 응답 헤더의 tr_cont는 공백이고 "N"으로 재요청해도 같은 데이터가 내려와서,
#   페이지네이션 없이 1회 호출로 구현했다. 더 과거 데이터는 날짜를 바꿔 다시 호출한다.
# ※ FID_ORG_ADJ_PRC(공란), FID_ETC_CLS_CODE("1")는 문서상 고정값이라 파라미터로 노출하지 않는다.

_TR_ID = "FHPTJ04160001"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    stck_prpr: Optional[str] = None                 # 주식 현재가
    prdy_vrss: Optional[str] = None                 # 전일 대비
    prdy_vrss_sign: Optional[str] = None            # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                 # 전일 대비율
    acml_vol: Optional[str] = None                  # 누적 거래량
    prdy_vol: Optional[str] = None                  # 전일 거래량
    rprs_mrkt_kor_name: Optional[str] = None        # 대표 시장 한글 명


@dataclass
class ResponseBodyOutput2:
    stck_bsop_date: Optional[str] = None            # 주식 영업 일자
    stck_clpr: Optional[str] = None                 # 주식 종가
    prdy_vrss: Optional[str] = None                 # 전일 대비
    prdy_vrss_sign: Optional[str] = None            # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                 # 전일 대비율
    acml_vol: Optional[str] = None                  # 누적 거래량(주)
    acml_tr_pbmn: Optional[str] = None              # 누적 거래 대금(백만원)
    stck_oprc: Optional[str] = None                 # 주식 시가2
    stck_hgpr: Optional[str] = None                 # 주식 최고가
    stck_lwpr: Optional[str] = None                 # 주식 최저가
    frgn_ntby_qty: Optional[str] = None             # 외국인 순매수 수량(주)
    frgn_reg_ntby_qty: Optional[str] = None         # 외국인 등록 순매수 수량
    frgn_nreg_ntby_qty: Optional[str] = None        # 외국인 비등록 순매수 수량
    prsn_ntby_qty: Optional[str] = None             # 개인 순매수 수량
    orgn_ntby_qty: Optional[str] = None             # 기관계 순매수 수량
    scrt_ntby_qty: Optional[str] = None             # 증권 순매수 수량
    ivtr_ntby_qty: Optional[str] = None             # 투자신탁 순매수 수량
    pe_fund_ntby_vol: Optional[str] = None          # 사모 펀드 순매수 거래량
    bank_ntby_qty: Optional[str] = None             # 은행 순매수 수량
    insu_ntby_qty: Optional[str] = None             # 보험 순매수 수량
    mrbn_ntby_qty: Optional[str] = None             # 종금 순매수 수량
    fund_ntby_qty: Optional[str] = None             # 기금 순매수 수량
    etc_ntby_qty: Optional[str] = None              # 기타 순매수 수량
    etc_corp_ntby_vol: Optional[str] = None         # 기타 법인 순매수 거래량
    etc_orgt_ntby_vol: Optional[str] = None         # 기타 단체 순매수 거래량
    frgn_reg_ntby_pbmn: Optional[str] = None        # 외국인 등록 순매수 대금(백만원)
    frgn_ntby_tr_pbmn: Optional[str] = None         # 외국인 순매수 거래 대금
    frgn_nreg_ntby_pbmn: Optional[str] = None       # 외국인 비등록 순매수 대금
    prsn_ntby_tr_pbmn: Optional[str] = None         # 개인 순매수 거래 대금
    orgn_ntby_tr_pbmn: Optional[str] = None         # 기관계 순매수 거래 대금
    scrt_ntby_tr_pbmn: Optional[str] = None         # 증권 순매수 거래 대금
    pe_fund_ntby_tr_pbmn: Optional[str] = None      # 사모 펀드 순매수 거래 대금
    ivtr_ntby_tr_pbmn: Optional[str] = None         # 투자신탁 순매수 거래 대금
    bank_ntby_tr_pbmn: Optional[str] = None         # 은행 순매수 거래 대금
    insu_ntby_tr_pbmn: Optional[str] = None         # 보험 순매수 거래 대금
    mrbn_ntby_tr_pbmn: Optional[str] = None         # 종금 순매수 거래 대금
    fund_ntby_tr_pbmn: Optional[str] = None         # 기금 순매수 거래 대금
    etc_ntby_tr_pbmn: Optional[str] = None          # 기타 순매수 거래 대금
    etc_corp_ntby_tr_pbmn: Optional[str] = None     # 기타 법인 순매수 거래 대금
    etc_orgt_ntby_tr_pbmn: Optional[str] = None     # 기타 단체 순매수 거래 대금
    frgn_seln_vol: Optional[str] = None             # 외국인 매도 거래량
    frgn_shnu_vol: Optional[str] = None             # 외국인 매수2 거래량
    frgn_seln_tr_pbmn: Optional[str] = None         # 외국인 매도 거래 대금
    frgn_shnu_tr_pbmn: Optional[str] = None         # 외국인 매수2 거래 대금
    frgn_reg_askp_qty: Optional[str] = None         # 외국인 등록 매도 수량
    frgn_reg_bidp_qty: Optional[str] = None         # 외국인 등록 매수 수량
    frgn_reg_askp_pbmn: Optional[str] = None        # 외국인 등록 매도 대금
    frgn_reg_bidp_pbmn: Optional[str] = None        # 외국인 등록 매수 대금
    frgn_nreg_askp_qty: Optional[str] = None        # 외국인 비등록 매도 수량
    frgn_nreg_bidp_qty: Optional[str] = None        # 외국인 비등록 매수 수량
    frgn_nreg_askp_pbmn: Optional[str] = None       # 외국인 비등록 매도 대금
    frgn_nreg_bidp_pbmn: Optional[str] = None       # 외국인 비등록 매수 대금
    prsn_seln_vol: Optional[str] = None             # 개인 매도 거래량
    prsn_shnu_vol: Optional[str] = None             # 개인 매수2 거래량
    prsn_seln_tr_pbmn: Optional[str] = None         # 개인 매도 거래 대금
    prsn_shnu_tr_pbmn: Optional[str] = None         # 개인 매수2 거래 대금
    orgn_seln_vol: Optional[str] = None             # 기관계 매도 거래량
    orgn_shnu_vol: Optional[str] = None             # 기관계 매수2 거래량
    orgn_seln_tr_pbmn: Optional[str] = None         # 기관계 매도 거래 대금
    orgn_shnu_tr_pbmn: Optional[str] = None         # 기관계 매수2 거래 대금
    scrt_seln_vol: Optional[str] = None             # 증권 매도 거래량
    scrt_shnu_vol: Optional[str] = None             # 증권 매수2 거래량
    scrt_seln_tr_pbmn: Optional[str] = None         # 증권 매도 거래 대금
    scrt_shnu_tr_pbmn: Optional[str] = None         # 증권 매수2 거래 대금
    ivtr_seln_vol: Optional[str] = None             # 투자신탁 매도 거래량
    ivtr_shnu_vol: Optional[str] = None             # 투자신탁 매수2 거래량
    ivtr_seln_tr_pbmn: Optional[str] = None         # 투자신탁 매도 거래 대금
    ivtr_shnu_tr_pbmn: Optional[str] = None         # 투자신탁 매수2 거래 대금
    pe_fund_seln_tr_pbmn: Optional[str] = None      # 사모 펀드 매도 거래 대금
    pe_fund_seln_vol: Optional[str] = None          # 사모 펀드 매도 거래량
    pe_fund_shnu_tr_pbmn: Optional[str] = None      # 사모 펀드 매수2 거래 대금
    pe_fund_shnu_vol: Optional[str] = None          # 사모 펀드 매수2 거래량
    bank_seln_vol: Optional[str] = None             # 은행 매도 거래량
    bank_shnu_vol: Optional[str] = None             # 은행 매수2 거래량
    bank_seln_tr_pbmn: Optional[str] = None         # 은행 매도 거래 대금
    bank_shnu_tr_pbmn: Optional[str] = None         # 은행 매수2 거래 대금
    insu_seln_vol: Optional[str] = None             # 보험 매도 거래량
    insu_shnu_vol: Optional[str] = None             # 보험 매수2 거래량
    insu_seln_tr_pbmn: Optional[str] = None         # 보험 매도 거래 대금
    insu_shnu_tr_pbmn: Optional[str] = None         # 보험 매수2 거래 대금
    mrbn_seln_vol: Optional[str] = None             # 종금 매도 거래량
    mrbn_shnu_vol: Optional[str] = None             # 종금 매수2 거래량
    mrbn_seln_tr_pbmn: Optional[str] = None         # 종금 매도 거래 대금
    mrbn_shnu_tr_pbmn: Optional[str] = None         # 종금 매수2 거래 대금
    fund_seln_vol: Optional[str] = None             # 기금 매도 거래량
    fund_shnu_vol: Optional[str] = None             # 기금 매수2 거래량
    fund_seln_tr_pbmn: Optional[str] = None         # 기금 매도 거래 대금
    fund_shnu_tr_pbmn: Optional[str] = None         # 기금 매수2 거래 대금
    etc_seln_vol: Optional[str] = None              # 기타 매도 거래량
    etc_shnu_vol: Optional[str] = None              # 기타 매수2 거래량
    etc_seln_tr_pbmn: Optional[str] = None          # 기타 매도 거래 대금
    etc_shnu_tr_pbmn: Optional[str] = None          # 기타 매수2 거래 대금
    etc_orgt_seln_vol: Optional[str] = None         # 기타 단체 매도 거래량
    etc_orgt_shnu_vol: Optional[str] = None         # 기타 단체 매수2 거래량
    etc_orgt_seln_tr_pbmn: Optional[str] = None     # 기타 단체 매도 거래 대금
    etc_orgt_shnu_tr_pbmn: Optional[str] = None     # 기타 단체 매수2 거래 대금
    etc_corp_seln_vol: Optional[str] = None         # 기타 법인 매도 거래량
    etc_corp_shnu_vol: Optional[str] = None         # 기타 법인 매수2 거래량
    etc_corp_seln_tr_pbmn: Optional[str] = None     # 기타 법인 매도 거래 대금
    etc_corp_shnu_tr_pbmn: Optional[str] = None     # 기타 법인 매수2 거래 대금
    bold_yn: Optional[str] = None                   # BOLD 여부


@dataclass
class ResponseBody:
    rt_cd: str                                                                  # 성공 실패 여부
    msg_cd: str                                                                 # 응답코드
    msg1: str                                                                   # 응답메세지
    output1: ResponseBodyOutput1 = field(default_factory=ResponseBodyOutput1)   # 종목 현재 시세(단일)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)            # 일별 투자자 매매동향(배열, 30영업일)


# ── 요청 함수 ───────────────────────────────────────────────

def investor_trade_by_stock_daily(
    code: str,
    date: str,
    market_div: Literal["J", "NX", "UN"] = "J",
) -> ResponseBody:
    """종목별 투자자매매동향(일별)을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0416] 종목별 일별동향 화면 기능과 동일.
    입력 날짜부터 과거로 30영업일의 투자자별 매매동향이 내려온다. 단위: 금액(백만원), 수량(주).

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930).
        date: 입력 날짜(FID_INPUT_DATE_1), YYYYMMDD(ex 20250812). 당일은 15:40 이후 조회 가능.
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".

    Returns:
        rt_cd/msg_cd/msg1과 종목 현재 시세(output1), 일별 투자자 매매동향(output2)을 담은 ResponseBody.
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
        "FID_COND_MRKT_DIV_CODE": market_div,
        "FID_INPUT_ISCD": code,
        "FID_INPUT_DATE_1": date,
        "FID_ORG_ADJ_PRC": "",
        "FID_ETC_CLS_CODE": "1",
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
    result = investor_trade_by_stock_daily(code="005930", date="20250812")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
