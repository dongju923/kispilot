# 주식기본조회[v1_국내주식-067]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/search-stock-info"
# ※ 모의투자 미지원 (실전투자 전용).

_TR_ID = "CTPF1002R"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    pdno: Optional[str] = None                        # 상품번호
    prdt_type_cd: Optional[str] = None                # 상품유형코드
    mket_id_cd: Optional[str] = None                  # 시장ID코드 (STK:유가증권, KSQ:코스닥, KNX:코넥스 등)
    scty_grp_id_cd: Optional[str] = None              # 증권그룹ID코드 (ST:주권, EF:ETF, EN:ETN 등)
    excg_dvsn_cd: Optional[str] = None                # 거래소구분코드
    setl_mmdd: Optional[str] = None                   # 결산월일
    lstg_stqt: Optional[str] = None                   # 상장주수
    lstg_cptl_amt: Optional[str] = None               # 상장자본금액
    cpta: Optional[str] = None                        # 자본금
    papr: Optional[str] = None                        # 액면가
    issu_pric: Optional[str] = None                   # 발행가격
    kospi200_item_yn: Optional[str] = None            # 코스피200종목여부
    scts_mket_lstg_dt: Optional[str] = None           # 유가증권시장상장일자
    scts_mket_lstg_abol_dt: Optional[str] = None      # 유가증권시장상장폐지일자
    kosdaq_mket_lstg_dt: Optional[str] = None         # 코스닥시장상장일자
    kosdaq_mket_lstg_abol_dt: Optional[str] = None    # 코스닥시장상장폐지일자
    frbd_mket_lstg_dt: Optional[str] = None           # 프리보드시장상장일자
    frbd_mket_lstg_abol_dt: Optional[str] = None      # 프리보드시장상장폐지일자
    reits_kind_cd: Optional[str] = None               # 리츠종류코드
    etf_dvsn_cd: Optional[str] = None                 # ETF구분코드
    oilf_fund_yn: Optional[str] = None                # 유전펀드여부
    idx_bztp_lcls_cd: Optional[str] = None            # 지수업종대분류코드
    idx_bztp_mcls_cd: Optional[str] = None            # 지수업종중분류코드
    idx_bztp_scls_cd: Optional[str] = None            # 지수업종소분류코드
    stck_kind_cd: Optional[str] = None                # 주식종류코드 (101:보통주, 201:우선주 등)
    mfnd_opng_dt: Optional[str] = None                # 뮤추얼펀드개시일자
    mfnd_end_dt: Optional[str] = None                 # 뮤추얼펀드종료일자
    dpsi_erlm_cncl_dt: Optional[str] = None           # 예탁등록취소일자
    etf_cu_qty: Optional[str] = None                  # ETFCU수량
    prdt_name: Optional[str] = None                   # 상품명
    prdt_name120: Optional[str] = None                # 상품명120
    prdt_abrv_name: Optional[str] = None              # 상품약어명
    std_pdno: Optional[str] = None                    # 표준상품번호
    prdt_eng_name: Optional[str] = None               # 상품영문명
    prdt_eng_name120: Optional[str] = None            # 상품영문명120
    prdt_eng_abrv_name: Optional[str] = None          # 상품영문약어명
    dpsi_aptm_erlm_yn: Optional[str] = None           # 예탁지정등록여부
    etf_txtn_type_cd: Optional[str] = None            # ETF과세유형코드
    etf_type_cd: Optional[str] = None                 # ETF유형코드
    lstg_abol_dt: Optional[str] = None                # 상장폐지일자
    nwst_odst_dvsn_cd: Optional[str] = None           # 신주구주구분코드
    sbst_pric: Optional[str] = None                   # 대용가격
    thco_sbst_pric: Optional[str] = None              # 당사대용가격
    thco_sbst_pric_chng_dt: Optional[str] = None      # 당사대용가격변경일자
    tr_stop_yn: Optional[str] = None                  # 거래정지여부
    admn_item_yn: Optional[str] = None                # 관리종목여부
    thdt_clpr: Optional[str] = None                   # 당일종가
    bfdy_clpr: Optional[str] = None                   # 전일종가
    clpr_chng_dt: Optional[str] = None                # 종가변경일자
    std_idst_clsf_cd: Optional[str] = None            # 표준산업분류코드
    std_idst_clsf_cd_name: Optional[str] = None       # 표준산업분류코드명
    idx_bztp_lcls_cd_name: Optional[str] = None       # 지수업종대분류코드명
    idx_bztp_mcls_cd_name: Optional[str] = None       # 지수업종중분류코드명
    idx_bztp_scls_cd_name: Optional[str] = None       # 지수업종소분류코드명
    ocr_no: Optional[str] = None                      # OCR번호
    crfd_item_yn: Optional[str] = None                # 크라우드펀딩종목여부
    elec_scty_yn: Optional[str] = None                # 전자증권여부
    issu_istt_cd: Optional[str] = None                # 발행기관코드
    etf_chas_erng_rt_dbnb: Optional[str] = None       # ETF추적수익율배수
    etf_etn_ivst_heed_item_yn: Optional[str] = None   # ETFETN투자유의종목여부
    stln_int_rt_dvsn_cd: Optional[str] = None         # 대주이자율구분코드
    frnr_psnl_lmt_rt: Optional[str] = None            # 외국인개인한도비율
    lstg_rqsr_issu_istt_cd: Optional[str] = None      # 상장신청인발행기관코드
    lstg_rqsr_item_cd: Optional[str] = None           # 상장신청인종목코드
    trst_istt_issu_istt_cd: Optional[str] = None      # 신탁기관발행기관코드
    cptt_trad_tr_psbl_yn: Optional[str] = None        # NXT 거래종목여부
    nxt_tr_stop_yn: Optional[str] = None              # NXT 거래정지여부


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output: ResponseBodyOutput          # 응답상세1


# ── 요청 함수 ───────────────────────────────────────────────

def search_stock_info(
    code: str,
    prdt_type: Literal["300", "301", "302", "306"] = "300",
) -> ResponseBody:
    """주식기본조회(종목상세정보)를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    Args:
        code: 상품번호(PDNO). 종목번호 6자리(ex 005930). ETN은 Q로 시작(ex Q500001).
        prdt_type: 상품유형코드(PRDT_TYPE_CD). 300:주식/ETF/ETN/ELW, 301:선물옵션, 302:채권, 306:ELS.
            기본값 "300".

    Returns:
        rt_cd/msg_cd/msg1과 종목 기본정보(output)를 담은 ResponseBody.
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
        "PRDT_TYPE_CD": prdt_type,
        "PDNO": code,
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
    result = search_stock_info(code="005930")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output)
