# 국내 증시자금 종합[국내주식-193]
from dataclasses import dataclass, field
from typing import List, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/mktfunds"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0470] 증시자금 종합 화면과 동일한 기능.
# ※ 금융투자협회 자료라 오류와 지연이 있을 수 있다. 실제로 영업일 기준 약 2일 늦게 반영되어
#   당일로 조회해도 최신 행은 2영업일 전 일자다.
# ※ output은 기준일부터 과거로 최신순 100영업일이 내려온다(연속조회 불가). 기준일 공란이면 최신부터.
# ※ bstp_nmix_*는 코스피 지수다. prdy_ctrt는 등락률(%)이 아니라 전일 지수를 100으로 둔 비율이다
#   (ex -0.04% 하락 -> "99.96").
# ※ 금액 단위는 억원(hts_avls만 백만원)이다.

_TR_ID = "FHKST649100C0"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    bsop_date: Optional[str] = None                 # 영업일자
    bstp_nmix_prpr: Optional[str] = None            # 업종지수현재가(코스피)
    bstp_nmix_prdy_vrss: Optional[str] = None       # 업종지수전일대비
    prdy_vrss_sign: Optional[str] = None            # 전일대비부호(1:상한 2:상승 3:보합 4:하한 5:하락)
    prdy_ctrt: Optional[str] = None                 # 전일대비율(전일=100 기준 비율)
    hts_avls: Optional[str] = None                  # HTS시가총액(백만원)
    cust_dpmn_amt: Optional[str] = None             # 고객예탁금금액(억원)
    cust_dpmn_amt_prdy_vrss: Optional[str] = None   # 고객예탁금금액전일대비(억원)
    amt_tnrt: Optional[str] = None                  # 금액회전율
    uncl_amt: Optional[str] = None                  # 미수금액(억원)
    crdt_loan_rmnd: Optional[str] = None            # 신용융자잔고(억원)
    futs_tfam_amt: Optional[str] = None             # 선물예수금금액(억원)
    sttp_amt: Optional[str] = None                  # 주식형금액(억원)
    mxtp_amt: Optional[str] = None                  # 혼합형금액(억원)
    bntp_amt: Optional[str] = None                  # 채권형금액(억원)
    mmf_amt: Optional[str] = None                   # MMF금액(억원)
    secu_lend_amt: Optional[str] = None             # 담보대출잔고금액(억원)


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 일별 증시자금(배열, 최신순, 100영업일)


# ── 요청 함수 ───────────────────────────────────────────────

def mktfunds(
    date: str = "",
) -> ResponseBody:
    """국내 증시자금 종합(고객예탁금, 신용융자잔고, 펀드 설정액 등)을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0470] 증시자금 종합 화면 기능과 동일. 금융투자협회 자료.

    Args:
        date: 기준일(FID_INPUT_DATE_1), YYYYMMDD. 공란이면 최신 일자부터. 기본값 "".

    Returns:
        rt_cd/msg_cd/msg1과 일별 증시자금(output)을 담은 ResponseBody.
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
        "FID_INPUT_DATE_1": date,
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
    result = mktfunds()
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
