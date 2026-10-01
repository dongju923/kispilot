# 국내주식 신용잔고 상위[국내주식-109]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/ranking/credit-balance"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0475] 신용잔고 상위 화면과 동일한 기능.
# ※ 연속조회(tr_cont) 불가. 문서에는 최대 30건으로 되어 있지만 실제로는 output2가 최대 100건까지 내려온다.
#   대주(5~9) 정렬은 잔고가 있는 종목만 내려와 100건보다 훨씬 적을 수 있다.
# ※ FID_COND_MRKT_DIV_CODE(J), FID_COND_SCR_DIV_CODE(11701)는 문서상 고정값이라 파라미터로 노출하지 않는다.
# ※ 신용잔고는 장 마감 후 집계되는 전 영업일 기준 데이터다. output1의 stnd_date2가 기준일,
#   stnd_date1이 증가율 비교일이며, FID_OPTION=N이면 기준일 포함 N영업일 구간(비교일 = N-1영업일 전)이다.

_TR_ID = "FHKST17010000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    bstp_cls_code: Optional[str] = None     # 업종 구분 코드(입력 코드와 체계가 다름. ex 0000→1001 종합, 1001→2001 KOSDAQ)
    hts_kor_isnm: Optional[str] = None      # HTS 한글 종목명(업종명)
    stnd_date1: Optional[str] = None        # 기준 일자1(증가율 비교일, YYYYMMDD)
    stnd_date2: Optional[str] = None        # 기준 일자2(잔고 기준일, YYYYMMDD)


@dataclass
class ResponseBodyOutput2:
    mksc_shrn_iscd: Optional[str] = None                # 유가증권 단축 종목코드
    hts_kor_isnm: Optional[str] = None                  # HTS 한글 종목명
    stck_prpr: Optional[str] = None                     # 주식 현재가
    prdy_vrss: Optional[str] = None                     # 전일 대비
    prdy_vrss_sign: Optional[str] = None                # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                     # 전일 대비율
    acml_vol: Optional[str] = None                      # 누적 거래량
    whol_loan_rmnd_stcn: Optional[str] = None           # 전체 융자 잔고 주수
    whol_loan_rmnd_amt: Optional[str] = None            # 전체 융자 잔고 금액(만원 단위로 추정)
    whol_loan_rmnd_rate: Optional[str] = None           # 전체 융자 잔고 비율(%)
    whol_stln_rmnd_stcn: Optional[str] = None           # 전체 대주 잔고 주수
    whol_stln_rmnd_amt: Optional[str] = None            # 전체 대주 잔고 금액(만원 단위로 추정)
    whol_stln_rmnd_rate: Optional[str] = None           # 전체 대주 잔고 비율(%)
    nday_vrss_loan_rmnd_inrt: Optional[str] = None      # N일 대비 융자 잔고 증가율
    nday_vrss_stln_rmnd_inrt: Optional[str] = None      # N일 대비 대주 잔고 증가율


@dataclass
class ResponseBody:
    rt_cd: str                                                          # 성공 실패 여부
    msg_cd: str                                                         # 응답코드
    msg1: str                                                           # 응답메세지
    output1: List[ResponseBodyOutput1] = field(default_factory=list)    # 조회 기준 정보(배열)
    output2: List[ResponseBodyOutput2] = field(default_factory=list)    # 신용잔고 상위(배열, 최대 100건)


# ── 요청 함수 ───────────────────────────────────────────────

def credit_balance(
    rank_sort_cls: Literal["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"] = "0",
    sector_code: Literal["0000", "0001", "1001", "2001"] = "0000",
    inrt_period: str = "2",
) -> ResponseBody:
    """국내주식 신용잔고 상위 종목을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0475] 신용잔고 상위 화면 기능과 동일. 최대 100건(문서상 30건), 연속조회 불가.

    Args:
        rank_sort_cls: 순위 정렬 구분 코드(FID_RANK_SORT_CLS_CODE). 기본값 "0".
            (융자) 0:잔고비율 상위, 1:잔고수량 상위, 2:잔고금액 상위, 3:잔고비율 증가상위, 4:잔고비율 감소상위
            (대주) 5:잔고비율 상위, 6:잔고수량 상위, 7:잔고금액 상위, 8:잔고비율 증가상위, 9:잔고비율 감소상위
            감소상위(4, 9)는 가장 많이 감소한 종목(음수가 가장 큰 값)부터 온다.
        sector_code: 입력 종목코드(FID_INPUT_ISCD). 0000:전체, 0001:거래소, 1001:코스닥, 2001:코스피200.
            기본값 "0000".
        inrt_period: 증가율 기간(FID_OPTION), 2~999 영업일. 기준일 포함 N영업일 구간으로 증가율을 계산한다
            (ex "2" → 직전 영업일 대비, "20" → 약 한 달 전 대비). 기본값 "2".

    Returns:
        rt_cd/msg_cd/msg1과 조회 기준 정보(output1), 신용잔고 상위 종목 목록(output2)을 담은 ResponseBody.
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
        "FID_COND_SCR_DIV_CODE": "11701",
        "FID_INPUT_ISCD": sector_code,
        "FID_OPTION": inrt_period,
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_RANK_SORT_CLS_CODE": rank_sort_cls,
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1/output2 키가 없거나 null일 수 있어 안전 파싱.
    # 단일 객체로 내려오는 경우에도 리스트로 감싸 동일하게 처리한다.
    fields1 = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or []
    if isinstance(raw_output1, dict):
        raw_output1 = [raw_output1]
    output1 = [ResponseBodyOutput1(**{k: v for k, v in item.items() if k in fields1}) for item in raw_output1]

    fields2 = set(ResponseBodyOutput2.__dataclass_fields__)
    raw_output2 = raw.get("output2") or []
    if isinstance(raw_output2, dict):
        raw_output2 = [raw_output2]
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
    result = credit_balance()
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output1)
        for row in result.output2:
            print(row)
