"""사용자 데이터 폴더 — 토큰 캐시, 종목 마스터 파일, 커스텀 전략.

설치 위치(site-packages)나 프로젝트 폴더가 아니라 사용자별 폴더에 둔다.
    Windows  %LOCALAPPDATA%\\kispilot
    macOS    ~/Library/Application Support/kispilot
    Linux    ~/.local/share/kispilot
환경변수 KISPILOT_HOME 으로 바꿀 수 있다.
"""
from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "kispilot"


def data_dir() -> Path:
    path = Path(os.environ.get("KISPILOT_HOME") or user_data_dir(APP_NAME, appauthor=False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_private(path: str | os.PathLike, text: str) -> None:
    """본인만 읽을 수 있게 파일을 쓴다 (POSIX 0600. Windows 는 사용자 폴더 권한을 따른다)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
