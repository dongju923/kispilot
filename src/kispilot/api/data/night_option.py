"""KRX연계 야간옵션 종목 마스터(fo_eurex_code.mst) 파싱. 내려받기·갱신은 master.py 가 한다.

예전 Eurex 연계 야간옵션 자리라 파일 이름에 eurex 가 남아 있다.
한 줄 = cp949 바이트 기준 고정 폭 (121바이트). 예:
    5B01610745KR4B016A7454C 202610   745.0          …          200745.00 2001     KOSPI200

필드 위치·열 이름은 한국투자증권 open-trading-api 의 stocks_info/domestic_eurex_option_code.py 예제를 따르되,
예제는 문자 위치로 자른 뒤 lstrip() 으로 어긋남을 메꾸므로 여기서는 바이트 위치로 고쳐 잡았다.
월물구분코드 자리(바이트 71)는 옵션이라 비어 있어 뺐다.
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
    ("한글종목명", 22, 59),
    ("ATM구분", 62, 63),
    ("행사가", 63, 71),
    ("기초자산단축코드", 72, 81),
    ("기초자산명", 81, None),
]


def parse(mst: Path) -> pd.DataFrame:
    return parse_fixed_bytes_mst(mst, FIELDS)
