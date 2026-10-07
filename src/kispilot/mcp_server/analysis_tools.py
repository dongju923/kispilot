"""MCP 분석 도구 — 백테스트 · 기술 지표 · 차트 봉.

웹 콘솔과 같은 코드(app/utils/backtest.py, app/utils/chart.py, backtest/indicators_lib.py)를 쓴다.
응답은 대화 컨텍스트를 아끼도록 요약해서 돌려준다 (백테스트 전체 결과는 약 100KB).

    backtest_options              기본 전략 11종 · 지표 분류 · 연산자 · 비용 기본값 · 저장된 커스텀 전략
    backtest_indicator_catalog    커스텀 전략용 지표 157개 (분류·검색어로 거름)
    backtest_run                  백테스트 실행 → 성과 지표 · 벤치마크 비교 · 월말 자산 · 거래 내역(요약)
    backtest_compare              한 종목에 전략·파라미터 여러 개를 한 번에 → 성과 비교 표
    backtest_portfolio            여러 종목 목표 비중 + 리밸런싱 → 성과 · 종목별 비중 · 리밸런싱 안 했을 때와 비교
    backtest_strategy_validate    커스텀 전략 검증
    backtest_strategy_list/load/save/delete   커스텀 전략 저장 관리 (데이터 폴더의 JSON)
    indicator_values              종목 하나에 지표를 계산해 최근 값 (예: RSI, MACD, 볼린저)
    chart_bars                    일·주·월·년봉 최근 N개 (yfinance 전체 + KIS 최근 거래일)
    stock_news                    주식 관련 뉴스 제목 (종목코드를 주면 그 종목 기사만) + 제목 검색 링크
"""
from __future__ import annotations

import dataclasses
import json
from datetime import date, timedelta
from typing import Any, Callable, Literal, Optional

STRATEGY_HINT = (
    "기본 전략은 strategy 에 id(예: sma_crossover)와 params 를, 커스텀 전략은 custom_strategy(전략 JSON) 또는 "
    "saved_strategy(저장 파일 이름) 중 하나를 넣는다. 전략 id·파라미터는 backtest_options 로 확인한다."
)


def register(mcp, *, execute: Callable, to_json: Callable, surface_errors: Callable, ToolError, ToolAnnotations,
             batchable: Optional[dict] = None) -> int:
    from kispilot.app.utils import backtest as bt
    from kispilot.app.utils import chart

    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
    local_write = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=False)
    local_delete = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False)

    def kis_call(fn, **kwargs) -> dict:
        """차트 모듈용 KIS 호출 (실전 키). 실패하면 차트 모듈이 yfinance 만으로 진행한다."""
        result = execute(fn, "real", kwargs)
        if dataclasses.is_dataclass(result) and not isinstance(result, type):
            result = dataclasses.asdict(result)
        return result if isinstance(result, dict) else {}

    def guard(fn: Callable, *args):
        try:
            return fn(*args)
        except bt.BacktestError as e:
            detail = (" / ".join(e.errors)) if e.errors else ""
            raise ToolError(f"{e}{' — ' + detail if detail else ''}") from e
        except chart.ChartError as e:
            raise ToolError(str(e)) from e

    def risk_body(stop_loss_pct, take_profit_pct, trailing_stop_pct) -> dict:
        return {k: {"enabled": v is not None, "pct": v if v is not None else 5}
                for k, v in (("stop_loss", stop_loss_pct), ("take_profit", take_profit_pct), ("trailing_stop", trailing_stop_pct))}

    count = 0

    # ── 옵션 · 지표 카탈로그 ─────────────────────────────────

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def backtest_options() -> str:
        """백테스트 준비 정보: 기본 전략 11종(id·설명·파라미터 범위·기본 손절/익절), 커스텀 전략용 지표 분류와 개수,
        조건 연산자, 가격 필드, 캔들 신호, 벤치마크 지수, 비용 기본값(수수료 0.147%·거래세 0.2%), 저장된 커스텀 전략 목록.

        Returns:
            JSON. 지표 157개의 상세(파라미터)는 backtest_indicator_catalog 로 본다.
        """
        o = bt.options()
        cats: dict[str, int] = {}
        for ind in o["indicators"]:
            cats[ind["category"]] = cats.get(ind["category"], 0) + 1
        return to_json({
            "strategies": o["strategies"],
            "indicator_categories": cats,
            "operators": o["operators"], "price_fields": o["price_fields"], "candle_signals": o["candle_signals"],
            "logics": o["logics"], "risk_pct_range": o["risk_pct_range"],
            "benchmarks": o["benchmarks"], "fee_defaults_pct": o["fee_defaults"], "saved_strategies": o["saved"],
            "custom_strategy_format": {
                "name": "전략 이름", "description": "",
                "indicators": [{"id": "sma_5", "indicator": "sma", "params": {"period": 5}}],
                "entry": {"logic": "and", "conditions": [
                    {"left": {"type": "indicator", "ref": "sma_5"}, "operator": "cross_up",
                     "right": {"type": "indicator", "ref": "sma_20"}}]},
                "exit": {"logic": "and", "conditions": []},
                "_note": "operand type: indicator(ref=지표 id) | price(field=close 등) | value(value=숫자). "
                         "캔들스틱 지표는 operator 대신 candle_signal(bullish/bearish/detected). "
                         "조건이 참으로 바뀌는 봉에서만 신호. 청산 조건이 비면 손절/익절로만 청산.",
            },
        })

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def backtest_indicator_catalog(category: Optional[str] = None, query: Optional[str] = None) -> str:
        """커스텀 전략에 쓸 수 있는 기술 지표 목록 (key·이름·분류·설명·파라미터 범위).

        Args:
            category: 분류로 거르기 — 가격 / 이동평균 / 추세 / 모멘텀 / 변동성 / 거래량 / 캔들스틱.
            query: 이름·설명·key 부분 일치 검색 (예: "RSI", "볼린저", "macd").

        Returns:
            [{key, label, category, description, params:[{name,label,default,min,max,step,type}]}] JSON.
        """
        items = bt.options()["indicators"]
        if category:
            items = [i for i in items if i["category"] == category.strip()]
        if query:
            q = query.strip().lower()
            items = [i for i in items if q in i["key"].lower() or q in i["label"].lower() or q in i["description"].lower()]
        return to_json(items)

    # ── 실행 ─────────────────────────────────────────────────

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def backtest_run(
        code: str,
        strategy: Optional[str] = None,
        params: Optional[dict[str, float]] = None,
        custom_strategy: Optional[dict[str, Any]] = None,
        saved_strategy: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        capital: float = 10_000_000,
        benchmark: Literal["0001", "1001", "2001", ""] = "0001",
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        trailing_stop_pct: Optional[float] = None,
        commission_pct: float = 0.147,
        tax_pct: float = 0.2,
        slippage_pct: float = 0.0,
        max_trades: int = 20,
    ) -> str:
        """종목 하나로 전략을 백테스트한다 (일봉, 실제 주문 아님).

        체결 규칙: 신호가 난 봉의 다음 봉 시가에 전량 매수/매도. 보유 중에는 손절·트레일링 → 익절 → 신호 순.
        기간 끝에 보유 중이면 마지막 종가로 정리. 지표는 시작일 이전 데이터부터 계산(워밍업)한다.
        기본 전략은 strategy 에 id(예: sma_crossover)와 params 를, 커스텀 전략은 custom_strategy(전략 JSON) 또는
        saved_strategy(저장 파일 이름) 중 하나를 넣는다. 전략 id·파라미터는 backtest_options 로 확인한다.

        Args:
            code: 6자리 종목코드 (예: "005930").
            strategy: 기본 전략 id (sma_crossover, momentum, rsi_mean_reversion, week52_high, consecutive_moves,
                ma_divergence, false_breakout, strong_close, volatility_breakout, short_term_reversal, trend_filter_signal).
            params: 기본 전략 파라미터 (예: {"short": 5, "long": 20}). 없으면 기본값.
            custom_strategy: 커스텀 전략 JSON (형식은 backtest_options 의 custom_strategy_format).
            saved_strategy: 저장된 커스텀 전략 파일 이름 (backtest_strategy_list 의 file).
            start: 시작일 "YYYY-MM-DD". 없으면 종료일 5년 전.
            end: 종료일 "YYYY-MM-DD". 없으면 오늘.
            capital: 초기 자본(원). 기본 1천만.
            benchmark: 비교 지수 — "0001" KOSPI, "1001" KOSDAQ, "2001" KOSPI 200, "" 없음.
            stop_loss_pct: 손절 % (진입가 대비, 1~50). 없으면 끔.
            take_profit_pct: 익절 % (1~50). 없으면 끔.
            trailing_stop_pct: 트레일링 스탑 % (보유 중 고점 대비, 1~50). 없으면 끔.
            commission_pct: 수수료 % (매수·매도 각각). 기본 0.147.
            tax_pct: 거래세 % (매도). 기본 0.2.
            slippage_pct: 슬리피지 %. 기본 0.
            max_trades: 돌려줄 최근 거래 수 (가장 좋은/나쁜 거래 3건은 따로 포함). 기본 20.

        Returns:
            {summary, metrics(전략), benchmark(지수 성과), stats, equity_monthly(월말 자산·지수 환산), trades_recent,
             best_trades, worst_trades} JSON. 수익률·MDD 는 %, 금액은 원.
        """
        chosen = [x for x in (strategy, custom_strategy, saved_strategy) if x]
        if len(chosen) != 1:
            raise ToolError("strategy / custom_strategy / saved_strategy 중 정확히 하나를 넣으세요. " + STRATEGY_HINT)
        if saved_strategy:
            spec = guard(bt.load_saved, saved_strategy)
            strat = {"kind": "custom", "spec": spec}
        elif custom_strategy:
            strat = {"kind": "custom", "spec": custom_strategy}
        else:
            strat = {"kind": "basic", "id": strategy, "params": params or {}}
            meta = next((s for s in bt.options()["strategies"] if s["id"] == strategy), None)
            # 기본 손절·익절이 있는 전략이고 사용자가 리스크를 안 정했으면 전략 기본값을 쓴다
            if meta and meta.get("default_risk") and stop_loss_pct is None and take_profit_pct is None and trailing_stop_pct is None:
                dr = meta["default_risk"]
                stop_loss_pct, take_profit_pct = dr.get("stop_loss_pct"), dr.get("take_profit_pct")
        no_risk_args = stop_loss_pct is None and take_profit_pct is None and trailing_stop_pct is None
        if strat["kind"] == "custom" and no_risk_args and isinstance(strat["spec"].get("risk"), dict):
            # 커스텀 전략에 저장된 손절·익절을 쓴다 (도구 인자로 따로 주면 그쪽이 우선)
            risk = {k: {"enabled": bool(v.get("enabled")), "pct": v.get("pct", 5)}
                    for k, v in strat["spec"]["risk"].items() if isinstance(v, dict)}
        else:
            risk = risk_body(stop_loss_pct, take_profit_pct, trailing_stop_pct)
        end_d = end or date.today().isoformat()
        start_d = start or (date.fromisoformat(end_d[:10]) - timedelta(days=365 * 5)).isoformat()
        req = {
            "code": code, "start": start_d, "end": end_d, "capital": capital, "benchmark": benchmark, "strategy": strat,
            "risk": risk,
            "fee": {"commission": commission_pct, "tax": tax_pct, "slippage": slippage_pct},
        }
        r = guard(bt.run, req, kis_call)
        return to_json(_summarize(r, max(0, min(int(max_trades), 200))))

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def backtest_compare(
        code: str,
        strategy: Optional[str] = None,
        param_sets: Optional[list[dict[str, float]]] = None,
        param_grid: Optional[dict[str, list[float]]] = None,
        strategies: Optional[list[str]] = None,
        saved_strategies: Optional[list[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        capital: float = 10_000_000,
        benchmark: Literal["0001", "1001", "2001", ""] = "0001",
        stop_loss_pct: Optional[float] = None,
        take_profit_pct: Optional[float] = None,
        trailing_stop_pct: Optional[float] = None,
        commission_pct: float = 0.147,
        tax_pct: float = 0.2,
        slippage_pct: float = 0.0,
        sort_by: Literal["total_return", "cagr", "sharpe", "max_drawdown"] = "total_return",
    ) -> str:
        """한 종목에서 전략·파라미터 여러 개를 한 번에 백테스트해 성과 표로 비교한다 (최대 20개, backtest_run 을 여러 번 부르는 대신 쓴다).

        비교 대상은 다음 중 하나 이상으로 정한다 (합쳐서 2~20개):
          - strategy + param_sets: 기본 전략 하나의 파라미터 조합 목록. 예) 이평 5/20, 10/60, 20/120 →
            strategy="sma_crossover", param_sets=[{"short":5,"long":20},{"short":10,"long":60},{"short":20,"long":120}]
          - strategy + param_grid: 값 목록의 모든 조합. 예) {"short":[5,10], "long":[20,60]} → 4개
          - strategies: 기본 전략 id 목록 (각 전략 기본 파라미터)
          - saved_strategies: 저장된 커스텀 전략 파일 이름 목록
        손절·익절을 주지 않으면 기본 전략은 각 전략의 기본 손절/익절을, 저장 전략은 저장된 값을 쓴다.

        Args:
            code: 6자리 종목코드.
            start / end: "YYYY-MM-DD". 없으면 최근 5년.
            sort_by: 순위 기준 — total_return, cagr, sharpe, max_drawdown(낙폭이 작은 순).
            나머지 인자는 backtest_run 과 같다.

        Returns:
            {summary, benchmark, rows:[{rank, label, params, total_return, cagr, max_drawdown, sharpe, total_trades,
             win_rate, profit_factor, final}], failed?} JSON. 수익률·MDD 는 %.
        """
        import itertools

        risk_given = not (stop_loss_pct is None and take_profit_pct is None and trailing_stop_pct is None)
        meta_of = {s["id"]: s for s in bt.options()["strategies"]}

        def basic(sid: str, params: dict, label: Optional[str] = None) -> dict:
            if sid not in meta_of:
                raise ToolError(f"없는 기본 전략입니다: {sid!r}. backtest_options 로 id 를 확인하세요.")
            v = {"strategy": {"kind": "basic", "id": sid, "params": params or {}}}
            dr = meta_of[sid].get("default_risk")
            if not risk_given and dr:
                v["risk"] = risk_body(dr.get("stop_loss_pct"), dr.get("take_profit_pct"), dr.get("trailing_stop_pct"))
            if label:
                v["label"] = label
            return v

        variants: list[dict] = []
        if param_sets or param_grid:
            if not strategy:
                raise ToolError("param_sets / param_grid 를 쓰려면 strategy(기본 전략 id)를 함께 넣으세요.")
            sets = list(param_sets or [])
            if param_grid:
                keys = list(param_grid)
                combos = list(itertools.product(*[param_grid[k] if isinstance(param_grid[k], list) else [param_grid[k]] for k in keys]))
                if len(combos) > bt.MAX_VARIANTS:
                    raise ToolError(f"param_grid 조합이 {len(combos)}개입니다. 최대 {bt.MAX_VARIANTS}개가 되도록 값을 줄이세요.")
                sets += [dict(zip(keys, c)) for c in combos]
            variants += [basic(strategy, p) for p in sets]
        elif strategy:
            strategies = [strategy, *(strategies or [])]
        variants += [basic(s, {}) for s in (strategies or [])]
        for file in saved_strategies or []:
            spec = guard(bt.load_saved, file)
            v = {"label": spec.get("name") or file, "strategy": {"kind": "custom", "spec": spec}}
            if not risk_given and isinstance(spec.get("risk"), dict):
                v["risk"] = {k: {"enabled": bool(x.get("enabled")), "pct": x.get("pct", 5)} for k, x in spec["risk"].items() if isinstance(x, dict)}
            variants.append(v)
        if not 2 <= len(variants) <= bt.MAX_VARIANTS:
            raise ToolError(f"비교할 설정이 {len(variants)}개입니다. 2~{bt.MAX_VARIANTS}개가 되게 param_sets · param_grid · strategies · saved_strategies 를 넣으세요.")

        end_d = end or date.today().isoformat()
        start_d = start or (date.fromisoformat(end_d[:10]) - timedelta(days=365 * 5)).isoformat()
        req = {
            "code": code, "start": start_d, "end": end_d, "capital": capital, "benchmark": benchmark,
            "variants": variants, "sort_by": sort_by,
            "risk": risk_body(stop_loss_pct, take_profit_pct, trailing_stop_pct),
            "fee": {"commission": commission_pct, "tax": tax_pct, "slippage": slippage_pct},
        }
        r = guard(bt.compare, req, kis_call)
        keys = ("total_return", "cagr", "max_drawdown", "sharpe", "total_trades", "win_rate", "profit_factor")
        rows = [{"rank": x["rank"], "label": x["label"], "params": x["params"], "risk_pct": x["risk"],
                 **{k: x["metrics"].get(k) for k in keys}, "final": x["final"]} for x in r["rows"] if "error" not in x]
        failed = [{"label": x["label"], "error": x["error"], "errors": x.get("errors")} for x in r["rows"] if "error" in x]
        meta = r["meta"]
        out = {
            "summary": {"code": meta["code"], "period": f"{meta['start']} ~ {meta['end']}", "bars": meta["bars"],
                        "capital": meta["capital"], "sorted_by": meta["sort_label"], "fee_pct": meta["fee"],
                        "benchmark": meta["benchmark"]["label"] if meta["benchmark"] else None, "data_sources": meta["sources"]},
            "benchmark": r["bench"],
            "rows": rows,
            "notes": "수익률·MDD·승률은 %, 금액은 원. 같은 기간·같은 데이터로 비교. 가장 좋은 조합은 그 기간에 맞춘 결과일 수 있다(과최적화).",
        }
        if failed:
            out["failed"] = failed
        return to_json(out)

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def backtest_portfolio(
        holdings: dict[str, float],
        rebalance: Literal["none", "monthly", "quarterly", "yearly"] = "quarterly",
        start: Optional[str] = None,
        end: Optional[str] = None,
        capital: float = 10_000_000,
        benchmark: Literal["0001", "1001", "2001", ""] = "0001",
        commission_pct: float = 0.147,
        tax_pct: float = 0.2,
        slippage_pct: float = 0.0,
    ) -> str:
        """여러 종목을 목표 비중으로 사서 보유하는 포트폴리오 백테스트 (리밸런싱 포함, 일봉 종가 체결, 실제 주문 아님).

        첫 거래일에 목표 비중대로 사고, 리밸런싱 주기의 첫 거래일마다 목표 비중으로 되돌린다(많은 종목 매도 → 적은 종목 매수).
        정수 주식 수, 수수료·거래세 반영. 리밸런싱을 하면 '안 했을 때(처음 비중으로 보유)' 결과도 같이 돌려준다.
        가장 늦게 상장한 종목의 첫 거래일이 시작일보다 늦으면 시작일을 그날로 미룬다.

        Args:
            holdings: {종목코드: 비중} 2~20종목. 예) {"005930": 40, "000660": 30, "035420": 30}. 비중 합이 100 이 아니면 비율로 맞춘다.
            rebalance: none(안 함) / monthly / quarterly / yearly. 기본 quarterly.
            start / end: "YYYY-MM-DD". 없으면 최근 5년.
            capital: 초기 자본(원).
            benchmark: 비교 지수 — "0001" KOSPI, "1001" KOSDAQ, "2001" KOSPI 200, "" 없음.

        Returns:
            {summary, metrics, benchmark, no_rebalance, holdings:[{code, name, target_weight, final_weight, final_value,
             price_return}], stats:{rebalances, trades, turnover, fees}, equity_monthly} JSON.
        """
        end_d = end or date.today().isoformat()
        start_d = start or (date.fromisoformat(end_d[:10]) - timedelta(days=365 * 5)).isoformat()
        req = {
            "holdings": [{"code": k, "weight": v} for k, v in (holdings or {}).items()],
            "rebalance": rebalance, "start": start_d, "end": end_d, "capital": capital, "benchmark": benchmark,
            "fee": {"commission": commission_pct, "tax": tax_pct, "slippage": slippage_pct},
        }
        r = guard(bt.portfolio, req, kis_call)
        try:
            from kispilot.api.data import master
            names = master.stock_names()
        except Exception:
            names = {}
        meta, s = r["meta"], r["series"]
        monthly = []
        for i, d in enumerate(s["dates"]):
            if i == len(s["dates"]) - 1 or s["dates"][i + 1][:7] != d[:7]:
                row = {"month": d[:7], "equity": s["equity"][i]}
                if s["no_rebalance"]:
                    row["no_rebalance"] = s["no_rebalance"][i]
                if s["bench"]:
                    row["benchmark"] = s["bench"][i]
                monthly.append(row)
        return to_json({
            "summary": {"period": f"{meta['start']} ~ {meta['end']}", "start_adjusted": meta["start_adjusted"],
                        "requested_start": meta["requested_start"], "bars": meta["bars"], "capital": meta["capital"],
                        "final": meta["final"], "rebalance": meta["rebalance_label"], "fee_pct": meta["fee"],
                        "benchmark": meta["benchmark"]["label"] if meta["benchmark"] else None},
            "metrics": {k: v for k, v in r["metrics"].items() if k != "bench"},
            "benchmark": r["metrics"].get("bench"),
            "no_rebalance": r["no_rebalance"],
            "holdings": [{**h, "name": names.get(h["code"], "")} for h in r["holdings"]],
            "stats": r["stats"],
            "equity_monthly": monthly[-60:],
            "notes": "수익률·MDD 는 %, 금액은 원. 리밸런싱일 종가 체결 가정, 수수료·거래세 반영. 실제 주문이 아닌 과거 데이터 시뮬레이션.",
        })

    # ── 커스텀 전략 관리 ─────────────────────────────────────

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def backtest_strategy_validate(custom_strategy: dict[str, Any], stop_loss_pct: Optional[float] = None,
                                   take_profit_pct: Optional[float] = None, trailing_stop_pct: Optional[float] = None) -> str:
        """커스텀 전략 JSON 을 검증한다 (지표 id·연산자·조건 구성, 청산 방법 유무). 실행·저장 전에 쓴다.

        Args:
            custom_strategy: 커스텀 전략 JSON.
            stop_loss_pct / take_profit_pct / trailing_stop_pct: 리스크 규칙 % (청산 조건이 없을 때 필요).

        Returns:
            {"valid": bool, "errors": [...]} JSON.
        """
        try:
            bt._custom_strategy(custom_strategy, bt._risk(risk_body(stop_loss_pct, take_profit_pct, trailing_stop_pct)), bt._fee(None))
            return to_json({"valid": True, "errors": []})
        except bt.BacktestError as e:
            return to_json({"valid": False, "errors": e.errors or [str(e)]})

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def backtest_strategy_list() -> str:
        """저장된 커스텀 전략 목록 (웹 콘솔 백테스트 화면과 공유).

        Returns:
            [{file, name, description}] JSON.
        """
        return to_json(bt.list_saved())

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def backtest_strategy_load(file: str) -> str:
        """저장된 커스텀 전략 하나를 불러온다 (지표·진입/청산 조건·리스크·비용).

        Args:
            file: backtest_strategy_list 의 file (예: "골든크로스_RSI.json").
        """
        return to_json(guard(bt.load_saved, file))

    @mcp.tool(annotations=local_write, structured_output=False)
    @surface_errors
    def backtest_strategy_save(custom_strategy: dict[str, Any], stop_loss_pct: Optional[float] = None,
                               take_profit_pct: Optional[float] = None, trailing_stop_pct: Optional[float] = None,
                               commission_pct: float = 0.147, tax_pct: float = 0.2, slippage_pct: float = 0.0) -> str:
        """커스텀 전략을 검증한 뒤 저장한다 (같은 이름이면 덮어씀). 웹 콘솔 백테스트 화면에서도 보인다.

        Args:
            custom_strategy: 커스텀 전략 JSON (name 필수).
            stop_loss_pct / take_profit_pct / trailing_stop_pct: 함께 저장할 리스크 규칙 % (없으면 끔).
            commission_pct / tax_pct / slippage_pct: 함께 저장할 비용 %.

        Returns:
            {file, name, saved:[...]} JSON.
        """
        fee = {"commission": commission_pct, "tax": tax_pct, "slippage": slippage_pct}
        return to_json(guard(bt.save, custom_strategy, risk_body(stop_loss_pct, take_profit_pct, trailing_stop_pct), fee))

    @mcp.tool(annotations=local_delete, structured_output=False)
    @surface_errors
    def backtest_strategy_delete(file: str) -> str:
        """저장된 커스텀 전략 파일을 지운다. 사용자가 요청한 경우에만 호출한다.

        Args:
            file: backtest_strategy_list 의 file.
        """
        return to_json(guard(bt.delete, file))

    # ── 지표 · 차트 ───────────────────────────────────────────

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def indicator_values(code: str, indicators: list[dict[str, Any]], last_n: int = 5) -> str:
        """종목 하나의 일봉에 기술 지표를 계산해 최근 값을 돌려준다 (예: RSI 가 과매도인지, 골든크로스가 났는지).

        Args:
            code: 6자리 종목코드.
            indicators: [{"indicator": "rsi", "params": {"period": 14}}, {"indicator": "sma", "params": {"period": 20}}].
                indicator 는 backtest_indicator_catalog 의 key. params 를 빼면 기본값.
            last_n: 최근 몇 개 봉의 값을 줄지 (1~60). 기본 5.

        Returns:
            {code, rows:[{date, close, <지표별 값>}...]} JSON. 지표 이름은 "<key>(<파라미터>)".
        """
        from kispilot.app.backtest.indicators_lib import INDICATOR_CATALOG, coerce_params, compute_indicator

        if not indicators:
            raise ToolError('indicators 에 하나 이상 넣으세요. 예: [{"indicator": "rsi"}]')
        raw, sources = guard(chart.daily_frame, code.strip().upper(), "stock", kis_call)
        df = bt._ohlcv(raw)
        n = max(1, min(int(last_n), 60))
        out = df[["date", "close"]].tail(n).reset_index(drop=True)
        for spec in indicators[:12]:
            key = str(spec.get("indicator", "")).strip()
            if key not in INDICATOR_CATALOG:
                raise ToolError(f"없는 지표입니다: {key!r}. backtest_indicator_catalog 로 key 를 확인하세요.")
            p = coerce_params(key, spec.get("params"))
            label = f"{key}({','.join(str(v) for v in p.values())})" if p else key
            series = compute_indicator(df, key, p)
            out[label] = [None if v != v else round(float(v), 4) for v in series.tail(n).tolist()]
        return to_json({"code": code, "sources": sources, "rows": out.to_dict(orient="records")})

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def chart_bars(code: str, tf: Literal["D", "W", "M", "Y"] = "D", count: int = 60,
                   kind: Literal["stock", "index"] = "stock") -> str:
        """일·주·월·년봉 최근 N개 (yfinance 전체 기록 + KIS 최근 거래일 보정, 웹 콘솔 차트와 같은 데이터).

        Args:
            code: 종목 6자리, 또는 지수 "0001"(KOSPI) / "1001"(KOSDAQ) / "2001"(KOSPI 200) — 지수는 kind="index".
            tf: D 일 / W 주 / M 월 / Y 년. 기본 D.
            count: 최근 몇 개 (1~500). 기본 60.
            kind: stock 또는 index.

        Returns:
            {code, tf, sources, bars:[{time, open, high, low, close, volume}]} JSON.
        """
        data = guard(chart.build, code.strip().upper(), tf, kind, kis_call)
        n = max(1, min(int(count), 500))
        return to_json({"code": data["code"], "tf": tf, "sources": data["sources"], "bars": data["bars"][-n:]})

    @mcp.tool(annotations=read_only, structured_output=False)
    @surface_errors
    def stock_news(code: str = "", count: int = 10) -> str:
        """주식 관련 뉴스 제목 (최신순). 종목 뉴스를 물으면 code 에 종목코드를 넣는다.

        sector_news_title(원본)과 달리 정치·사회 기사, 종목이 본문에만 나오는 시황 기사, 중복 송고를 걸러 낸다.

        Args:
            code: 6자리 종목코드 → 그 종목 기사만. 비우면 시장 전체에서 주식 관련 기사만.
            count: 몇 건 (1~50). 기본 10.

        Returns:
            {code, news: [{date, time, title, source, code, name, url}]} JSON.
            url 은 제목 검색 링크다 (KIS 는 기사 주소를 주지 않음). 본문이 없으니 제목만 보고 내용을 넘겨짚지 않는다.
        """
        from kispilot.app.utils import news

        rows = news.fetch(kis_call, code, max(1, min(int(count), 50)))
        return to_json({"code": code.strip(), "news": rows})

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False),
              structured_output=False)
    @surface_errors
    def market_session() -> str:
        """지금(한국 시간) 장 운영 구간과 그 구간에서 쓸 수 있는 주문 호가 유형(ord_dvsn)을 알려준다. 주문 전에 확인한다.
        공휴일은 반영하지 않는다.

        Returns:
            {now_kst, session, label, order_types:[{code, label}], note} JSON.
        """
        return to_json(_market_session())

    if batchable is not None:  # batch_query 로 여러 종목에 돌릴 수 있게 (각자 last_n · count 로 기간을 정하므로 기본으로 자르지 않음)
        batchable["indicator_values"] = (lambda kw: json.loads(indicator_values(**kw)), "code", True)
        batchable["chart_bars"] = (lambda kw: json.loads(chart_bars(**kw)), "code", True)
        batchable["stock_news"] = (lambda kw: json.loads(stock_news(**kw)), "code", True)

    count = 14
    return count


_REGULAR_TYPES = [("00", "지정가"), ("01", "시장가"), ("02", "조건부지정가"), ("03", "최유리지정가"), ("04", "최우선지정가")]
_AFTER_TYPES = [("41", "애프터 지정가"), ("44", "애프터 최유리지정가"), ("47", "애프터 최우선지정가")]


def _market_session(now=None) -> dict:
    """웹 콘솔 상단 표시(layout.js)와 같은 구간. 한국은 서머타임이 없어 UTC+9 고정."""
    from datetime import datetime, timezone

    kst = now or datetime.now(timezone(timedelta(hours=9)))
    t = kst.hour * 100 + kst.minute
    types = lambda pairs: [{"code": c, "label": l} for c, l in pairs]  # noqa: E731
    if kst.weekday() >= 5:
        s = ("closed", "휴장 (주말)", [], "예약주문(order_reserve_*, 실전 전용)은 접수할 수 있습니다.")
    elif 800 <= t < 850:
        s = ("pre", "NXT 프리마켓 (~08:50)", [], "프리마켓 주문 규칙은 KIS 안내를 확인하세요. 정규장 주문은 09:00 부터입니다.")
    elif 850 <= t < 900:
        s = ("auction", "장 시작 동시호가 (~09:00)", types(_REGULAR_TYPES + [("05", "장전 시간외")]), "")
    elif 900 <= t < 1520:
        s = ("regular", "정규장 (09:00~15:30)", types(_REGULAR_TYPES), "")
    elif 1520 <= t < 1530:
        s = ("auction", "장 마감 동시호가 (~15:30)", types([("00", "지정가"), ("01", "시장가")]), "")
    elif 1530 <= t < 2000:
        s = ("after", "NXT 애프터마켓 (15:30~20:00)", types(_AFTER_TYPES),
             "애프터마켓에는 애프터 전용 호가(41/44/47)만 받습니다. 모의투자는 NXT 를 지원하지 않습니다.")
    else:
        s = ("closed", "장 마감", [], "예약주문(order_reserve_*, 실전 전용)은 접수할 수 있습니다.")
    sid, label, order_types, note = s
    return {"now_kst": kst.strftime("%Y-%m-%d %H:%M (%a)"), "session": sid, "label": label,
            "order_types": order_types, "note": note or None}


def _summarize(r: dict, max_trades: int) -> dict:
    """백테스트 전체 결과 → 대화용 요약."""
    m, meta, s = r["metrics"], r["meta"], r["series"]
    dates, eq, bench = s["dates"], s["equity"], s["bench"]
    # 월말 자산 (그래프 대신 흐름을 말로 설명할 수 있게)
    monthly = []
    for i, d in enumerate(dates):
        if i == len(dates) - 1 or dates[i + 1][:7] != d[:7]:
            row = {"month": d[:7], "equity": eq[i]}
            if bench:
                row["benchmark"] = bench[i]
            monthly.append(row)
    trades = r["trades"]
    keep = ("entry_signal", "entry_date", "entry_price", "exit_signal", "exit_date", "exit_price", "qty", "pnl", "pnl_pct", "reason_label", "hold")
    slim = [{k: t.get(k) for k in keep} for t in trades]
    ranked = sorted(slim, key=lambda t: t["pnl_pct"] or 0)
    bench_label = meta["benchmark"]["label"] if meta.get("benchmark") else None
    return {
        "summary": {
            "strategy": meta["label"], "params": meta["params"], "code": meta["code"],
            "period": f"{meta['start']} ~ {meta['end']}", "bars": meta["bars"],
            "capital": meta["capital"], "final": meta["final"],
            "risk_pct": meta["risk"], "fee_pct": meta["fee"], "benchmark": bench_label,
            "data_sources": meta["sources"],
        },
        "metrics": {k: m.get(k) for k in ("total_return", "cagr", "max_drawdown", "sharpe", "total_trades", "win_rate",
                                         "profit_factor", "avg_win", "avg_loss", "benchmark_return")},
        "benchmark": m.get("bench"),
        "stats": r["stats"],
        "equity_monthly": monthly[-60:],
        "trades_total": len(slim),
        "trades_recent": slim[-max_trades:] if max_trades else [],
        "best_trades": ranked[-3:][::-1],
        "worst_trades": ranked[:3],
        "notes": "수익률·MDD·승률은 %, 금액은 원. 손익은 수수료·세금 반영. 실제 주문이 아닌 과거 데이터 시뮬레이션.",
    }
