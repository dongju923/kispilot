# 설치 · 키 등록

[← README](../README.md)

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
- 접근 토큰은 자동으로 발급·갱신됩니다 (만료 6시간 전, 또는 KIS 가 토큰을 거절하면 새로 발급).

### 키체인을 쓸 수 없는 환경

서버처럼 키체인을 쓸 수 없는 환경에서는 환경변수로 넣을 수 있습니다. 환경변수가 키체인보다 먼저 쓰입니다.
변수 이름은 [.env.example](https://github.com/dongju923/kispilot/blob/main/.env.example)을 참고하여, .env 파일을 새로 생성하세요.

## 데이터 저장 위치

토큰 캐시 · 종목 마스터 · 커스텀 전략은 사용자 데이터 폴더에 둡니다 (`kispilot status` 에 표시, 환경변수 `KISPILOT_HOME` 으로 변경).

| OS | 기본 위치 |
|---|---|
| Windows | `%LOCALAPPDATA%\kispilot` |
| macOS | `~/Library/Application Support/kispilot` |
| Linux | `~/.local/share/kispilot` |

종목 마스터(주식·업종·선물옵션)는 한국투자증권이 매일 갱신하는 파일을 하루 한 번(오전 7시 기준) 내려받아 씁니다.
