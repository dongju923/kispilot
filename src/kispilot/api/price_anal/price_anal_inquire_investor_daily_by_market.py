# 시장별 투자자매매동향(일별)[국내주식-075]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0404] 시장별 일별동향 화면과 동일한 기능.
# ※ output은 입력 날짜(FID_INPUT_DATE_1)부터 과거로 300영업일이 최신순으로 한 번에 내려온다.
#   조회 기간을 줄이는 파라미터가 없어 응답을 받은 뒤 앞에서부터 days개만 잘라 반환한다.
#   FID_INPUT_DATE_2는 값을 바꿔도 결과에 영향이 없어 문서대로 입력 날짜1과 동일하게 보낸다.
# ※ 지수 시세(bstp_nmix_*)는 FID_INPUT_ISCD, 투자자 매매 수치는 FID_INPUT_ISCD_2(하위 분류코드)를
#   따른다. 둘을 다르게 주면 서로 다른 업종이 섞이므로 같은 업종코드로 맞춰 보낸다.
# ※ FID_COND_MRKT_DIV_CODE는 문서상 업종 "U" 고정값이라 파라미터로 노출하지 않는다.

_TR_ID = "FHPTJ04040000"

_MAX_DAYS = 300


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stck_bsop_date: Optional[str] = None            # 주식 영업 일자
    bstp_nmix_prpr: Optional[str] = None            # 업종 지수 현재가
    bstp_nmix_prdy_vrss: Optional[str] = None       # 업종 지수 전일 대비
    prdy_vrss_sign: Optional[str] = None            # 전일 대비 부호
    bstp_nmix_prdy_ctrt: Optional[str] = None       # 업종 지수 전일 대비율
    bstp_nmix_oprc: Optional[str] = None            # 업종 지수 시가2
    bstp_nmix_hgpr: Optional[str] = None            # 업종 지수 최고가
    bstp_nmix_lwpr: Optional[str] = None            # 업종 지수 최저가
    stck_prdy_clpr: Optional[str] = None            # 주식 전일 종가
    frgn_ntby_qty: Optional[str] = None             # 외국인 순매수 수량
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
    etc_orgt_ntby_vol: Optional[str] = None         # 기타 단체 순매수 거래량
    etc_corp_ntby_vol: Optional[str] = None         # 기타 법인 순매수 거래량
    frgn_ntby_tr_pbmn: Optional[str] = None         # 외국인 순매수 거래 대금
    frgn_reg_ntby_pbmn: Optional[str] = None        # 외국인 등록 순매수 대금
    frgn_nreg_ntby_pbmn: Optional[str] = None       # 외국인 비등록 순매수 대금
    prsn_ntby_tr_pbmn: Optional[str] = None         # 개인 순매수 거래 대금
    orgn_ntby_tr_pbmn: Optional[str] = None         # 기관계 순매수 거래 대금
    scrt_ntby_tr_pbmn: Optional[str] = None         # 증권 순매수 거래 대금
    ivtr_ntby_tr_pbmn: Optional[str] = None         # 투자신탁 순매수 거래 대금
    pe_fund_ntby_tr_pbmn: Optional[str] = None      # 사모 펀드 순매수 거래 대금
    bank_ntby_tr_pbmn: Optional[str] = None         # 은행 순매수 거래 대금
    insu_ntby_tr_pbmn: Optional[str] = None         # 보험 순매수 거래 대금
    mrbn_ntby_tr_pbmn: Optional[str] = None         # 종금 순매수 거래 대금
    fund_ntby_tr_pbmn: Optional[str] = None         # 기금 순매수 거래 대금
    etc_ntby_tr_pbmn: Optional[str] = None          # 기타 순매수 거래 대금
    etc_orgt_ntby_tr_pbmn: Optional[str] = None     # 기타 단체 순매수 거래 대금
    etc_corp_ntby_tr_pbmn: Optional[str] = None     # 기타 법인 순매수 거래 대금


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 일별 투자자 매매동향(배열, 최신순, 최대 300영업일)


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_investor_daily_by_market(
    market: Literal["KSP", "KSQ"],
    sector_code: str,
    date: str,
    days: int = 30,
) -> ResponseBody:
    """시장별 투자자매매동향(일별)을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0404] 시장별 일별동향 화면 기능과 동일.
    입력 날짜부터 과거로 days 영업일의 업종 지수와 투자자별 순매수 동향을 최신순으로 돌려준다.
    (API는 항상 300영업일을 내려주고, 앞에서부터 days개만 잘라 반환한다.)

    Args:
        market: 시장 구분(FID_INPUT_ISCD_1). KSP:코스피, KSQ:코스닥.
        sector_code: 업종분류코드(FID_INPUT_ISCD, FID_INPUT_ISCD_2). ex) 0001:코스피 종합, 1001:코스닥 종합.
            종목정보파일 - 업종코드 참조.
        date: 입력 날짜(FID_INPUT_DATE_1), YYYYMMDD(ex 20240517).
        days: 조회할 영업일 수(1~300). 1이면 입력 날짜만, 2면 입력 날짜와 그 전 영업일까지. 기본값 30.

    Returns:
        rt_cd/msg_cd/msg1과 일별 투자자 매매동향(output, 최대 days개)을 담은 ResponseBody.
    """
    if not 1 <= days <= _MAX_DAYS:
        raise ValueError(f"days는 1~{_MAX_DAYS} 사이로 입력하세요. (입력: {days})")

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
        "FID_COND_MRKT_DIV_CODE": "U",
        "FID_INPUT_ISCD": sector_code,
        "FID_INPUT_DATE_1": date,
        "FID_INPUT_ISCD_1": market,
        "FID_INPUT_DATE_2": date,
        "FID_INPUT_ISCD_2": sector_code,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output 키가 없거나 null일 수 있어 안전 파싱.
    # output은 최신순이라 앞에서부터 days개만 사용한다.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_output = (raw.get("output") or [])[:days]
    output = [ResponseBodyOutput(**{k: v for k, v in item.items() if k in fields}) for item in raw_output]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output=output,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_investor_daily_by_market(market="KSP", sector_code="0001", date="20260921")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
