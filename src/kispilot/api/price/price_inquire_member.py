# 주식현재가 회원사[v1_국내주식-013]
from dataclasses import dataclass
from typing import Literal, Optional

from kispilot.api.config import DOMAIN, REAL_APPKEY, REAL_APP_SECRET, PAPER_APPKEY, PAPER_APP_SECRET
from kispilot.api.oauth.kis_token import load_token
from kispilot.api.utils.http_session import get_session

URL = "/uapi/domestic-stock/v1/quotations/inquire-member"
# ※ 매도/매수2 상위 5개 회원사 정보가 접미사 1~5로 한 객체에 담겨 있고, 그 객체가 원소 1개짜리 배열로 내려온다.

_TR_ID = "FHKST01010600"


# ── DataClass 정의 ──────────────────────────────────────────

@dataclass
class ResponseBodyOutput:
    seln_mbcr_no1: Optional[str] = None                    # 매도 회원사 번호1
    seln_mbcr_no2: Optional[str] = None                    # 매도 회원사 번호2
    seln_mbcr_no3: Optional[str] = None                    # 매도 회원사 번호3
    seln_mbcr_no4: Optional[str] = None                    # 매도 회원사 번호4
    seln_mbcr_no5: Optional[str] = None                    # 매도 회원사 번호5
    seln_mbcr_name1: Optional[str] = None                  # 매도 회원사 명1
    seln_mbcr_name2: Optional[str] = None                  # 매도 회원사 명2
    seln_mbcr_name3: Optional[str] = None                  # 매도 회원사 명3
    seln_mbcr_name4: Optional[str] = None                  # 매도 회원사 명4
    seln_mbcr_name5: Optional[str] = None                  # 매도 회원사 명5
    total_seln_qty1: Optional[str] = None                  # 총 매도 수량1
    total_seln_qty2: Optional[str] = None                  # 총 매도 수량2
    total_seln_qty3: Optional[str] = None                  # 총 매도 수량3
    total_seln_qty4: Optional[str] = None                  # 총 매도 수량4
    total_seln_qty5: Optional[str] = None                  # 총 매도 수량5
    seln_mbcr_rlim1: Optional[str] = None                  # 매도 회원사 비중1
    seln_mbcr_rlim2: Optional[str] = None                  # 매도 회원사 비중2
    seln_mbcr_rlim3: Optional[str] = None                  # 매도 회원사 비중3
    seln_mbcr_rlim4: Optional[str] = None                  # 매도 회원사 비중4
    seln_mbcr_rlim5: Optional[str] = None                  # 매도 회원사 비중5
    seln_qty_icdc1: Optional[str] = None                   # 매도 수량 증감1
    seln_qty_icdc2: Optional[str] = None                   # 매도 수량 증감2
    seln_qty_icdc3: Optional[str] = None                   # 매도 수량 증감3
    seln_qty_icdc4: Optional[str] = None                   # 매도 수량 증감4
    seln_qty_icdc5: Optional[str] = None                   # 매도 수량 증감5
    shnu_mbcr_no1: Optional[str] = None                    # 매수2 회원사 번호1
    shnu_mbcr_no2: Optional[str] = None                    # 매수2 회원사 번호2
    shnu_mbcr_no3: Optional[str] = None                    # 매수2 회원사 번호3
    shnu_mbcr_no4: Optional[str] = None                    # 매수2 회원사 번호4
    shnu_mbcr_no5: Optional[str] = None                    # 매수2 회원사 번호5
    shnu_mbcr_name1: Optional[str] = None                  # 매수2 회원사 명1
    shnu_mbcr_name2: Optional[str] = None                  # 매수2 회원사 명2
    shnu_mbcr_name3: Optional[str] = None                  # 매수2 회원사 명3
    shnu_mbcr_name4: Optional[str] = None                  # 매수2 회원사 명4
    shnu_mbcr_name5: Optional[str] = None                  # 매수2 회원사 명5
    total_shnu_qty1: Optional[str] = None                  # 총 매수2 수량1
    total_shnu_qty2: Optional[str] = None                  # 총 매수2 수량2
    total_shnu_qty3: Optional[str] = None                  # 총 매수2 수량3
    total_shnu_qty4: Optional[str] = None                  # 총 매수2 수량4
    total_shnu_qty5: Optional[str] = None                  # 총 매수2 수량5
    shnu_mbcr_rlim1: Optional[str] = None                  # 매수2 회원사 비중1
    shnu_mbcr_rlim2: Optional[str] = None                  # 매수2 회원사 비중2
    shnu_mbcr_rlim3: Optional[str] = None                  # 매수2 회원사 비중3
    shnu_mbcr_rlim4: Optional[str] = None                  # 매수2 회원사 비중4
    shnu_mbcr_rlim5: Optional[str] = None                  # 매수2 회원사 비중5
    shnu_qty_icdc1: Optional[str] = None                   # 매수2 수량 증감1
    shnu_qty_icdc2: Optional[str] = None                   # 매수2 수량 증감2
    shnu_qty_icdc3: Optional[str] = None                   # 매수2 수량 증감3
    shnu_qty_icdc4: Optional[str] = None                   # 매수2 수량 증감4
    shnu_qty_icdc5: Optional[str] = None                   # 매수2 수량 증감5
    glob_total_seln_qty: Optional[str] = None              # 외국계 총 매도 수량
    glob_seln_rlim: Optional[str] = None                   # 외국계 매도 비중
    glob_ntby_qty: Optional[str] = None                    # 외국계 순매수 수량
    glob_total_shnu_qty: Optional[str] = None              # 외국계 총 매수2 수량
    glob_shnu_rlim: Optional[str] = None                   # 외국계 매수2 비중
    seln_mbcr_glob_yn_1: Optional[str] = None              # 매도 회원사 외국계 여부1
    seln_mbcr_glob_yn_2: Optional[str] = None              # 매도 회원사 외국계 여부2
    seln_mbcr_glob_yn_3: Optional[str] = None              # 매도 회원사 외국계 여부3
    seln_mbcr_glob_yn_4: Optional[str] = None              # 매도 회원사 외국계 여부4
    seln_mbcr_glob_yn_5: Optional[str] = None              # 매도 회원사 외국계 여부5
    shnu_mbcr_glob_yn_1: Optional[str] = None              # 매수2 회원사 외국계 여부1
    shnu_mbcr_glob_yn_2: Optional[str] = None              # 매수2 회원사 외국계 여부2
    shnu_mbcr_glob_yn_3: Optional[str] = None              # 매수2 회원사 외국계 여부3
    shnu_mbcr_glob_yn_4: Optional[str] = None              # 매수2 회원사 외국계 여부4
    shnu_mbcr_glob_yn_5: Optional[str] = None              # 매수2 회원사 외국계 여부5
    glob_total_seln_qty_icdc: Optional[str] = None         # 외국계 총 매도 수량 증감
    glob_total_shnu_qty_icdc: Optional[str] = None         # 외국계 총 매수2 수량 증감


@dataclass
class ResponseBody:
    rt_cd: str                          # 성공 실패 여부
    msg_cd: str                         # 응답코드
    msg1: str                           # 응답메세지
    output: ResponseBodyOutput          # 회원사 매매동향 상세


# ── 요청 함수 ───────────────────────────────────────────────

def inquire_member(
    code: str,
    market_div: Literal["J", "NX", "UN"] = "J",
    mode: Literal["real", "paper"] = "real",
) -> ResponseBody:
    """주식현재가 회원사(매도/매수2 상위 5개 회원사 매매동향)를 조회한다.

    Args:
        code: 입력 종목코드(FID_INPUT_ISCD), 6자리(ex 005930 삼성전자). ETN은 앞에 Q를 붙인 6자리.
        market_div: 조건 시장 분류 코드(FID_COND_MRKT_DIV_CODE). J:KRX, NX:NXT, UN:통합. 기본값 "J".
        mode: "real"(실전투자) 또는 "paper"(모의투자). 기본값 "real".

    Returns:
        rt_cd/msg_cd/msg1과 회원사 매매동향 상세(output)를 담은 ResponseBody.
    """
    token = load_token(mode)
    if mode == "real":
        app_key, app_secret = REAL_APPKEY, REAL_APP_SECRET
    else:
        app_key, app_secret = PAPER_APPKEY, PAPER_APP_SECRET

    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": _TR_ID,
        "custtype": "P",
    }
    params = {
        "FID_COND_MRKT_DIV_CODE": market_div,
        "FID_INPUT_ISCD": code,
    }
    response = get_session().get(DOMAIN[mode] + URL, headers=headers, params=params, timeout=10)
    raw = response.json()

    # output은 원소 1개짜리 배열로 내려온다. 에러 응답(rt_cd != "0")은 배열이 비어있거나
    # 키가 없을 수 있어 안전 파싱.
    fields = set(ResponseBodyOutput.__dataclass_fields__)
    raw_output_list = raw.get("output") or []
    raw_output = raw_output_list[0] if raw_output_list else {}
    output = ResponseBodyOutput(**{k: v for k, v in raw_output.items() if k in fields})

    return ResponseBody(
        rt_cd=raw.get("rt_cd", ""),
        msg_cd=raw.get("msg_cd", ""),
        msg1=raw.get("msg1", ""),
        output=output,
    )


# ── 실행 ────────────────────────────────────────────────────

if __name__ == "__main__":
    result = inquire_member(code="005930")
    if result.rt_cd != "0":
        print(f"조회 실패: {result.msg_cd} - {result.msg1}")
    else:
        print(result.output)
