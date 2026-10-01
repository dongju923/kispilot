# 국내주식 공매도 상위종목[국내주식-133]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/ranking/short-sale"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0482] 공매도 상위 화면과 동일한 기능.
# ※ 최대 30건까지만 조회되며 연속조회(tr_cont) 불가. 30건 이상은 종목조건검색 API(최대 100건)로 대체.
# ※ FID_COND_MRKT_DIV_CODE(J), FID_COND_SCR_DIV_CODE(20482)는 문서상 고정값이라 파라미터로 노출하지 않는다.
# ※ 공매도 데이터는 전 영업일까지 집계된 값이다(장중에 조회해도 stnd_date2 = 전 영업일).
#   stnd_date1~stnd_date2가 집계 구간이며, acml_vol/acml_tr_pbmn/공매도 수치는 모두 이 구간 합계다.
#   stck_prpr/prdy_vrss/prdy_ctrt만 조회 시점 현재가 기준이다.
# ※ 공매도 체결 수량(ssts_cntg_qty) 내림차순으로 내려온다.

_TR_ID = "FHPST04820000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    mksc_shrn_iscd: Optional[str] = None        # 유가증권 단축 종목코드
    hts_kor_isnm: Optional[str] = None          # HTS 한글 종목명
    stck_prpr: Optional[str] = None             # 주식 현재가
    prdy_vrss: Optional[str] = None             # 전일 대비
    prdy_vrss_sign: Optional[str] = None        # 전일 대비 부호
    prdy_ctrt: Optional[str] = None             # 전일 대비율
    acml_vol: Optional[str] = None              # 누적 거래량(집계 구간 합계)
    acml_tr_pbmn: Optional[str] = None          # 누적 거래 대금(원, 집계 구간 합계)
    ssts_cntg_qty: Optional[str] = None         # 공매도 체결 수량
    ssts_vol_rlim: Optional[str] = None         # 공매도 거래량 비중(%), 공매도 체결 수량 / 누적 거래량 × 100
    ssts_tr_pbmn: Optional[str] = None          # 공매도 거래 대금(원)
    ssts_tr_pbmn_rlim: Optional[str] = None     # 공매도 거래대금 비중(%)
    stnd_date1: Optional[str] = None            # 기준 일자1(집계 시작일, YYYYMMDD)
    stnd_date2: Optional[str] = None            # 기준 일자2(집계 종료일 = 전 영업일, YYYYMMDD)
    avrg_prc: Optional[str] = None              # 평균가격(공매도 평균가 = 공매도 거래 대금 / 공매도 체결 수량)


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 공매도 상위(배열, 최대 30건)


# ── 요청 함수 ───────────────────────────────────────────────

def short_sale(
    period_div: Literal["D", "M"] = "D",
    input_cnt: str = "0",
    sector_code: Literal["0000", "0001", "1001", "2001", "4001", "3003"] = "0000",
    price_1: str = "",
    price_2: str = "",
    vol: str = "",
    trgt_cls: str = "",
    trgt_exls_cls: str = "",
) -> ResponseBody:
    """국내주식 공매도 상위 종목을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0482] 공매도 상위 화면 기능과 동일. 최대 30건, 연속조회 불가.

    Args:
        period_div: 조회구분(FID_PERIOD_DIV_CODE). D:일, M:월. 기본값 "D".
        input_cnt: 조회기간(FID_INPUT_CNT_1). period_div에 따라 의미가 달라진다. 기본값 "0".
            D → 0:1일, 1:2일, 2:3일, 3:4일, 4:1주일, 9:2주일, 14:3주일 (문서 값)
                실제로는 N을 넣으면 전 영업일 포함 N+1영업일 구간이라 문서에 없는 값(ex "5", "29")도 동작한다.
            M → 1:1개월, 2:2개월, 3:3개월
        sector_code: 입력 종목코드(FID_INPUT_ISCD). 0000:전체, 0001:코스피, 1001:코스닥, 2001:코스피200,
            4001:KRX100, 3003:코스닥150. 기본값 "0000".
        price_1: 적용 범위 가격1(FID_APLY_RANG_PRC_1), 가격 ~. 공백이면 전체.
        price_2: 적용 범위 가격2(FID_APLY_RANG_PRC_2), ~ 가격. 공백이면 전체.
        vol: 적용 범위 거래량(FID_APLY_RANG_VOL). 문서상 공백. 값을 넣으면 결과가 바뀌지만 최소 거래량
            필터로 동작하지 않아(ex "10000000" → 삼성전자가 빠지고 거래량 0인 종목이 포함) 사용을 권장하지 않는다.
        trgt_cls: 대상 구분 코드(FID_TRGT_CLS_CODE). 문서상 공백이지만 다른 순위 API와 같은 1/0 9자리가 동작한다
            (증거금 30% 40% 50% 60% 100%, 신용보증금 30% 40% 50% 60% 순, 1=포함).
            ex) "000010000" → 증거금 100% 종목만. 기본값 ""(전체).
        trgt_exls_cls: 대상 제외 구분 코드(FID_TRGT_EXLS_CLS_CODE). 문서상 공백이지만 1/0 10자리가 동작한다
            (투자위험/경고/주의, 관리종목, 정리매매, 불성실공시, 우선주, 거래정지, ETF, ETN, 신용주문불가, SPAC 순,
            1=제외). ex) "0000001101" → ETF, ETN, SPAC 제외. 기본값 ""(전체).

    Returns:
        rt_cd/msg_cd/msg1과 공매도 상위 종목 목록(output)을 담은 ResponseBody.
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
        "FID_APLY_RANG_VOL": vol,
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_COND_SCR_DIV_CODE": "20482",
        "FID_INPUT_ISCD": sector_code,
        "FID_PERIOD_DIV_CODE": period_div,
        "FID_INPUT_CNT_1": input_cnt,
        "FID_TRGT_EXLS_CLS_CODE": trgt_exls_cls,
        "FID_TRGT_CLS_CODE": trgt_cls,
        "FID_APLY_RANG_PRC_1": price_1,
        "FID_APLY_RANG_PRC_2": price_2,
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
    result = short_sale()
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
