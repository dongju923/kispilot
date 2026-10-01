"""앱키 · 앱시크릿 · 계좌번호 보관.

값을 찾는 순서
    1. 환경변수 — MCP 클라이언트 설정의 env, 서버·CI 환경변수, 또는 개발용 .env
    2. OS 키체인 — `kispilot setup` 이 저장한 값
       (Windows 자격 증명 관리자 / macOS 키체인 / Linux Secret Service)

규칙
    - 값을 로그·화면·도구 응답에 그대로 내보내지 않는다. 보여줘야 하면 mask() 를 쓴다.
    - 키를 채팅창에 붙여넣게 하지 않는다. 입력은 setup 명령(화면에 안 보이는 입력)으로만 받는다.
"""
from __future__ import annotations

import os
from typing import Literal, Optional

SERVICE = "kispilot"

# 이름: (설명, 비밀값 여부)
FIELDS: dict[str, tuple[str, bool]] = {
    "REAL_APPKEY": ("실전 앱키", True),
    "REAL_APP_SECRET": ("실전 앱시크릿", True),
    "CANO": ("실전 계좌번호 앞 8자리", False),
    "ACNT_PRDT_CD": ("실전 계좌 상품코드 2자리", False),
    "PAPER_APPKEY": ("모의투자 앱키", True),
    "PAPER_APP_SECRET": ("모의투자 앱시크릿", True),
    "PAPER_CANO": ("모의투자 계좌번호 앞 8자리", False),
    "PAPER_ACNT_PRDT_CD": ("모의투자 계좌 상품코드 2자리", False),
}
MODE_FIELDS = {
    "real": ("REAL_APPKEY", "REAL_APP_SECRET", "CANO", "ACNT_PRDT_CD"),
    "paper": ("PAPER_APPKEY", "PAPER_APP_SECRET", "PAPER_CANO", "PAPER_ACNT_PRDT_CD"),
}

try:  # 키체인 백엔드가 없는 환경(일부 Linux 서버 등)에서도 환경변수만으로 동작하게
    import keyring
    from keyring.errors import KeyringError
except ImportError:  # pragma: no cover
    keyring = None
    KeyringError = Exception


def keyring_backend() -> Optional[str]:
    """사용 가능한 키체인 백엔드 이름 (없으면 None)."""
    if keyring is None:
        return None
    try:
        kr = keyring.get_keyring()
    except Exception:
        return None
    name = type(kr).__name__
    return None if name in ("FailKeyring", "NullKeyring") else name


def _from_keyring(name: str) -> Optional[str]:
    if keyring is None:
        return None
    try:
        return keyring.get_password(SERVICE, name)
    except (KeyringError, RuntimeError, OSError):
        return None


def get(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value:
        return value.strip()
    value = _from_keyring(name)
    return value.strip() if value else None


def source(name: str) -> Literal["env", "keyring", None]:
    if os.environ.get(name):
        return "env"
    if _from_keyring(name):
        return "keyring"
    return None


def save(name: str, value: str) -> None:
    if name not in FIELDS:
        raise KeyError(name)
    if keyring_backend() is None:
        raise RuntimeError("OS 키체인을 쓸 수 없습니다. 환경변수로 설정하세요 (README 참고).")
    keyring.set_password(SERVICE, name, value.strip())


def delete(name: str) -> bool:
    if keyring is None:
        return False
    try:
        keyring.delete_password(SERVICE, name)
        return True
    except (KeyringError, RuntimeError, OSError):
        return False


def mask(value: Optional[str], keep: int = 4) -> str:
    if not value:
        return "—"
    if len(value) <= keep:
        return "*" * len(value)
    return value[:keep] + "*" * min(12, len(value) - keep)


def mask_account(cano: Optional[str], prdt: Optional[str]) -> Optional[str]:
    if not cano:
        return None
    return f"{cano[:4]}****-{prdt or '**'}"
