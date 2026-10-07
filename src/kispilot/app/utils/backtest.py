"""백테스트 실행·커스텀 전략 저장 — main.py 의 /api/backtest/* 와 MCP 백테스트 도구가 부른다.

    run        종목 하나 · 전략 하나
    compare    종목 하나 · 전략/파라미터 여러 개 (일봉은 한 번만 받음)
    portfolio  여러 종목 · 목표 비중 · 리밸런싱 주기

데이터
    종목·벤치마크 일봉은 차트와 같은 경로(utils/chart.daily_frame: yfinance 전체 일봉 + KIS 최근 거래일)로 받는다.
    지표·신호는 시작일 이전 데이터까지 포함한 전체 구간에서 계산한 뒤 [시작일, 종료일] 만 엔진에 넘긴다.
    → 시작일부터 이동평균 등이 이미 채워져 있어 첫 구간 신호가 빠지지 않는다.

체결 규칙 (src/kispilot/app/backtest/engine.py)
    신호가 난 봉의 다음 봉 시가에 전량 매수/매도. 보유 중에는 손절·트레일링 → 익절 → 신호 순.
    기간이 끝날 때 보유 중이면 마지막 종가로 정리한다.

커스텀 전략은 Cache/custom_strategies/<이름>.json 으로 저장한다.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import date
from typing import Any, Callable, Optional

import pandas as pd

from kispilot.app.backtest import STRATEGIES, run_backtest
from kispilot.app.backtest.custom_strategy import (
    CANDLE_SIGNALS, COMPARE_OPERATORS, CUSTOM_STRATEGY_DIR, LOGIC_OPERATORS, RISK_PCT_MAX, RISK_PCT_MIN,
    CustomStrategy, FeeSpec, RiskRule, _safe_filename,
)
from kispilot.app.backtest.indicators_lib import PRICE_FIELDS, list_indicators
from kispilot.app.backtest.metrics import compute_metrics
from kispilot.app.utils import chart

Call = Callable[..., dict]

# 기본 비용 (한국투자증권): 수수료 0.147% (매수·매도), 매도 거래세 0.2%
FEE_DEFAULTS = {"commission": 0.147, "tax": 0.2, "slippage": 0.0}
BENCHMARKS = [("0001", "KOSPI"), ("1001", "KOSDAQ"), ("2001", "KOSPI 200")]
CATEGORY_LABEL = {"trend": "추세", "momentum": "모멘텀", "mean_reversion": "평균회귀", "volatility": "변동성", "composite": "복합"}
REASON_LABEL = {"signal": "신호 매도", "stop_loss": "손절", "take_profit": "익절",
                "trailing_stop": "트레일링", "open_at_end": "기간 종료"}
MIN_BARS = 5
_CODE = re.compile(r"^[0-9A-Z]{6}$")


class BacktestError(Exception):
    def __init__(self, message: str, errors: Optional[list[str]] = None, status: int = 400):
        super().__init__(message)
        self.errors = errors or []
        self.status = status


# ── 옵션 ─────────────────────────────────────────────────────

def options() -> dict:
    """화면 구성용 메타데이터: 기본 전략, 커스텀 빌더(지표·연산자), 벤치마크, 비용 기본값, 저장된 전략."""
    strategies = [{
        "id": sid, "label": m["label"], "category": m.get("category", ""),
        "category_label": CATEGORY_LABEL.get(m.get("category", ""), m.get("category", "")),
        "description": m.get("description", ""), "params": m["params"], "default_risk": m.get("default_risk"),
    } for sid, m in STRATEGIES.items()]
    return {
        "strategies": strategies,
        "categories": [{"key": k, "label": v} for k, v in CATEGORY_LABEL.items()],
        "indicators": list_indicators(),
        "price_fields": [{"key": k, "label": v} for k, v in PRICE_FIELDS.items()],
        "operators": [{"key": k, "label": v} for k, v in COMPARE_OPERATORS.items()],
        "candle_signals": [{"key": k, "label": v} for k, v in CANDLE_SIGNALS.items()],
        "logics": [{"key": k, "label": v} for k, v in LOGIC_OPERATORS.items()],
        "risk_pct_range": {"min": RISK_PCT_MIN, "max": RISK_PCT_MAX},
        "benchmarks": [{"code": c, "label": l} for c, l in BENCHMARKS],
        "fee_defaults": FEE_DEFAULTS,
        "saved": list_saved(),
    }


# ── 입력 정리 ────────────────────────────────────────────────

def _num(v: Any, name: str, lo: float, hi: float) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise BacktestError(f"{name} 값이 숫자가 아닙니다: {v!r}") from None
    if not math.isfinite(x) or not (lo <= x <= hi):
        raise BacktestError(f"{name} 은(는) {lo:g} ~ {hi:g} 사이여야 합니다 (입력 {x:g}).")
    return x


def _date(v: Any, name: str) -> str:
    try:
        return date.fromisoformat(str(v)[:10]).isoformat()
    except ValueError:
        raise BacktestError(f"{name} 형식이 잘못되었습니다 (YYYY-MM-DD): {v!r}") from None


def _risk(raw: dict | None) -> dict[str, Optional[float]]:
    """{stop_loss: {enabled, pct}, ...} → 엔진 인자 (꺼진 규칙은 None)."""
    raw = raw or {}
    out: dict[str, Optional[float]] = {}
    for key, label in (("stop_loss", "손절"), ("take_profit", "익절"), ("trailing_stop", "트레일링 스탑")):
        r = raw.get(key) or {}
        out[f"{key}_pct"] = _num(r.get("pct"), f"{label} 비율(%)", RISK_PCT_MIN, RISK_PCT_MAX) if r.get("enabled") else None
    return out


def _fee(raw: dict | None) -> dict[str, float]:
    raw = {**FEE_DEFAULTS, **(raw or {})}
    return {
        "commission": _num(raw["commission"], "수수료(%)", 0, 5),
        "tax": _num(raw["tax"], "거래세(%)", 0, 5),
        "slippage": _num(raw["slippage"], "슬리피지(%)", 0, 5),
    }


def _ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """chart.daily_frame 결과 → 엔진 규약(date, open, high, low, close, volume)."""
    out = pd.DataFrame({
        "date": df.index.strftime("%Y-%m-%d"),
        "open": df["Open"].astype(float).values,
        "high": df["High"].astype(float).values,
        "low": df["Low"].astype(float).values,
        "close": df["Close"].astype(float).values,
        "volume": df["Volume"].fillna(0).astype(float).values,
    })
    for k in ("open", "high", "low"):
        out[k] = out[k].fillna(out["close"])
    return out.reset_index(drop=True)


def _basic_signals(sid: str, raw_params: dict, df: pd.DataFrame) -> tuple[pd.Series, dict, str]:
    meta = STRATEGIES.get(sid)
    if meta is None:
        raise BacktestError(f"없는 기본 전략입니다: {sid}")
    kwargs = {}
    for p in meta["params"]:
        label = p.get("label", p["name"])
        v = _num((raw_params or {}).get(p["name"], p["default"]), label, p["min"], p["max"])
        kwargs[p["name"]] = int(round(v)) if p.get("type") == "int" else v
    try:
        sig = meta["fn"](df, **kwargs)
    except Exception as e:  # 전략 함수 내부 오류
        raise BacktestError(f"전략 계산 오류: {type(e).__name__}: {e}", status=500) from e
    return sig, kwargs, meta["label"]


def _custom_strategy(spec: dict, risk: dict, fee: dict) -> CustomStrategy:
    """화면의 리스크·비용 설정을 전략에 넣고 검증한다."""
    try:
        strat = CustomStrategy.from_dict(spec or {})
    except Exception as e:
        raise BacktestError(f"커스텀 전략 형식 오류: {e}") from e
    for key in ("stop_loss", "take_profit", "trailing_stop"):
        pct = risk[f"{key}_pct"]
        setattr(strat.risk, key, RiskRule(enabled=pct is not None, pct=pct if pct is not None else getattr(strat.risk, key).pct))
    strat.fee = FeeSpec(**fee)
    errs = strat.validate()
    if errs:
        raise BacktestError("커스텀 전략 설정을 확인하세요.", errors=errs)
    return strat


# ── 실행 ─────────────────────────────────────────────────────

def _clean_num(x: Any, nd: int = 2) -> Optional[float]:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return round(f, nd) if math.isfinite(f) else None


def _common(req: dict) -> dict:
    """여러 실행 방식이 같이 쓰는 입력: 기간 · 자본 · 리스크 · 비용 · 벤치마크."""
    start = _date(req.get("start"), "시작일")
    end = _date(req.get("end"), "종료일")
    if start >= end:
        raise BacktestError("시작일은 종료일보다 앞이어야 합니다.")
    bench_code = str(req.get("benchmark") or "")
    if bench_code and bench_code not in dict(BENCHMARKS):
        raise BacktestError(f"벤치마크는 {[c for c, _ in BENCHMARKS]} 중 하나입니다.")
    return {
        "start": start, "end": end, "bench": bench_code,
        "capital": _num(req.get("capital", 10_000_000), "초기 자본", 100_000, 1e12),
        "risk": _risk(req.get("risk")), "fee": _fee(req.get("fee")),
    }


def _code(v: Any) -> str:
    code = str(v or "").strip().upper()
    if not _CODE.match(code):
        raise BacktestError(f"종목코드(6자리)를 확인하세요: {v!r}")
    return code


def _load(code: str, start: str, end: str, call: Call) -> tuple[pd.DataFrame, pd.Series, list]:
    """종목 일봉 (종료일까지 전체 → 지표 워밍업 포함) 과 기간 안 여부."""
    try:
        raw, sources = chart.daily_frame(code, "stock", call)
    except chart.ChartError as e:
        raise BacktestError(f"{code}: {e}", status=404) from e
    full = _ohlcv(raw)
    full = full[full["date"] <= end].reset_index(drop=True)
    in_range = full["date"] >= start
    if int(in_range.sum()) < MIN_BARS:
        first = full["date"].iloc[0] if len(full) else "—"
        raise BacktestError(f"{code}: 기간 안의 일봉이 {int(in_range.sum())}개뿐입니다 (최소 {MIN_BARS}개). 데이터 시작일: {first}")
    return full, in_range, sources


def _signals(strat_req: dict, full: pd.DataFrame, risk: dict, fee: dict):
    """전략 → (전체 구간 신호, 파라미터, 이름, 종류, 커스텀 전략 객체)."""
    kind = strat_req.get("kind", "basic")
    if kind == "custom":
        custom = _custom_strategy(strat_req.get("spec") or {}, risk, fee)
        try:
            sig_full = custom.generate_signals(full)
        except ValueError as e:
            raise BacktestError(str(e)) from e
        except Exception as e:
            raise BacktestError(f"전략 계산 오류: {type(e).__name__}: {e}", status=500) from e
        return sig_full, {}, custom.name or "커스텀 전략", kind, custom
    sig_full, params, label = _basic_signals(str(strat_req.get("id", "")), strat_req.get("params") or {}, full)
    return sig_full, params, label, "basic", None


def _simulate(full: pd.DataFrame, in_range: pd.Series, sig_full: pd.Series, capital: float, fee: dict, risk: dict):
    df = full[in_range].reset_index(drop=True)
    sig = pd.Series(sig_full[in_range.values].values, index=df.index).fillna(0).astype(int)
    result = run_backtest(
        df, sig, initial_capital=capital,
        commission=fee["commission"] / 100, tax=fee["tax"] / 100, slippage=fee["slippage"] / 100,
        **risk,
    )
    return df, result


def _benchmark(bench_code: str, dates: list[str], capital: float, call: Call):
    """벤치마크 지수 → (일봉, 초기 자본 기준 환산 곡선, 성과, 출처). 실패해도 결과 전체를 막지 않는다."""
    if not bench_code:
        return None, None, None, []
    try:
        braw, sources = chart.daily_frame(bench_code, "index", call)
        b = _ohlcv(braw)[["date", "close"]]
        s = b.set_index("date")["close"].reindex(dates).ffill()
        base = s.dropna().iloc[0] if s.notna().any() else None
        if not base:
            return b, None, None, sources
        norm = s / base * capital
        valid = norm.dropna()
        metrics = None
        if len(valid) >= 2:
            bm = compute_metrics(valid, [])
            metrics = {k: bm[k] for k in ("total_return", "cagr", "max_drawdown", "sharpe")}
        return b, [_clean_num(v, 0) for v in norm], metrics, sources
    except Exception as e:
        return None, None, None, [f"벤치마크 조회 실패: {type(e).__name__}"]


def run(req: dict, call: Call) -> dict:
    code = _code(req.get("code"))
    c = _common(req)
    start, end, capital, risk, fee, bench_code = c["start"], c["end"], c["capital"], c["risk"], c["fee"], c["bench"]
    strat_req = req.get("strategy") or {}
    if strat_req.get("kind", "basic") == "custom":
        _custom_strategy(strat_req.get("spec") or {}, risk, fee)  # 데이터를 받기 전에 형식부터 확인

    full, in_range, sources = _load(code, start, end, call)
    sig_full, params, label, kind, custom = _signals(strat_req, full, risk, fee)
    df, result = _simulate(full, in_range, sig_full, capital, fee, risk)
    dates = list(df["date"])
    equity = result.equity.astype(float)
    bench_df, bench_curve, bench_metrics, bench_sources = _benchmark(bench_code, dates, capital, call)
    metrics = compute_metrics(equity, result.trades, bench_df)

    # 거래 내역: 신호일(조건이 충족된 봉) / 체결일(그다음 봉) / 보유 봉 수
    pos = {d: i for i, d in enumerate(dates)}
    trades, holding = [], [False] * len(dates)
    for t in result.trades:
        ei, xi = pos.get(t["entry_date"]), pos.get(t["exit_date"])
        reason = t["exit_reason"]
        if ei is not None and xi is not None:
            for k in range(ei, xi + 1):
                holding[k] = True
        trades.append({
            "entry_signal": dates[ei - 1] if ei else None,
            "entry_date": t["entry_date"], "entry_price": _clean_num(t["entry_price"]),
            "exit_signal": dates[xi - 1] if reason == "signal" and xi else None,
            "exit_date": t["exit_date"], "exit_price": _clean_num(t["exit_price"]),
            "qty": int(t["qty"]), "pnl": _clean_num(t["pnl"], 0), "pnl_pct": _clean_num(t["pnl_pct"]),
            "reason": reason, "reason_label": REASON_LABEL.get(reason, reason),
            "hold": (xi - ei) if ei is not None and xi is not None else None,
        })

    pnls = [t["pnl"] or 0 for t in trades]
    streak = run_len = 0
    for p in pnls:
        run_len = run_len + 1 if p < 0 else 0
        streak = max(streak, run_len)
    holds = [t["hold"] for t in trades if t["hold"] is not None]

    return {
        "meta": {
            "code": code, "kind": kind, "label": label, "params": params,
            "start": dates[0], "end": dates[-1], "bars": len(dates), "warmup_bars": int((~in_range).sum()),
            "capital": capital, "final": _clean_num(result.final_capital, 0),
            "benchmark": {"code": bench_code, "label": dict(BENCHMARKS).get(bench_code, "")} if bench_code else None,
            "risk": risk, "fee": fee, "sources": sources, "bench_sources": bench_sources,
        },
        "metrics": {**{k: (_clean_num(v, 4) if isinstance(v, float) else v) for k, v in metrics.items()},
                    "bench": bench_metrics},
        "series": {
            "dates": dates,
            "open": [_clean_num(v) for v in df["open"]], "high": [_clean_num(v) for v in df["high"]],
            "low": [_clean_num(v) for v in df["low"]], "close": [_clean_num(v) for v in df["close"]],
            "equity": [_clean_num(v, 0) for v in equity], "bench": bench_curve, "holding": holding,
        },
        "trades": trades,
        "stats": {
            "reasons": {k: sum(1 for t in trades if t["reason"] == k) for k in REASON_LABEL},
            "total_pnl": sum(pnls), "avg_hold": (sum(holds) / len(holds)) if holds else None,
            "max_loss_streak": streak, "exposure": sum(holding) / len(holding) * 100 if holding else 0,
        },
        "strategy": custom.to_dict() if custom is not None else None,
    }


# ── 여러 설정 비교 ───────────────────────────────────────────
# 같은 종목·기간에 전략·파라미터만 바꿔 여러 번 돌린다. 일봉·벤치마크는 한 번만 받는다.

MAX_VARIANTS = 20
SORT_KEYS = {"total_return": "총수익률", "cagr": "CAGR", "sharpe": "샤프", "max_drawdown": "최대 낙폭"}


def _variant_label(label: str, params: dict) -> str:
    return f"{label} ({', '.join(f'{v:g}' if isinstance(v, float) else str(v) for v in params.values())})" if params else label


def compare(req: dict, call: Call) -> dict:
    """variants: [{label?, strategy: {kind, id, params} | {kind: "custom", spec}, risk?}] (2~20개)."""
    code = _code(req.get("code"))
    c = _common(req)
    variants = req.get("variants") or []
    if not isinstance(variants, list) or not 2 <= len(variants) <= MAX_VARIANTS:
        raise BacktestError(f"비교할 설정은 2~{MAX_VARIANTS}개입니다 (입력 {len(variants) if isinstance(variants, list) else 0}개).")
    sort_by = req.get("sort_by") or "total_return"
    if sort_by not in SORT_KEYS:
        raise BacktestError(f"정렬 기준은 {list(SORT_KEYS)} 중 하나입니다.")

    full, in_range, sources = _load(code, c["start"], c["end"], call)
    dates = list(full[in_range]["date"])
    bench_df, bench_curve, bench_metrics, bench_sources = _benchmark(c["bench"], dates, c["capital"], call)

    rows = []
    for k, v in enumerate(variants):
        v = v if isinstance(v, dict) else {}
        strat_req = v.get("strategy") or {}
        row: dict[str, Any] = {"index": k, "kind": strat_req.get("kind", "basic"), "strategy_id": strat_req.get("id")}
        try:
            risk = _risk(v["risk"]) if v.get("risk") is not None else c["risk"]
            sig_full, params, label, kind, _ = _signals(strat_req, full, risk, c["fee"])
            _, result = _simulate(full, in_range, sig_full, c["capital"], c["fee"], risk)
            m = compute_metrics(result.equity.astype(float), result.trades, bench_df)
            row.update({
                "label": v.get("label") or _variant_label(label, params), "params": params, "risk": risk,
                "final": _clean_num(result.final_capital, 0),
                "metrics": {k2: (_clean_num(x, 4) if isinstance(x, float) else x) for k2, x in m.items()},
                "equity": [_clean_num(x, 0) for x in result.equity],
            })
        except BacktestError as e:
            meta = STRATEGIES.get(str(strat_req.get("id")))
            fallback = _variant_label(meta["label"], strat_req.get("params") or {}) if meta else f"설정 {k + 1}"
            row.update({"label": v.get("label") or fallback, "error": str(e), "errors": e.errors})
        rows.append(row)

    ok = [r for r in rows if "error" not in r]
    ok.sort(key=lambda r: r["metrics"].get(sort_by) if r["metrics"].get(sort_by) is not None else -1e18, reverse=True)
    for i, r in enumerate(ok):
        r["rank"] = i + 1
    return {
        "meta": {
            "code": code, "start": dates[0], "end": dates[-1], "bars": len(dates), "warmup_bars": int((~in_range).sum()),
            "capital": c["capital"], "risk": c["risk"], "fee": c["fee"], "sort_by": sort_by, "sort_label": SORT_KEYS[sort_by],
            "benchmark": {"code": c["bench"], "label": dict(BENCHMARKS).get(c["bench"], "")} if c["bench"] else None,
            "sources": sources, "bench_sources": bench_sources,
        },
        "bench": bench_metrics,
        "rows": ok + [r for r in rows if "error" in r],
        "series": {"dates": dates, "bench": bench_curve},
    }


# ── 포트폴리오 ───────────────────────────────────────────────
# 종목별 목표 비중으로 사고, 정해진 주기의 첫 거래일에 목표 비중으로 되돌린다(리밸런싱).
# 체결은 그날 종가, 정수 주식 수. 매도 먼저 → 매수. 남는 돈은 현금으로 둔다.

MAX_HOLDINGS = 20
REBALANCE = {"none": "안 함 (처음 비중으로 사서 보유)", "monthly": "매월", "quarterly": "분기마다", "yearly": "매년"}


def _period_key(d: str, rebalance: str) -> str:
    if rebalance == "monthly":
        return d[:7]
    if rebalance == "quarterly":
        return f"{d[:4]}Q{(int(d[5:7]) - 1) // 3}"
    if rebalance == "yearly":
        return d[:4]
    return ""


def _run_portfolio(prices: pd.DataFrame, weights: dict[str, float], capital: float, fee: dict, rebalance: str) -> dict:
    comm, tax, slip = fee["commission"] / 100, fee["tax"] / 100, fee["slippage"] / 100
    codes = list(weights)
    cash = float(capital)
    shares = {c: 0 for c in codes}
    fees = turnover = 0.0
    trades = rebalances = 0
    equity = []
    prev = None
    for d, row in zip(prices.index, prices.itertuples(index=False)):
        px = dict(zip(codes, row))
        key = _period_key(d, rebalance)
        if prev is None or (rebalance != "none" and key != prev):
            total = cash + sum(shares[c] * px[c] for c in codes)
            for c in codes:  # 목표보다 많은 종목부터 판다
                over = shares[c] * px[c] - total * weights[c]
                q = int(over // px[c]) if over > 0 else 0
                if q > 0:
                    p = px[c] * (1 - slip)
                    cash += q * p * (1 - comm - tax)
                    fees += q * p * (comm + tax)
                    turnover += q * p
                    shares[c] -= q
                    trades += 1
            for c in codes:
                need = total * weights[c] - shares[c] * px[c]
                p = px[c] * (1 + slip)
                q = int(min(need, cash) // (p * (1 + comm))) if need > 0 else 0
                if q > 0:
                    cash -= q * p * (1 + comm)
                    fees += q * p * comm
                    turnover += q * p
                    shares[c] += q
                    trades += 1
            if prev is not None:
                rebalances += 1
        prev = key
        equity.append(cash + sum(shares[c] * px[c] for c in codes))
    last = prices.iloc[-1]
    return {"equity": equity, "shares": shares, "cash": cash, "fees": fees, "turnover": turnover,
            "trades": trades, "rebalances": rebalances, "values": {c: shares[c] * float(last[c]) for c in codes}}


def portfolio(req: dict, call: Call) -> dict:
    """holdings: [{code, weight}] (2~20종목, 비중은 합이 100 이 되도록 맞춘다), rebalance: none/monthly/quarterly/yearly."""
    c = _common(req)
    rebalance = req.get("rebalance") or "none"
    if rebalance not in REBALANCE:
        raise BacktestError(f"리밸런싱은 {list(REBALANCE)} 중 하나입니다.")
    raw_holdings = req.get("holdings") or []
    weights: dict[str, float] = {}
    for h in raw_holdings if isinstance(raw_holdings, list) else []:
        code = _code((h or {}).get("code"))
        w = _num((h or {}).get("weight"), f"{code} 비중", 0, 1e6)
        if w > 0:
            weights[code] = weights.get(code, 0) + w
    if not 2 <= len(weights) <= MAX_HOLDINGS:
        raise BacktestError(f"비중이 0 보다 큰 종목을 2~{MAX_HOLDINGS}개 넣으세요 (지금 {len(weights)}개).")
    total_w = sum(weights.values())
    weights = {k: v / total_w for k, v in weights.items()}

    closes, sources, firsts = {}, {}, {}
    for code in weights:
        try:
            raw, src = chart.daily_frame(code, "stock", call)
        except chart.ChartError as e:
            raise BacktestError(f"{code}: {e}", status=404) from e
        df = _ohlcv(raw)
        df = df[df["date"] <= c["end"]]
        if df.empty:
            raise BacktestError(f"{code}: 종료일 이전 일봉이 없습니다.")
        closes[code] = df.set_index("date")["close"]
        sources[code] = src
        firsts[code] = df["date"].iloc[0]
    # 가장 늦게 상장한 종목의 첫 거래일 전에는 비중대로 살 수 없으므로 시작일을 그날로 미룬다
    late_code = max(firsts, key=firsts.get)
    start = max(c["start"], firsts[late_code])
    prices = pd.DataFrame(closes).sort_index().ffill()
    prices = prices[(prices.index >= start) & (prices.index <= c["end"])].dropna()
    if len(prices) < MIN_BARS:
        raise BacktestError(f"모든 종목이 함께 거래된 일봉이 {len(prices)}개뿐입니다 (최소 {MIN_BARS}개).")
    dates = list(prices.index)
    capital, fee = c["capital"], c["fee"]

    sim = _run_portfolio(prices, weights, capital, fee, rebalance)
    hold = _run_portfolio(prices, weights, capital, fee, "none") if rebalance != "none" else None
    _, bench_curve, bench_metrics, bench_sources = _benchmark(c["bench"], dates, capital, call)
    pick = ("total_return", "cagr", "max_drawdown", "sharpe")
    metric = lambda eq: {k: v for k, v in compute_metrics(pd.Series(eq, index=dates), []).items() if k in pick}  # noqa: E731

    final = sim["equity"][-1]
    holdings = []
    for code, w in weights.items():
        first_px, last_px = float(prices[code].iloc[0]), float(prices[code].iloc[-1])
        holdings.append({
            "code": code, "target_weight": round(w * 100, 2),
            "final_weight": round(sim["values"][code] / final * 100, 2) if final else None,
            "final_value": round(sim["values"][code]), "shares": sim["shares"][code],
            "price_return": round((last_px / first_px - 1) * 100, 2) if first_px else None,
            "first_close": _clean_num(first_px), "last_close": _clean_num(last_px),
        })
    return {
        "meta": {
            "start": dates[0], "end": dates[-1], "requested_start": c["start"],
            "start_adjusted": {"code": late_code, "listed": firsts[late_code]} if firsts[late_code] > c["start"] else None,
            "bars": len(dates), "capital": capital, "final": round(final), "rebalance": rebalance,
            "rebalance_label": REBALANCE[rebalance], "fee": fee,
            "benchmark": {"code": c["bench"], "label": dict(BENCHMARKS).get(c["bench"], "")} if c["bench"] else None,
            "sources": sources, "bench_sources": bench_sources,
        },
        "metrics": {**metric(sim["equity"]), "bench": bench_metrics},
        "no_rebalance": {**metric(hold["equity"]), "final": round(hold["equity"][-1]), "fees": round(hold["fees"])} if hold else None,
        "holdings": holdings,
        "stats": {"rebalances": sim["rebalances"], "trades": sim["trades"], "turnover": round(sim["turnover"]),
                  "fees": round(sim["fees"]), "cash": round(sim["cash"])},
        "series": {"dates": dates, "equity": [round(v) for v in sim["equity"]], "bench": bench_curve,
                   "no_rebalance": [round(v) for v in hold["equity"]] if hold else None},
    }


# ── 커스텀 전략 저장 ─────────────────────────────────────────

def _path(file: str) -> str:
    if not re.fullmatch(r"[\w\- ]+\.json", file or ""):
        raise BacktestError("잘못된 전략 파일 이름입니다.")
    path = os.path.join(CUSTOM_STRATEGY_DIR, file)
    if os.path.dirname(os.path.abspath(path)) != os.path.abspath(CUSTOM_STRATEGY_DIR):
        raise BacktestError("잘못된 전략 파일 이름입니다.")
    return path


def list_saved() -> list[dict]:
    if not os.path.isdir(CUSTOM_STRATEGY_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(CUSTOM_STRATEGY_DIR)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(CUSTOM_STRATEGY_DIR, fn), encoding="utf-8") as f:
                d = json.load(f)
            out.append({"file": fn, "name": d.get("name") or fn[:-5], "description": d.get("description", "")})
        except Exception:
            out.append({"file": fn, "name": fn[:-5], "description": "(읽기 실패)"})
    return out


def load_saved(file: str) -> dict:
    path = _path(file)
    if not os.path.exists(path):
        raise BacktestError("저장된 전략이 없습니다.", status=404)
    with open(path, encoding="utf-8") as f:
        return CustomStrategy.from_dict(json.load(f)).to_dict()


def save(spec: dict, risk_raw: dict | None, fee_raw: dict | None) -> dict:
    risk, fee = _risk(risk_raw), _fee(fee_raw)
    strat = _custom_strategy(spec, risk, fee)
    if not str(strat.name).strip():
        raise BacktestError("전략 이름을 입력하세요.")
    os.makedirs(CUSTOM_STRATEGY_DIR, exist_ok=True)
    file = _safe_filename(strat.name) + ".json"
    with open(_path(file), "w", encoding="utf-8") as f:
        json.dump(strat.to_dict(), f, ensure_ascii=False, indent=2)
    return {"file": file, "name": strat.name, "saved": list_saved()}


def delete(file: str) -> dict:
    path = _path(file)
    if os.path.exists(path):
        os.remove(path)
    return {"saved": list_saved()}
