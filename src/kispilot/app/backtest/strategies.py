import numpy as np
import pandas as pd


# ── 지표 헬퍼 ─────────────────────────────────────────────────

def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_up = up.ewm(alpha=1 / period, adjust=False).mean()
    avg_down = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_up / avg_down.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.fillna(50)


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder smoothing)."""
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def _ibs(df: pd.DataFrame) -> pd.Series:
    """Internal Bar Strength: (close - low) / (high - low). 분모 0이면 0.5."""
    high = df['high'].astype(float)
    low = df['low'].astype(float)
    close = df['close'].astype(float)
    rng = (high - low).replace(0, np.nan)
    ibs = (close - low) / rng
    return ibs.fillna(0.5)


def _consecutive_streak(mask: pd.Series) -> pd.Series:
    """True가 연속된 길이를 반환. 예: [T,T,T,F,T,T] → [1,2,3,0,1,2]."""
    m = mask.astype(bool).astype(int)
    grp = (m != m.shift()).cumsum()
    streak = m.groupby(grp).cumcount() + 1
    return streak * m


# ── 전략 함수 ─────────────────────────────────────────────────

def sma_crossover(df: pd.DataFrame, short: int = 5, long: int = 20) -> pd.Series:
    short = int(short)
    long = int(long)
    close = df['close'].astype(float)
    s = close.rolling(short).mean()
    l = close.rolling(long).mean()
    cross_up = (s > l) & (s.shift(1) <= l.shift(1))
    cross_dn = (s < l) & (s.shift(1) >= l.shift(1))
    sig = pd.Series(0, index=df.index)
    sig[cross_up] = 1
    sig[cross_dn] = -1
    return sig


def momentum(df: pd.DataFrame, lookback: int = 20, threshold: float = 0.05) -> pd.Series:
    lookback = int(lookback)
    close = df['close'].astype(float)
    ret = close.pct_change(lookback, fill_method=None)
    sig = pd.Series(0, index=df.index)
    sig[ret > threshold] = 1
    sig[ret < 0] = -1
    sig = sig.where(sig != sig.shift(1), 0)
    return sig.fillna(0).astype(int)


def rsi_mean_reversion(df: pd.DataFrame, period: int = 14,
                       oversold: float = 30, overbought: float = 70) -> pd.Series:
    period = int(period)
    rsi = _rsi(df['close'].astype(float), period)
    sig = pd.Series(0, index=df.index)
    sig[(rsi < oversold) & (rsi.shift(1) >= oversold)] = 1
    sig[(rsi > overbought) & (rsi.shift(1) <= overbought)] = -1
    return sig


def week52_high(df: pd.DataFrame, lookback: int = 252) -> pd.Series:
    """종가가 N일 최고가를 상향 돌파하면 매수. 청산은 손절/익절에 의존."""
    lookback = int(lookback)
    close = df['close'].astype(float)
    # 직전까지의 N일 최고가 (오늘은 제외)
    prev_max = close.shift(1).rolling(lookback).max()
    cross_up = (close > prev_max) & (close.shift(1) <= prev_max.shift(1))
    sig = pd.Series(0, index=df.index)
    sig[cross_up] = 1
    return sig


def consecutive_moves(df: pd.DataFrame, up_days: int = 5, down_days: int = 5) -> pd.Series:
    """N일 연속 종가 상승 시 매수, M일 연속 하락 시 매도."""
    up_days = int(up_days)
    down_days = int(down_days)
    close = df['close'].astype(float)
    up = close > close.shift(1)
    down = close < close.shift(1)
    streak_up = _consecutive_streak(up)
    streak_dn = _consecutive_streak(down)
    sig = pd.Series(0, index=df.index)
    sig[streak_up == up_days] = 1
    sig[streak_dn == down_days] = -1
    return sig


def ma_divergence(df: pd.DataFrame, period: int = 20,
                  buy_ratio: float = 0.9, sell_ratio: float = 1.1) -> pd.Series:
    """이격도(close/SMA)가 buy_ratio 이하면 매수, sell_ratio 이상이면 매도."""
    period = int(period)
    close = df['close'].astype(float)
    ma = close.rolling(period).mean()
    ratio = close / ma
    buy = (ratio < buy_ratio) & (ratio.shift(1) >= buy_ratio)
    sell = (ratio > sell_ratio) & (ratio.shift(1) <= sell_ratio)
    sig = pd.Series(0, index=df.index)
    sig[buy] = 1
    sig[sell] = -1
    return sig


def false_breakout(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
    """N일 고점 돌파 시 매수, 이후 다시 고점 아래로 이탈하면 매도 (단순화 버전)."""
    lookback = int(lookback)
    close = df['close'].astype(float)
    prev_high = close.shift(1).rolling(lookback).max()
    breakout = (close > prev_high) & (close.shift(1) <= prev_high.shift(1))
    fall_back = (close < prev_high) & (close.shift(1) >= prev_high.shift(1))
    sig = pd.Series(0, index=df.index)
    sig[breakout] = 1
    sig[fall_back] = -1
    return sig


def strong_close(df: pd.DataFrame, min_close_ratio: float = 0.8) -> pd.Series:
    """IBS >= min_close_ratio일 때 매수, IBS < (1 - min_close_ratio)일 때 매도."""
    ibs = _ibs(df)
    exit_threshold = 1 - min_close_ratio
    sig = pd.Series(0, index=df.index)
    sig[(ibs >= min_close_ratio) & (ibs.shift(1) < min_close_ratio)] = 1
    sig[(ibs < exit_threshold) & (ibs.shift(1) >= exit_threshold)] = -1
    return sig


def volatility_breakout(df: pd.DataFrame, atr_period: int = 10,
                        lookback: int = 20, breakout_pct: float = 3.0) -> pd.Series:
    """ATR이 ATR의 SMA보다 작은 변동성 축소 구간에서 ROC(1)>임계% 돌파 시 매수, ROC(1)<-임계% 시 매도."""
    atr_period = int(atr_period)
    lookback = int(lookback)
    close = df['close'].astype(float)
    atr = _atr(df, atr_period)
    atr_ma = atr.rolling(lookback).mean()
    daily_return = close.pct_change(fill_method=None) * 100
    squeeze = atr < atr_ma
    sig = pd.Series(0, index=df.index)
    sig[squeeze & (daily_return > breakout_pct)] = 1
    sig[daily_return < -breakout_pct] = -1
    return sig


def short_term_reversal(df: pd.DataFrame, period: int = 5,
                        threshold_pct: float = 3.0) -> pd.Series:
    """close < SMA(period)*(1-threshold%) 매수, close > SMA(period)*(1+threshold%) 매도."""
    period = int(period)
    close = df['close'].astype(float)
    ma = close.rolling(period).mean()
    buy_band = ma * (1 - threshold_pct / 100)
    sell_band = ma * (1 + threshold_pct / 100)
    buy = (close < buy_band) & (close.shift(1) >= buy_band.shift(1))
    sell = (close > sell_band) & (close.shift(1) <= sell_band.shift(1))
    sig = pd.Series(0, index=df.index)
    sig[buy] = 1
    sig[sell] = -1
    return sig


def trend_filter_signal(df: pd.DataFrame, trend_period: int = 60) -> pd.Series:
    """close > SMA(trend) AND ROC(1) > 0 매수, close < SMA(trend) AND ROC(1) < 0 매도."""
    trend_period = int(trend_period)
    close = df['close'].astype(float)
    trend = close.rolling(trend_period).mean()
    daily_return = close.pct_change(fill_method=None)
    entry = ((close > trend) & (daily_return > 0)).fillna(False).astype(bool)
    exit_ = ((close < trend) & (daily_return < 0)).fillna(False).astype(bool)
    # 상태 변화 시점에만 시그널 (연속 발화 방지)
    entry_edge = entry & ~entry.shift(1, fill_value=False)
    exit_edge = exit_ & ~exit_.shift(1, fill_value=False)
    sig = pd.Series(0, index=df.index)
    sig[entry_edge] = 1
    sig[exit_edge] = -1
    return sig


# ── 전략 카탈로그 ──────────────────────────────────────────────

STRATEGIES = {
    "sma_crossover": {
        "label": "SMA 골든/데드크로스",
        "category": "trend",
        "description": "단기 이동평균이 장기 이동평균을 상향 돌파하면 매수, 하향 돌파하면 매도.",
        "fn": sma_crossover,
        "params": [
            {"name": "short", "label": "단기 이평 (일)", "default": 5, "min": 2, "max": 60, "step": 1, "type": "int"},
            {"name": "long",  "label": "장기 이평 (일)", "default": 20, "min": 5, "max": 240, "step": 1, "type": "int"},
        ],
    },
    "momentum": {
        "label": "모멘텀",
        "category": "momentum",
        "description": "최근 N일 수익률이 임계치를 넘으면 매수, 0 미만이면 매도.",
        "fn": momentum,
        "params": [
            {"name": "lookback",  "label": "기간 (일)",   "default": 20,   "min": 5,    "max": 120,  "step": 1,    "type": "int"},
            {"name": "threshold", "label": "매수 임계 수익률", "default": 0.05, "min": 0.01, "max": 0.30, "step": 0.01, "type": "float"},
        ],
    },
    "rsi_mean_reversion": {
        "label": "RSI 평균회귀",
        "category": "mean_reversion",
        "description": "RSI가 과매도(기본 30) 아래로 진입하면 매수, 과매수(기본 70) 위로 돌파하면 매도.",
        "fn": rsi_mean_reversion,
        "params": [
            {"name": "period",     "label": "RSI 기간 (일)", "default": 14, "min": 5,  "max": 50, "step": 1, "type": "int"},
            {"name": "oversold",   "label": "과매도 임계",   "default": 30, "min": 10, "max": 40, "step": 1, "type": "float"},
            {"name": "overbought", "label": "과매수 임계",   "default": 70, "min": 60, "max": 90, "step": 1, "type": "float"},
        ],
    },
    "week52_high": {
        "label": "52주 신고가 돌파",
        "category": "trend",
        "description": "종가가 N일(기본 252=52주) 최고가를 돌파하면 매수. 손절·익절로 청산.",
        "fn": week52_high,
        "params": [
            {"name": "lookback", "label": "최고가 기간 (일)", "default": 252, "min": 60, "max": 504, "step": 1, "type": "int"},
        ],
        "default_risk": {"stop_loss_pct": 5.0, "take_profit_pct": 15.0},
    },
    "consecutive_moves": {
        "label": "연속 상승·하락",
        "category": "momentum",
        "description": "N일 연속 종가 상승 시 매수, M일 연속 하락 시 매도.",
        "fn": consecutive_moves,
        "params": [
            {"name": "up_days",   "label": "연속 상승일", "default": 5, "min": 2, "max": 10, "step": 1, "type": "int"},
            {"name": "down_days", "label": "연속 하락일", "default": 5, "min": 2, "max": 10, "step": 1, "type": "int"},
        ],
        "default_risk": {"stop_loss_pct": 5.0},
    },
    "ma_divergence": {
        "label": "이동평균 이격도",
        "category": "mean_reversion",
        "description": "종가/SMA 비율이 매수 임계 이하면 매수, 매도 임계 이상이면 매도.",
        "fn": ma_divergence,
        "params": [
            {"name": "period",     "label": "이평 기간 (일)", "default": 20,  "min": 10,   "max": 60,   "step": 1,   "type": "int"},
            {"name": "buy_ratio",  "label": "매수 이격도",    "default": 0.9, "min": 0.8,  "max": 0.95, "step": 0.01, "type": "float"},
            {"name": "sell_ratio", "label": "매도 이격도",    "default": 1.1, "min": 1.05, "max": 1.2,  "step": 0.01, "type": "float"},
        ],
    },
    "false_breakout": {
        "label": "추세 돌파 후 이탈",
        "category": "trend",
        "description": "N일 고점 돌파 시 매수, 다시 고점 아래로 이탈하면 매도.",
        "fn": false_breakout,
        "params": [
            {"name": "lookback", "label": "전고점 기간 (일)", "default": 20, "min": 10, "max": 60, "step": 1, "type": "int"},
        ],
        "default_risk": {"stop_loss_pct": 3.0},
    },
    "strong_close": {
        "label": "강한 종가",
        "category": "momentum",
        "description": "종가가 당일 범위의 상위 구간(IBS≥기준)에 위치할 때 매수, 하위 구간으로 떨어지면 매도.",
        "fn": strong_close,
        "params": [
            {"name": "min_close_ratio", "label": "최소 종가 비율 (IBS)", "default": 0.8, "min": 0.5, "max": 0.99, "step": 0.01, "type": "float"},
        ],
        "default_risk": {"stop_loss_pct": 5.0},
    },
    "volatility_breakout": {
        "label": "변동성 축소 후 확장",
        "category": "volatility",
        "description": "ATR이 평균 이하로 축소된 상태에서 일중 수익률이 임계% 돌파 시 매수, 급락 시 매도.",
        "fn": volatility_breakout,
        "params": [
            {"name": "atr_period",   "label": "ATR 기간 (일)",   "default": 10,  "min": 5,   "max": 20,  "step": 1,   "type": "int"},
            {"name": "lookback",     "label": "변동성 비교 기간", "default": 20,  "min": 10,  "max": 60,  "step": 1,   "type": "int"},
            {"name": "breakout_pct", "label": "돌파 기준 %",     "default": 3.0, "min": 1.0, "max": 10.0,"step": 0.1, "type": "float"},
        ],
        "default_risk": {"stop_loss_pct": 5.0},
    },
    "short_term_reversal": {
        "label": "단기 반전",
        "category": "mean_reversion",
        "description": "종가가 N일 평균보다 M% 이상 낮으면 매수, M% 이상 높으면 매도.",
        "fn": short_term_reversal,
        "params": [
            {"name": "period",        "label": "평균 기간 (일)", "default": 5,   "min": 3,   "max": 20,   "step": 1,   "type": "int"},
            {"name": "threshold_pct", "label": "이격 임계 %",    "default": 3.0, "min": 1.0, "max": 10.0, "step": 0.1, "type": "float"},
        ],
        "default_risk": {"stop_loss_pct": 5.0},
    },
    "trend_filter_signal": {
        "label": "추세 필터 + 시그널",
        "category": "composite",
        "description": "추세선 위에서 전일 대비 상승 시 매수, 추세선 아래에서 하락 시 매도.",
        "fn": trend_filter_signal,
        "params": [
            {"name": "trend_period", "label": "추세 MA 기간 (일)", "default": 60, "min": 20, "max": 200, "step": 1, "type": "int"},
        ],
        "default_risk": {"stop_loss_pct": 5.0, "take_profit_pct": 10.0},
    },
}
