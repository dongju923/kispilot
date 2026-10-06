"""AI 클라이언트에 MCP 서버 등록 — `kispilot install / uninstall`.

사용자가 설정 파일을 직접 만들거나 고치지 않아도 되게 한다.
설정 파일을 고치는 대상은 기존 파일을 백업하고 다른 항목은 그대로 둔다.

    claude-desktop  Claude Desktop  claude_desktop_config.json 의 mcpServers
    claude-code     Claude Code     `claude mcp add --scope user` (내 계정 전체, 어느 폴더에서 열어도 연결)
    cursor          Cursor          ~/.cursor/mcp.json 의 mcpServers
    vscode          VS Code (GitHub Copilot 에이전트 모드)   사용자 프로필의 mcp.json 의 servers
    gemini          Gemini CLI      ~/.gemini/settings.json 의 mcpServers
    codex           OpenAI Codex (CLI · IDE 확장)   ~/.codex/config.toml 의 [mcp_servers.<이름>]

등록하는 명령은 지금 설치된 kispilot 실행 파일의 전체 경로다 (PATH 에 없어도 동작).
실전 주문은 기본으로 끈 상태로 넣는다 (--allow-real-orders 로 켬, 켜도 2단계 확인을 거침).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

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


def cursor_config_paths() -> list[Path]:
    return [Path.home() / ".cursor" / "mcp.json"]


def vscode_config_paths() -> list[Path]:
    """VS Code 사용자 프로필의 mcp.json (모든 작업 폴더에서 쓰임)."""
    home = Path.home()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return [base / "Code" / "User" / "mcp.json"]


def gemini_config_paths() -> list[Path]:
    return [Path.home() / ".gemini" / "settings.json"]


def codex_config_path() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "config.toml"


@dataclass(frozen=True)
class JsonTarget:
    """mcpServers 같은 JSON 객체에 서버 항목을 넣는 클라이언트."""
    label: str
    key: str                              # 서버 목록이 들어가는 최상위 키
    paths: Callable[[], list[Path]]
    restart: str                          # 등록 뒤 안내
    stdio_type: bool = False              # 항목에 "type": "stdio" 를 넣는지 (VS Code)


JSON_TARGETS: dict[str, JsonTarget] = {
    "claude-desktop": JsonTarget(
        "Claude Desktop", "mcpServers", desktop_config_paths,
        "Claude Desktop 을 완전히 종료한 뒤(트레이 아이콘 → 종료) 다시 켜면 연결됩니다."),
    "cursor": JsonTarget(
        "Cursor", "mcpServers", cursor_config_paths,
        "Cursor 를 다시 시작하면 연결됩니다. 설정의 MCP 항목에서 kispilot 가 켜져 있는지 확인하세요."),
    "vscode": JsonTarget(
        "VS Code", "servers", vscode_config_paths,
        "VS Code 를 다시 시작한 뒤 Copilot 채팅을 에이전트(Agent) 모드로 쓰면 도구가 보입니다. "
        "명령 팔레트 → 'MCP: List Servers' 로 상태를 확인할 수 있습니다.", stdio_type=True),
    "gemini": JsonTarget(
        "Gemini CLI", "mcpServers", gemini_config_paths,
        "gemini 를 다시 실행하고 /mcp 로 연결 상태를 확인하세요."),
}


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)  # 깨진 파일(주석·끝 쉼표 포함)은 덮어쓰지 않도록 예외를 그대로 올린다
    if not isinstance(data, dict):
        raise ValueError("설정 파일의 최상위가 JSON 객체가 아닙니다.")
    return data


def _backup(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    backup = path.with_name(f"{path.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
    shutil.copy2(path, backup)
    return backup


def _write_text(path: Path, text: str) -> Optional[Path]:
    """백업을 남기고 원자적으로 쓴다. 백업 경로를 돌려준다 (새 파일이면 None)."""
    backup = _backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return backup


def _write_json(path: Path, data: dict) -> Optional[Path]:
    return _write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def _real_label(allow_real: bool) -> str:
    return "켜짐 (2단계 확인)" if allow_real else "꺼짐 (모의투자만)"


def install_json(target: str, name: str, allow_real: bool, config: Optional[str], dry_run: bool, out) -> int:
    t = JSON_TARGETS[target]
    command, args = server_command()
    paths = [Path(config)] if config else t.paths()
    for path in paths:
        try:
            data = _read_json(path)
        except (ValueError, json.JSONDecodeError) as e:
            out(f"✗ {path}\n  설정 파일을 읽지 못해 건드리지 않았습니다 ({e}).\n"
                "  주석이나 끝 쉼표가 있으면 읽지 못합니다. 파일을 확인하거나 README 의 항목을 직접 넣으세요.")
            return 1
        servers = data.setdefault(t.key, {})
        if not isinstance(servers, dict):
            out(f"✗ {path}\n  \"{t.key}\" 가 JSON 객체가 아니라서 건드리지 않았습니다.")
            return 1
        before = servers.get(name)
        env = dict((before or {}).get("env") or {})
        env.pop(LEGACY_ENV, None)
        env[REAL_ORDERS_ENV] = "1" if allow_real else "0"
        entry = ({"type": "stdio"} if t.stdio_type else {}) | {"command": command, "args": args, "env": env}
        servers[name] = entry
        out(f"{'(미리보기) ' if dry_run else ''}{t.label}: {path}")
        label = "추가" if not before else ("변경 없음" if before == entry else "변경")
        out(f"  {label}: \"{name}\" → {command} {' '.join(args)}")
        if before and before != entry:
            out(f"  이전: {before.get('command')} {' '.join(before.get('args') or [])}")
        if dry_run or before == entry:
            continue
        backup = _write_json(path, data)
        if backup:
            out(f"  백업: {backup.name}")
    out(f"\n실전 주문: {_real_label(allow_real)}")
    if not dry_run:
        out(t.restart)
    return 0


def uninstall_json(target: str, name: str, config: Optional[str], out) -> int:
    t = JSON_TARGETS[target]
    paths = [Path(config)] if config else t.paths()
    removed = False
    for path in paths:
        try:
            data = _read_json(path)
        except (ValueError, json.JSONDecodeError) as e:
            out(f"✗ {path}: 읽지 못해 건드리지 않았습니다 ({e})")
            return 1
        servers = data.get(t.key)
        if isinstance(servers, dict) and name in servers:
            del servers[name]
            backup = _write_json(path, data)
            out(f"{path}\n  삭제: \"{name}\" (백업: {backup.name if backup else '-'})")
            removed = True
    if not removed:
        out(f"{t.label} 설정에 \"{name}\" 항목이 없습니다.")
    return 0


# ── Codex (TOML) ──────────────────────────────────────────────
# 표준 라이브러리에는 TOML 쓰기가 없어서, 우리 항목([mcp_servers.<이름>] 과 그 하위 표)만 텍스트로 빼고 다시 붙인다.
# 고치기 전후로 tomllib 로 읽어 보고, 원래 파일이 깨져 있거나 결과가 깨지면 쓰지 않는다.

CODEX_STARTUP_TIMEOUT = 30  # 초. 기본 10초는 pandas 등을 불러오는 첫 실행에 빠듯하다


def _toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # JSON 문자열 이스케이프는 TOML 기본 문자열과 호환


def _strip_codex_entry(text: str, name: str) -> tuple[str, bool]:
    """[mcp_servers.<name>] 과 [mcp_servers.<name>.*] 표를 지운다."""
    head = re.compile(r"^\s*\[\s*mcp_servers\.(\"?)" + re.escape(name) + r"\1\s*(\.[^\]]*)?\]\s*(#.*)?$")
    out, skipping, found = [], False, False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("["):
            skipping = bool(head.match(line))
            found = found or skipping
        if not skipping:
            out.append(line)
    rest = "".join(out).rstrip()
    return (rest + "\n" if rest else ""), found


def _codex_block(name: str, command: str, args: list[str], allow_real: bool) -> str:
    key = name if re.fullmatch(r"[A-Za-z0-9_-]+", name) else _toml_str(name)
    return (f"[mcp_servers.{key}]\n"
            f"command = {_toml_str(command)}\n"
            f"args = [{', '.join(_toml_str(a) for a in args)}]\n"
            f"startup_timeout_sec = {CODEX_STARTUP_TIMEOUT}\n\n"
            f"[mcp_servers.{key}.env]\n"
            f"{REAL_ORDERS_ENV} = {_toml_str('1' if allow_real else '0')}\n")


def _read_codex(path: Path) -> str:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    tomllib.loads(text)  # 깨진 파일은 건드리지 않도록 예외를 그대로 올린다
    return text


def install_codex(name: str, allow_real: bool, config: Optional[str], dry_run: bool, out) -> int:
    path = Path(config) if config else codex_config_path()
    try:
        text = _read_codex(path)
    except tomllib.TOMLDecodeError as e:
        out(f"✗ {path}\n  설정 파일을 읽지 못해 건드리지 않았습니다 ({e}).")
        return 1
    command, args = server_command()
    rest, found = _strip_codex_entry(text, name)
    new = (rest + "\n" if rest else "") + _codex_block(name, command, args, allow_real)
    try:
        parsed = tomllib.loads(new)["mcp_servers"][name]
    except (tomllib.TOMLDecodeError, KeyError) as e:
        out(f"✗ {path}\n  설정을 만들다 문제가 생겨 저장하지 않았습니다 ({e}). README 의 항목을 직접 넣으세요.")
        return 1
    before = tomllib.loads(text).get("mcp_servers", {}).get(name)
    out(f"{'(미리보기) ' if dry_run else ''}Codex: {path}")
    label = "추가" if not found else ("변경 없음" if before == parsed else "변경")
    out(f"  {label}: \"{name}\" → {parsed['command']} {' '.join(parsed['args'])}")
    if not dry_run and before != parsed:
        backup = _write_text(path, new)
        if backup:
            out(f"  백업: {backup.name}")
    out(f"\n실전 주문: {_real_label(allow_real)}")
    if not dry_run:
        out("Codex(CLI · IDE 확장)를 다시 시작하면 연결됩니다. 확인: codex mcp list")
    return 0


def uninstall_codex(name: str, config: Optional[str], out) -> int:
    path = Path(config) if config else codex_config_path()
    try:
        text = _read_codex(path)
    except tomllib.TOMLDecodeError as e:
        out(f"✗ {path}: 읽지 못해 건드리지 않았습니다 ({e})")
        return 1
    rest, found = _strip_codex_entry(text, name)
    if not found:
        out(f"Codex 설정에 \"{name}\" 항목이 없습니다.")
        return 0
    backup = _write_text(path, rest)
    out(f"{path}\n  삭제: \"{name}\" (백업: {backup.name if backup else '-'})")
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
