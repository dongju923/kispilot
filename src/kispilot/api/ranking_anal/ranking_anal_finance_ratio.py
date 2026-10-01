# 국내주식 재무비율 순위[v1_국내주식-092]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/ranking/finance-ratio"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0175] 재무비율순위 화면과 동일한 기능.
# ※ 최대 30건까지만 조회되며 연속조회(tr_cont) 불가. 30건 이상은 종목조건검색 API(최대 100건)로 대체.
# ※ fid_cond_scr_div_code(20175)는 문서상 고정값이라 파라미터로 노출하지 않는다.
# ※ 이 API는 쿼리 파라미터 키가 소문자(fid_...)로 문서화되어 있다.

_TR_ID = "FHPST01750000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    data_rank: Optional[str] = None                 # 데이터 순위
    hts_kor_isnm: Optional[str] = None              # HTS 한글 종목명
    mksc_shrn_iscd: Optional[str] = None            # 유가증권 단축 종목코드
    stck_prpr: Optional[str] = None                 # 주식 현재가
    prdy_vrss: Optional[str] = None                 # 전일 대비
    prdy_vrss_sign: Optional[str] = None            # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                 # 전일 대비율
    acml_vol: Optional[str] = None                  # 누적 거래량
    cptl_op_prfi: Optional[str] = None              # 총자본경상이익율
    cptl_ntin_rate: Optional[str] = None            # 총자본 순이익율
    sale_totl_rate: Optional[str] = None            # 매출액 총이익율
    sale_ntin_rate: Optional[str] = None            # 매출액 순이익율
    bis: Optional[str] = None                       # 자기자본비율
    lblt_rate: Optional[str] = None                 # 부채 비율
    bram_depn: Optional[str] = None                 # 차입금 의존도
    rsrv_rate: Optional[str] = None                 # 유보 비율
    grs: Optional[str] = None                       # 매출액 증가율
    op_prfi_inrt: Optional[str] = None              # 경상 이익 증가율
    bsop_prfi_inrt: Optional[str] = None            # 영업 이익 증가율
    ntin_inrt: Optional[str] = None                 # 순이익 증가율
    equt_inrt: Optional[str] = None                 # 자기자본 증가율
    cptl_tnrt: Optional[str] = None                 # 총자본회전율
    sale_bond_tnrt: Optional[str] = None            # 매출 채권 회전율
    totl_aset_inrt: Optional[str] = None            # 총자산 증가율
    stac_month: Optional[str] = None                # 결산 월
    stac_month_cls_code: Optional[str] = None       # 결산 월 구분 코드
    iqry_csnu: Optional[str] = None                 # 조회 건수


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 재무비율 순위(배열, 최대 30건)


# ── 요청 함수 ───────────────────────────────────────────────

def finance_ratio(
    fiscal_year: str,
    quarter: Literal["0", "1", "2", "3"] = "3",
    rank_sort_cls: Literal[
        "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22"
    ] = "7",
    sector_code: Literal["0000", "0001", "1001", "2001"] = "0000",
    market_div: Literal["J", "NX"] = "J",
    price_1: str = "",
    price_2: str = "",
    vol_cnt: str = "",
    trgt_cls: str = "0",
    trgt_exls_cls: str = "0",
    div_cls: str = "0",
    blng_cls: str = "0",
) -> ResponseBody:
    """국내주식 재무비율 순위를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0175] 재무비율순위 화면 기능과 동일. 최대 30건, 연속조회 불가.

    Args:
        fiscal_year: 회계연도(fid_input_option_1), 4자리(ex 2023).
        quarter: 분기(fid_input_option_2). 0:1/4분기, 1:반기, 2:3/4분기, 3:결산. 기본값 "3".
        rank_sort_cls: 순위 정렬 구분 코드(fid_rank_sort_cls_code). 문서에는 7:수익성 분석, 11:안정성 분석,
            15:성장성 분석, 20:활동성 분석만 나오지만, 실제로는 7~22가 각각 아래 응답 필드의
            내림차순으로 정렬한다. 기본값 "7".
              수익성  7:총자본경상이익율(cptl_op_prfi)  8:총자본순이익율(cptl_ntin_rate)
                      9:매출액총이익율(sale_totl_rate)  10:매출액순이익율(sale_ntin_rate)
              안정성  11:자기자본비율(bis)  12:부채비율(lblt_rate)
                      13:차입금의존도(bram_depn)  14:유보비율(rsrv_rate)
              성장성  15:매출액증가율(grs)  16:경상이익증가율(op_prfi_inrt)  17:영업이익증가율(bsop_prfi_inrt)
                      18:순이익증가율(ntin_inrt)  19:자기자본증가율(equt_inrt)
              활동성  20:총자본회전율(cptl_tnrt)  21:매출채권회전율(sale_bond_tnrt)
                      22:총자산증가율(totl_aset_inrt)
        sector_code: 입력 종목코드(fid_input_iscd). 0000:전체, 0001:거래소, 1001:코스닥, 2001:코스피200.
            기본값 "0000".
        market_div: 조건 시장 분류 코드(fid_cond_mrkt_div_code). J:KRX, NX:NXT. 기본값 "J".
        price_1: 입력 가격1(fid_input_price_1), 가격 ~. 공백이면 전체.
        price_2: 입력 가격2(fid_input_price_2), ~ 가격. 공백이면 전체.
        vol_cnt: 거래량 수(fid_vol_cnt), 거래량 ~. 공백이면 전체.
        trgt_cls: 대상 구분 코드(fid_trgt_cls_code). "0":전체, 또는 1/0 9자리로 포함할 대상을 지정
            (증거금 30% 40% 50% 60% 100%, 신용보증금 30% 40% 50% 60% 순, 1=포함).
            ex) "000010000" → 증거금 100% 종목만. "0"과 "111111111"은 결과가 같다. 기본값 "0".
        trgt_exls_cls: 대상 제외 구분 코드(fid_trgt_exls_cls_code). "0":전체(제외 없음), 또는 1/0 10자리로
            제외할 대상을 지정(투자위험/경고/주의, 관리종목, 정리매매, 불성실공시, 우선주, 거래정지, ETF, ETN,
            신용주문불가, SPAC 순, 1=제외). ex) "1100000000" → 투자위험/경고/주의, 관리종목 제외. 기본값 "0".
        div_cls: 분류 구분 코드(fid_div_cls_code). 0:전체. 기본값 "0".
        blng_cls: 소속 구분 코드(fid_blng_cls_code). 0:전체. 기본값 "0".

    Returns:
        rt_cd/msg_cd/msg1과 재무비율 순위 종목 목록(output)을 담은 ResponseBody.
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
        "fid_trgt_cls_code": trgt_cls,
        "fid_cond_mrkt_div_code": market_div,
        "fid_cond_scr_div_code": "20175",
        "fid_input_iscd": sector_code,
        "fid_div_cls_code": div_cls,
        "fid_input_price_1": price_1,
        "fid_input_price_2": price_2,
        "fid_vol_cnt": vol_cnt,
        "fid_input_option_1": fiscal_year,
        "fid_input_option_2": quarter,
        "fid_rank_sort_cls_code": rank_sort_cls,
        "fid_blng_cls_code": blng_cls,
        "fid_trgt_exls_cls_code": trgt_exls_cls,
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
    result = finance_ratio(fiscal_year="2025")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
