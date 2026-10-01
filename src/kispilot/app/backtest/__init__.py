"""백테스트 엔진·전략·지표.

기본 전략 구성(골든크로스·모멘텀·52주 신고가·연속 상승/하락·이격도 등 프리셋)은 한국투자증권
open-trading-api 의 strategy_builder 를 참고해 새로 구현했다 (https://github.com/koreainvestment/open-trading-api).

    engine.py          단일 종목 풀포지션 시뮬레이터 (다음 봉 시가 체결, 손절/익절/트레일링)
    metrics.py         CAGR · MDD · 샤프 · 승률 · 손익비 · 벤치마크 수익률
    strategies.py      기본 전략 11종 (STRATEGIES)
    indicators_lib.py  커스텀 전략용 지표 카탈로그 (INDICATOR_CATALOG)
    custom_strategy.py 커스텀 전략 (지표 + 진입/청산 조건 + 리스크 + 비용)

웹 앱에서 쓰는 실행·저장 로직은 src/kispilot/app/utils/backtest.py 에 있다.
"""
from kispilot.app.backtest.engine import run_backtest, BacktestResult
from kispilot.app.backtest.strategies import STRATEGIES
from kispilot.app.backtest.indicators_lib import (
    INDICATOR_CATALOG,
    PRICE_FIELDS,
    compute_indicator,
    list_indicators,
)
from kispilot.app.backtest.custom_strategy import (
    CustomStrategy,
    IndicatorInstance,
    Operand,
    Condition,
    ConditionGroup,
    RiskRule,
    RiskSpec,
    COMPARE_OPERATORS,
    LOGIC_OPERATORS,
    RISK_KINDS,
    CUSTOM_STRATEGY_DIR,
    indicator_operand,
    price_operand,
    value_operand,
    build_options,
    list_saved_strategies,
)

__all__ = [
    "run_backtest", "BacktestResult", "STRATEGIES",
    "INDICATOR_CATALOG", "PRICE_FIELDS", "compute_indicator", "list_indicators",
    "CustomStrategy", "IndicatorInstance", "Operand", "Condition", "ConditionGroup",
    "RiskRule", "RiskSpec", "COMPARE_OPERATORS", "LOGIC_OPERATORS", "RISK_KINDS",
    "CUSTOM_STRATEGY_DIR", "indicator_operand", "price_operand", "value_operand",
    "build_options", "list_saved_strategies",
]
