# 관심종목(멀티종목) 시세조회[국내주식-205]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/intstock-multprice"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0161] 관심종목 화면과 동일한 기능.
# ※ 최대 30종목을 FID_COND_MRKT_DIV_CODE_1~30 / FID_INPUT_ISCD_1~30 쌍으로 한 번에 조회한다.
#   사용하지 않는 슬롯은 종목코드만 빈 문자열로 보낸다. 시장 분류 코드까지 비우면
#   OPSQ2002(ERROR INVALID INPUT FID_COND_MRKT_DIV_CODE_n) 에러가 나므로 항상 채운다.
# ※ 문서상 output은 Object로 표기되어 있지만 종목별로 한 건씩 내려오는 배열이라 List로 받는다.
#   단일 객체로 내려오는 경우도 대비해 안전 파싱한다.
# ※ 빈 슬롯까지 항상 30건이 내려오며, 빈 슬롯은 모든 값이 빈 문자열이다.

_TR_ID = "FHKST11300006"

_MAX_CODES = 30


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    kospi_kosdaq_cls_name: Optional[str] = None             # 코스피 코스닥 구분 명
    mrkt_trtm_cls_name: Optional[str] = None                # 시장 조치 구분 명
    hour_cls_code: Optional[str] = None                     # 시간 구분 코드
    inter_shrn_iscd: Optional[str] = None                   # 관심 단축 종목코드
    inter_kor_isnm: Optional[str] = None                    # 관심 한글 종목명
    inter2_prpr: Optional[str] = None                       # 관심2 현재가
    inter2_prdy_vrss: Optional[str] = None                  # 관심2 전일 대비
    prdy_vrss_sign: Optional[str] = None                    # 전일 대비 부호
    prdy_ctrt: Optional[str] = None                         # 전일 대비율
    acml_vol: Optional[str] = None                          # 누적 거래량
    inter2_oprc: Optional[str] = None                       # 관심2 시가
    inter2_hgpr: Optional[str] = None                       # 관심2 고가
    inter2_lwpr: Optional[str] = None                       # 관심2 저가
    inter2_llam: Optional[str] = None                       # 관심2 하한가
    inter2_mxpr: Optional[str] = None                       # 관심2 상한가
    inter2_askp: Optional[str] = None                       # 관심2 매도호가
    inter2_bidp: Optional[str] = None                       # 관심2 매수호가
    seln_rsqn: Optional[str] = None                         # 매도 잔량
    shnu_rsqn: Optional[str] = None                         # 매수2 잔량
    total_askp_rsqn: Optional[str] = None                   # 총 매도호가 잔량
    total_bidp_rsqn: Optional[str] = None                   # 총 매수호가 잔량
    acml_tr_pbmn: Optional[str] = None                      # 누적 거래 대금
    inter2_prdy_clpr: Optional[str] = None                  # 관심2 전일 종가
    oprc_vrss_hgpr_rate: Optional[str] = None               # 시가 대비 최고가 비율
    intr_antc_cntg_vrss: Optional[str] = None               # 관심 예상 체결 대비
    intr_antc_cntg_vrss_sign: Optional[str] = None          # 관심 예상 체결 대비 부호
    intr_antc_cntg_prdy_ctrt: Optional[str] = None          # 관심 예상 체결 전일 대비율
    intr_antc_vol: Optional[str] = None                     # 관심 예상 거래량
    inter2_sdpr: Optional[str] = None                       # 관심2 기준가


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 종목별 시세(배열, 최대 30개)


# ── 요청 함수 ───────────────────────────────────────────────

def intstock_multprice(
    codes: List[str],
    market_div: Literal["J", "NX", "UN"] = "J",
) -> ResponseBody:
    """관심종목(멀티종목) 시세를 한 번에 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0161] 관심종목 화면 기능과 동일.

    Args:
        codes: 입력 종목코드 목록(FID_INPUT_ISCD_1~30), 6자리(ex ["005930", "000660"]). 최대 30개.
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE_1~30). J:KRX, NX:NXT, UN:통합. 기본값 "J".
            입력한 모든 종목에 동일하게 적용된다.

    Returns:
        rt_cd/msg_cd/msg1과 종목별 시세(output)를 담은 ResponseBody.
    """
    if not codes:
        raise ValueError("조회할 종목코드를 1개 이상 입력하세요.")
    if len(codes) > _MAX_CODES:
        raise ValueError(f"종목코드는 최대 {_MAX_CODES}개까지 조회할 수 있습니다. (입력: {len(codes)}개)")

    token = load_token("real")

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": REAL_APPKEY,
        "appsecret": REAL_APP_SECRET,
        "tr_id": _TR_ID,
        "custtype": "P",
    }
    params = {}
    for i in range(1, _MAX_CODES + 1):
        code = codes[i - 1] if i <= len(codes) else ""
        params[f"FID_COND_MRKT_DIV_CODE_{i}"] = market_div
        params[f"FID_INPUT_ISCD_{i}"] = code
    response = get_session().get(DOMAIN["real"] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # 에러 응답(rt_cd != "0")은 output 키가 없거나 null일 수 있어 안전 파싱.
    # 단일 객체로 내려오는 경우에도 리스트로 감싸 동일하게 처리한다.
    # 빈 슬롯도 모든 값이 빈 문자열인 행으로 내려오므로 종목코드가 없는 행은 제외한다.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_output = raw.get("output") or []
    if isinstance(raw_output, dict):
        raw_output = [raw_output]
    output = [
        ResponseBodyOutput(**{k: v for k, v in item.items() if k in fields})
        for item in raw_output
        if item.get("inter_shrn_iscd")
    ]

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output=output,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = intstock_multprice(codes=["005930", "000660", "035420"])
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
