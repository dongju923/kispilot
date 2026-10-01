"""yfinance 기반 과거 시세 조회.

종목코드와 기간을 받아 일/주/월봉 등 과거 OHLCV 를 pandas DataFrame 으로 반환한다.
국내 6자리 종목코드(예: "005930")는 yfinance 심볼 규칙에 맞게 거래소 접미사를
자동으로 붙인다 — 코스피(.KS)를 먼저 시도하고 데이터가 없으면 코스닥(.KQ)으로 재시도.
해외 티커(예: "AAPL")나 접미사가 이미 붙은 심볼("005930.KS")은 그대로 사용한다.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Union

import pandas as pd
import yfinance as yf

DateLike = Union[str, date, datetime]

_KR_SUFFIXES = (".KS", ".KQ")
_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def _candidate_symbols(code: str) -> list[str]:
    code = code.strip().upper()
    if code.isdigit() and len(code) == 6:
        return [code + s for s in _KR_SUFFIXES]
    return [code]


def get_history(
    code: str,
    start: Optional[DateLike] = None,
    end: Optional[DateLike] = None,
    period: Optional[str] = None,
    interval: str = "1d",
    auto_adjust: bool = True,
) -> pd.DataFrame:
    """종목의 과거 시세를 DataFrame 으로 반환.

    Args:
        code: 종목코드. 국내 6자리("005930") 또는 yfinance 티커("AAPL", "005930.KS").
        start: 시작일(포함). "YYYY-MM-DD" 문자열 또는 date/datetime.
        end: 종료일(포함). 생략 시 오늘까지.
        period: start 대신 상대 기간 지정 — "1mo", "6mo", "1y", "5y", "max" 등.
            start 와 period 가 모두 없으면 "1y".
        interval: 봉 단위 — "1d", "1wk", "1mo" 등 (분봉은 yfinance 조회 가능 기간 제한 있음).
        auto_adjust: True 면 배당/분할 반영 수정주가.

    Returns:
        index=Date(tz 제거), columns=[Open, High, Low, Close, Volume] 인 DataFrame.

    Raises:
        ValueError: 해당 종목/기간의 데이터가 없을 때.
    """
    kwargs: dict = {"interval": interval, "auto_adjust": auto_adjust}
    if start is not None:
        kwargs["start"] = pd.Timestamp(start).strftime("%Y-%m-%d")
        if end is not None:
            # yfinance 의 end 는 미포함이므로 하루 더해 종료일까지 포함시킨다.
            kwargs["end"] = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        kwargs["period"] = period or "1y"

    for symbol in _candidate_symbols(code):
        df = yf.Ticker(symbol).history(**kwargs)
        if df.empty:
            continue
        df = df[[c for c in _COLUMNS if c in df.columns]]
        df.index = pd.DatetimeIndex(df.index).tz_localize(None)
        df.index.name = "Date"
        df.attrs["symbol"] = symbol
        return df

    raise ValueError(f"yfinance 데이터 없음: code={code}, {kwargs}")


if __name__ == "__main__":
    print(get_history("005930", start="2024-01-01", end="2024-01-31").head())
    print(get_history("247540", period="1mo").tail())  # 코스닥(에코프로비엠)
    print(get_history("AAPL", period="5d"))
