# KISPilot

한국투자증권 Open API를 **AI 에이전트(MCP)** 와 **웹 콘솔**에서 쓰기 위한 도구 모음입니다.

> **비공식 프로젝트입니다.** 한국투자증권과 관계가 없으며, 한국투자증권이 만들거나 검증하지 않았습니다.
> 이 소프트웨어는 투자 조언이 아니며, 주문·백테스트 결과로 생긴 손실에 대해 책임지지 않습니다 (MIT 라이선스, 무보증).
> 실전 계좌로 쓰기 전에 모의투자로 충분히 확인하세요.

## 할 수 있는 것

- **조회** — 시세·호가·체결, 투자자·수급, 재무, 순위, 업종·지수, ETF, 계좌 잔고·손익 (KIS API 80여 개)
- **선물·옵션** — KOSPI200 선물·옵션(미니·위클리 포함) 주간·야간 전광판, 실시간 호가·체결, 차트
- **주문** — 현금·신용·예약 주문, 정정·취소 (에이전트는 모의투자가 기본, 실전은 2단계 확인)
- **차트** — 1분~년봉, 이동평균·볼린저·일목균형표 등 지표, 보조 차트 30여 종
- **백테스트** — 기본 전략 11종 + 지표 157개로 만드는 커스텀 전략, 여러 전략 비교, 여러 종목 포트폴리오
- **실시간** — KIS 웹소켓 체결·호가 (웹 콘솔)

## 빠른 시작

Python 3.11 이상이 필요합니다.

**1. 설치**

```bash
uv tool install kispilot      # 또는: pipx install kispilot / pip install kispilot
```

**2. 키 등록 (처음 한 번)** — [KIS Developers](https://apiportal.koreainvestment.com)에서 앱키·앱시크릿을 발급받은 뒤:

```bash
kispilot setup        # 실전 / 모의투자 / 둘 다 선택 → 앱키·시크릿·계좌 입력
```

앱키는 OS 키체인에 저장됩니다. **키를 AI 채팅창에 붙여넣지 마세요.**

**3. 쓰는 방법 고르기**

| 이렇게 쓰려면 | 실행 |
|---|---|
| 웹 화면에서 직접 보기 | `kispilot ui` → http://127.0.0.1:8000 |
| Claude 등 AI 에이전트에게 맡기기 | `kispilot install claude-desktop` (Claude Code · Cursor · VS Code · Gemini CLI · Codex 도 지원) 후 앱 다시 시작 |

## 안내 문서

| 문서 | 이럴 때 보세요 |
|---|---|
| [설치 · 키 등록](https://github.com/dongju923/kispilot/blob/main/docs/install.md) | 업데이트·삭제, 소스 설치, 서버처럼 키체인이 없는 환경, 데이터 저장 위치 |
| [웹 콘솔](https://github.com/dongju923/kispilot/blob/main/docs/web-console.md) | 화면마다 무엇을 볼 수 있는지, 다른 기기에서 접속하기 |
| [선물 · 옵션](https://github.com/dongju923/kispilot/blob/main/docs/futures-options.md) | KOSPI200 선물·옵션 전광판, 주간/야간, 알아 둘 점 |
| [AI 에이전트 (MCP)](https://github.com/dongju923/kispilot/blob/main/docs/mcp.md) | 클라이언트별 등록, 도구·프롬프트 목록, 직접 설정, 주문 안전장치 |

버전별 변경 내용은 [Releases](https://github.com/dongju923/kispilot/releases) 에 있습니다.

## 데이터 출처 · 참고

- [한국투자증권 Open API](https://apiportal.koreainvestment.com) — 모든 시세·계좌·주문 기능은 이 API 를 호출합니다.
- [yfinance](https://github.com/ranaroussi/yfinance) — 주식 과거 일봉·분봉 (Yahoo Finance, 개인적·연구 목적 이용 권장). 최근 거래일은 KIS API로 보강
- [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts) — 차트 (Apache-2.0)
- [koreainvestment/open-trading-api](https://github.com/koreainvestment/open-trading-api) — 백테스트 기본 전략 구성(프리셋 종류)과 종목 마스터 파일 형식(필드 폭·열 이름)을 참고했습니다.

## 라이선스

[MIT](https://github.com/dongju923/kispilot/blob/main/LICENSE)
