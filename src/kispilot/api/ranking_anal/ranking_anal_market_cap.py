# 국내주식 시가총액 상위[v1_국내주식-091]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/ranking/market-cap"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0174] 시가총액 상위 화면과 동일한 기능.
# ※ 최대 30건까지만 조회되며 연속조회(tr_cont) 불가. 30건 이상은 종목조건검색 API(최대 100건)로 대체.
# ※ fid_cond_scr_div_code(20174)는 문서상 고정값이라 파라미터로 노출하지 않는다.
# ※ 이 API는 쿼리 파라미터 키가 소문자(fid_...)로 문서화되어 있다.

_TR_ID = "FHPST01740000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    mksc_shrn_iscd: Optional[str] = None            # 유가증권 단축 종목코드
    data_rank: Optional[str] = None                 # 데이터 순위
    hts_kor_isnm: Optional[str] = None              # HTS 한글 종목명
    stck_prpr: Optional[str] = None                 # 주식 현재가
    prdy_vrss: Optional[str] = None                 # 전일 대비
    prdy_vrss_sign: Optional[str] = None            # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                 # 전일 대비율
    acml_vol: Optional[str] = None                  # 누적 거래량
    lstn_stcn: Optional[str] = None                 # 상장 주수
    stck_avls: Optional[str] = None                 # 시가 총액(억원)
    mrkt_whol_avls_rlim: Optional[str] = None       # 시장 전체 시가총액 비중(%)


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 시가총액 상위(배열, 최대 30건)


# ── 요청 함수 ───────────────────────────────────────────────

def market_cap(
    sector_code: Literal["0000", "0001", "1001", "2001"] = "0000",
    div_cls: Literal["0", "1", "2"] = "0",
    market_div: Literal["J", "NX"] = "J",
    price_1: str = "",
    price_2: str = "",
    vol_cnt: str = "",
    trgt_cls: str = "0",
    trgt_exls_cls: str = "0",
) -> ResponseBody:
    """국내주식 시가총액 상위 종목을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0174] 시가총액 상위 화면 기능과 동일. 최대 30건, 연속조회 불가.

    Args:
        sector_code: 입력 종목코드(fid_input_iscd). 0000:전체, 0001:거래소, 1001:코스닥, 2001:코스피200.
            기본값 "0000".
        div_cls: 분류 구분 코드(fid_div_cls_code). 0:전체, 1:보통주, 2:우선주. 기본값 "0".
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

    Returns:
        rt_cd/msg_cd/msg1과 시가총액 상위 종목 목록(output)을 담은 ResponseBody.
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
        "fid_input_price_2": price_2,
        "fid_cond_mrkt_div_code": market_div,
        "fid_cond_scr_div_code": "20174",
        "fid_div_cls_code": div_cls,
        "fid_input_iscd": sector_code,
        "fid_trgt_cls_code": trgt_cls,
        "fid_trgt_exls_cls_code": trgt_exls_cls,
        "fid_input_price_1": price_1,
        "fid_vol_cnt": vol_cnt,
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
    result = market_cap()
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
