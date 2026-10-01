"""AI 클라이언트에 MCP 서버 등록 — `kispilot install / uninstall`.

사용자가 JSON 설정 파일을 직접 만들거나 고치지 않아도 되게 한다.

    claude-desktop  Claude Desktop 설정 파일(claude_desktop_config.json)의 mcpServers 에 항목을 넣는다.
                    기존 파일은 백업하고 다른 항목은 그대로 둔다.
    claude-code     `claude mcp add --scope user` 로 내 계정 전체에 등록한다 (어느 폴더에서 열어도 연결).

등록하는 명령은 지금 설치된 kispilot 실행 파일의 전체 경로다 (PATH 에 없어도 동작).
실전 주문은 기본으로 끈 상태로 넣는다 (--allow-real-orders 로 켬, 켜도 2단계 확인을 거침).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import sysconfig
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_NAME = "kispilot"
REAL_ORDERS_ENV = "KIS_ALLOW_REAL_ORDERS"
LEGACY_ENV = "KIS_MCP_ALLOW_REAL_ORDERS"


# ── 실행 명령 ─────────────────────────────────────────────────

def server_command() -> tuple[str, list[str]]:
    """MCP 서버 실행 명령 (전체 경로). uvx 처럼 임시 환경이면 uvx 로 실행하게 한다."""
    exe_name = "kispilot.exe" if os.name == "nt" else "kispilot"
    prefix = str(Path(sys.prefix)).replace("\\", "/").lower()
    if "/uv/cache/" in prefix or "/.cache/uv/" in prefix or "/uv/archive" in prefix:
        uvx = shutil.which("uvx")
        if uvx:
            return _slash(uvx), ["kispilot", "mcp"]
    script = Path(sysconfig.get_path("scripts")) / exe_name
    if script.exists():
        return _slash(script), ["mcp"]
    # 실행 파일을 못 찾으면 지금 쓰는 파이썬으로 모듈 실행
    return _slash(sys.executable), ["-m", "kispilot", "mcp"]


def _slash(p) -> str:
    return str(p).replace("\\", "/")


# ── Claude Desktop ────────────────────────────────────────────

def desktop_config_paths() -> list[Path]:
    """Claude Desktop 설정 파일 후보. 이미 있는 것 우선, 없으면 설치 형태에 맞는 기본 위치 하나."""
    home = Path.home()
    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        # 스토어(MSIX) 설치본은 AppData 를 패키지 폴더 안으로 돌려서 쓴다
        msix = sorted((local / "Packages").glob("Claude_*/LocalCache/Roaming/Claude"))
        dirs = msix + [appdata / "Claude"]
    elif sys.platform == "darwin":
        dirs = [home / "Library" / "Application Support" / "Claude"]
    else:
        dirs = [Path(os.environ.get("XDG_CONFIG_HOME", home / ".config")) / "Claude"]
    existing = [d / "claude_desktop_config.json" for d in dirs if (d / "claude_desktop_config.json").exists()]
    if existing:
        return existing
    for d in dirs:  # 설정 파일은 없지만 앱 폴더는 있는 곳 (설치는 됐지만 아직 설정을 안 만든 경우)
        if d.is_dir():
            return [d / "claude_desktop_config.json"]
    return [dirs[0] / "claude_desktop_config.json"]


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)  # 깨진 파일은 덮어쓰지 않도록 예외를 그대로 올린다
    if not isinstance(data, dict):
        raise ValueError("설정 파일의 최상위가 JSON 객체가 아닙니다.")
    return data


def _write_json(path: Path, data: dict) -> Optional[Path]:
    """백업을 남기고 원자적으로 쓴다. 백업 경로를 돌려준다 (새 파일이면 None)."""
    backup = None
    if path.exists():
        backup = path.with_name(f"{path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.copy2(path, backup)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return backup


def install_desktop(name: str, allow_real: bool, config: Optional[str], dry_run: bool, out) -> int:
    command, args = server_command()
    paths = [Path(config)] if config else desktop_config_paths()
    for path in paths:
        try:
            data = _read_json(path)
        except (ValueError, json.JSONDecodeError) as e:
            out(f"✗ {path}\n  설정 파일을 읽지 못해 건드리지 않았습니다 ({e}). 파일을 확인한 뒤 다시 실행하세요.")
            return 1
        servers = data.setdefault("mcpServers", {})
        before = servers.get(name)
        env = dict((before or {}).get("env") or {})
        env.pop(LEGACY_ENV, None)
        env[REAL_ORDERS_ENV] = "1" if allow_real else "0"
        entry = {"command": command, "args": args, "env": env}
        servers[name] = entry
        out(f"{'(미리보기) ' if dry_run else ''}{path}")
        label = "추가" if not before else ("변경 없음" if before == entry else "변경")
        out(f"  {label}: \"{name}\" → {command} {' '.join(args)}")
        if before and before != entry:
            out(f"  이전: {before.get('command')} {' '.join(before.get('args') or [])}")
        if dry_run:
            continue
        backup = _write_json(path, data)
        if backup:
            out(f"  백업: {backup.name}")
    out(f"\n실전 주문: {'켜짐 (2단계 확인)' if allow_real else '꺼짐 (모의투자만)'}")
    if not dry_run:
        out("Claude Desktop 을 완전히 종료한 뒤(트레이 아이콘 → 종료) 다시 켜면 연결됩니다.")
    return 0


def uninstall_desktop(name: str, config: Optional[str], out) -> int:
    paths = [Path(config)] if config else desktop_config_paths()
    removed = False
    for path in paths:
        try:
            data = _read_json(path)
        except (ValueError, json.JSONDecodeError) as e:
            out(f"✗ {path}: 읽지 못해 건드리지 않았습니다 ({e})")
            return 1
        if name in (data.get("mcpServers") or {}):
            del data["mcpServers"][name]
            backup = _write_json(path, data)
            out(f"{path}\n  삭제: \"{name}\" (백업: {backup.name if backup else '-'})")
            removed = True
    if not removed:
        out(f"Claude Desktop 설정에 \"{name}\" 항목이 없습니다.")
    return 0


# ── Claude Code ───────────────────────────────────────────────

def _claude_cli() -> Optional[str]:
    return shutil.which("claude")


def install_code(name: str, allow_real: bool, dry_run: bool, out) -> int:
    command, args = server_command()
    env_arg = f"{REAL_ORDERS_ENV}={'1' if allow_real else '0'}"
    add = ["mcp", "add", name, "--scope", "user", "--env", env_arg, "--", command, *args]
    cli = _claude_cli()
    if cli is None or dry_run:
        out(("(미리보기) " if dry_run else "claude 명령을 찾지 못했습니다. Claude Code 를 설치한 뒤 아래 명령을 실행하세요.\n")
            + "  claude " + " ".join(f'"{a}"' if " " in a else a for a in add))
        return 0 if dry_run else 1
    # 이미 있으면 add 가 실패하므로 먼저 지운다 (없으면 조용히 실패)
    subprocess.run([cli, "mcp", "remove", name, "--scope", "user"], capture_output=True, text=True)
    r = subprocess.run([cli, *add], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        out(f"✗ 등록 실패: {(r.stderr or r.stdout).strip()}")
        return 1
    out(f"Claude Code(내 계정 전체)에 \"{name}\" 등록 → {command} {' '.join(args)}")
    out(f"실전 주문: {'켜짐 (2단계 확인)' if allow_real else '꺼짐 (모의투자만)'}")
    out("Claude Code 를 다시 시작하면 연결됩니다. 확인: claude mcp list")
    return 0


def uninstall_code(name: str, out) -> int:
    cli = _claude_cli()
    if cli is None:
        out(f"claude 명령을 찾지 못했습니다. 직접 실행하세요: claude mcp remove {name} --scope user")
        return 1
    r = subprocess.run([cli, "mcp", "remove", name, "--scope", "user"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out(f"\"{name}\" 삭제" if r.returncode == 0 else f"Claude Code(내 계정)에 \"{name}\" 항목이 없습니다.")
    return 0
