"""업종 마스터(idxcode.mst) 파싱. 내려받기·갱신은 master.py 가 한다.

한 줄 = [구분 1][업종코드 4][업종명 …] (cp949). 예: "00001종합" → ("0001", "종합")
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def parse(mst: Path) -> pd.DataFrame:
    rows = []
    with open(mst, encoding="cp949") as f:
        for row in f:
            row = row.rstrip("\r\n")
            if len(row) >= 5:
                rows.append((row[1:5], row[5:].strip()))
    return pd.DataFrame(rows, columns=["업종코드", "업종명"])


def get_sector_codes() -> pd.DataFrame:
    """마스터를 새로 받아 CSV 를 만들고 DataFrame 을 돌려준다 (예전 함수 이름 호환)."""
    from kispilot.api.data import master
    master.refresh("sector")
    return master.load("sector")


if __name__ == "__main__":
    print(get_sector_codes().head())
