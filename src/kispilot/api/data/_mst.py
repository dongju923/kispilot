"""마스터(.mst) 고정 폭 파일 파싱 공통부 — 종목 마스터는 앞부분(코드·이름) + 뒤쪽 고정 폭 필드로 이뤄진다."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd


def parse_stock_mst(path: Path, tail_len: int, name_col: str, widths: list[int], columns: list[str]) -> pd.DataFrame:
    """한 줄 = [단축코드 9][표준코드 12][한글명 …][고정 폭 필드 tail_len] (cp949)."""
    head, tail = [], []
    with open(path, encoding="cp949") as f:
        for row in f:
            front = row[: len(row) - tail_len]
            head.append((front[0:9].rstrip(), front[9:21].rstrip(), front[21:].strip()))
            tail.append(row[-tail_len:])
    df1 = pd.DataFrame(head, columns=["단축코드", "표준코드", name_col])
    df2 = pd.read_fwf(io.StringIO("".join(tail)), widths=widths, names=columns)
    return pd.merge(df1, df2, how="outer", left_index=True, right_index=True)
