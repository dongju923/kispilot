"""KOSPI200 야간선물 종목 마스터(fo_cme_code.mst) 파싱. 내려받기·갱신은 master.py 가 한다.

예전 CME 연계 야간선물 자리라 파일 이름에 cme 가 남아 있다.
한 줄 = cp949 바이트 기준 고정 폭 (121바이트). 예:
    1A01612   KR4A016C0004F 202612          …          00000.0012001     KOSPI200

열 이름은 한국투자증권 open-trading-api 의 stocks_info/domestic_cme_future_code.py 예제를 따른다.
예제의 row[63:72] 는 행사가(8)에 월물구분코드(1)까지 붙여 읽고 기초자산 코드도 한 칸 밀려 있어,
야간옵션 마스터(night_option.py)와 같은 꼬리 배치로 고쳐 잡았다.
https://github.com/koreainvestment/open-trading-api
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from kispilot.api.data._mst import parse_fixed_bytes_mst

FIELDS = [
    ("상품종류", 0, 1),
    ("단축코드", 1, 10),
    ("표준코드", 10, 22),
    ("한글종목명", 22, 63),
    ("행사가", 63, 71),
    ("월물구분코드", 71, 72),
    ("기초자산단축코드", 72, 81),
    ("기초자산명", 81, None),
]


def parse(mst: Path) -> pd.DataFrame:
    return parse_fixed_bytes_mst(mst, FIELDS)
