"""
커스텀 전략 빌더용 기술적 지표 라이브러리.

- 모든 지표 함수는 OHLCV `DataFrame`을 받아 입력과 같은 길이의 `pd.Series`를 반환한다.
  (데이터가 부족한 구간은 NaN — 백테스트 워밍업 구간에서 자연스럽게 무시됨)
- `INDICATOR_CATALOG`: 지표 키 → 메타데이터(라벨/카테고리/설명/파라미터/함수).
  프런트엔드의 "지표 추가" 목록과 그대로 매핑된다.
- `compute_indicator(df, key, params)`: 카탈로그 기준으로 파라미터를 검증/보정한 뒤 지표 Series 계산.

DataFrame 컬럼 규약: open, high, low, close, volume (소문자).
"""

from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np
import pandas as pd

# 조건식에서 지표 대신 직접 쓸 수 있는 원본 가격 필드
PRICE_FIELDS: dict[str, str] = {
    "close": "종가",
    "open": "시가",
    "high": "고가",
    "low": "저가",
    "volume": "거래량",
}


# ── 파라미터 스펙 헬퍼 ────────────────────────────────────────

def _ip(name: str, label: str, default, lo, hi, step=1, typ: str = "int") -> dict:
    return {"name": name, "label": label, "default": default,
            "min": lo, "max": hi, "step": step, "type": typ}


def _period(default: int = 20, lo: int = 2, hi: int = 240) -> dict:
    return _ip("period", "기간 (일)", default, lo, hi, 1, "int")


# ── 기초 유틸 ─────────────────────────────────────────────────

def _col(df: pd.DataFrame, name: str) -> pd.Series:
    return df[name].astype(float)


def _true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = _col(df, "high"), _col(df, "low"), _col(df, "close")
    prev = close.shift(1)
    return pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return _true_range(df).ewm(alpha=1.0 / period, adjust=False).mean()


def _ema(s: pd.Series, period: int) -> pd.Series:
    return s.ewm(span=period, adjust=False).mean()


# ──────────────────────────────────────────────────────────────
# 이동평균 계열
# ──────────────────────────────────────────────────────────────

def sma(df, period=20):
    return _col(df, "close").rolling(window=int(period)).mean()


def ema(df, period=20):
    return _ema(_col(df, "close"), int(period))


def wma_wilder(df, period=20):
    return _col(df, "close").ewm(alpha=1.0 / int(period), adjust=False).mean()


def lwma(df, period=20):
    w = np.arange(1, int(period) + 1, dtype=float)
    return _col(df, "close").rolling(int(period)).apply(lambda x: np.dot(x, w) / w.sum(), raw=True)


def hma(df, period=20):
    period = int(period)
    half, sqrt_p = max(1, period // 2), max(1, int(math.sqrt(period)))
    close = _col(df, "close")
    raw = 2 * close.rolling(half).mean() - close.rolling(period).mean()
    return raw.rolling(sqrt_p).mean()


def dema(df, period=20):
    e1 = _ema(_col(df, "close"), int(period))
    e2 = _ema(e1, int(period))
    return 2 * e1 - e2


def tema(df, period=20):
    e1 = _ema(_col(df, "close"), int(period))
    e2 = _ema(e1, int(period))
    e3 = _ema(e2, int(period))
    return 3 * e1 - 3 * e2 + e3


def trima(df, period=20):
    half = (int(period) + 1) // 2
    return _col(df, "close").rolling(half).mean().rolling(half).mean()


def zlema(df, period=20):
    period = int(period)
    lag = (period - 1) // 2
    close = _col(df, "close")
    return _ema(2 * close - close.shift(lag), period)


def t3(df, period=20, vfactor=0.7):
    period, v = int(period), float(vfactor)
    c1 = -(v ** 3)
    c2 = 3 * v * v + 3 * v ** 3
    c3 = -6 * v * v - 3 * v - 3 * v ** 3
    c4 = 1 + 3 * v + v ** 3 + 3 * v * v
    close = _col(df, "close")
    e1 = _ema(close, period); e2 = _ema(e1, period); e3 = _ema(e2, period)
    e4 = _ema(e3, period); e5 = _ema(e4, period); e6 = _ema(e5, period)
    return c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3


def kama(df, period=20):
    period = int(period)
    close = _col(df, "close")
    direction = (close - close.shift(period)).abs()
    volatility = close.diff().abs().rolling(period).sum()
    er = (direction / volatility.replace(0, np.nan)).fillna(0)
    fast_sc, slow_sc = 2 / 3, 2 / 31
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    out = pd.Series(np.nan, index=close.index)
    if len(close) >= period:
        out.iloc[period - 1] = close.iloc[period - 1]
        for i in range(period, len(close)):
            out.iloc[i] = out.iloc[i - 1] + sc.iloc[i] * (close.iloc[i] - out.iloc[i - 1])
    return out


def alma(df, period=20, sigma=6.0, offset=0.85):
    period = int(period)
    m = float(offset) * (period - 1)
    s = period / float(sigma)
    w = np.exp(-((np.arange(period) - m) ** 2) / (2 * s * s))
    w /= w.sum()
    return _col(df, "close").rolling(period).apply(lambda x: np.dot(x, w), raw=True)


def vidya(df, period=20):
    period = int(period)
    close = _col(df, "close")
    cmo_abs = (cmo(df, period).abs() / 100).fillna(0)
    sc = 2 / (period + 1)
    out = pd.Series(np.nan, index=close.index)
    if len(close) >= period:
        out.iloc[period - 1] = close.iloc[period - 1]
        for i in range(period, len(close)):
            k = sc * cmo_abs.iloc[i]
            out.iloc[i] = k * close.iloc[i] + (1 - k) * out.iloc[i - 1]
    return out


def frama(df, period=20):
    period = int(period)
    close = _col(df, "close")
    half = max(1, period // 2)
    h1, l1 = close.rolling(half).max(), close.rolling(half).min()
    h2, l2 = close.shift(half).rolling(half).max(), close.shift(half).rolling(half).min()
    h_all, l_all = close.rolling(period).max(), close.rolling(period).min()
    n1 = (h1 - l1) / half
    n2 = (h2 - l2) / half
    n3 = (h_all - l_all) / period
    d = (np.log((n1 + n2).replace(0, np.nan)) - np.log(n3.replace(0, np.nan))) / np.log(2)
    alpha = np.exp(-4.6 * (d - 1)).clip(0.01, 1.0)
    out = pd.Series(np.nan, index=close.index)
    if len(close) >= period:
        start = period - 1
        out.iloc[start] = close.iloc[start]
        for i in range(start + 1, len(close)):
            a = alpha.iloc[i] if not np.isnan(alpha.iloc[i]) else 0.5
            out.iloc[i] = a * close.iloc[i] + (1 - a) * out.iloc[i - 1]
    return out


def vwma(df, period=20):
    pv = _col(df, "close") * _col(df, "volume")
    return pv.rolling(int(period)).sum() / _col(df, "volume").rolling(int(period)).sum()


def midpoint(df, period=14):
    close = _col(df, "close")
    return (close.rolling(int(period)).max() + close.rolling(int(period)).min()) / 2


def midprice(df, period=14):
    return (_col(df, "high").rolling(int(period)).max() + _col(df, "low").rolling(int(period)).min()) / 2


# ──────────────────────────────────────────────────────────────
# 추세 / 방향성
# ──────────────────────────────────────────────────────────────

def macd_line(df, fast=12, slow=26, signal=9):
    close = _col(df, "close")
    return _ema(close, int(fast)) - _ema(close, int(slow))


def macd_signal(df, fast=12, slow=26, signal=9):
    return _ema(macd_line(df, fast, slow, signal), int(signal))


def macd_hist(df, fast=12, slow=26, signal=9):
    return macd_line(df, fast, slow, signal) - macd_signal(df, fast, slow, signal)


def _dm(df: pd.DataFrame):
    high, low = _col(df, "high"), _col(df, "low")
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    return plus_dm, minus_dm


def di_plus(df, period=14):
    plus_dm, _ = _dm(df)
    atr = _atr(df, int(period))
    return 100 * (plus_dm.ewm(span=int(period), adjust=False).mean() / atr.replace(0, np.nan))


def di_minus(df, period=14):
    _, minus_dm = _dm(df)
    atr = _atr(df, int(period))
    return 100 * (minus_dm.ewm(span=int(period), adjust=False).mean() / atr.replace(0, np.nan))


def adx(df, period=14):
    pdi, mdi = di_plus(df, period), di_minus(df, period)
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(span=int(period), adjust=False).mean()


def adxr(df, period=14):
    a = adx(df, period)
    return (a + a.shift(int(period))) / 2


def aroon_up(df, period=25):
    period = int(period)
    high = _col(df, "high")
    out = pd.Series(np.nan, index=df.index)
    for i in range(period, len(df)):
        window = high.iloc[i - period:i + 1].values
        out.iloc[i] = window.argmax() / period * 100
    return out


def aroon_down(df, period=25):
    period = int(period)
    low = _col(df, "low")
    out = pd.Series(np.nan, index=df.index)
    for i in range(period, len(df)):
        window = low.iloc[i - period:i + 1].values
        out.iloc[i] = (window.argmin()) / period * 100
    return out


def aroon_osc(df, period=25):
    return aroon_up(df, period) - aroon_down(df, period)


def supertrend_dir(df, period=10, multiplier=3.0):
    period, mult = int(period), float(multiplier)
    atr = _atr(df, period)
    hl2 = (_col(df, "high") + _col(df, "low")) / 2
    upper = hl2 + mult * atr
    lower = hl2 - mult * atr
    close = _col(df, "close")
    direction = pd.Series(1.0, index=df.index)
    for i in range(1, len(df)):
        if close.iloc[i] > upper.iloc[i - 1]:
            direction.iloc[i] = 1.0
        elif close.iloc[i] < lower.iloc[i - 1]:
            direction.iloc[i] = -1.0
        else:
            direction.iloc[i] = direction.iloc[i - 1]
    return direction


def parabolic_sar(df, af_start=0.02, af_max=0.2):
    af_start, af_max = float(af_start), float(af_max)
    high, low = _col(df, "high").values, _col(df, "low").values
    sar = pd.Series(np.nan, index=df.index)
    if len(df) < 2:
        return sar
    trend = 1
    ep = high[0]
    af = af_start
    sar.iloc[0] = low[0]
    for i in range(1, len(df)):
        sar.iloc[i] = sar.iloc[i - 1] + af * (ep - sar.iloc[i - 1])
        if trend == 1:
            if low[i] < sar.iloc[i]:
                trend, sar.iloc[i], ep, af = -1, ep, low[i], af_start
            elif high[i] > ep:
                ep, af = high[i], min(af + af_start, af_max)
        else:
            if high[i] > sar.iloc[i]:
                trend, sar.iloc[i], ep, af = 1, ep, high[i], af_start
            elif low[i] < ep:
                ep, af = low[i], min(af + af_start, af_max)
    return sar


def ichimoku_tenkan(df, period=9):
    return (_col(df, "high").rolling(int(period)).max() + _col(df, "low").rolling(int(period)).min()) / 2


def ichimoku_kijun(df, period=26):
    return (_col(df, "high").rolling(int(period)).max() + _col(df, "low").rolling(int(period)).min()) / 2


def donchian_upper(df, period=20):
    return _col(df, "high").rolling(int(period)).max()


def donchian_lower(df, period=20):
    return _col(df, "low").rolling(int(period)).min()


def vortex_plus(df, period=14):
    period = int(period)
    vm = (_col(df, "high") - _col(df, "low").shift(1)).abs()
    tr = _true_range(df)
    return vm.rolling(period).sum() / tr.rolling(period).sum()


def vortex_minus(df, period=14):
    period = int(period)
    vm = (_col(df, "low") - _col(df, "high").shift(1)).abs()
    tr = _true_range(df)
    return vm.rolling(period).sum() / tr.rolling(period).sum()


def trix(df, period=15):
    period = int(period)
    e1 = _ema(_col(df, "close"), period)
    e2 = _ema(e1, period)
    e3 = _ema(e2, period)
    return e3.pct_change() * 100


def dpo(df, period=20):
    period = int(period)
    shift = period // 2 + 1
    return _col(df, "close") - _col(df, "close").rolling(period).mean().shift(shift)


def kst(df):
    close = _col(df, "close")
    r1 = close.pct_change(10) * 100
    r2 = close.pct_change(15) * 100
    r3 = close.pct_change(20) * 100
    r4 = close.pct_change(30) * 100
    return (r1.rolling(10).mean() * 1 + r2.rolling(10).mean() * 2
            + r3.rolling(10).mean() * 3 + r4.rolling(15).mean() * 4)


def coppock(df):
    close = _col(df, "close")
    return ((close.pct_change(14) * 100) + (close.pct_change(11) * 100)).ewm(span=10, adjust=False).mean()


def mass_index(df, period=25):
    hl = _col(df, "high") - _col(df, "low")
    e1 = _ema(hl, 9)
    e2 = _ema(e1, 9)
    return (e1 / e2.replace(0, np.nan)).rolling(int(period)).sum()


def schaff(df, period=23, fast=10, slow=50):
    period, fast, slow = int(period), int(fast), int(slow)
    close = _col(df, "close")
    macd_l = _ema(close, fast) - _ema(close, slow)
    ll, hh = macd_l.rolling(period).min(), macd_l.rolling(period).max()
    st1 = ((macd_l - ll) / (hh - ll).replace(0, np.nan)) * 100
    pf = st1.ewm(com=1, adjust=False).mean()
    ll2, hh2 = pf.rolling(period).min(), pf.rolling(period).max()
    st2 = ((pf - ll2) / (hh2 - ll2).replace(0, np.nan)) * 100
    return st2.ewm(com=1, adjust=False).mean()


def chop(df, period=14):
    period = int(period)
    tr = _true_range(df)
    tr_sum = tr.rolling(period).sum()
    rng = (_col(df, "high").rolling(period).max() - _col(df, "low").rolling(period).min()).replace(0, np.nan)
    return 100 * np.log10(tr_sum / rng) / np.log10(period)


def regression_slope(df, period=20):
    period = int(period)
    x = np.arange(period, dtype=float)
    x_mean = x.mean()
    x_var = ((x - x_mean) ** 2).sum()
    return _col(df, "close").rolling(period).apply(
        lambda y: np.sum((x - x_mean) * (y - y.mean())) / x_var, raw=True)


def regression_intercept(df, period=20):
    period = int(period)
    x = np.arange(period, dtype=float)
    x_mean = x.mean()
    x_var = ((x - x_mean) ** 2).sum()

    def _ic(y):
        slope = np.sum((x - x_mean) * (y - y.mean())) / x_var
        return y.mean() - slope * x_mean

    return _col(df, "close").rolling(period).apply(_ic, raw=True)


# ──────────────────────────────────────────────────────────────
# 모멘텀 / 오실레이터
# ──────────────────────────────────────────────────────────────

def rsi(df, period=14):
    period = int(period)
    delta = _col(df, "close").diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_up = up.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_down = down.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_up / avg_down.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50)


def stoch_rsi(df, period=14):
    period = int(period)
    r = rsi(df, period)
    ll, hh = r.rolling(period).min(), r.rolling(period).max()
    return ((r - ll) / (hh - ll).replace(0, np.nan)) * 100


def stoch_k(df, period=14):
    period = int(period)
    ll = _col(df, "low").rolling(period).min()
    hh = _col(df, "high").rolling(period).max()
    return ((_col(df, "close") - ll) / (hh - ll).replace(0, np.nan)) * 100


def stoch_d(df, k_period=14, d_period=3):
    return stoch_k(df, int(k_period)).rolling(int(d_period)).mean()


def cci(df, period=20):
    period = int(period)
    tp = (_col(df, "high") + _col(df, "low") + _col(df, "close")) / 3
    tp_sma = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    return (tp - tp_sma) / (0.015 * mad.replace(0, np.nan))


def williams_r(df, period=14):
    period = int(period)
    hh = _col(df, "high").rolling(period).max()
    ll = _col(df, "low").rolling(period).min()
    return ((hh - _col(df, "close")) / (hh - ll).replace(0, np.nan)) * -100


def mfi(df, period=14):
    period = int(period)
    tp = (_col(df, "high") + _col(df, "low") + _col(df, "close")) / 3
    rmf = tp * _col(df, "volume")
    diff = tp.diff()
    pos = rmf.where(diff > 0, 0.0).rolling(period).sum()
    neg = rmf.where(diff < 0, 0.0).rolling(period).sum()
    mr = pos / neg.replace(0, np.nan)
    return 100 - 100 / (1 + mr)


def roc(df, period=10):
    return _col(df, "close").pct_change(int(period)) * 100


def momentum_diff(df, period=10):
    return _col(df, "close") - _col(df, "close").shift(int(period))


def returns_ratio(df, period=20):
    return _col(df, "close").pct_change(int(period))


def disparity(df, period=20):
    return (_col(df, "close") / _col(df, "close").rolling(int(period)).mean()) * 100


def daily_change(df):
    return _col(df, "close").pct_change() * 100


def cmo(df, period=14):
    period = int(period)
    diff = _col(df, "close").diff()
    gain = diff.clip(lower=0).rolling(period).sum()
    loss = (-diff.clip(upper=0)).rolling(period).sum()
    return ((gain - loss) / (gain + loss).replace(0, np.nan)) * 100


def apo(df, fast=12, slow=26):
    close = _col(df, "close")
    return _ema(close, int(fast)) - _ema(close, int(slow))


def ppo(df, fast=12, slow=26):
    close = _col(df, "close")
    ef, es = _ema(close, int(fast)), _ema(close, int(slow))
    return ((ef - es) / es.replace(0, np.nan)) * 100


def awesome_osc(df):
    hl2 = (_col(df, "high") + _col(df, "low")) / 2
    return hl2.rolling(5).mean() - hl2.rolling(34).mean()


def ultimate_osc(df, p1=7, p2=14, p3=28):
    p1, p2, p3 = int(p1), int(p2), int(p3)
    close, low, high = _col(df, "close"), _col(df, "low"), _col(df, "high")
    prev_close = close.shift(1)
    tl = pd.concat([low, prev_close], axis=1).min(axis=1)
    bp = close - tl
    tr = pd.concat([high, prev_close], axis=1).max(axis=1) - tl
    a1 = bp.rolling(p1).sum() / tr.rolling(p1).sum()
    a2 = bp.rolling(p2).sum() / tr.rolling(p2).sum()
    a3 = bp.rolling(p3).sum() / tr.rolling(p3).sum()
    return 100 * (4 * a1 + 2 * a2 + a3) / 7


def tsi(df, long=25, short=13):
    long, short = int(long), int(short)
    diff = _col(df, "close").diff()
    s1 = _ema(_ema(diff, long), short)
    s2 = _ema(_ema(diff.abs(), long), short)
    return (s1 / s2.replace(0, np.nan)) * 100


def rvi(df, period=10):
    period = int(period)
    co = _col(df, "close") - _col(df, "open")
    hl = _col(df, "high") - _col(df, "low")
    num = (co + 2 * co.shift(1) + 2 * co.shift(2) + co.shift(3)) / 6
    den = (hl + 2 * hl.shift(1) + 2 * hl.shift(2) + hl.shift(3)) / 6
    return num.rolling(period).mean() / den.rolling(period).mean().replace(0, np.nan)


def fisher_transform(df, period=9):
    period = int(period)
    hl2 = (_col(df, "high") + _col(df, "low")) / 2
    hh, ll = hl2.rolling(period).max(), hl2.rolling(period).min()
    val = (2 * ((hl2 - ll) / (hh - ll).replace(0, np.nan)) - 1).clip(-0.999, 0.999).fillna(0)
    out = pd.Series(0.0, index=df.index)
    for i in range(period, len(df)):
        out.iloc[i] = 0.25 * np.log((1 + val.iloc[i]) / (1 - val.iloc[i])) + 0.5 * out.iloc[i - 1]
    return out


def klinger_osc(df, fast=34, slow=55):
    fast, slow = int(fast), int(slow)
    hlc = _col(df, "high") + _col(df, "low") + _col(df, "close")
    trend = np.where(hlc > hlc.shift(1), 1, -1)
    dm = _col(df, "high") - _col(df, "low")
    cm = pd.Series(np.nan, index=df.index)
    if len(df):
        cm.iloc[0] = dm.iloc[0]
        for i in range(1, len(df)):
            cm.iloc[i] = (cm.iloc[i - 1] + dm.iloc[i]) if trend[i] == trend[i - 1] else (dm.iloc[i - 1] + dm.iloc[i])
    vf = _col(df, "volume") * (2 * dm / cm.replace(0, np.nan) - 1).abs() * trend * 100
    return _ema(vf, fast) - _ema(vf, slow)


def chaikin_osc(df, fast=3, slow=10):
    line = adl(df)
    return _ema(line, int(fast)) - _ema(line, int(slow))


def bop(df):
    return (_col(df, "close") - _col(df, "open")) / (_col(df, "high") - _col(df, "low")).replace(0, np.nan)


def augen_spike(df, period=14):
    period = int(period)
    log_ret = np.log(_col(df, "close") / _col(df, "close").shift(1))
    return log_ret / log_ret.rolling(period).std().replace(0, np.nan)


def ibs(df):
    """Internal Bar Strength: (종가-저가)/(고가-저가). 0~1, 분모 0이면 0.5."""
    rng = (_col(df, "high") - _col(df, "low")).replace(0, np.nan)
    return ((_col(df, "close") - _col(df, "low")) / rng).fillna(0.5)


def _streak(mask: pd.Series) -> pd.Series:
    m = mask.astype(bool).astype(int)
    grp = (m != m.shift()).cumsum()
    return (m.groupby(grp).cumcount() + 1) * m


def consecutive_up(df):
    return _streak(_col(df, "close") > _col(df, "close").shift(1)).astype(float)


def consecutive_down(df):
    return _streak(_col(df, "close") < _col(df, "close").shift(1)).astype(float)


# ──────────────────────────────────────────────────────────────
# 변동성
# ──────────────────────────────────────────────────────────────

def atr_value(df, period=14):
    return _atr(df, int(period))


def natr(df, period=14):
    return (_atr(df, int(period)) / _col(df, "close").replace(0, np.nan)) * 100


def std_dev(df, period=20):
    return _col(df, "close").rolling(int(period)).std()


def variance(df, period=20):
    return _col(df, "close").rolling(int(period)).var()


def volatility(df, period=10):
    return _col(df, "close").pct_change().rolling(int(period)).std()


def bb_middle(df, period=20):
    return _col(df, "close").rolling(int(period)).mean()


def bb_upper(df, period=20, std=2.0):
    mid = _col(df, "close").rolling(int(period)).mean()
    return mid + _col(df, "close").rolling(int(period)).std() * float(std)


def bb_lower(df, period=20, std=2.0):
    mid = _col(df, "close").rolling(int(period)).mean()
    return mid - _col(df, "close").rolling(int(period)).std() * float(std)


def bb_width(df, period=20, std=2.0):
    return bb_upper(df, period, std) - bb_lower(df, period, std)


def bb_percent(df, period=20, std=2.0):
    up, lo = bb_upper(df, period, std), bb_lower(df, period, std)
    return (_col(df, "close") - lo) / (up - lo).replace(0, np.nan)


def keltner_upper(df, ema_period=20, atr_period=10, multiplier=2.0):
    return _ema(_col(df, "close"), int(ema_period)) + _atr(df, int(atr_period)) * float(multiplier)


def keltner_lower(df, ema_period=20, atr_period=10, multiplier=2.0):
    return _ema(_col(df, "close"), int(ema_period)) - _atr(df, int(atr_period)) * float(multiplier)


def accbands_upper(df, period=20):
    high, low = _col(df, "high"), _col(df, "low")
    factor = high * (1 + 2 * ((high - low) / (high + low).replace(0, np.nan)))
    return factor.rolling(int(period)).mean()


def accbands_lower(df, period=20):
    high, low = _col(df, "high"), _col(df, "low")
    factor = low * (1 - 2 * ((high - low) / (high + low).replace(0, np.nan)))
    return factor.rolling(int(period)).mean()


# ──────────────────────────────────────────────────────────────
# 거래량
# ──────────────────────────────────────────────────────────────

def obv(df):
    close, vol = _col(df, "close"), _col(df, "volume")
    direction = np.sign(close.diff()).fillna(0)
    return (direction * vol).cumsum()


def volume_ma(df, period=20):
    return _col(df, "volume").rolling(int(period)).mean()


def vwap(df):
    tp = (_col(df, "high") + _col(df, "low") + _col(df, "close")) / 3
    vol = _col(df, "volume")
    return (tp * vol).cumsum() / vol.cumsum().replace(0, np.nan)


def ad(df):
    hl = (_col(df, "high") - _col(df, "low")).replace(0, np.nan)
    mfm = ((_col(df, "close") - _col(df, "low")) - (_col(df, "high") - _col(df, "close"))) / hl
    return mfm.fillna(0) * _col(df, "volume")


def adl(df):
    return ad(df).cumsum()


def cmf(df, period=20):
    period = int(period)
    hl = (_col(df, "high") - _col(df, "low")).replace(0, np.nan)
    mfm = (((_col(df, "close") - _col(df, "low")) - (_col(df, "high") - _col(df, "close"))) / hl).fillna(0)
    mfv = mfm * _col(df, "volume")
    return mfv.rolling(period).sum() / _col(df, "volume").rolling(period).sum().replace(0, np.nan)


def force_index(df, period=13):
    return _ema(_col(df, "close").diff() * _col(df, "volume"), int(period))


def ease_of_movement(df, period=14):
    period = int(period)
    dm = ((_col(df, "high") + _col(df, "low")) / 2) - ((_col(df, "high").shift(1) + _col(df, "low").shift(1)) / 2)
    br = _col(df, "volume") / (_col(df, "high") - _col(df, "low")).replace(0, np.nan)
    return (dm / br.replace(0, np.nan)).rolling(period).mean()


def vol_price_trend(df):
    return (_col(df, "close").pct_change().fillna(0) * _col(df, "volume")).cumsum()


# ──────────────────────────────────────────────────────────────
# 가격 / 기타
# ──────────────────────────────────────────────────────────────

def highest_high(df, period=20):
    return _col(df, "high").rolling(int(period)).max()


def lowest_low(df, period=20):
    return _col(df, "low").rolling(int(period)).min()


def highest_close(df, period=20):
    return _col(df, "close").rolling(int(period)).max()


def lowest_close(df, period=20):
    return _col(df, "close").rolling(int(period)).min()


def typical_price(df):
    return (_col(df, "high") + _col(df, "low") + _col(df, "close")) / 3


def median_price(df):
    return (_col(df, "high") + _col(df, "low")) / 2


def log_return(df):
    return np.log(_col(df, "close") / _col(df, "close").shift(1))


# ──────────────────────────────────────────────────────────────
# 캔들스틱 패턴  (+1=강세, -1=약세, 0=미감지)
# ──────────────────────────────────────────────────────────────

def _body(o, c): return abs(c - o)
def _upper_shadow(h, o, c): return h - max(o, c)
def _lower_shadow(o, c, l): return min(o, c) - l
def _rng(h, l): return h - l
def _is_bull(o, c): return c > o
def _is_bear(o, c): return c < o

def _ohlc(df, idx=-1):
    return (float(df["open"].iloc[idx]), float(df["high"].iloc[idx]),
            float(df["low"].iloc[idx]), float(df["close"].iloc[idx]))

def _avgbody(df, n=10):
    b = abs(df["close"].tail(n) - df["open"].tail(n))
    return float(b.mean()) if len(b) > 0 else 1.0


# Single candle

def _c_doji(df):
    o, h, l, c = _ohlc(df)
    r = _rng(h, l)
    return 1 if r > 0 and _body(o, c) / r < 0.1 else 0

def _c_dragonfly_doji(df):
    o, h, l, c = _ohlc(df)
    r = _rng(h, l)
    if r == 0: return 0
    return 1 if _body(o, c) / r < 0.1 and _lower_shadow(o, c, l) / r > 0.6 and _upper_shadow(h, o, c) / r < 0.1 else 0

def _c_gravestone_doji(df):
    o, h, l, c = _ohlc(df)
    r = _rng(h, l)
    if r == 0: return 0
    return -1 if _body(o, c) / r < 0.1 and _upper_shadow(h, o, c) / r > 0.6 and _lower_shadow(o, c, l) / r < 0.1 else 0

def _c_long_legged_doji(df):
    o, h, l, c = _ohlc(df)
    r = _rng(h, l)
    if r == 0: return 0
    return 1 if _body(o, c) / r < 0.1 and _upper_shadow(h, o, c) / r > 0.3 and _lower_shadow(o, c, l) / r > 0.3 else 0

def _c_hammer(df):
    o, h, l, c = _ohlc(df)
    b = _body(o, c); r = _rng(h, l)
    if r == 0 or b == 0: return 0
    return 1 if _lower_shadow(o, c, l) >= 2 * b and _upper_shadow(h, o, c) <= b * 0.3 else 0

def _c_hanging_man(df):
    o, h, l, c = _ohlc(df)
    b = _body(o, c); r = _rng(h, l)
    if r == 0 or b == 0: return 0
    return -1 if _lower_shadow(o, c, l) >= 2 * b and _upper_shadow(h, o, c) <= b * 0.3 else 0

def _c_inverted_hammer(df):
    o, h, l, c = _ohlc(df)
    b = _body(o, c)
    if b == 0: return 0
    return 1 if _upper_shadow(h, o, c) >= 2 * b and _lower_shadow(o, c, l) <= b * 0.3 else 0

def _c_shooting_star(df):
    o, h, l, c = _ohlc(df)
    b = _body(o, c)
    if b == 0: return 0
    return -1 if _upper_shadow(h, o, c) >= 2 * b and _lower_shadow(o, c, l) <= b * 0.3 else 0

def _c_marubozu(df):
    o, h, l, c = _ohlc(df)
    r = _rng(h, l)
    if r == 0: return 0
    if _upper_shadow(h, o, c) / r < 0.05 and _lower_shadow(o, c, l) / r < 0.05:
        return 1 if _is_bull(o, c) else -1
    return 0

def _c_closing_marubozu(df):
    o, h, l, c = _ohlc(df)
    r = _rng(h, l)
    if r == 0: return 0
    if _is_bull(o, c) and _upper_shadow(h, o, c) / r < 0.05: return 1
    if _is_bear(o, c) and _lower_shadow(o, c, l) / r < 0.05: return -1
    return 0

def _c_opening_marubozu(df):
    o, h, l, c = _ohlc(df)
    r = _rng(h, l)
    if r == 0: return 0
    if _is_bull(o, c) and _lower_shadow(o, c, l) / r < 0.05: return 1
    if _is_bear(o, c) and _upper_shadow(h, o, c) / r < 0.05: return -1
    return 0

def _c_spinning_top(df):
    o, h, l, c = _ohlc(df)
    r = _rng(h, l)
    if r == 0: return 0
    b = _body(o, c)
    return 1 if b / r < 0.3 and _upper_shadow(h, o, c) > b and _lower_shadow(o, c, l) > b else 0

def _c_belt_hold(df):
    o, h, l, c = _ohlc(df)
    avg = _avgbody(df); b = _body(o, c)
    if b > avg * 1.5:
        if _is_bull(o, c) and _lower_shadow(o, c, l) < b * 0.05: return 1
        if _is_bear(o, c) and _upper_shadow(h, o, c) < b * 0.05: return -1
    return 0

def _c_high_wave(df):
    o, h, l, c = _ohlc(df)
    r = _rng(h, l)
    if r == 0: return 0
    b = _body(o, c)
    return 1 if b / r < 0.15 and _upper_shadow(h, o, c) / r > 0.3 and _lower_shadow(o, c, l) / r > 0.3 else 0

def _c_rickshaw_man(df): return _c_long_legged_doji(df)


# Double candle

def _c_engulfing(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    if _is_bear(o1, c1) and _is_bull(o2, c2) and o2 <= c1 and c2 >= o1: return 1
    if _is_bull(o1, c1) and _is_bear(o2, c2) and o2 >= c1 and c2 <= o1: return -1
    return 0

def _c_harami(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    b1, b2 = _body(o1, c1), _body(o2, c2)
    if b1 > 0 and b2 < b1:
        if _is_bear(o1, c1) and _is_bull(o2, c2) and o2 >= c1 and c2 <= o1: return 1
        if _is_bull(o1, c1) and _is_bear(o2, c2) and o2 <= c1 and c2 >= o1: return -1
    return 0

def _c_harami_cross(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    r2 = _rng(h2, l2)
    if _body(o1, c1) > 0 and r2 > 0 and _body(o2, c2) / r2 < 0.1:
        if min(o2, c2) >= min(o1, c1) and max(o2, c2) <= max(o1, c1):
            return 1 if _is_bear(o1, c1) else -1
    return 0

def _c_piercing(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    mid1 = (o1 + c1) / 2
    return 1 if _is_bear(o1, c1) and _is_bull(o2, c2) and o2 < c1 and c2 > mid1 and c2 < o1 else 0

def _c_dark_cloud_cover(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    mid1 = (o1 + c1) / 2
    return -1 if _is_bull(o1, c1) and _is_bear(o2, c2) and o2 > c1 and c2 < mid1 and c2 > o1 else 0

def _c_counterattack(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.05
    if _is_bear(o1, c1) and _is_bull(o2, c2) and abs(c2 - c1) < tol: return 1
    if _is_bull(o1, c1) and _is_bear(o2, c2) and abs(c2 - c1) < tol: return -1
    return 0

def _c_tweezer_top(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.05
    return -1 if abs(h1 - h2) < tol and _is_bull(o1, c1) and _is_bear(o2, c2) else 0

def _c_tweezer_bottom(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.05
    return 1 if abs(l1 - l2) < tol and _is_bear(o1, c1) and _is_bull(o2, c2) else 0

def _c_on_neck(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.05
    return -1 if _is_bear(o1, c1) and _is_bull(o2, c2) and abs(c2 - l1) < tol else 0

def _c_in_neck(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.05
    return -1 if _is_bear(o1, c1) and _is_bull(o2, c2) and abs(c2 - c1) < tol else 0

def _c_thrusting(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    mid1 = (o1 + c1) / 2
    return -1 if _is_bear(o1, c1) and _is_bull(o2, c2) and c2 > c1 and c2 < mid1 else 0

def _c_separating_lines(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.05
    if _is_bear(o1, c1) and _is_bull(o2, c2) and abs(o1 - o2) < tol: return 1
    if _is_bull(o1, c1) and _is_bear(o2, c2) and abs(o1 - o2) < tol: return -1
    return 0

def _c_meeting_lines(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.05
    if _is_bear(o1, c1) and _is_bull(o2, c2) and abs(c1 - c2) < tol: return 1
    if _is_bull(o1, c1) and _is_bear(o2, c2) and abs(c1 - c2) < tol: return -1
    return 0

def _c_kicking(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    r1, r2 = _rng(h1, l1), _rng(h2, l2)
    if r1 == 0 or r2 == 0: return 0
    m1 = _body(o1, c1) / r1 > 0.9; m2 = _body(o2, c2) / r2 > 0.9
    if m1 and m2 and _is_bear(o1, c1) and _is_bull(o2, c2) and o2 > o1: return 1
    if m1 and m2 and _is_bull(o1, c1) and _is_bear(o2, c2) and o2 < o1: return -1
    return 0

def _c_matching_low(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.03
    return 1 if _is_bear(o1, c1) and _is_bear(o2, c2) and abs(c1 - c2) < tol else 0

def _c_matching_high(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.03
    return -1 if _is_bull(o1, c1) and _is_bull(o2, c2) and abs(c1 - c2) < tol else 0

def _c_gap_side_by_side_white(df):
    o1, _, _, c1 = _ohlc(df, -2); o2, _, _, c2 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.1
    return 1 if _is_bull(o1, c1) and _is_bull(o2, c2) and abs(o1 - o2) < tol else 0

def _c_homing_pigeon(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    if _is_bear(o1, c1) and _is_bear(o2, c2) and o2 < o1 and c2 > c1 and _body(o2, c2) < _body(o1, c1):
        return 1
    return 0

def _c_dojistar(df):
    o1, h1, l1, c1 = _ohlc(df, -2); o2, h2, l2, c2 = _ohlc(df, -1)
    r2 = _rng(h2, l2)
    if r2 > 0 and _body(o2, c2) / r2 < 0.1:
        if _is_bull(o1, c1) and o2 > c1: return -1
        if _is_bear(o1, c1) and o2 < c1: return 1
    return 0

def _c_kicking_by_length(df): return _c_kicking(df)


# Triple+ candle

def _c_morning_star(df):
    o1, h1, l1, c1 = _ohlc(df, -3); o2, h2, l2, c2 = _ohlc(df, -2); o3, h3, l3, c3 = _ohlc(df, -1)
    return 1 if _is_bear(o1, c1) and _body(o2, c2) < _body(o1, c1) * 0.3 and _is_bull(o3, c3) and c3 > (o1 + c1) / 2 else 0

def _c_morning_doji_star(df):
    o1, h1, l1, c1 = _ohlc(df, -3); o2, h2, l2, c2 = _ohlc(df, -2); o3, h3, l3, c3 = _ohlc(df, -1)
    r2 = _rng(h2, l2)
    return 1 if _is_bear(o1, c1) and r2 > 0 and _body(o2, c2) / r2 < 0.1 and _is_bull(o3, c3) and c3 > (o1 + c1) / 2 else 0

def _c_evening_star(df):
    o1, h1, l1, c1 = _ohlc(df, -3); o2, h2, l2, c2 = _ohlc(df, -2); o3, h3, l3, c3 = _ohlc(df, -1)
    return -1 if _is_bull(o1, c1) and _body(o2, c2) < _body(o1, c1) * 0.3 and _is_bear(o3, c3) and c3 < (o1 + c1) / 2 else 0

def _c_evening_doji_star(df):
    o1, h1, l1, c1 = _ohlc(df, -3); o2, h2, l2, c2 = _ohlc(df, -2); o3, h3, l3, c3 = _ohlc(df, -1)
    r2 = _rng(h2, l2)
    return -1 if _is_bull(o1, c1) and r2 > 0 and _body(o2, c2) / r2 < 0.1 and _is_bear(o3, c3) and c3 < (o1 + c1) / 2 else 0

def _c_three_white_soldiers(df):
    cs = [_ohlc(df, i) for i in [-3, -2, -1]]
    if not all(_is_bull(c[0], c[3]) for c in cs): return 0
    return 1 if cs[1][3] > cs[0][3] and cs[2][3] > cs[1][3] else 0

def _c_three_black_crows(df):
    cs = [_ohlc(df, i) for i in [-3, -2, -1]]
    if not all(_is_bear(c[0], c[3]) for c in cs): return 0
    return -1 if cs[1][3] < cs[0][3] and cs[2][3] < cs[1][3] else 0

def _c_three_inside(df):
    sub = pd.DataFrame({"open": df["open"].iloc[-3:-1].values, "high": df["high"].iloc[-3:-1].values,
                         "low": df["low"].iloc[-3:-1].values, "close": df["close"].iloc[-3:-1].values})
    h = _c_harami(sub)
    if h == 0: return 0
    o3, _, _, c3 = _ohlc(df, -1); _, _, _, c1 = _ohlc(df, -3)
    if h == 1 and c3 > c1: return 1
    if h == -1 and c3 < c1: return -1
    return 0

def _c_three_outside(df):
    sub = pd.DataFrame({"open": df["open"].iloc[-3:-1].values, "high": df["high"].iloc[-3:-1].values,
                         "low": df["low"].iloc[-3:-1].values, "close": df["close"].iloc[-3:-1].values})
    e = _c_engulfing(sub)
    if e == 0: return 0
    _, _, _, c2 = _ohlc(df, -2); _, _, _, c3 = _ohlc(df, -1)
    if e == 1 and c3 > c2: return 1
    if e == -1 and c3 < c2: return -1
    return 0

def _c_abandoned_baby(df):
    o1, h1, l1, c1 = _ohlc(df, -3); o2, h2, l2, c2 = _ohlc(df, -2); o3, h3, l3, c3 = _ohlc(df, -1)
    r2 = _rng(h2, l2)
    if r2 == 0: return 0
    is_doji = _body(o2, c2) / r2 < 0.1
    if _is_bear(o1, c1) and is_doji and h2 < l1 and l2 < l3 and _is_bull(o3, c3): return 1
    if _is_bull(o1, c1) and is_doji and l2 > h1 and h2 > h3 and _is_bear(o3, c3): return -1
    return 0


def _c_tasuki_gap(df):
    o1, _, _, c1 = _ohlc(df, -3); o2, _, _, c2 = _ohlc(df, -2); o3, _, _, c3 = _ohlc(df, -1)
    if _is_bull(o1, c1) and _is_bull(o2, c2) and o2 > c1 and _is_bear(o3, c3): return 1
    if _is_bear(o1, c1) and _is_bear(o2, c2) and o2 < c1 and _is_bull(o3, c3): return -1
    return 0

def _c_upside_gap_two_crows(df):
    o1, _, _, c1 = _ohlc(df, -3); o2, _, _, c2 = _ohlc(df, -2); o3, _, _, c3 = _ohlc(df, -1)
    return -1 if _is_bull(o1, c1) and _is_bear(o2, c2) and o2 > c1 and _is_bear(o3, c3) and o3 > o2 and c3 < c2 else 0

def _c_three_line_strike(df):
    if len(df) < 4: return 0
    cs = [_ohlc(df, i) for i in [-4, -3, -2, -1]]
    if all(_is_bear(c[0], c[3]) for c in cs[:3]) and cs[1][3] < cs[0][3] and cs[2][3] < cs[1][3]:
        if _is_bull(cs[3][0], cs[3][3]) and cs[3][3] > cs[0][0]: return 1
    if all(_is_bull(c[0], c[3]) for c in cs[:3]) and cs[1][3] > cs[0][3] and cs[2][3] > cs[1][3]:
        if _is_bear(cs[3][0], cs[3][3]) and cs[3][3] < cs[0][0]: return -1
    return 0



def _c_stick_sandwich(df):
    o1, _, _, c1 = _ohlc(df, -3); o2, _, _, c2 = _ohlc(df, -2); o3, _, _, c3 = _ohlc(df, -1)
    tol = _avgbody(df) * 0.03
    return 1 if _is_bear(o1, c1) and _is_bull(o2, c2) and _is_bear(o3, c3) and abs(c1 - c3) < tol else 0

def _c_tristar(df):
    for i in [-3, -2, -1]:
        o, h, l, c = _ohlc(df, i)
        r = _rng(h, l)
        if r == 0 or _body(o, c) / r >= 0.1: return 0
    _, _, l2, _ = _ohlc(df, -2); _, _, l1, _ = _ohlc(df, -3); _, _, l3, _ = _ohlc(df, -1)
    if l2 < l1 and l2 < l3: return 1
    _, h2, _, _ = _ohlc(df, -2); _, h1, _, _ = _ohlc(df, -3); _, h3, _, _ = _ohlc(df, -1)
    if h2 > h1 and h2 > h3: return -1
    return 0

def _c_identical_three_crows(df):
    cs = [_ohlc(df, i) for i in [-3, -2, -1]]
    if not all(_is_bear(c[0], c[3]) for c in cs): return 0
    tol = _avgbody(df) * 0.03
    return -1 if abs(cs[1][0] - cs[0][3]) < tol and abs(cs[2][0] - cs[1][3]) < tol else 0

def _c_two_crows(df):
    o1, _, _, c1 = _ohlc(df, -3); o2, _, _, c2 = _ohlc(df, -2); o3, _, _, c3 = _ohlc(df, -1)
    return -1 if _is_bull(o1, c1) and _is_bear(o2, c2) and o2 > c1 and _is_bear(o3, c3) and c3 < c1 else 0

def _c_up_down_gap_three_methods(df): return _c_tasuki_gap(df)
def _c_downside_tasuki_gap(df):
    v = _c_tasuki_gap(df); return v if v == -1 else 0
def _c_upside_tasuki_gap(df):
    v = _c_tasuki_gap(df); return v if v == 1 else 0
def _c_side_by_side_white_lines(df): return _c_gap_side_by_side_white(df)


_CANDLE_DETECTORS: dict[str, Callable] = {
    "doji": _c_doji, "dragonfly_doji": _c_dragonfly_doji, "gravestone_doji": _c_gravestone_doji,
    "long_legged_doji": _c_long_legged_doji, "hammer": _c_hammer, "hanging_man": _c_hanging_man,
    "inverted_hammer": _c_inverted_hammer, "shooting_star": _c_shooting_star, "marubozu": _c_marubozu,
    "closing_marubozu": _c_closing_marubozu, "opening_marubozu": _c_opening_marubozu,
    "spinning_top": _c_spinning_top, "belt_hold": _c_belt_hold, "high_wave": _c_high_wave,
    "rickshaw_man": _c_rickshaw_man, "engulfing": _c_engulfing, "harami": _c_harami,
    "harami_cross": _c_harami_cross, "piercing": _c_piercing, "dark_cloud_cover": _c_dark_cloud_cover,
    "counterattack": _c_counterattack, "tweezer_top": _c_tweezer_top, "tweezer_bottom": _c_tweezer_bottom,
    "on_neck": _c_on_neck, "in_neck": _c_in_neck, "thrusting": _c_thrusting,
    "separating_lines": _c_separating_lines, "meeting_lines": _c_meeting_lines, "kicking": _c_kicking,
    "kicking_by_length": _c_kicking_by_length, "matching_low": _c_matching_low,
    "matching_high": _c_matching_high, "gap_side_by_side_white": _c_gap_side_by_side_white,
    "homing_pigeon": _c_homing_pigeon, "dojistar": _c_dojistar, "morning_star": _c_morning_star,
    "morning_doji_star": _c_morning_doji_star, "evening_star": _c_evening_star,
    "evening_doji_star": _c_evening_doji_star, "three_white_soldiers": _c_three_white_soldiers,
    "three_black_crows": _c_three_black_crows, "three_inside": _c_three_inside,
    "three_outside": _c_three_outside, "abandoned_baby": _c_abandoned_baby,
    "tasuki_gap": _c_tasuki_gap, "upside_gap_two_crows": _c_upside_gap_two_crows,
    "three_line_strike": _c_three_line_strike, "stick_sandwich": _c_stick_sandwich,
    "tristar": _c_tristar, "identical_three_crows": _c_identical_three_crows, "two_crows": _c_two_crows,
    "up_down_gap_three_methods": _c_up_down_gap_three_methods,
    "downside_tasuki_gap": _c_downside_tasuki_gap, "upside_tasuki_gap": _c_upside_tasuki_gap,
    "side_by_side_white_lines": _c_side_by_side_white_lines,
}


def detect_candle_pattern(df: pd.DataFrame, pattern_id: str) -> int:
    """최근 캔들에서 단일 패턴 감지. +1/−1/0 반환."""
    if len(df) < 5:
        return 0
    fn = _CANDLE_DETECTORS.get(pattern_id)
    if fn is None:
        return 0
    try:
        return int(fn(df))
    except Exception:
        return 0


def _candle_series(df: pd.DataFrame, fn: Callable) -> pd.Series:
    """캔들스틱 패턴 함수를 각 행에 롤링 적용해 +1/−1/0 Series 반환."""
    result = pd.Series(0.0, index=df.index)
    df_r = df.reset_index(drop=True)
    for i in range(4, len(df_r)):
        sub = df_r.iloc[max(0, i - 14):i + 1]
        try:
            result.iat[i] = float(fn(sub))
        except Exception:
            pass
    return result


def _mk(fn: Callable) -> Callable:
    def _impl(df): return _candle_series(df, fn)
    return _impl


# ──────────────────────────────────────────────────────────────
# 카탈로그
# ──────────────────────────────────────────────────────────────

# (key, label, category, description, params, fn)
_DEFS: list[tuple[str, str, str, str, list, Callable]] = [
    # 이동평균
    ("sma", "단순 이동평균 (SMA)", "이동평균", "종가의 N일 단순 평균", [_period(20, 2, 240)], sma),
    ("ema", "지수 이동평균 (EMA)", "이동평균", "최근 가격에 가중치를 둔 이동평균", [_period(20, 2, 240)], ema),
    ("wma", "가중 이동평균 (Wilder)", "이동평균", "Wilder 방식 가중 이동평균", [_period(14, 2, 240)], wma_wilder),
    ("lwma", "선형가중 이동평균 (LWMA)", "이동평균", "최근일에 선형 가중치", [_period(20, 2, 240)], lwma),
    ("hma", "헐 이동평균 (HMA)", "이동평균", "지연을 줄인 부드러운 이동평균", [_period(20, 4, 240)], hma),
    ("dema", "이중 지수 이동평균 (DEMA)", "이동평균", "EMA를 이중 적용해 지연 감소", [_period(20, 2, 240)], dema),
    ("tema", "삼중 지수 이동평균 (TEMA)", "이동평균", "EMA를 삼중 적용해 지연 감소", [_period(20, 2, 240)], tema),
    ("trima", "삼각 이동평균 (TRIMA)", "이동평균", "중앙에 가중치를 둔 이동평균", [_period(20, 2, 240)], trima),
    ("zlema", "제로 래그 EMA", "이동평균", "지연을 보정한 EMA", [_period(20, 2, 240)], zlema),
    ("t3", "T3 이동평균 (Tillson)", "이동평균",
     "여러 EMA를 조합한 부드러운 이동평균",
     [_period(20, 2, 240), _ip("vfactor", "볼륨 팩터", 0.7, 0.1, 1.0, 0.05, "float")], t3),
    ("kama", "카우프만 적응형 이동평균 (KAMA)", "이동평균", "변동성에 따라 민감도를 조절", [_period(20, 2, 240)], kama),
    ("alma", "ALMA (Arnaud Legoux)", "이동평균",
     "가우시안 가중 이동평균",
     [_period(20, 2, 240), _ip("sigma", "시그마", 6.0, 1.0, 12.0, 0.5, "float"),
      _ip("offset", "오프셋", 0.85, 0.0, 1.0, 0.05, "float")], alma),
    ("vidya", "VIDYA (가변 동적 평균)", "이동평균", "CMO 기반 적응형 이동평균", [_period(20, 2, 240)], vidya),
    ("frama", "프랙탈 적응형 이동평균 (FRAMA)", "이동평균", "프랙탈 차원으로 민감도 조절", [_period(20, 4, 240)], frama),
    ("vwma", "거래량 가중 이동평균 (VWMA)", "이동평균", "거래량으로 가중한 이동평균", [_period(20, 2, 240)], vwma),
    ("midpoint", "중간점 (Midpoint)", "이동평균", "기간 내 종가 (최고+최저)/2", [_period(14, 2, 240)], midpoint),
    ("midprice", "중간가격 (Midprice)", "이동평균", "기간 내 (고가최고+저가최저)/2", [_period(14, 2, 240)], midprice),

    # 추세
    ("macd", "MACD 라인", "추세",
     "단기 EMA - 장기 EMA",
     [_ip("fast", "단기", 12, 2, 100), _ip("slow", "장기", 26, 5, 200), _ip("signal", "시그널", 9, 2, 100)], macd_line),
    ("macd_signal", "MACD 시그널선", "추세",
     "MACD의 시그널 EMA",
     [_ip("fast", "단기", 12, 2, 100), _ip("slow", "장기", 26, 5, 200), _ip("signal", "시그널", 9, 2, 100)], macd_signal),
    ("macd_hist", "MACD 히스토그램", "추세",
     "MACD - 시그널",
     [_ip("fast", "단기", 12, 2, 100), _ip("slow", "장기", 26, 5, 200), _ip("signal", "시그널", 9, 2, 100)], macd_hist),
    ("di_plus", "+DI", "추세", "상승 방향 지표 (DMI)", [_period(14, 2, 100)], di_plus),
    ("di_minus", "-DI", "추세", "하락 방향 지표 (DMI)", [_period(14, 2, 100)], di_minus),
    ("adx", "ADX (추세 강도)", "추세", "추세의 강도 (25↑ 추세, 20↓ 횡보)", [_period(14, 2, 100)], adx),
    ("adxr", "ADXR", "추세", "ADX의 평활값", [_period(14, 2, 100)], adxr),
    ("aroon_up", "아룬 업 (Aroon Up)", "추세", "최근 고점까지의 경과 비율 (0~100)", [_period(25, 2, 200)], aroon_up),
    ("aroon_down", "아룬 다운 (Aroon Down)", "추세", "최근 저점까지의 경과 비율 (0~100)", [_period(25, 2, 200)], aroon_down),
    ("aroon_osc", "아룬 오실레이터", "추세", "Aroon Up - Aroon Down", [_period(25, 2, 200)], aroon_osc),
    ("supertrend", "슈퍼트렌드 방향", "추세",
     "추세 방향 (1=상승, -1=하락)",
     [_period(10, 2, 100), _ip("multiplier", "ATR 배수", 3.0, 1.0, 10.0, 0.5, "float")], supertrend_dir),
    ("sar", "파라볼릭 SAR", "추세",
     "추세 추종 손절선",
     [_ip("af_start", "AF 시작", 0.02, 0.01, 0.1, 0.01, "float"),
      _ip("af_max", "AF 최대", 0.2, 0.1, 0.5, 0.01, "float")], parabolic_sar),
    ("ichimoku_tenkan", "이치모쿠 전환선", "추세", "(9일 고가최고+저가최저)/2", [_period(9, 2, 100)], ichimoku_tenkan),
    ("ichimoku_kijun", "이치모쿠 기준선", "추세", "(26일 고가최고+저가최저)/2", [_period(26, 2, 200)], ichimoku_kijun),
    ("donchian_upper", "돈치안 채널 상단", "추세", "N일 최고가", [_period(20, 2, 240)], donchian_upper),
    ("donchian_lower", "돈치안 채널 하단", "추세", "N일 최저가", [_period(20, 2, 240)], donchian_lower),
    ("vortex_plus", "Vortex +", "추세", "상승 보텍스", [_period(14, 2, 100)], vortex_plus),
    ("vortex_minus", "Vortex -", "추세", "하락 보텍스", [_period(14, 2, 100)], vortex_minus),
    ("trix", "TRIX", "추세", "삼중 EMA의 변화율", [_period(15, 2, 100)], trix),
    ("dpo", "DPO (추세제거 오실레이터)", "추세", "추세를 제거한 가격 변동", [_period(20, 2, 200)], dpo),
    ("kst", "KST (Know Sure Thing)", "추세", "여러 ROC를 가중 합산한 모멘텀", [], kst),
    ("coppock", "코폭 커브", "추세", "장기 모멘텀 지표", [], coppock),
    ("mass_index", "Mass Index", "추세", "고저폭 EMA 비율의 합 (반전 신호)", [_period(25, 5, 100)], mass_index),
    ("schaff", "Schaff Trend Cycle", "추세", "MACD에 스토캐스틱을 적용 (0~100)", [_period(23, 5, 100)], schaff),
    ("chop", "Choppiness Index", "추세", "추세/횡보 판별 (61.8↑ 횡보, 38.2↓ 추세)", [_period(14, 2, 100)], chop),
    ("regression_slope", "선형회귀 기울기", "추세", "N일 종가 회귀선의 기울기", [_period(20, 2, 200)], regression_slope),
    ("regression_intercept", "선형회귀 절편", "추세", "N일 종가 회귀선의 절편", [_period(20, 2, 200)], regression_intercept),

    # 모멘텀 / 오실레이터
    ("rsi", "RSI", "모멘텀", "상대강도지수 (70↑ 과매수, 30↓ 과매도)", [_period(14, 2, 100)], rsi),
    ("stoch_rsi", "스토캐스틱 RSI", "모멘텀", "RSI에 스토캐스틱 적용 (0~100)", [_period(14, 2, 100)], stoch_rsi),
    ("stoch_k", "스토캐스틱 %K", "모멘텀", "기간 내 종가 위치 (0~100)", [_period(14, 2, 100)], stoch_k),
    ("stoch_d", "스토캐스틱 %D", "모멘텀",
     "%K의 이동평균",
     [_ip("k_period", "%K 기간", 14, 2, 100), _ip("d_period", "%D 기간", 3, 1, 50)], stoch_d),
    ("cci", "CCI", "모멘텀", "상품채널지수 (+100↑ 과매수, -100↓ 과매도)", [_period(20, 2, 100)], cci),
    ("williams_r", "윌리엄스 %R", "모멘텀", "기간 내 종가 위치 (-100~0)", [_period(14, 2, 100)], williams_r),
    ("mfi", "MFI (자금흐름지수)", "모멘텀", "거래량 가중 RSI (80↑ 과매수, 20↓ 과매도)", [_period(14, 2, 100)], mfi),
    ("roc", "ROC (변화율 %)", "모멘텀", "N일 전 대비 변화율 (%)", [_period(10, 1, 200)], roc),
    ("momentum", "모멘텀 (가격차)", "모멘텀", "현재가 - N일 전 가격", [_period(10, 1, 200)], momentum_diff),
    ("returns", "기간 수익률", "모멘텀", "N일 수익률 (소수, 0.05=5%)", [_period(20, 1, 240)], returns_ratio),
    ("disparity", "이격도", "모멘텀", "종가/SMA × 100 (100 기준)", [_period(20, 2, 240)], disparity),
    ("daily_change", "전일대비 등락률 (%)", "모멘텀", "전일 종가 대비 변화율 (%)", [], daily_change),
    ("cmo", "CMO (샹데 모멘텀)", "모멘텀", "찬데 모멘텀 오실레이터 (-100~100)", [_period(14, 2, 100)], cmo),
    ("apo", "APO (절대가격 오실레이터)", "모멘텀",
     "단기 EMA - 장기 EMA (절대값)",
     [_ip("fast", "단기", 12, 2, 100), _ip("slow", "장기", 26, 5, 200)], apo),
    ("ppo", "PPO (백분율 가격 오실레이터)", "모멘텀",
     "(단기 EMA - 장기 EMA)/장기 EMA × 100",
     [_ip("fast", "단기", 12, 2, 100), _ip("slow", "장기", 26, 5, 200)], ppo),
    ("ao", "어썸 오실레이터 (AO)", "모멘텀", "5일 - 34일 중간가격 SMA 차이", [], awesome_osc),
    ("ultosc", "궁극 오실레이터 (Ultimate)", "모멘텀",
     "3개 기간을 가중 합산 (0~100)",
     [_ip("p1", "단기", 7, 2, 50), _ip("p2", "중기", 14, 3, 100), _ip("p3", "장기", 28, 5, 200)], ultimate_osc),
    ("tsi", "TSI (참강도지수)", "모멘텀",
     "가격 변화의 이중 평활 비율",
     [_ip("long", "장기", 25, 2, 100), _ip("short", "단기", 13, 2, 100)], tsi),
    ("rvi", "RVI (상대활력지수)", "모멘텀", "종가-시가 vs 고가-저가 비율", [_period(10, 2, 100)], rvi),
    ("fisher", "Fisher Transform", "모멘텀", "가격을 정규분포화한 반전 지표", [_period(9, 2, 100)], fisher_transform),
    ("kvo", "Klinger 거래량 오실레이터", "모멘텀",
     "장단기 거래량 흐름 차이",
     [_ip("fast", "단기", 34, 2, 100), _ip("slow", "장기", 55, 5, 200)], klinger_osc),
    ("cho", "차이킨 오실레이터", "모멘텀",
     "ADL의 단기 EMA - 장기 EMA",
     [_ip("fast", "단기", 3, 2, 50), _ip("slow", "장기", 10, 3, 100)], chaikin_osc),
    ("bop", "BOP (매수/매도 파워)", "모멘텀", "(종가-시가)/(고가-저가)", [], bop),
    ("augen", "Augen 가격 스파이크", "모멘텀", "로그수익률의 표준화 값", [_period(14, 2, 100)], augen_spike),
    ("ibs", "IBS (종가 강도)", "모멘텀", "(종가-저가)/(고가-저가), 0~1", [], ibs),
    ("consecutive_up", "연속 상승일수", "모멘텀", "현재까지 연속 종가 상승 일수", [], consecutive_up),
    ("consecutive_down", "연속 하락일수", "모멘텀", "현재까지 연속 종가 하락 일수", [], consecutive_down),

    # 변동성
    ("atr", "ATR (평균실질변동폭)", "변동성", "Wilder ATR (변동성 크기)", [_period(14, 2, 100)], atr_value),
    ("natr", "NATR (정규화 ATR %)", "변동성", "ATR/종가 × 100", [_period(14, 2, 100)], natr),
    ("std", "표준편차", "변동성", "N일 종가 표준편차", [_period(20, 2, 240)], std_dev),
    ("variance", "분산", "변동성", "N일 종가 분산", [_period(20, 2, 240)], variance),
    ("volatility", "변동성 (수익률 표준편차)", "변동성", "일간 수익률의 N일 표준편차", [_period(10, 2, 240)], volatility),
    ("bb_upper", "볼린저밴드 상단", "변동성",
     "SMA + N×표준편차",
     [_period(20, 2, 240), _ip("std", "표준편차 배수", 2.0, 0.5, 4.0, 0.1, "float")], bb_upper),
    ("bb_middle", "볼린저밴드 중심선", "변동성", "N일 SMA", [_period(20, 2, 240)], bb_middle),
    ("bb_lower", "볼린저밴드 하단", "변동성",
     "SMA - N×표준편차",
     [_period(20, 2, 240), _ip("std", "표준편차 배수", 2.0, 0.5, 4.0, 0.1, "float")], bb_lower),
    ("bb_width", "볼린저밴드 폭", "변동성",
     "상단 - 하단 (밴드 수축/확장)",
     [_period(20, 2, 240), _ip("std", "표준편차 배수", 2.0, 0.5, 4.0, 0.1, "float")], bb_width),
    ("bb_percent", "볼린저밴드 %B", "변동성",
     "밴드 내 종가 위치 (0=하단, 1=상단)",
     [_period(20, 2, 240), _ip("std", "표준편차 배수", 2.0, 0.5, 4.0, 0.1, "float")], bb_percent),
    ("keltner_upper", "켈트너 채널 상단", "변동성",
     "EMA + ATR×배수",
     [_ip("ema_period", "EMA 기간", 20, 2, 200), _ip("atr_period", "ATR 기간", 10, 2, 100),
      _ip("multiplier", "ATR 배수", 2.0, 0.5, 5.0, 0.1, "float")], keltner_upper),
    ("keltner_lower", "켈트너 채널 하단", "변동성",
     "EMA - ATR×배수",
     [_ip("ema_period", "EMA 기간", 20, 2, 200), _ip("atr_period", "ATR 기간", 10, 2, 100),
      _ip("multiplier", "ATR 배수", 2.0, 0.5, 5.0, 0.1, "float")], keltner_lower),
    ("accbands_upper", "가속밴드 상단", "변동성", "고가 기반 가속 밴드 상단", [_period(20, 2, 200)], accbands_upper),
    ("accbands_lower", "가속밴드 하단", "변동성", "저가 기반 가속 밴드 하단", [_period(20, 2, 200)], accbands_lower),

    # 거래량
    ("obv", "OBV (누적거래량)", "거래량", "상승/하락에 따른 거래량 누적", [], obv),
    ("volume_ma", "거래량 이동평균", "거래량", "거래량의 N일 SMA", [_period(20, 2, 240)], volume_ma),
    ("vwap", "VWAP (거래량가중평균가)", "거래량", "누적 거래량 가중 평균가", [], vwap),
    ("ad", "축적/분배 (A/D, 단일봉)", "거래량", "단일 봉의 자금 흐름량", [], ad),
    ("adl", "축적/분배선 (ADL)", "거래량", "A/D의 누적합", [], adl),
    ("cmf", "차이킨 자금흐름 (CMF)", "거래량", "N일 자금 흐름 비율 (-1~1)", [_period(20, 2, 100)], cmf),
    ("force", "Force Index", "거래량", "가격 변화 × 거래량의 EMA", [_period(13, 2, 100)], force_index),
    ("eom", "Ease of Movement", "거래량", "가격 이동의 용이성", [_period(14, 2, 100)], ease_of_movement),
    ("vpt", "Volume Price Trend (VPT)", "거래량", "수익률 × 거래량의 누적합", [], vol_price_trend),

    # 가격 / 기타
    ("highest_high", "N일 최고가", "가격", "최근 N일 고가의 최대값", [_period(20, 2, 504)], highest_high),
    ("lowest_low", "N일 최저가", "가격", "최근 N일 저가의 최소값", [_period(20, 2, 504)], lowest_low),
    ("highest_close", "N일 최고 종가", "가격", "최근 N일 종가의 최대값", [_period(20, 2, 504)], highest_close),
    ("lowest_close", "N일 최저 종가", "가격", "최근 N일 종가의 최소값", [_period(20, 2, 504)], lowest_close),
    ("typical_price", "대표가격 (HLC/3)", "가격", "(고가+저가+종가)/3", [], typical_price),
    ("median_price", "중앙가격 (HL/2)", "가격", "(고가+저가)/2", [], median_price),
    ("pivot", "피봇 포인트", "가격", "(고가+저가+종가)/3", [], typical_price),
    ("log_return", "로그 수익률", "가격", "ln(종가 / 전일 종가)", [], log_return),

    # 캔들스틱 패턴 (단일봉 15)
    ("doji", "도지", "캔들스틱", "우유부단 (시가≒종가)", [], _mk(_c_doji)),
    ("dragonfly_doji", "잠자리 도지", "캔들스틱", "긴 아래꼬리, 상승 반전", [], _mk(_c_dragonfly_doji)),
    ("gravestone_doji", "비석 도지", "캔들스틱", "긴 위꼬리, 하락 반전", [], _mk(_c_gravestone_doji)),
    ("long_legged_doji", "긴다리 도지", "캔들스틱", "극심한 우유부단 (위아래 꼬리 모두 김)", [], _mk(_c_long_legged_doji)),
    ("hammer", "망치형", "캔들스틱", "긴 아래꼬리, 상승 반전 신호", [], _mk(_c_hammer)),
    ("hanging_man", "교수형", "캔들스틱", "긴 아래꼬리, 하락 반전 신호", [], _mk(_c_hanging_man)),
    ("inverted_hammer", "역망치형", "캔들스틱", "긴 위꼬리, 상승 반전 신호", [], _mk(_c_inverted_hammer)),
    ("shooting_star", "유성형", "캔들스틱", "긴 위꼬리, 하락 반전 신호", [], _mk(_c_shooting_star)),
    ("marubozu", "장대봉", "캔들스틱", "꼬리 없는 강한 추세봉 (상승/하락)", [], _mk(_c_marubozu)),
    ("closing_marubozu", "종가 장대봉", "캔들스틱", "종가가 고점/저점인 장대봉", [], _mk(_c_closing_marubozu)),
    ("opening_marubozu", "시가 장대봉", "캔들스틱", "시가가 고점/저점인 장대봉", [], _mk(_c_opening_marubozu)),
    ("spinning_top", "팽이형", "캔들스틱", "몸통 작고 위아래 꼬리가 긴 우유부단", [], _mk(_c_spinning_top)),
    ("belt_hold", "띠 잡기", "캔들스틱", "한쪽 꼬리 없는 강한 추세 시작봉", [], _mk(_c_belt_hold)),
    ("high_wave", "큰 파도", "캔들스틱", "작은 몸통 + 매우 긴 위아래 꼬리", [], _mk(_c_high_wave)),
    ("rickshaw_man", "인력거꾼", "캔들스틱", "긴다리 도지 변형", [], _mk(_c_rickshaw_man)),

    # 캔들스틱 패턴 (두봉 20)
    ("engulfing", "장악형", "캔들스틱", "전봉을 완전히 감싸는 강한 반전", [], _mk(_c_engulfing)),
    ("harami", "잉태형", "캔들스틱", "전봉 안에 포함된 작은 봉 (추세 약화)", [], _mk(_c_harami)),
    ("harami_cross", "잉태 십자형", "캔들스틱", "잉태형 + 도지 (강한 추세 약화)", [], _mk(_c_harami_cross)),
    ("piercing", "관통형", "캔들스틱", "하락 후 전봉 중간 이상 상승 (상승 반전)", [], _mk(_c_piercing)),
    ("dark_cloud_cover", "먹구름형", "캔들스틱", "상승 후 전봉 중간 이하 하락 (하락 반전)", [], _mk(_c_dark_cloud_cover)),
    ("counterattack", "반격형", "캔들스틱", "전봉 종가와 같은 종가로 반격", [], _mk(_c_counterattack)),
    ("tweezer_top", "집게 천장", "캔들스틱", "두 봉의 고점이 같은 하락 반전", [], _mk(_c_tweezer_top)),
    ("tweezer_bottom", "집게 바닥", "캔들스틱", "두 봉의 저점이 같은 상승 반전", [], _mk(_c_tweezer_bottom)),
    ("on_neck", "목 위형", "캔들스틱", "하락봉 저가 부근 종가 (하락 지속)", [], _mk(_c_on_neck)),
    ("in_neck", "목 안형", "캔들스틱", "하락봉 종가 부근 종가 (하락 지속)", [], _mk(_c_in_neck)),
    ("thrusting", "밀어붙이기", "캔들스틱", "하락봉 중간 미만 상승 (하락 지속)", [], _mk(_c_thrusting)),
    ("separating_lines", "분리선", "캔들스틱", "시가 같고 방향 반대 (추세 지속)", [], _mk(_c_separating_lines)),
    ("meeting_lines", "만남선", "캔들스틱", "종가 같고 방향 반대 (추세 반전)", [], _mk(_c_meeting_lines)),
    ("kicking", "킥킹", "캔들스틱", "마루보주 갭 반전 (강한 방향 전환)", [], _mk(_c_kicking)),
    ("kicking_by_length", "길이 기준 킥킹", "캔들스틱", "킥킹 (길이 기준 변형)", [], _mk(_c_kicking_by_length)),
    ("matching_low", "일치 저가", "캔들스틱", "두 하락봉의 종가 같음 (상승 반전)", [], _mk(_c_matching_low)),
    ("matching_high", "일치 고가", "캔들스틱", "두 상승봉의 종가 같음 (하락 반전)", [], _mk(_c_matching_high)),
    ("gap_side_by_side_white", "갭 나란히 양봉", "캔들스틱", "갭업 후 비슷한 양봉 (상승 지속)", [], _mk(_c_gap_side_by_side_white)),
    ("homing_pigeon", "귀소비둘기", "캔들스틱", "큰 음봉 안의 작은 음봉 (상승 반전)", [], _mk(_c_homing_pigeon)),
    ("dojistar", "도지별", "캔들스틱", "갭 후 도지 (추세 반전 경고)", [], _mk(_c_dojistar)),

    # 캔들스틱 패턴 (삼봉+ 30)
    ("morning_star", "샛별형", "캔들스틱", "하락→소봉→상승, 강한 상승 반전", [], _mk(_c_morning_star)),
    ("morning_doji_star", "샛별 도지", "캔들스틱", "하락→도지→상승, 강한 상승 반전", [], _mk(_c_morning_doji_star)),
    ("evening_star", "저녁별형", "캔들스틱", "상승→소봉→하락, 강한 하락 반전", [], _mk(_c_evening_star)),
    ("evening_doji_star", "저녁별 도지", "캔들스틱", "상승→도지→하락, 강한 하락 반전", [], _mk(_c_evening_doji_star)),
    ("three_white_soldiers", "적삼병", "캔들스틱", "연속 3 상승봉, 강한 상승 추세", [], _mk(_c_three_white_soldiers)),
    ("three_black_crows", "흑삼병", "캔들스틱", "연속 3 하락봉, 강한 하락 추세", [], _mk(_c_three_black_crows)),
    ("three_inside", "삼내형", "캔들스틱", "잉태형 + 확인봉 (추세 반전 확인)", [], _mk(_c_three_inside)),
    ("three_outside", "삼외형", "캔들스틱", "장악형 + 확인봉 (강한 추세 반전)", [], _mk(_c_three_outside)),
    ("abandoned_baby", "버려진 아기", "캔들스틱", "갭 도지로 완전 고립 (강한 반전)", [], _mk(_c_abandoned_baby)),
    ("tasuki_gap", "타스키 갭", "캔들스틱", "갭 후 반대봉 (추세 지속)", [], _mk(_c_tasuki_gap)),
    ("upside_gap_two_crows", "갭업 두 까마귀", "캔들스틱", "갭업 후 두 하락봉 (하락 반전)", [], _mk(_c_upside_gap_two_crows)),
    ("three_line_strike", "삼선 타격", "캔들스틱", "3봉 추세 후 역방향 대봉 (반전)", [], _mk(_c_three_line_strike)),
    ("stick_sandwich", "스틱 샌드위치", "캔들스틱", "음봉-양봉-음봉 같은 저가 (상승 반전)", [], _mk(_c_stick_sandwich)),
    ("tristar", "삼성형", "캔들스틱", "3 도지 패턴 (강한 반전)", [], _mk(_c_tristar)),
    ("identical_three_crows", "동일 흑삼병", "캔들스틱", "전봉 종가에서 시작하는 흑삼병", [], _mk(_c_identical_three_crows)),
    ("two_crows", "두 까마귀", "캔들스틱", "갭업 후 두 음봉 (하락 반전)", [], _mk(_c_two_crows)),
    ("up_down_gap_three_methods", "갭 삼법", "캔들스틱", "갭 방향 삼법 (추세 지속)", [], _mk(_c_up_down_gap_three_methods)),
    ("downside_tasuki_gap", "하락 타스키 갭", "캔들스틱", "하락 갭 후 상승봉 (하락 지속)", [], _mk(_c_downside_tasuki_gap)),
    ("upside_tasuki_gap", "상승 타스키 갭", "캔들스틱", "상승 갭 후 하락봉 (상승 지속)", [], _mk(_c_upside_tasuki_gap)),
    ("side_by_side_white_lines", "나란히 양봉선", "캔들스틱", "갭 후 나란한 두 양봉 (상승 지속)", [], _mk(_c_side_by_side_white_lines)),
]


INDICATOR_CATALOG: dict[str, dict[str, Any]] = {
    key: {"key": key, "label": label, "category": category,
          "description": description, "params": params, "fn": fn}
    for (key, label, category, description, params, fn) in _DEFS
}


def list_indicators() -> list[dict[str, Any]]:
    """프런트엔드 "지표 추가" 목록 (함수 객체 제외)."""
    return [
        {"key": v["key"], "label": v["label"], "category": v["category"],
         "description": v["description"], "params": v["params"]}
        for v in INDICATOR_CATALOG.values()
    ]


def coerce_params(key: str, raw: dict | None) -> dict:
    """카탈로그 스펙에 맞춰 파라미터를 형변환/클리핑한다."""
    spec = INDICATOR_CATALOG.get(key)
    if spec is None:
        raise KeyError(f"알 수 없는 지표: {key}")
    raw = raw or {}
    out: dict[str, Any] = {}
    for p in spec["params"]:
        v = raw.get(p["name"], p["default"])
        try:
            v = int(v) if p["type"] == "int" else float(v)
        except (TypeError, ValueError):
            v = p["default"]
        v = max(p["min"], min(p["max"], v))
        out[p["name"]] = v
    return out


def compute_indicator(df: pd.DataFrame, key: str, params: dict | None = None) -> pd.Series:
    """카탈로그 지표를 계산해 df.index에 정렬된 Series를 반환."""
    spec = INDICATOR_CATALOG.get(key)
    if spec is None:
        raise KeyError(f"알 수 없는 지표: {key}")
    clean = coerce_params(key, params)
    result = spec["fn"](df, **clean)
    if not isinstance(result, pd.Series):
        result = pd.Series(result, index=df.index)
    return result.reindex(df.index).astype(float)
