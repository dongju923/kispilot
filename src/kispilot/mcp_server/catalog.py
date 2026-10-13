"""경량 도구 모드 — 환경변수 KISPILOT_TOOLS=catalog.

MCP 클라이언트는 연결할 때 모든 도구의 이름·설명·입력 스키마를 대화에 싣는다 (KISPilot 은 100개 넘게, 5만 토큰 안팎).
Claude Code 처럼 도구를 필요할 때만 불러오는 클라이언트는 상관없지만, VS Code·Cursor·Gemini CLI·Codex 등은
질문마다 전체를 싣고, 도구 수 상한(예: 128개)에 걸리기도 한다.

catalog 모드에서는 도구를 서버에 모두 등록해 두되 목록에서는 숨기고, 아래 몇 개만 보여 준다.

    kis_find   도구 찾기 (이름·설명 검색, 빈 검색어면 분류별 전체 이름)
    kis_spec   도구 사용법 (설명 + 입력 스키마), 여러 개를 한 번에
    kis_call   숨긴 도구 실행 — 인자 검증·응답 줄이기(rows·fields)·호출 한도 처리는 원래 도구와 똑같다
    + 늘 보이는 도구: 종목 검색, 주문(매수·매도·정정·취소, 실전 주문 확인·버리기)

주문이나 저장된 전략 삭제처럼 되돌릴 수 없는 도구는 kis_call 로 부를 수 없다. 도구별 '위험' 표시가 있어야 클라이언트가
실행 전에 사용자 승인을 받기 때문이다. 그래서 자주 쓰는 주문 도구는 목록에 그대로 두고,
신용·예약 주문과 전략 삭제는 full 모드에서만 쓴다.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Optional

ENV = "KISPILOT_TOOLS"
MODES = ("full", "catalog")

# catalog 모드에서도 목록에 남기는 도구
VISIBLE = {
    "search_stock_code",
    "order_buy_cash", "order_sell_cash", "order_revise_order", "order_cancel_order",
    "order_confirm", "order_discard",
}

# 자주 쓰는 도구 — 검색 점수가 같으면 먼저 보이게
COMMON = {
    "price_inquire_price", "price_inquire_daily_price", "price_inquire_investor", "price_inquire_asking_price",
    "order_inquire_balance", "order_inquire_psbl_order", "order_inquire_daily_ccld", "chart_bars", "indicator_values",
    "stock_news", "batch_query", "market_session", "backtest_run", "ranking_anal_volume_rank", "ranking_anal_fluctuation",
    "sector_inquire_index_price", "info_financial_ratio",
}

# 검색에만 쓰는 낱말 (설명에 그 낱말이 없어 놓치기 쉬운 것)
ALIASES = {
    "chart_bars": "일봉 주봉 월봉 년봉 분봉 차트 캔들 시가 고가 저가 종가 OHLC",
    "price_inquire_investor": "수급 외인 외국인 기관 개인 투자자 순매수",
    "price_inquire_daily_price": "일봉 일별 시세",
    "order_inquire_balance": "잔고 보유 종목 평가손익 내 주식",
    "stock_news": "뉴스 기사 공시 소식",
    "market_session": "장 시간 장운영 개장 마감 동시호가 애프터마켓 프리마켓",
    "indicator_values": "보조지표 이동평균 이평 RSI MACD 볼린저",
}

# 이름 앞부분 → 분류 (kis_find 의 전체 목록용). 위에서부터 먼저 맞는 것.
CATEGORIES = [
    ("search_", "검색"), ("price_anal_", "시세 분석·수급"), ("price_", "시세"), ("ranking_anal_", "순위"),
    ("sector_", "업종·지수·뉴스 원본"), ("info_", "재무·기업정보"), ("account_", "계좌"), ("order_inquire_", "주문 조회"),
    ("order_", "주문"), ("futureoption_", "선물·옵션"), ("fo_", "선물·옵션"), ("backtest_", "백테스트"),
    ("indicator_", "차트·지표"), ("chart_", "차트·지표"), ("yf_", "차트·지표"), ("stock_news", "뉴스"),
    ("batch_query", "여러 종목 한 번에"), ("market_session", "장 구간"),
]

INSTRUCTIONS = """
[경량 도구 모드 (catalog)] 도구 목록에는 일부만 보인다. 나머지 100여 개는 이렇게 쓴다:
  1) kis_find(query) 로 도구를 찾는다 (예: "현재가", "외국인 순매수", "거래량 순위", "백테스트"). 검색어 없이 부르면 분류별 전체 이름.
  2) 처음 쓰는 도구는 kis_spec(names=[...]) 로 인자를 확인한다 (한 번에 여러 개 가능).
  3) kis_call(name, args) 로 실행한다. 이 안내와 도구 설명에 나오는 도구 이름(예: price_inquire_price, batch_query,
     backtest_run, stock_news)은 모두 kis_call 의 name 으로 부른다.
  주문(매수·매도·정정·취소·실전 주문 확인)은 목록에 있는 주문 도구를 직접 부른다 (kis_call 로는 안 된다).
  신용·예약 주문과 저장된 전략 삭제는 이 모드에서 쓸 수 없다 — 필요하면 사용자에게 KISPILOT_TOOLS=full 로 바꾸라고 안내한다."""


def mode() -> str:
    v = (os.getenv(ENV) or "full").strip().lower()
    if v not in MODES:
        print(f"[kispilot] {ENV}={v!r} 는 알 수 없는 값이라 full 로 실행합니다 ({' / '.join(MODES)}).", file=sys.stderr)
        return "full"
    return v


def _category(name: str) -> str:
    return next((label for prefix, label in CATEGORIES if name.startswith(prefix)), "기타")


def _first_line(text: str) -> str:
    return (text or "").strip().splitlines()[0][:120] if (text or "").strip() else ""


def _is_side_effect(tool) -> bool:
    """되돌릴 수 없는 일을 하는 도구 (주문, 저장된 전략 삭제). 클라이언트 승인 없이 실행되면 안 되므로 kis_call 로 부르지 않는다."""
    a = tool.annotations
    return bool(a and a.destructive_hint)


def apply(mcp, *, ToolError, to_json) -> int:
    """등록된 도구 중 VISIBLE 밖의 것을 목록에서 빼고 kis_find / kis_spec / kis_call 을 더한다. 숨긴 개수를 돌려준다."""
    manager = mcp._tool_manager
    hidden = {t.name: t for t in manager.list_tools() if t.name not in VISIBLE}
    for name in hidden:
        mcp.remove_tool(name)

    from mcp_types import ToolAnnotations

    read_only = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)

    def lookup(name: str):
        tool = hidden.get((name or "").strip())
        if tool is None:
            raise ToolError(f"없는 도구입니다: {name!r}. kis_find 로 이름을 찾으세요.")
        return tool

    @mcp.tool(annotations=read_only, structured_output=False)
    def kis_find(query: str = "", limit: int = 20) -> str:
        """KISPilot 도구를 찾는다 (이름·설명 검색). 찾은 도구는 kis_spec 으로 인자를 보고 kis_call 로 실행한다.

        Args:
            query: 찾을 내용. 공백으로 나눈 단어가 많이 맞는 순 (예: "현재가", "외국인 순매수", "거래량 순위", "옵션 전광판").
                비우면 분류별 전체 도구 이름을 돌려준다.
            limit: 최대 결과 수 (기본 20).

        Returns:
            검색어가 있으면 [{name, category, summary}], 없으면 {분류: [이름, ...]} JSON.
        """
        if not query.strip():
            groups: dict[str, list[str]] = {}
            for name in sorted(hidden):
                groups.setdefault(_category(name), []).append(name)
            return to_json({"tools": groups, "visible_tools": sorted(VISIBLE),
                            "next": "kis_spec(names=[...]) 로 인자를 보고 kis_call(name, args) 로 실행"})
        words = [w.lower() for w in query.split() if w.strip()]
        phrase = " ".join(words)
        scored = []
        for name, tool in hidden.items():
            low_name, summary = name.lower(), f"{_first_line(tool.description)} {ALIASES.get(name, '')}".lower()
            desc = (tool.description or "").lower()
            # 이름 > 첫 줄(요약) > 나머지 설명 순으로 무게를 두고, 검색어가 요약에 통째로 있으면 더 위로
            score = sum(3 if w in low_name else 2 if w in summary else 1 if w in desc else 0 for w in words)
            if len(words) > 1 and phrase in summary:
                score += 3
            if score:
                score += 0.5 if name in COMMON else 0
                score -= 2 if _is_side_effect(tool) else 0  # 주문 도구는 뒤로 (kis_call 로 못 부름)
                scored.append((score, len(summary), name, tool))
        scored.sort(key=lambda x: (-x[0], x[1], x[2]))  # 점수가 같으면 요약이 짧은(일반적인) 도구부터
        out = [{"name": n, "category": _category(n), "summary": _first_line(t.description)}
               for _, _, n, t in scored[:max(1, min(int(limit), 50))]]
        return to_json(out or {"result": [], "hint": "맞는 도구가 없습니다. 다른 낱말로 찾거나 query 를 비워 전체 목록을 보세요."})

    @mcp.tool(annotations=read_only, structured_output=False)
    def kis_spec(names: list[str]) -> str:
        """도구 사용법: 설명 전체와 입력 스키마(인자 이름·타입·기본값·필수 여부). kis_call 전에 처음 쓰는 도구만 본다.

        Args:
            names: 도구 이름 목록 (최대 5개). kis_find 결과의 name.

        Returns:
            [{name, description, input_schema, call_only_directly?}] JSON.
        """
        out = []
        for name in list(dict.fromkeys(names or []))[:5]:
            tool = lookup(name)
            item: dict[str, Any] = {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}
            if _is_side_effect(tool):
                item["call_only_directly"] = "주문·삭제처럼 되돌릴 수 없는 도구라 kis_call 로 부를 수 없습니다 (full 모드에서만 사용)."
            out.append(item)
        return to_json(out)

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True),
              structured_output=False)
    async def kis_call(name: str, args: Optional[dict[str, Any]] = None) -> str:
        """kis_find 로 찾은 도구를 실행한다 (조회·분석·백테스트. 주문은 불가 — 목록의 주문 도구를 직접 부른다).

        Args:
            name: 도구 이름 (예: "price_inquire_price").
            args: 그 도구의 인자 (예: {"code": "005930"}). KIS 조회 도구는 rows · fields 도 여기에 넣는다.

        Returns:
            그 도구의 응답 JSON 그대로.
        """
        tool = lookup(name)
        if _is_side_effect(tool):
            raise ToolError(f"{tool.name} 은(는) 주문·삭제처럼 되돌릴 수 없는 도구라 kis_call 로 부를 수 없습니다. "
                            "매수·매도·정정·취소는 목록의 order_* 도구를 직접 부르고, 그 밖의 것은 full 모드에서 쓰세요.")
        try:
            return await tool.run(args or {}, None)
        except ToolError as e:
            raise ToolError(f"{e} — 인자는 kis_spec(names=[{tool.name!r}]) 로 확인하세요.") from e

    return len(hidden)
