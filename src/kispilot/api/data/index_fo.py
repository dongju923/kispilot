"""지수선물옵션 종목 마스터(fo_idx_code_mts.mst) 파싱. 내려받기·갱신은 master.py 가 한다.

한 줄 = '|' 로 나뉜 9개 필드 (cp949). 예:
    5|B01612610|KR4B016C6108|C 202612   610.0|2|00610.00| |2001|KOSPI200

열 이름은 한국투자증권 open-trading-api 의 stocks_info/domestic_index_future_code.py 예제를 따른다
(예제 열 이름 앞 공백은 뺐다). https://github.com/koreainvestment/open-trading-api
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from kispilot.api.data._mst import parse_pipe_mst

COLUMNS = ["상품종류", "단축코드", "표준코드", "한글종목명", "ATM구분",
           "행사가", "월물구분코드", "기초자산단축코드", "기초자산명"]


def parse(mst: Path) -> pd.DataFrame:
    return parse_pipe_mst(mst, COLUMNS)
