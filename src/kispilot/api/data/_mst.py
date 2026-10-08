"""마스터(.mst) 고정 폭 파일 파싱 공통부 — 종목 마스터는 앞부분(코드·이름) + 뒤쪽 고정 폭 필드로 이뤄진다."""
from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Optional

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


def parse_fixed_bytes_mst(path: Path, fields: list[tuple[str, int, Optional[int]]]) -> pd.DataFrame:
    """필드 위치가 cp949 바이트 기준으로 고정된 마스터. fields = [(열 이름, 시작, 끝)], 끝이 None 이면 줄 끝까지.

    한글이 2바이트라 문자열로 디코딩한 뒤 문자 위치로 자르면 한글 이름이 있는 줄마다 뒤 필드가 밀린다.
    그래서 줄을 바이트로 읽어 자른 뒤 필드마다 디코딩한다.
    """
    rows = []
    with open(path, "rb") as f:
        for line in f:
            line = line.rstrip(b"\r\n")
            if line.strip():
                rows.append([line[a:b].decode("cp949").strip() for _, a, b in fields])
    return pd.DataFrame(rows, columns=[name for name, _, _ in fields])


def parse_pipe_mst(path: Path, columns: list[str]) -> pd.DataFrame:
    """'|' 로 나뉜 마스터. 코드 앞자리 0 이 사라지지 않게 모든 값을 문자열로 읽는다."""
    df = pd.read_csv(path, sep="|", header=None, names=columns, dtype=str, encoding="cp949",
                     keep_default_na=False, quoting=csv.QUOTE_NONE)
    return df.apply(lambda col: col.str.strip())
