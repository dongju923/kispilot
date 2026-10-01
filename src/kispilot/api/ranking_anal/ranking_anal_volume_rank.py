# 거래량순위[v1_국내주식-047]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/volume-rank"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0171] 거래량 순위 화면과 동일한 기능.
# ※ 최대 30건까지만 조회되며 연속조회(tr_cont) 불가. 30건 이상은 종목조건검색 API(최대 100건)로 대체.
# ※ FID_COND_SCR_DIV_CODE(20171)는 문서상 고정값이라 파라미터로 노출하지 않는다.
# ※ 문서 표기가 Output(대문자)이라 실제 JSON 키가 소문자일 가능성을 대비해 둘 다 확인한다.

_TR_ID = "FHPST01710000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    hts_kor_isnm: Optional[str] = None                  # HTS 한글 종목명
    mksc_shrn_iscd: Optional[str] = None                # 유가증권 단축 종목코드
    data_rank: Optional[str] = None                     # 데이터 순위
    stck_prpr: Optional[str] = None                     # 주식 현재가
    prdy_vrss_sign: Optional[str] = None                # 전일 대비 부호
    prdy_vrss: Optional[str] = None                     # 전일 대비
    prdy_ctrt: Optional[str] = None                     # 전일 대비율
    acml_vol: Optional[str] = None                      # 누적 거래량
    prdy_vol: Optional[str] = None                      # 전일 거래량
    lstn_stcn: Optional[str] = None                     # 상장 주수
    avrg_vol: Optional[str] = None                      # 평균 거래량
    n_befr_clpr_vrss_prpr_rate: Optional[str] = None    # N일전종가대비현재가대비율
    vol_inrt: Optional[str] = None                      # 거래량증가율
    vol_tnrt: Optional[str] = None                      # 거래량 회전율
    nday_vol_tnrt: Optional[str] = None                 # N일 거래량 회전율
    avrg_tr_pbmn: Optional[str] = None                  # 평균 거래 대금
    tr_pbmn_tnrt: Optional[str] = None                  # 거래대금회전율
    nday_tr_pbmn_tnrt: Optional[str] = None             # N일 거래대금 회전율
    acml_tr_pbmn: Optional[str] = None                  # 누적 거래 대금


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 거래량 순위(배열, 최대 30건)


# ── 요청 함수 ───────────────────────────────────────────────

def volume_rank(
    sector_code: str = "0000",
    market_div: Literal["J", "NX"] = "J",
    div_cls: Literal["0", "1", "2"] = "0",
    blng_cls: Literal["0", "1", "2", "3", "4"] = "0",
    trgt_cls: str = "111111111",
    trgt_exls_cls: str = "0000000000",
    price_1: str = "",
    price_2: str = "",
    vol_cnt: str = "",
) -> ResponseBody:
    """국내주식 거래량 순위를 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0171] 거래량 순위 화면 기능과 동일. 최대 30건, 연속조회 불가.

    Args:
        sector_code: 입력 종목코드(FID_INPUT_ISCD). 0000:전체, 그 외 업종코드. 기본값 "0000".
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT. 기본값 "J".
        div_cls: 분류 구분 코드(FID_DIV_CLS_CODE). 0:전체, 1:보통주, 2:우선주. 기본값 "0".
        blng_cls: 소속 구분 코드(FID_BLNG_CLS_CODE). 0:평균거래량, 1:거래증가율, 2:평균거래회전율,
            3:거래금액순, 4:평균거래금액회전율. 기본값 "0".
        trgt_cls: 대상 구분 코드(FID_TRGT_CLS_CODE). 1/0 9자리
            (증거금 30% 40% 50% 60% 100%, 신용보증금 30% 40% 50% 60% 순). 기본값 "111111111".
        trgt_exls_cls: 대상 제외 구분 코드(FID_TRGT_EXLS_CLS_CODE). 1/0 10자리
            (투자위험/경고/주의, 관리종목, 정리매매, 불성실공시, 우선주, 거래정지, ETF, ETN,
            신용주문불가, SPAC 순). 기본값 "0000000000".
        price_1: 입력 가격1(FID_INPUT_PRICE_1), 가격 ~. 전체 가격 대상은 price_1/price_2 모두 "".
        price_2: 입력 가격2(FID_INPUT_PRICE_2), ~ 가격. 전체 가격 대상은 price_1/price_2 모두 "".
        vol_cnt: 거래량 수(FID_VOL_CNT), 거래량 ~. 전체 거래량 대상은 "".

    Returns:
        rt_cd/msg_cd/msg1과 거래량 순위 종목 목록(output)을 담은 ResponseBody.
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
        "FID_COND_SCR_DIV_CODE": "20171",
        "FID_INPUT_ISCD": sector_code,
        "FID_DIV_CLS_CODE": div_cls,
        "FID_BLNG_CLS_CODE": blng_cls,
        "FID_TRGT_CLS_CODE": trgt_cls,
        "FID_TRGT_EXLS_CLS_CODE": trgt_exls_cls,
        "FID_INPUT_PRICE_1": price_1,
        "FID_INPUT_PRICE_2": price_2,
        "FID_VOL_CNT": vol_cnt,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output 키가 없거나 null일 수 있어 안전 파싱.
    # 단일 객체로 내려오는 경우에도 리스트로 감싸 동일하게 처리한다.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_output = raw.get("output") or raw.get("Output") or []
    if isinstance(raw_output, dict):
        raw_output = [raw_output]
    output = [ResponseBodyOutput(**{k: v for k, v in item.items() if k in fields}) for item in raw_output]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output=output,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = volume_rank()
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
