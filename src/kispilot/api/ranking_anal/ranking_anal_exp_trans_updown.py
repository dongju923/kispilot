# 국내주식 예상체결 상승/하락상위[v1_국내주식-103]
from dataclasses import dataclass, field
from typing import List, Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/ranking/exp-trans-updown"
# ※ 모의투자 미지원 (실전투자 전용). HTS(eFriend Plus) [0182] 예상체결 상승/하락상위 화면과 동일한 기능.
# ※ 최대 30건까지만 조회되며 연속조회(tr_cont) 불가. 30건 이상은 종목조건검색 API(최대 100건)로 대체.
# ※ FID_COND_MRKT_DIV_CODE(J), fid_cond_scr_div_code(20182)는 문서상 고정값이라 파라미터로 노출하지 않는다.
#   (다른 순위 API와 달리 NX(NXT)는 문서에 없다.)
# ※ 이 API는 쿼리 파라미터 키가 소문자(fid_...)로 문서화되어 있다.
# ※ 장전 예상(mkop_cls=0)은 장 시작 후에도 조회되며, 그때는 당일 시초가 단일가 결과가 그대로 내려온다
#   (stck_prpr = 당일 시가, cntg_vol/antc_tr_pbmn = 시가 체결량/대금). 장중 현재가가 아니다.
#   장마감 예상(mkop_cls=1)은 마감 동시호가 시간이 아니면 빈 결과(0건)가 온다.

_TR_ID = "FHPST01820000"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    stck_shrn_iscd: Optional[str] = None    # 주식 단축 종목코드
    hts_kor_isnm: Optional[str] = None      # HTS 한글 종목명
    stck_prpr: Optional[str] = None         # 주식 현재가(예상 체결가)
    prdy_vrss: Optional[str] = None         # 전일 대비
    prdy_vrss_sign: Optional[str] = None    # 전일 대비 부호
    prdy_ctrt: Optional[str] = None         # 전일 대비율
    stck_sdpr: Optional[str] = None         # 주식 기준가
    seln_rsqn: Optional[str] = None         # 매도 잔량
    askp: Optional[str] = None              # 매도호가
    bidp: Optional[str] = None              # 매수호가
    shnu_rsqn: Optional[str] = None         # 매수2 잔량
    cntg_vol: Optional[str] = None          # 체결 거래량
    antc_tr_pbmn: Optional[str] = None      # 체결 거래대금(원, 예상 체결가 × 체결 거래량)
    total_askp_rsqn: Optional[str] = None   # 총 매도호가 잔량
    total_bidp_rsqn: Optional[str] = None   # 총 매수호가 잔량


@dataclass
class ResponseBody:
    rt_cd: str                                                       # 성공 실패 여부
    msg_cd: str                                                      # 응답코드
    msg1: str                                                        # 응답메세지
    output: List[ResponseBodyOutput] = field(default_factory=list)   # 예상체결 상승/하락상위(배열, 최대 30건)


# ── 요청 함수 ───────────────────────────────────────────────

def exp_trans_updown(
    rank_sort_cls: Literal["0", "1", "2", "3", "4", "5", "6"] = "0",
    mkop_cls: Literal["0", "1"] = "0",
    sector_code: Literal["0000", "0001", "1001", "2001", "4001"] = "0000",
    div_cls: Literal["0", "1", "2"] = "0",
    price_1: str = "",
    vol_cnt: str = "",
    pbmn: str = "",
    blng_cls: str = "0",
) -> ResponseBody:
    """국내주식 예상체결 상승/하락 상위 종목을 조회한다. (모의투자 미지원, 실전 계좌 전용)

    한국투자 HTS(eFriend Plus) [0182] 예상체결 상승/하락상위 화면 기능과 동일. 최대 30건, 연속조회 불가.

    Args:
        rank_sort_cls: 순위 정렬 구분 코드(fid_rank_sort_cls_code). 0:상승률, 1:상승폭, 2:보합, 3:하락률,
            4:하락폭, 5:체결량, 6:거래대금. 기본값 "0".
            하락률/하락폭(3, 4)은 가장 많이 떨어진 종목(음수가 가장 큰 값)부터 온다.
        mkop_cls: 장운영 구분 코드(fid_mkop_cls_code). 0:장전 예상, 1:장마감 예상. 기본값 "0".
            장 시작 후 0으로 조회하면 당일 시초가 단일가 결과가 오고, 1은 마감 동시호가 시간 외에는 0건이다.
        sector_code: 입력 종목코드(fid_input_iscd). 0000:전체, 0001:거래소, 1001:코스닥, 2001:코스피200,
            4001:KRX100. 기본값 "0000".
        div_cls: 분류 구분 코드(fid_div_cls_code). 0:전체, 1:보통주, 2:우선주. 기본값 "0".
        price_1: 적용 범위 가격1(fid_aply_rang_prc_1), 가격 ~. 공백이면 전체.
        vol_cnt: 거래량 수(fid_vol_cnt), 거래량 ~. 공백이면 전체.
        pbmn: 거래대금(fid_pbmn), 거래대금 ~ (천원 단위). 공백이면 전체.
            응답의 antc_tr_pbmn은 원 단위라 단위가 다르다.
        blng_cls: 소속 구분 코드(fid_blng_cls_code). 0:전체. 기본값 "0".

    Returns:
        rt_cd/msg_cd/msg1과 예상체결 순위 종목 목록(output)을 담은 ResponseBody.
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
        "fid_rank_sort_cls_code": rank_sort_cls,
        "fid_cond_mrkt_div_code": "J",
        "fid_cond_scr_div_code": "20182",
        "fid_input_iscd": sector_code,
        "fid_div_cls_code": div_cls,
        "fid_aply_rang_prc_1": price_1,
        "fid_vol_cnt": vol_cnt,
        "fid_pbmn": pbmn,
        "fid_blng_cls_code": blng_cls,
        "fid_mkop_cls_code": mkop_cls,
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
    result = exp_trans_updown(rank_sort_cls="6")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        for row in result.output:
            print(row)
