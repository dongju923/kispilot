import math
import numpy as np
import pandas as pd


def _safe(v):
    if v is None: return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): return None
    return v


def compute_metrics(equity: pd.Series, trades: list, benchmark: pd.DataFrame | None = None) -> dict:
    """자산곡선 + 거래내역 + (선택) 벤치마크 → 성과 지표 dict."""
    if len(equity) < 2:
        return {
            "total_return": 0.0, "cagr": 0.0, "max_drawdown": 0.0, "sharpe": 0.0,
            "total_trades": 0, "win_rate": 0.0, "avg_win": 0.0, "avg_loss": 0.0,
            "profit_factor": 0.0, "benchmark_return": None,
        }

    eq = equity.astype(float)
    total_return = (eq.iloc[-1] / eq.iloc[0] - 1) * 100

    try:
        days = (pd.to_datetime(eq.index[-1]) - pd.to_datetime(eq.index[0])).days
        years = max(days / 365.25, 1e-9)
        cagr = ((eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1) * 100
    except Exception:
        cagr = 0.0

    cummax = eq.cummax()
    dd = (eq / cummax - 1) * 100
    max_drawdown = float(dd.min())

    daily_ret = eq.pct_change().dropna()
    if len(daily_ret) > 1 and daily_ret.std() > 0:
        sharpe = float(daily_ret.mean() / daily_ret.std() * math.sqrt(252))
    else:
        sharpe = 0.0

    total_trades = len(trades)
    if total_trades > 0:
        pnls = [t["pnl"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        win_rate = len(wins) / total_trades * 100
        avg_win = (sum(wins) / len(wins)) if wins else 0.0
        avg_loss = (sum(losses) / len(losses)) if losses else 0.0
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)
    else:
        win_rate = avg_win = avg_loss = profit_factor = 0.0

    benchmark_return = None
    if benchmark is not None and len(benchmark) >= 2:
        try:
            b = benchmark.set_index('date')['close'].astype(float)
            b = b.reindex(eq.index, method='ffill').dropna()
            if len(b) >= 2:
                benchmark_return = float((b.iloc[-1] / b.iloc[0] - 1) * 100)
        except Exception:
            pass

    return {
        "total_return": _safe(round(float(total_return), 2)),
        "cagr": _safe(round(float(cagr), 2)),
        "max_drawdown": _safe(round(max_drawdown, 2)),
        "sharpe": _safe(round(sharpe, 3)),
        "total_trades": int(total_trades),
        "win_rate": _safe(round(float(win_rate), 2)),
        "avg_win": _safe(round(float(avg_win), 0)),
        "avg_loss": _safe(round(float(avg_loss), 0)),
        "profit_factor": _safe(round(float(profit_factor), 2)) if profit_factor != float('inf') else None,
        "benchmark_return": _safe(round(benchmark_return, 2)) if benchmark_return is not None else None,
    }
