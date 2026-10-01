"""
커스텀 전략 빌더 — 백엔드 알고리즘.

전략은 5개 블록으로 구성된다:

1. 지표(indicators)  : ``indicators_lib.INDICATOR_CATALOG``의 지표를 인스턴스로 추가.
                       각 인스턴스에 전략 내 고유 ``id``(별칭)를 부여한다. 예) sma_5, sma_20
2. 진입(entry)       : 조건들의 묶음. 조건 = (좌변) (연산자) (우변).
3. 청산(exit)        : 진입과 동일 구조. 비워두면 리스크 규칙으로만 청산.
4. 리스크(risk)      : 손절 / 익절 / 트레일링 스탑. 각각 on/off + 비율(1~50%).
5. 정보(meta)        : 전략 이름 / 설명.

피연산자(operand) 종류
  - ``indicator`` : 위에서 추가한 지표 인스턴스 ``id`` 참조
  - ``price``     : 원본 가격 필드 (close / open / high / low / volume)
  - ``value``     : 상수 숫자

연산자(operator)
  - ``gt``         : 보다 클 때        ( > )
  - ``lt``         : 보다 작을 때      ( < )
  - ``gte``        : 이상일 때         ( >= )
  - ``lte``        : 이하일 때         ( <= )
  - ``cross_up``   : 상향 돌파할 때
  - ``cross_down`` : 하향 돌파할 때
  - ``eq``         : 와 같을 때        ( ≈ )

묶음 로직(logic)
  - ``and`` : 모든 조건 충족
  - ``or``  : 조건 중 하나라도 충족

조건은 "참이 된 그 시점(상태 전이)"에만 시그널을 발생시킨다 → 같은 조건이
여러 봉 연속 참이어도 신호는 한 번만 나간다.

``CustomStrategy.generate_signals(df)`` 는 ``engine.run_backtest`` 가 받는
1(매수) / -1(매도) / 0(관망) 시그널 Series 를 돌려준다.
``CustomStrategy.run(df, ...)`` 는 리스크 규칙까지 엔진에 전달해 백테스트를 실행한다.
``to_yaml / from_yaml / save_yaml / load_yaml`` 으로 YAML 저장·복원이 가능하다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from kispilot.app.backtest.indicators_lib import (
    INDICATOR_CATALOG,
    PRICE_FIELDS,
    coerce_params,
    compute_indicator,
)

try:  # YAML 저장/복원용 (pip install pyyaml)
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


# ── 상수 ─────────────────────────────────────────────────────

COMPARE_OPERATORS: dict[str, str] = {
    "gt": "보다 클 때 (>)",
    "lt": "보다 작을 때 (<)",
    "gte": "이상일 때 (>=)",
    "lte": "이하일 때 (<=)",
    "cross_up": "상향 돌파할 때",
    "cross_down": "하향 돌파할 때",
    "eq": "와 같을 때 (≈)",
}

CANDLE_SIGNALS: dict[str, str] = {
    "bullish": "강세 신호 (> 0)",
    "bearish": "약세 신호 (< 0)",
    "detected": "패턴 감지 (!= 0)",
}

LOGIC_OPERATORS: dict[str, str] = {
    "and": "모든 조건 충족 (AND)",
    "or": "조건 중 하나라도 충족 (OR)",
}

RISK_KINDS: dict[str, str] = {
    "stop_loss": "손절 (진입가 대비 하락)",
    "take_profit": "익절 (진입가 대비 상승)",
    "trailing_stop": "트레일링 스탑 (보유 중 고점 대비 하락)",
}

RISK_PCT_MIN = 1.0
RISK_PCT_MAX = 50.0

# 커스텀 전략 기본 저장 위치 (pykis_ui: Cache/custom_strategies — 웹 앱은 JSON 으로 저장한다)
from kispilot.api.config import BASE_CACHE_PATH  # noqa: E402

CUSTOM_STRATEGY_DIR = os.path.join(BASE_CACHE_PATH, "custom_strategies")


# ── 데이터 구조 ──────────────────────────────────────────────

@dataclass
class IndicatorInstance:
    """전략에 추가된 지표 하나 (카탈로그 지표 + 파라미터 + 별칭)."""
    id: str                       # 전략 내 고유 별칭, 예: "sma_5"
    indicator: str                # 카탈로그 키, 예: "sma"
    params: dict[str, Any] = field(default_factory=dict)
    label: str = ""               # 표시용 라벨 (선택)

    def resolved_params(self) -> dict[str, Any]:
        return coerce_params(self.indicator, self.params)

    def to_dict(self) -> dict:
        d = {"id": self.id, "indicator": self.indicator, "params": self.resolved_params()}
        if self.label:
            d["label"] = self.label
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "IndicatorInstance":
        return cls(id=str(d["id"]), indicator=str(d["indicator"]),
                   params=dict(d.get("params") or {}), label=str(d.get("label") or ""))


@dataclass
class Operand:
    """조건의 좌변/우변 피연산자."""
    type: str                     # "indicator" | "price" | "value"
    ref: str = ""                 # type == "indicator" 일 때 지표 인스턴스 id
    field: str = "close"          # type == "price" 일 때 가격 필드
    value: float = 0.0            # type == "value" 일 때 상수

    def to_dict(self) -> dict:
        if self.type == "indicator":
            return {"type": "indicator", "ref": self.ref}
        if self.type == "price":
            return {"type": "price", "field": self.field}
        return {"type": "value", "value": float(self.value)}

    @classmethod
    def from_dict(cls, d: dict) -> "Operand":
        t = str(d.get("type"))
        if t == "indicator":
            return cls(type="indicator", ref=str(d.get("ref", "")))
        if t == "price":
            return cls(type="price", field=str(d.get("field", "close")))
        if t == "value":
            return cls(type="value", value=float(d.get("value", 0.0)))
        raise ValueError(f"알 수 없는 operand type: {t}")


# 피연산자 생성 헬퍼
def indicator_operand(ref: str) -> Operand:
    return Operand(type="indicator", ref=ref)


def price_operand(field: str = "close") -> Operand:
    return Operand(type="price", field=field)


def value_operand(value: float) -> Operand:
    return Operand(type="value", value=float(value))


@dataclass
class Condition:
    """단일 조건: 좌변 (연산자) 우변 또는 캔들스틱 신호 조건."""
    left: Operand
    operator: str                        # COMPARE_OPERATORS 키 (candle_signal 사용 시 무시)
    right: Operand
    candle_signal: str | None = None     # None 또는 CANDLE_SIGNALS 키

    def to_dict(self) -> dict:
        d = {"left": self.left.to_dict(), "operator": self.operator, "right": self.right.to_dict()}
        if self.candle_signal:
            d["candle_signal"] = self.candle_signal
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Condition":
        right_raw = d.get("right") or {"type": "value", "value": 0}
        return cls(
            left=Operand.from_dict(d["left"]),
            operator=str(d.get("operator", "")),
            right=Operand.from_dict(right_raw),
            candle_signal=d.get("candle_signal") or None,
        )


@dataclass
class ConditionGroup:
    """조건들의 묶음 (AND / OR)."""
    logic: str = "and"            # "and" | "or"
    conditions: list[Condition] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"logic": self.logic, "conditions": [c.to_dict() for c in self.conditions]}

    @classmethod
    def from_dict(cls, d: dict | None) -> "ConditionGroup":
        d = d or {}
        return cls(logic=str(d.get("logic", "and")),
                   conditions=[Condition.from_dict(c) for c in (d.get("conditions") or [])])

    def add(self, left: Operand, operator: str, right: Operand,
            candle_signal: str | None = None) -> "ConditionGroup":
        self.conditions.append(Condition(left, operator, right, candle_signal))
        return self


@dataclass
class FeeSpec:
    """수수료 / 거래세 / 슬리피지 (% 단위 저장)."""
    commission: float = 0.147   # 0.147%
    tax: float = 0.2            # 0.2%
    slippage: float = 0.1       # 0.1%

    def to_dict(self) -> dict:
        return {"commission": self.commission, "tax": self.tax, "slippage": self.slippage}

    @classmethod
    def from_dict(cls, d: dict | None) -> "FeeSpec":
        d = d or {}
        return cls(
            commission=float(d.get("commission", 0.147)),
            tax=float(d.get("tax", 0.2)),
            slippage=float(d.get("slippage", 0.1)),
        )

    def engine_kwargs(self) -> dict[str, float]:
        return {
            "commission": self.commission / 100,
            "tax": self.tax / 100,
            "slippage": self.slippage / 100,
        }


@dataclass
class RiskRule:
    enabled: bool = False
    pct: float = 5.0

    def to_dict(self) -> dict:
        return {"enabled": bool(self.enabled), "pct": float(self.pct)}

    @classmethod
    def from_dict(cls, d: dict | None, default_pct: float = 5.0) -> "RiskRule":
        d = d or {}
        return cls(enabled=bool(d.get("enabled", False)), pct=float(d.get("pct", default_pct)))


@dataclass
class RiskSpec:
    """손절 / 익절 / 트레일링 스탑."""
    stop_loss: RiskRule = field(default_factory=lambda: RiskRule(False, 5.0))
    take_profit: RiskRule = field(default_factory=lambda: RiskRule(False, 10.0))
    trailing_stop: RiskRule = field(default_factory=lambda: RiskRule(False, 5.0))

    def to_dict(self) -> dict:
        return {
            "stop_loss": self.stop_loss.to_dict(),
            "take_profit": self.take_profit.to_dict(),
            "trailing_stop": self.trailing_stop.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "RiskSpec":
        d = d or {}
        return cls(
            stop_loss=RiskRule.from_dict(d.get("stop_loss"), 5.0),
            take_profit=RiskRule.from_dict(d.get("take_profit"), 10.0),
            trailing_stop=RiskRule.from_dict(d.get("trailing_stop"), 5.0),
        )

    def engine_kwargs(self) -> dict[str, float | None]:
        return {
            "stop_loss_pct": self.stop_loss.pct if self.stop_loss.enabled else None,
            "take_profit_pct": self.take_profit.pct if self.take_profit.enabled else None,
            "trailing_stop_pct": self.trailing_stop.pct if self.trailing_stop.enabled else None,
        }


@dataclass
class CustomStrategy:
    """사용자 정의 전략 전체."""
    name: str = "나의 커스텀 전략"
    description: str = ""
    indicators: list[IndicatorInstance] = field(default_factory=list)
    entry: ConditionGroup = field(default_factory=ConditionGroup)
    exit: ConditionGroup = field(default_factory=ConditionGroup)
    risk: RiskSpec = field(default_factory=RiskSpec)
    fee: FeeSpec = field(default_factory=FeeSpec)
    version: int = 1

    # ── 빌더 편의 메서드 ──────────────────────────────────────

    def add_indicator(self, indicator: str, params: dict | None = None,
                      instance_id: str | None = None, label: str = "") -> str:
        """지표를 추가하고 부여된 인스턴스 id 를 반환한다."""
        if indicator not in INDICATOR_CATALOG:
            raise KeyError(f"알 수 없는 지표: {indicator}")
        params = coerce_params(indicator, params)
        if instance_id is None:
            instance_id = self._auto_id(indicator, params)
        if any(i.id == instance_id for i in self.indicators):
            raise ValueError(f"이미 사용 중인 지표 id: {instance_id}")
        self.indicators.append(IndicatorInstance(id=instance_id, indicator=indicator,
                                                 params=params, label=label))
        return instance_id

    def _auto_id(self, indicator: str, params: dict) -> str:
        # period 가 있으면 sma_5 처럼, 없으면 rsi / rsi_2 처럼
        period = params.get("period")
        base = f"{indicator}_{int(period)}" if isinstance(period, (int, float)) else indicator
        candidate, n = base, 2
        existing = {i.id for i in self.indicators}
        while candidate in existing:
            candidate = f"{base}_{n}"
            n += 1
        return candidate

    def get_indicator(self, instance_id: str) -> IndicatorInstance | None:
        return next((i for i in self.indicators if i.id == instance_id), None)

    # ── 검증 ────────────────────────────────────────────────

    def validate(self) -> list[str]:
        """전략 설정의 오류 목록을 반환한다 (빈 리스트면 정상)."""
        errs: list[str] = []
        if not str(self.name).strip():
            errs.append("전략 이름이 비어 있습니다.")

        ids = [i.id for i in self.indicators]
        if len(ids) != len(set(ids)):
            errs.append("지표 id 가 중복되었습니다.")
        for inst in self.indicators:
            if inst.indicator not in INDICATOR_CATALOG:
                errs.append(f"알 수 없는 지표: {inst.indicator} (id={inst.id})")

        known_ids = set(ids)

        ind_category: dict[str, str] = {
            inst.id: INDICATOR_CATALOG.get(inst.indicator, {}).get("category", "")
            for inst in self.indicators
        }

        def _check_group(group: ConditionGroup, where: str, required: bool) -> None:
            if group.logic not in LOGIC_OPERATORS:
                errs.append(f"{where}: 알 수 없는 묶음 로직 '{group.logic}'")
            if required and not group.conditions:
                errs.append(f"{where} 조건이 하나도 없습니다.")
            for k, c in enumerate(group.conditions, 1):
                if c.candle_signal is not None:
                    # 캔들스틱 조건 검증
                    if c.candle_signal not in CANDLE_SIGNALS:
                        errs.append(f"{where} #{k}: 알 수 없는 캔들스틱 신호 '{c.candle_signal}'")
                    if c.left.type != "indicator":
                        errs.append(f"{where} #{k}: 캔들스틱 조건의 좌변은 지표여야 합니다.")
                    elif c.left.ref not in known_ids:
                        errs.append(f"{where} #{k} 좌변: 존재하지 않는 지표 id '{c.left.ref}'")
                    elif ind_category.get(c.left.ref) != "캔들스틱":
                        errs.append(f"{where} #{k}: '{c.left.ref}'은 캔들스틱 지표가 아닙니다.")
                else:
                    if c.operator not in COMPARE_OPERATORS:
                        errs.append(f"{where} #{k}: 알 수 없는 연산자 '{c.operator}'")
                    for side, o in (("좌변", c.left), ("우변", c.right)):
                        if o.type == "indicator":
                            if o.ref not in known_ids:
                                errs.append(f"{where} #{k} {side}: 존재하지 않는 지표 id '{o.ref}'")
                        elif o.type == "price":
                            if o.field not in PRICE_FIELDS:
                                errs.append(f"{where} #{k} {side}: 알 수 없는 가격 필드 '{o.field}'")
                        elif o.type == "value":
                            if not np.isfinite(o.value):
                                errs.append(f"{where} #{k} {side}: 잘못된 상수값")
                        else:
                            errs.append(f"{where} #{k} {side}: 알 수 없는 operand type '{o.type}'")

        _check_group(self.entry, "진입", required=True)
        _check_group(self.exit, "청산", required=False)

        if not self.exit.conditions and not any(
            r.enabled for r in (self.risk.stop_loss, self.risk.take_profit, self.risk.trailing_stop)
        ):
            errs.append("청산 조건도, 리스크 규칙(손절/익절/트레일링)도 없습니다. 포지션을 빠져나갈 방법이 없습니다.")

        for kind, rule in (("손절", self.risk.stop_loss), ("익절", self.risk.take_profit),
                           ("트레일링 스탑", self.risk.trailing_stop)):
            if rule.enabled and not (RISK_PCT_MIN <= rule.pct <= RISK_PCT_MAX):
                errs.append(f"{kind} 비율은 {RISK_PCT_MIN:g}% ~ {RISK_PCT_MAX:g}% 사이여야 합니다 (현재 {rule.pct}%).")
        return errs

    # ── 시그널 / 백테스트 ────────────────────────────────────

    def _indicator_series(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        return {inst.id: compute_indicator(df, inst.indicator, inst.params) for inst in self.indicators}

    def generate_signals(self, df: pd.DataFrame) -> pd.Series:
        """1(매수) / -1(매도) / 0(관망) 시그널 Series 생성.

        같은 봉에서 진입·청산 조건이 동시에 참이면 청산(-1)이 우선한다.
        엔진은 보유 상태에 따라 알아서 무시하므로 안전하다.
        """
        errs = self.validate()
        # validate 가 잡는 것 중 '청산 없음/리스크 없음'은 시그널 계산 자체엔 문제 없으므로 제외
        blocking = [e for e in errs if "포지션을 빠져나갈 방법" not in e]
        if blocking:
            raise ValueError("전략 설정 오류: " + " / ".join(blocking))

        series_map = self._indicator_series(df)
        entry_mask = _eval_group(self.entry, df, series_map)
        exit_mask = _eval_group(self.exit, df, series_map)

        entry_edge = entry_mask & ~entry_mask.shift(1, fill_value=False)
        exit_edge = exit_mask & ~exit_mask.shift(1, fill_value=False)

        sig = pd.Series(0, index=df.index, dtype=int)
        sig[entry_edge] = 1
        sig[exit_edge] = -1
        return sig

    def run(self, df: pd.DataFrame, **engine_kwargs):
        """리스크 규칙 + 수수료/세금/슬리피지를 적용해 ``run_backtest`` 를 실행한다."""
        from kispilot.app.backtest.engine import run_backtest
        signals = self.generate_signals(df)
        kwargs = dict(self.fee.engine_kwargs())
        kwargs.update(self.risk.engine_kwargs())
        kwargs.update(engine_kwargs)
        return run_backtest(df, signals, **kwargs)

    # ── 직렬화 ──────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "version": int(self.version),
            "name": str(self.name),
            "description": str(self.description),
            "indicators": [i.to_dict() for i in self.indicators],
            "entry": self.entry.to_dict(),
            "exit": self.exit.to_dict(),
            "risk": self.risk.to_dict(),
            "fee": self.fee.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CustomStrategy":
        d = d or {}
        return cls(
            name=str(d.get("name", "나의 커스텀 전략")),
            description=str(d.get("description", "")),
            indicators=[IndicatorInstance.from_dict(x) for x in (d.get("indicators") or [])],
            entry=ConditionGroup.from_dict(d.get("entry")),
            exit=ConditionGroup.from_dict(d.get("exit")),
            risk=RiskSpec.from_dict(d.get("risk")),
            fee=FeeSpec.from_dict(d.get("fee")),
            version=int(d.get("version", 1)),
        )

    def to_yaml(self) -> str:
        if yaml is None:
            raise RuntimeError("PyYAML 이 설치되어 있지 않습니다. `pip install pyyaml` 후 다시 시도하세요.")
        return yaml.safe_dump(self.to_dict(), allow_unicode=True, sort_keys=False)

    @classmethod
    def from_yaml(cls, text: str) -> "CustomStrategy":
        if yaml is None:
            raise RuntimeError("PyYAML 이 설치되어 있지 않습니다. `pip install pyyaml` 후 다시 시도하세요.")
        return cls.from_dict(yaml.safe_load(text) or {})

    def save_yaml(self, path: str | None = None, *, overwrite: bool = True) -> str:
        """YAML 파일로 저장하고 저장 경로를 반환한다.

        path 가 None 이면 ``CUSTOM_STRATEGY_DIR/<safe_name>.yaml`` 에 저장한다.
        """
        if path is None:
            os.makedirs(CUSTOM_STRATEGY_DIR, exist_ok=True)
            path = os.path.join(CUSTOM_STRATEGY_DIR, _safe_filename(self.name) + ".yaml")
        else:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        if not overwrite and os.path.exists(path):
            raise FileExistsError(path)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_yaml())
        return path

    @classmethod
    def load_yaml(cls, path: str) -> "CustomStrategy":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_yaml(f.read())


# ── 조건 평가 (내부) ─────────────────────────────────────────

def _to_series(x: Any, index: pd.Index) -> pd.Series:
    if isinstance(x, pd.Series):
        return x.astype(float)
    return pd.Series(float(x), index=index)


def _resolve_operand(op: Operand, df: pd.DataFrame, series_map: dict[str, pd.Series]) -> pd.Series | float:
    if op.type == "value":
        return float(op.value)
    if op.type == "price":
        if op.field not in PRICE_FIELDS:
            raise KeyError(f"알 수 없는 가격 필드: {op.field}")
        return df[op.field].astype(float)
    if op.type == "indicator":
        if op.ref not in series_map:
            raise KeyError(f"존재하지 않는 지표 id: {op.ref}")
        return series_map[op.ref]
    raise ValueError(f"알 수 없는 operand type: {op.type}")


def _eval_condition(cond: Condition, df: pd.DataFrame, series_map: dict[str, pd.Series]) -> pd.Series:
    if cond.candle_signal is not None:
        # 캔들스틱 패턴 신호 조건 (+1 강세 / -1 약세 / 0 미감지)
        series = _to_series(_resolve_operand(cond.left, df, series_map), df.index)
        sig = cond.candle_signal
        if sig == "bullish":
            m = series > 0
        elif sig == "bearish":
            m = series < 0
        else:  # "detected"
            m = series != 0
        return pd.Series(m, index=df.index).fillna(False).astype(bool)

    left = _to_series(_resolve_operand(cond.left, df, series_map), df.index)
    right = _to_series(_resolve_operand(cond.right, df, series_map), df.index)
    op = cond.operator
    if op == "gt":
        m = left > right
    elif op == "lt":
        m = left < right
    elif op == "gte":
        m = left >= right
    elif op == "lte":
        m = left <= right
    elif op == "eq":
        m = pd.Series(np.isclose(left.values, right.values, equal_nan=False), index=df.index)
    elif op == "cross_up":   # 좌변이 우변을 상향 돌파
        m = (left > right) & (left.shift(1) <= right.shift(1))
    elif op == "cross_down":  # 좌변이 우변을 하향 돌파
        m = (left < right) & (left.shift(1) >= right.shift(1))
    else:
        raise ValueError(f"알 수 없는 연산자: {op}")
    return pd.Series(m, index=df.index).fillna(False).astype(bool)


def _eval_group(group: ConditionGroup, df: pd.DataFrame, series_map: dict[str, pd.Series]) -> pd.Series:
    if not group.conditions:
        return pd.Series(False, index=df.index)
    masks = [_eval_condition(c, df, series_map) for c in group.conditions]
    out = masks[0]
    for m in masks[1:]:
        out = (out & m) if group.logic != "or" else (out | m)
    return out


# ── 유틸 ─────────────────────────────────────────────────────

def _safe_filename(name: str) -> str:
    keep = "".join(c if (c.isalnum() or c in (" ", "_", "-")) else "_" for c in str(name).strip())
    return ("_".join(keep.split()) or "custom_strategy")[:80]


def list_saved_strategies(directory: str | None = None) -> list[dict[str, str]]:
    """저장된 커스텀 전략 YAML 목록 ({name, description, path})."""
    directory = directory or CUSTOM_STRATEGY_DIR
    if not os.path.isdir(directory):
        return []
    out: list[dict[str, str]] = []
    for fn in sorted(os.listdir(directory)):
        if not fn.lower().endswith((".yaml", ".yml")):
            continue
        path = os.path.join(directory, fn)
        try:
            strat = CustomStrategy.load_yaml(path)
            out.append({"name": strat.name, "description": strat.description, "path": path})
        except Exception:
            out.append({"name": fn, "description": "(읽기 실패)", "path": path})
    return out


# ── 카탈로그 노출 (프런트엔드 "지표 추가" 등에서 사용) ────────

def build_options() -> dict[str, Any]:
    """프런트엔드가 빌더 UI를 구성하는 데 필요한 메타데이터 일체."""
    from kispilot.app.backtest.indicators_lib import list_indicators
    fee_default = FeeSpec()
    return {
        "indicators": list_indicators(),
        "price_fields": [{"key": k, "label": v} for k, v in PRICE_FIELDS.items()],
        "operators": [{"key": k, "label": v} for k, v in COMPARE_OPERATORS.items()],
        "candle_signals": [{"key": k, "label": v} for k, v in CANDLE_SIGNALS.items()],
        "logics": [{"key": k, "label": v} for k, v in LOGIC_OPERATORS.items()],
        "risk_kinds": [{"key": k, "label": v} for k, v in RISK_KINDS.items()],
        "risk_pct_range": {"min": RISK_PCT_MIN, "max": RISK_PCT_MAX},
        "fee_defaults": fee_default.to_dict(),
    }
