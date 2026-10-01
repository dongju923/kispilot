from dataclasses import dataclass, field
import pandas as pd


@dataclass
class BacktestResult:
    equity: pd.Series
    trades: list = field(default_factory=list)
    initial_capital: float = 0.0
    final_capital: float = 0.0


def _close_position(
    shares: int,
    entry_price: float,
    entry_date,
    exit_price: float,
    exit_date,
    commission: float,
    tax: float,
    exit_reason: str,
) -> tuple[float, dict]:
    proceeds = shares * exit_price * (1 - commission - tax)
    cost_basis = shares * entry_price * (1 + commission)
    pnl = proceeds - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0.0
    trade = {
        "entry_date": entry_date,
        "exit_date": exit_date,
        "entry_price": round(entry_price, 2),
        "exit_price": round(exit_price, 2),
        "qty": shares,
        "pnl": round(pnl, 0),
        "pnl_pct": round(pnl_pct, 2),
        "exit_reason": exit_reason,
    }
    return proceeds, trade


def run_backtest(
    df: pd.DataFrame,
    signals: pd.Series,
    initial_capital: float = 10_000_000,
    commission: float = 0.00015,
    tax: float = 0.002,
    slippage: float = 0.0,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    trailing_stop_pct: float | None = None,
) -> BacktestResult:
    """단일 종목 풀포지션 시뮬레이터.

    매매 규칙:
        - signal=1 → 다음봉 시가 전량 매수
        - signal=-1 → 다음봉 시가 전량 매도
        - stop_loss_pct / take_profit_pct / trailing_stop_pct 가 설정된 경우 보유 중인 봉마다 검사:
            손절가      = 진입가 × (1 - stop_loss_pct/100)
            트레일링가  = (진입 이후 최고가) × (1 - trailing_stop_pct/100)
            유효 손절가 = max(손절가, 트레일링가)  ← 더 높은 쪽이 먼저 걸린다
            익절가      = 진입가 × (1 + take_profit_pct/100)
            오늘 low  <= 유효 손절가 → 그 가격에 매도
            오늘 high >= 익절가      → 그 가격에 매도
            (체결 우선순위: 손절/트레일링 > 익절 > 시그널)
    수수료는 매수/매도 양쪽에 적용, 세금은 매도에만 적용. 손절/익절 체결가는 슬리피지/세금 적용.
    """
    df = df.reset_index(drop=True)
    n = len(df)
    if n < 2 or len(signals) != n:
        eq = pd.Series([initial_capital] * max(n, 1),
                       index=df['date'] if 'date' in df else range(max(n, 1)))
        return BacktestResult(equity=eq, trades=[], initial_capital=initial_capital,
                              final_capital=initial_capital)

    sig = signals.fillna(0).astype(int).values
    opens = df['open'].astype(float).values
    highs = df['high'].astype(float).values
    lows = df['low'].astype(float).values
    closes = df['close'].astype(float).values
    dates = df['date'].astype(str).values

    has_risk = (stop_loss_pct is not None or take_profit_pct is not None
                or trailing_stop_pct is not None)

    cash = float(initial_capital)
    shares = 0
    entry_price = 0.0
    entry_date = None
    peak_price = 0.0          # 진입 이후(진입봉 포함) 최고가 — 트레일링 스탑용
    trades = []
    equity = [cash]

    for i in range(1, n):
        # 1) 보유 중이면 손절/익절/트레일링 우선 검사
        if shares > 0 and has_risk:
            sl_price = entry_price * (1 - stop_loss_pct / 100) if stop_loss_pct else None
            trail_price = peak_price * (1 - trailing_stop_pct / 100) if trailing_stop_pct else None
            tp_price = entry_price * (1 + take_profit_pct / 100) if take_profit_pct else None

            # 유효 손절가: 고정 손절가와 트레일링가 중 더 높은 쪽
            eff_stop = None
            stop_reason = None
            if sl_price is not None:
                eff_stop, stop_reason = sl_price, "stop_loss"
            if trail_price is not None and (eff_stop is None or trail_price >= eff_stop):
                eff_stop, stop_reason = trail_price, "trailing_stop"

            triggered_reason = None
            triggered_price = None
            if eff_stop is not None and lows[i] <= eff_stop:
                triggered_reason = stop_reason
                triggered_price = eff_stop
            elif tp_price is not None and highs[i] >= tp_price:
                triggered_reason = "take_profit"
                triggered_price = tp_price

            if triggered_reason is not None:
                proceeds, trade = _close_position(
                    shares, entry_price, entry_date,
                    triggered_price, dates[i],
                    commission, tax, triggered_reason,
                )
                cash += proceeds
                trades.append(trade)
                shares = 0
                entry_price = 0.0
                entry_date = None
                peak_price = 0.0
                equity.append(cash + shares * closes[i])
                continue  # 시그널 처리 스킵

            # 트리거 안 됨 → 고점 갱신
            if highs[i] > peak_price:
                peak_price = highs[i]

        # 2) 시그널 처리 (전봉 시그널 → 오늘 시가 체결)
        s = sig[i - 1]
        exec_price = opens[i]

        if s == 1 and shares == 0:
            buy_price = exec_price * (1 + slippage)
            qty = int(cash // (buy_price * (1 + commission)))
            if qty > 0:
                cost = qty * buy_price * (1 + commission)
                cash -= cost
                shares = qty
                entry_price = buy_price
                entry_date = dates[i]
                peak_price = max(buy_price, highs[i])  # 진입봉 포함 최고가

        elif s == -1 and shares > 0:
            sell_price = exec_price * (1 - slippage)
            proceeds, trade = _close_position(
                shares, entry_price, entry_date,
                sell_price, dates[i],
                commission, tax, "signal",
            )
            cash += proceeds
            trades.append(trade)
            shares = 0
            entry_price = 0.0
            entry_date = None
            peak_price = 0.0

        equity.append(cash + shares * closes[i])

    # 3) 종료 시 미청산 포지션 정리
    if shares > 0:
        sell_price = closes[-1] * (1 - slippage)
        proceeds, trade = _close_position(
            shares, entry_price, entry_date,
            sell_price, dates[-1],
            commission, tax, "open_at_end",
        )
        cash += proceeds
        trade["open_at_end"] = True
        trades.append(trade)

    eq_series = pd.Series(equity, index=dates[:len(equity)])
    return BacktestResult(
        equity=eq_series,
        trades=trades,
        initial_capital=initial_capital,
        final_capital=float(eq_series.iloc[-1]),
    )
