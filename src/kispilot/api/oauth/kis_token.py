import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Literal, Optional

import requests

from kispilot.api import config
from kispilot.paths import write_private


TOKEN_URL = "/oauth2/tokenP"
REVOKE_URL = "/oauth2/revokeP"
WEBSOCKET_URL = "/oauth2/Approval"

TOKEN_FILES_PATH = os.path.join(config.BASE_CACHE_PATH, "access_token")
os.makedirs(TOKEN_FILES_PATH, exist_ok=True)

WEBSOCKET_KEY_FILES_PATH = os.path.join(config.BASE_CACHE_PATH, "access_token")
os.makedirs(WEBSOCKET_KEY_FILES_PATH, exist_ok=True)


class CredentialsMissing(ValueError):
    """앱키·앱시크릿이 등록되지 않음 (`kispilot setup` 필요)."""


class KisApiError(Exception):
    """한국투자증권 API가 에러 응답을 반환했을 때 발생하는 예외"""

    def __init__(self, error_code: str, error_description: str):
        self.error_code = error_code
        self.error_description = error_description
        super().__init__(f"[{error_code}] {error_description}")


@dataclass
class ResponseBodyOutput:
    access_token: str    #접근토큰
    token_type: str    #접근토큰유형
    expires_in: float    #접근토큰 유효기간(초)
    access_token_token_expired: str    #접근토큰 유효기간(날짜)


@dataclass
class ApprovalKeyOutput:
    approval_key: str    # 웹소켓 접속키


def _get_credentials(mode: Literal["real", "paper"], path: str) -> tuple[str, str, str]:
    """모드에 맞는 앱키, 앱시크릿, 요청 URL을 반환한다."""
    if mode == "real":
        appkey, app_secret, domain = config.REAL_APPKEY, config.REAL_APP_SECRET, config.DOMAIN["real"]
    else:
        appkey, app_secret, domain = config.PAPER_APPKEY, config.PAPER_APP_SECRET, config.DOMAIN["paper"]

    label = "실전" if mode == "real" else "모의투자"
    if appkey is None:
        raise CredentialsMissing(f"{label} 앱키가 없습니다. 터미널에서 `kispilot setup` 으로 등록한 뒤 서버를 다시 시작하세요.")
    if app_secret is None:
        raise CredentialsMissing(f"{label} 앱시크릿이 없습니다. 터미널에서 `kispilot setup` 으로 등록한 뒤 서버를 다시 시작하세요.")

    return appkey, app_secret, domain + path


def _post(url: str, body: dict) -> dict:
    """공통 POST 요청 처리: 네트워크 예외와 API 에러 응답을 KisApiError로 통일."""
    try:
        response = requests.post(url, json=body, timeout=10)
    except requests.exceptions.RequestException as e:
        raise KisApiError("REQUEST_FAILED", str(e)) from e

    data = response.json()
    if "error_code" in data:
        raise KisApiError(data["error_code"], data.get("error_description", ""))
    return data


def _available_modes() -> list[str]:
    """앱키/앱시크릿이 등록된(환경변수 또는 키체인) 모드만 반환한다."""
    modes = []
    if config.REAL_APPKEY and config.REAL_APP_SECRET:
        modes.append("real")
    if config.PAPER_APPKEY and config.PAPER_APP_SECRET:
        modes.append("paper")
    return modes


def require_mode(mode: Literal["real", "paper"]) -> None:
    """그 모드의 앱키가 없으면 KIS 에 요청하기 전에 알기 쉬운 오류를 낸다."""
    if mode in _available_modes():
        return
    if mode == "real" and "paper" in _available_modes():
        raise CredentialsMissing("이 기능은 실전 앱키가 필요합니다 (KIS 모의투자 미지원). "
                                 "`kispilot setup` 으로 실전 키를 등록한 뒤 서버를 다시 시작하세요.")
    label = "실전" if mode == "real" else "모의투자"
    raise CredentialsMissing(f"{label} 앱키가 없습니다. 터미널에서 `kispilot setup` 으로 등록한 뒤 서버를 다시 시작하세요.")


# ── 접근토큰 (REST API) ──────────────────────────────────────

def _token_file(mode: Literal["real", "paper"]) -> str:
    return os.path.join(TOKEN_FILES_PATH, f"{mode}_token.json")


def _issue_access_token(mode: Literal["real", "paper"]) -> str:
    token_file = _token_file(mode)

    # 캐시된 토큰이 있고 만료까지 6시간 넘게 남았으면 재사용 (KIS API는 1분당 1회로 발급을 제한함)
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
            expired_at = datetime.strptime(saved["access_token_token_expired"], "%Y-%m-%d %H:%M:%S")
            if expired_at - datetime.now() > timedelta(hours=6):
                return saved["access_token"]
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            pass

    appkey, app_secret, url = _get_credentials(mode, TOKEN_URL)
    body = {
        "grant_type": "client_credentials",
        "appkey": appkey,
        "appsecret": app_secret,
    }
    data = _post(url, body)

    fields = {f for f in ResponseBodyOutput.__dataclass_fields__}
    output = ResponseBodyOutput(**{k: v for k, v in data.items() if k in fields})

    write_private(token_file, json.dumps(asdict(output), ensure_ascii=False, indent=2))

    return output.access_token


def get_access_token() -> dict[str, dict[str, str]]:
    """앱키가 등록된 모드(real/paper)를 자동으로 찾아 각각 접근토큰과 웹소켓 접속키를 함께 발급/재사용한다.

    반환값 예: {"real": {"access_token": "...", "approval_key": "..."}, "paper": {...}}
    (모드별로 실제 발급에 성공한 값만 채워진다.)
    """
    available = _available_modes()
    if not available:
        print("등록된 앱키가 없습니다. 터미널에서 `kispilot setup` 으로 등록하세요.")

    result = {}
    for mode in available:
        entry = {}
        try:
            entry["access_token"] = _issue_access_token(mode)
        except (KisApiError, ValueError) as e:
            print(f"{mode} 토큰 발급 실패: {e}")

        try:
            entry["approval_key"] = _issue_websocket_key(mode)
        except (KisApiError, ValueError) as e:
            print(f"{mode} 웹소켓 접속키 발급 실패: {e}")

        if entry:
            result[mode] = entry
    return result


def revoke_token(mode: Literal["real", "paper"]) -> None:
    """접근토큰을 폐기(revoke)하고 캐시 파일도 삭제한다."""
    token_file = _token_file(mode)
    if not os.path.exists(token_file):
        raise ValueError("접근토큰이 존재하지 않습니다. 먼저 get_access_token()을 호출하여 토큰을 발급받으세요.")

    with open(token_file, "r", encoding="utf-8") as f:
        saved = json.load(f)
    token = saved["access_token"]

    appkey, app_secret, url = _get_credentials(mode, REVOKE_URL)
    data = _post(url, {"appkey": appkey, "appsecret": app_secret, "token": token})
    if str(data.get("code")) not in ("None", "200"):
        raise KisApiError(data.get("code", ""), data.get("message", ""))

    os.remove(token_file)


# ── 웹소켓 접속키 ────────────────────────────────────────────

def _websocket_key_file(mode: Literal["real", "paper"]) -> str:
    return os.path.join(WEBSOCKET_KEY_FILES_PATH, f"{mode}_websocket_key.json")


def _issue_websocket_key(mode: Literal["real", "paper"]) -> str:
    """웹소켓 접속키(approval_key)를 발급받아 파일에 저장하고 반환한다.

    REST 접근토큰과 달리 응답에 만료 시각이 없어 캐시 재사용 없이 매번 새로 발급받는다.
    """
    appkey, app_secret, url = _get_credentials(mode, WEBSOCKET_URL)
    body = {
        "grant_type": "client_credentials",
        "appkey": appkey,
        "secretkey": app_secret,
    }
    data = _post(url, body)

    fields = {f for f in ApprovalKeyOutput.__dataclass_fields__}
    output = ApprovalKeyOutput(**{k: v for k, v in data.items() if k in fields})

    write_private(_websocket_key_file(mode), json.dumps(asdict(output), ensure_ascii=False, indent=2))

    return output.approval_key

def _read_saved_value(file_path: str, key: str) -> Optional[str]:
    """캐시 파일에서 지정한 키의 값만 읽어서 반환한다 (파일이 없거나 읽기 실패하면 None)."""
    if not os.path.exists(file_path):
        raise FileExistsError("토큰 파일이 없습니다. 토큰을 발급받으세요.")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        return saved.get(key)
    except:
        raise ValueError("토큰을 다시 발급받아주세요.")


def load_token(mode: Literal["real", "paper"]) -> dict[str, Optional[str]]:
    if mode == "real":
        return _read_saved_value(_token_file("real"), "access_token")
    else:
        return _read_saved_value(_token_file("paper"), "access_token")


def load_websocket_token(mode: Literal["real", "paper"]) -> dict[str, Optional[str]]:
    if mode == "real":
        return _read_saved_value(_websocket_key_file("real"), "approval_key")
    else:
        return _read_saved_value(_websocket_key_file("paper"), "approval_key")




if __name__ == "__main__":
    print(get_access_token())
