# KISPilot

한국투자증권 Open API를 **AI 에이전트(MCP)** 와 **웹 콘솔**에서 쓰기 위한 도구 모음입니다.

> **비공식 프로젝트입니다.** 한국투자증권과 관계가 없으며, 한국투자증권이 만들거나 검증하지 않았습니다.
> 이 소프트웨어는 투자 조언이 아니며, 주문·백테스트 결과로 생긴 손실에 대해 책임지지 않습니다 (MIT 라이선스, 무보증).
> 실전 계좌로 쓰기 전에 모의투자로 충분히 확인하세요.

## 할 수 있는 것

- **조회** — 시세·호가·체결, 투자자·수급, 재무, 순위, 업종·지수, ETF, 계좌 잔고·손익 (KIS API 80여 개)
- **주문** — 현금·신용·예약 주문, 정정·취소 (에이전트는 모의투자가 기본, 실전은 2단계 확인)
- **차트** — 1분~년봉, 이동평균·볼린저·일목균형표 등 지표, 보조 차트 30여 종
- **백테스트** — 기본 전략 11종 + 지표 157개로 만드는 커스텀 전략, 벤치마크 비교, 거래 내역
- **실시간** — KIS 웹소켓 체결·호가 (웹 콘솔)

## 설치

Python 3.11 이상이 필요합니다.

**추천** — 도구 전용 환경에 설치되고 `kispilot` 명령이 PATH 에 자동으로 등록됩니다.

```bash
uv tool install kispilot      # 또는: pipx install kispilot
```

일반 `pip` 로도 설치할 수 있습니다. 가상환경·conda 를 켠 상태에서 설치하면 그 환경을 켰을 때만 `kispilot` 명령이 보입니다.

```bash
pip install kispilot
```

설치 없이 바로 실행 (`uv` 필요):

```bash
uvx kispilot ui
```

| 할 일 | uv | pipx | pip |
|---|---|---|---|
| 업데이트 | `uv tool upgrade kispilot` | `pipx upgrade kispilot` | `pip install -U kispilot` |
| 특정 버전 | `uv tool install kispilot==0.1.0` | `pipx install kispilot==0.1.0` | `pip install kispilot==0.1.0` |
| 삭제 | `uv tool uninstall kispilot` | `pipx uninstall kispilot` | `pip uninstall kispilot` |

버전별 변경 내용은 [Releases](https://github.com/dongju923/kispilot/releases) 에 있습니다.

소스에서 개발용으로 설치하려면:

```bash
git clone https://github.com/dongju923/kispilot
cd kispilot
pip install -e .
```

## 키 등록 (처음 한 번)

[KIS Developers](https://apiportal.koreainvestment.com)에서 앱키·앱시크릿을 발급받은 뒤 터미널에서 실행합니다.

```bash
kispilot setup        # 실전 / 모의투자 / 둘 다 선택 → 앱키·시크릿·계좌 입력
kispilot status       # 등록 상태 확인 (값은 가려서 표시)
```

- 앱키·시크릿은 **OS 키체인**(Windows 자격 증명 관리자, macOS 키체인, Linux Secret Service)에 저장됩니다. 파일에 평문으로 남지 않습니다.
- 입력은 화면에 보이지 않고, 저장 전에 실제로 토큰을 발급해 키가 맞는지 확인합니다.
- **키를 AI 채팅창에 붙여넣지 마세요.** 채팅 내용은 대화 기록과 AI 서비스 쪽에 남습니다.
- 지우려면 `kispilot logout` (키체인 삭제 + 토큰 폐기).

키체인을 쓸 수 없는 환경(서버 등)에서는 환경변수로 넣을 수 있습니다. 환경변수가 키체인보다 먼저 쓰입니다.
변수 이름은 [.env.example](https://github.com/dongju923/kispilot/blob/main/.env.example)을 참고하여, .env 파일을 새로 생성하세요.

## 웹 콘솔

```bash
kispilot ui           # http://127.0.0.1:8000
```

대시보드, 시장·업종, 순위, 종목 분석(차트·호가·수급·재무), ETF, 주문, 계좌, 백테스트 화면이 있습니다.
같은 PC에서만 접속되도록 127.0.0.1에 열립니다.

## AI 에이전트에서 쓰기 (MCP)

KISPilot 은 공개 표준인 MCP(Model Context Protocol) 서버라서, 내 PC 에서 MCP 서버를 실행할 수 있는 AI 클라이언트라면 어디서나 쓸 수 있습니다.
명령 한 줄로 등록합니다. 설정 파일은 이 명령이 대신 써 줍니다.

```bash
kispilot install claude-desktop   # Claude Desktop 앱
kispilot install claude-code      # Claude Code (내 계정 전체, 어느 폴더에서나)
kispilot install cursor           # Cursor
kispilot install vscode           # VS Code (GitHub Copilot 에이전트 모드)
kispilot install gemini           # Gemini CLI
kispilot install codex            # OpenAI Codex (CLI · IDE 확장)
```

| 대상 | 고치는 설정 | 연결 확인 |
|---|---|---|
| `claude-desktop` | `claude_desktop_config.json` | 트레이 아이콘 → 종료 후 다시 켜기, 설정 → 개발자 |
| `claude-code` | `claude mcp add --scope user` | `claude mcp list` |
| `cursor` | `~/.cursor/mcp.json` | Cursor 다시 시작, 설정의 MCP 항목 |
| `vscode` | 사용자 프로필의 `mcp.json` | Copilot 채팅 에이전트 모드, 명령 팔레트 → `MCP: List Servers` |
| `gemini` | `~/.gemini/settings.json` | `gemini` 실행 후 `/mcp` |
| `codex` | `~/.codex/config.toml` | `codex mcp list` |

- 등록한 뒤 해당 앱을 다시 시작하면 연결됩니다.
- 지금 설치된 `kispilot` 실행 파일의 전체 경로로 등록하므로 PATH 설정이 필요 없습니다.
- 설정 파일은 바꾸기 전에 `<파일이름>.bak-날짜` 로 백업하고, 다른 항목은 건드리지 않습니다.
  주석이 들어간 JSON 처럼 읽을 수 없는 파일은 고치지 않고 알려 줍니다 (아래 "직접 설정" 참고).
- 실전 주문은 꺼진 상태로 등록됩니다. 켜려면 `--allow-real-orders` 를 붙입니다 (아래 안전장치 참고).
- 바뀔 내용만 보려면 `--dry-run`, 설정 파일 위치를 바꾸려면 `--config <경로>`, 해제는 `kispilot uninstall <대상>`.
- 동작 확인: `kispilot mcp --check`

ChatGPT·Gemini 웹처럼 브라우저에서 쓰는 서비스는 내 PC 의 프로그램을 실행할 수 없어서 지금은 연결되지 않습니다
(인터넷에 공개된 원격 MCP 서버가 필요합니다).

### MCP 도구 (97개)

| 묶음 | 도구 |
|---|---|
| 시세·분석·순위·업종·재무·계좌 | KIS API 조회 도구 (`price_*`, `price_anal_*`, `ranking_anal_*`, `sector_*`, `info_*`, `account_*`, `order_inquire_*`) |
| 주문 | `order_buy_cash` 등 (모의투자 기본), 실전 주문 확인 `order_confirm` · 취소 `order_discard`, 지금 장 구간·호가 유형 `market_session` |
| 검색 | `search_stock_code`, `search_sector_code` |
| 여러 종목 한 번에 | `batch_query` — 조회 도구 하나를 최대 50종목에 돌려 표 하나로 (예: 거래대금 상위 30종목의 최근 3일 외국인 순매수) |
| 백테스트 | `backtest_options`, `backtest_indicator_catalog`, `backtest_run`, `backtest_strategy_validate` / `list` / `load` / `save` / `delete` |
| 지표·차트 | `indicator_values` (RSI·MACD 등 최근 값), `chart_bars` (일·주·월·년봉), `yf_get_history` |
| 뉴스 | `stock_news` — 주식 관련 기사 제목만 (종목코드를 주면 그 종목 기사), 제목 검색 링크 포함 |

예: "삼성전자 최근 5년 골든크로스(5/20) 백테스트, 손절 7% 익절 20%로 해줘", "SK하이닉스 RSI랑 20일선 지금 얼마야?"

대화 길이를 아끼도록 KIS 조회 도구는 응답을 줄여서 돌려줍니다.

- 목록은 `{cols, rows}` 표 형식으로 옵니다 (행마다 필드 이름을 반복하지 않음).
- 일자별 목록은 기본으로 최근 7줄만 옵니다. 순위·잔고처럼 날짜가 없는 목록, 분봉·체결 같은 장중 목록, 시작일을 지정하는 조회는 전부 옵니다.
- 공통 인자 `rows`(줄 수, `0` 이면 전부)와 `fields`(남길 필드)로 에이전트가 필요한 만큼만 받습니다.

### MCP 프롬프트 (작업 템플릿)

자주 하는 작업의 진행 순서를 담은 템플릿입니다. 고르는 방법은 클라이언트마다 다릅니다:
Claude Desktop 은 입력창의 `+` 메뉴, Claude Code 는 `/kispilot:<이름>`, Gemini CLI 는 `/<이름>`, VS Code 는 `/kispilot.<이름>`.
프롬프트를 지원하지 않는 클라이언트도 있는데, 그때는 "오늘 시장 브리핑해 줘" 처럼 말로 요청하면 됩니다. 칸을 비워 두면 대화로 물어봅니다.

| 프롬프트 | 하는 일 |
|---|---|
| 오늘 시장 브리핑 (`market_briefing`) | 지수 · 투자자 수급 · 강한/약한 업종 · 등락률/거래량 상위 · 주요 뉴스 |
| 종목 종합 분석 (`stock_analysis`) | 시세 · 추세(이동평균·RSI·MACD·볼린저) · 수급 · 재무 · 긍정/위험 신호 |
| 백테스트 마법사 (`backtest_wizard`) | 전략 선택 → 실행 → 지수 대비 해석 → 파라미터 비교 → 저장 |
| 전략 만들기 (`strategy_builder`) | 말로 설명한 아이디어 → 커스텀 전략 JSON → 검증 → 백테스트 → 저장 |
| 주문 도우미 (`order_assistant`) | 장 구간 확인 → 시세·주문 가능 수량 → 주문 내용 확인 → (실전) 2단계 승인 |
| 보유 종목 점검 (`portfolio_review`) | 잔고 · 손익 · 종목별 추세/지표 · 쏠림 점검 (주문 안 함) |

<details>
<summary>직접 설정하려면</summary>

등록되는 내용은 "MCP 서버를 `kispilot mcp` 명령으로 실행하라" 는 한 항목입니다.
이 명령은 AI 클라이언트가 실행해서 표준 입출력으로 대화하므로, 터미널에서 직접 치면 아무것도 출력하지 않고 기다리는 것이 정상입니다.

Claude Desktop · Claude Code(`.mcp.json`) · Cursor · Gemini CLI (`mcpServers`):

```json
{
  "mcpServers": {
    "kispilot": {
      "command": "<kispilot 실행 파일 전체 경로>",
      "args": ["mcp"],
      "env": { "KIS_ALLOW_REAL_ORDERS": "0" }
    }
  }
}
```

VS Code (`mcp.json`, 최상위 키가 `servers`):

```json
{
  "servers": {
    "kispilot": {
      "type": "stdio",
      "command": "<kispilot 실행 파일 전체 경로>",
      "args": ["mcp"],
      "env": { "KIS_ALLOW_REAL_ORDERS": "0" }
    }
  }
}
```

Codex (`~/.codex/config.toml`):

```toml
[mcp_servers.kispilot]
command = "<kispilot 실행 파일 전체 경로>"
args = ["mcp"]
startup_timeout_sec = 30

[mcp_servers.kispilot.env]
KIS_ALLOW_REAL_ORDERS = "0"
```

- 실행 파일 경로: Windows `where kispilot`, macOS·Linux `which kispilot` (Windows 경로의 `\` 는 `/` 로 바꾸거나 JSON·TOML 에서는 `\\` 로 적습니다)
- Claude Desktop: 설정 → 개발자 → 구성 편집 (`claude_desktop_config.json`)
- Claude Code: 프로젝트 폴더의 `.mcp.json` (예시: [.mcp.json.example](https://github.com/dongju923/kispilot/blob/main/.mcp.json.example))
- 그 밖의 MCP 클라이언트(Windsurf, Cline, LM Studio 등)도 같은 `command` · `args` · `env` 를 각자의 MCP 설정에 넣으면 됩니다.
  한 번에 쓸 수 있는 도구 수에 제한이 있는 클라이언트(예: 100개)는 다른 MCP 서버와 함께 켜면 일부 도구가 빠질 수 있습니다.
- `uv` 사용자는 설치 없이 `"command": "uvx", "args": ["kispilot", "mcp"]`

</details>

### 주문 안전장치 (에이전트)

AI 모델이 스스로 도구를 부르기 때문에 웹 콘솔보다 보수적으로 동작합니다.

1. 주문 도구의 기본값은 **모의투자**입니다.
2. 실전 주문은 MCP 서버 환경변수 `KIS_ALLOW_REAL_ORDERS=1` 을 사용자가 직접 넣어야 켜집니다.
3. 켜져 있어도 바로 나가지 않습니다. 주문 내용과 확인 번호를 먼저 돌려주고, 사용자가 승인한 뒤 `order_confirm` 을 불러야 전송됩니다 (3분 안, 1회용).

## 데이터 출처와 저장 위치

- 과거 일봉·분봉: [yfinance](https://github.com/ranaroussi/yfinance) (Yahoo Finance, 개인적·연구 목적 이용 권장), 최근 거래일은 KIS API로 보강
- 토큰 캐시·종목 마스터·커스텀 전략: 사용자 데이터 폴더 (`kispilot status` 에 표시, 환경변수 `KISPILOT_HOME` 으로 변경)
- 차트: [TradingView Lightweight Charts](https://github.com/tradingview/lightweight-charts) (Apache-2.0)

## 참고

- [한국투자증권 Open API](https://apiportal.koreainvestment.com) — 모든 시세·계좌·주문 기능은 이 API 를 호출합니다.
- [koreainvestment/open-trading-api](https://github.com/koreainvestment/open-trading-api) — 백테스트 기본 전략 구성(프리셋 종류)과 종목 마스터 파일 형식(필드 폭·열 이름)을 참고했습니다.

## 라이선스

[MIT](https://github.com/dongju923/kispilot/blob/main/LICENSE)
