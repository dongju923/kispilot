# 종목별 일별 대차거래추이[국내주식-135]
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/daily-loan-trans"
# ※ 모의투자 미지원 (실전투자 전용).
# ※ 조회구분 1(코스피)/2(코스닥)은 시장 전체 합계로, 종목코드는 무시되고 stck_prpr에 지수가 담긴다.
#   3(종목)은 해당 종목의 대차거래 추이다.
# ※ 한 번에 종료일부터 과거로 최신순 최대 100건이 내려온다. 응답 헤더 tr_cont는 데이터가 더 있어도
#   "E"로 내려와 신뢰할 수 없고, 응답에 다음 조회용 CTS 값도 없다. 그래서 문서 안내대로 100건을 받으면
#   마지막 일자 전날을 새 종료일로 다시 조회해 기간 전체를 이어 붙인다.
# ※ 대차 데이터는 1영업일 늦게 반영되어 당일로 조회해도 최신 행은 전 영업일이다.
# ※ rmnd_amt(잔고 금액) 단위는 백만원이다.

_TR_ID = "HHPST074500C0"

_PAGE_SIZE = 100


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput1:
    bsop_date: Optional[str] = None         # 일자
    stck_prpr: Optional[str] = None         # 주식 종가(조회구분 1/2는 지수)
    prdy_vrss_sign: Optional[str] = None    # 전일 대비 부호
    prdy_vrss: Optional[str] = None         # 전일 대비
    prdy_ctrt: Optional[str] = None         # 전일 대비율
    acml_vol: Optional[str] = None          # 누적 거래량
    new_stcn: Optional[str] = None          # 당일 증가 주수(체결)
    rdmp_stcn: Optional[str] = None         # 당일 감소 주수(상환)
    prdy_rmnd_vrss: Optional[str] = None    # 대차거래 증감
    rmnd_stcn: Optional[str] = None         # 당일 잔고 주수
    rmnd_amt: Optional[str] = None          # 당일 잔고 금액(백만원)


@dataclass
class ResponseBody:
    rt_cd: str                                                         # 성공 실패 여부
    msg_cd: str                                                        # 응답코드
    msg1: str                                                          # 응답메세지
    output1: List[ResponseBodyOutput1] = field(default_factory=list)   # 일별 대차거래추이(배열, 최신순)


# ── 요청 함수 ───────────────────────────────────────────────

def _fetch_page(
    market: str,
    code: str,
    start_date: str,
    end_date: str,
) -> ResponseBody:
    """대차거래추이 한 페이지(종료일부터 최대 100건)를 조회한다."""
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
        "MRKT_DIV_CLS_CODE": market,
        "MKSC_SHRN_ISCD": code,
        "START_DATE": start_date,
        "END_DATE": end_date,
        "CTS": "",
    }
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output1 키가 없거나 null일 수 있어 안전 파싱.
    fields = set(ResponseBodyOutput1.__dataclass_fields__)
    raw_output1 = raw.get("output1") or []
    output1 = [ResponseBodyOutput1(**{k: v for k, v in item.items() if k in fields}) for item in raw_output1]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output1=output1,
    )


def daily_loan_trans(
    market: Literal["1", "2", "3"],
    start_date: str,
    end_date: str,
    code: str = "",
) -> ResponseBody:
    """일별 대차거래추이를 기간 전체 조회한다(100건 초과 시 자동 이어 조회). (모의투자 미지원, 실전 계좌 전용)

    Args:
        market: 조회구분(MRKT_DIV_CLS_CODE). 1:코스피 전체, 2:코스닥 전체, 3:종목.
        start_date: 조회 시작일(START_DATE), YYYYMMDD.
        end_date: 조회 종료일(END_DATE), YYYYMMDD.
        code: 종목코드(MKSC_SHRN_ISCD), 6자리(ex 005930). market="3"일 때만 사용. 기본값 "".

    Returns:
        rt_cd/msg_cd/msg1(마지막으로 받은 페이지 기준)과, 모든 페이지를 합친 일별 대차거래추이(output1)를
        담은 ResponseBody. 실패 여부는 반드시 rt_cd로 확인할 것.
    """
    all_output1: List[ResponseBodyOutput1] = []
    body = ResponseBody(rt_cd="", msg_cd="", msg1="")
    page_end = end_date

    while True:
        body = _fetch_page(market, code, start_date, page_end)
        all_output1.extend(body.output1)

        if body.rt_cd != "0" or len(body.output1) < _PAGE_SIZE:
            break
        # 100건을 꽉 채워 받았으면 마지막(가장 과거) 일자 전날을 새 종료일로 이어 조회한다.
        last_date = datetime.strptime(body.output1[-1].bsop_date, "%Y%m%d")
        page_end = (last_date - timedelta(days=1)).strftime("%Y%m%d")
        if page_end < start_date:
            break

    return ResponseBody(
        rt_cd=body.rt_cd,
        msg_cd=body.msg_cd,
        msg1=body.msg1,
        output1=all_output1,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = daily_loan_trans(market="3", code="005930", start_date="20260901", end_date="20260921")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output1:
            print(row)
