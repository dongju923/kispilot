"""kispilot 명령.

    kispilot setup     앱키·계좌를 OS 키체인에 등록 (입력은 화면에 보이지 않음, 토큰 발급으로 검증)
    kispilot status    등록 상태 확인 (값은 가려서 표시)
    kispilot logout    키체인에서 키를 지우고 토큰을 폐기
    kispilot ui        웹 콘솔 실행 (http://127.0.0.1:8000)
    kispilot install <대상>     AI 클라이언트에 MCP 서버 등록 (설정 파일 자동 작성)
    kispilot uninstall <대상>   등록 해제
                대상: claude-desktop, claude-code, cursor, vscode, gemini, codex
    kispilot mcp       MCP 서버 실행 (stdio — 등록해 두면 AI 클라이언트가 실행한다)

키는 채팅창이나 설정 파일에 붙여넣지 말고 이 명령으로 등록한다.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import sys
from datetime import datetime
from typing import Optional

from kispilot import __version__, credentials
from kispilot.paths import data_dir, write_private

MODES = {"real": "실전", "paper": "모의투자"}
DOMAIN = {"real": "https://openapi.koreainvestment.com:9443", "paper": "https://openapivts.koreainvestment.com:29443"}


def _print(msg: str = "") -> None:
    print(msg, flush=True)


def _ask_modes(arg: Optional[str]) -> list[str]:
    if arg:
        return ["real", "paper"] if arg == "both" else [arg]
    _print("등록할 계좌를 고르세요:  1) 실전   2) 모의투자   3) 둘 다")
    while True:
        c = input("> ").strip()
        if c in ("1", "2", "3"):
            return {"1": ["real"], "2": ["paper"], "3": ["real", "paper"]}[c]


def _ask_account(label: str) -> tuple[str, str]:
    while True:
        raw = input(f"{label} 계좌번호 (예: 12345678-01): ").strip()
        m = re.fullmatch(r"(\d{8})-?(\d{2})", raw)
        if m:
            return m.group(1), m.group(2)
        _print("  8자리-2자리 형식으로 입력하세요.")


def _ask_secret(prompt: str) -> str:
    while True:
        v = getpass.getpass(f"{prompt} (입력이 화면에 보이지 않습니다): ").strip()
        if len(v) >= 16 and re.fullmatch(r"[A-Za-z0-9+/=_\-]+", v):
            return v
        _print("  값이 비었거나 형식이 맞지 않습니다. KIS Developers 에서 복사한 값을 다시 붙여넣으세요.")


def _verify(mode: str, appkey: str, secret: str) -> tuple[bool, str]:
    """접근토큰을 발급해 키를 검증하고, 받은 토큰은 캐시에 저장한다 (KIS 는 1분에 1회만 발급)."""
    import requests

    try:
        r = requests.post(f"{DOMAIN[mode]}/oauth2/tokenP", timeout=10,
                          json={"grant_type": "client_credentials", "appkey": appkey, "appsecret": secret})
        data = r.json()
    except Exception as e:  # 네트워크 오류 등
        return False, f"KIS 서버에 연결하지 못했습니다 ({type(e).__name__})"
    if not data.get("access_token"):
        return False, f"{data.get('error_code', '')} {data.get('error_description', '') or data.get('msg1', '')}".strip()
    token_dir = data_dir() / "access_token"
    keep = ("access_token", "token_type", "expires_in", "access_token_token_expired")
    write_private(token_dir / f"{mode}_token.json", json.dumps({k: data.get(k) for k in keep}, ensure_ascii=False, indent=2))
    return True, f"토큰 발급 성공 (만료 {data.get('access_token_token_expired')})"


def cmd_setup(args: argparse.Namespace) -> int:
    backend = credentials.keyring_backend()
    if backend is None:
        _print("이 PC 에서는 OS 키체인을 쓸 수 없습니다. 환경변수(REAL_APPKEY 등)로 설정하세요 — README 의 '키 설정' 참고.")
        return 1
    _print(f"kispilot {__version__} · 키 저장 위치: OS 키체인 ({backend})")
    _print("앱키·시크릿은 KIS Developers(apiportal.koreainvestment.com) 에서 발급합니다.\n")

    if args.from_env:
        # 개발용 .env / 환경변수에 있는 값을 키체인으로 옮긴다
        from dotenv import find_dotenv, load_dotenv
        load_dotenv(find_dotenv(usecwd=True))
        values = {m: {f: os.environ.get(f, "").strip() for f in credentials.MODE_FIELDS[m]} for m in MODES}
        modes = [m for m in MODES if all(values[m].values())]
        if not modes:
            _print("환경변수에 완전한 키 묶음(앱키·시크릿·계좌)이 없습니다.")
            return 1
    else:
        modes = _ask_modes(args.mode)
        values = {}
        for m in modes:
            label = MODES[m]
            _print(f"\n[{label}]")
            appkey = _ask_secret(f"{label} 앱키")
            secret = _ask_secret(f"{label} 앱시크릿")
            cano, prdt = _ask_account(label)
            fields = credentials.MODE_FIELDS[m]
            values[m] = dict(zip(fields, (appkey, secret, cano, prdt)))

    ok_all = True
    for m in modes:
        label = MODES[m]
        appkey_f, secret_f, *_ = credentials.MODE_FIELDS[m]
        if not args.no_verify:
            ok, msg = _verify(m, values[m][appkey_f], values[m][secret_f])
            _print(f"  {label}: {msg}")
            if not ok:
                ok_all = False
                _print(f"  → {label} 키는 저장하지 않았습니다. 값을 확인하세요 (토큰 발급은 1분에 1회만 됩니다).")
                continue
        for name, v in values[m].items():
            credentials.save(name, v)
        f = credentials.MODE_FIELDS[m]
        _print(f"  {label} 저장 완료 · 앱키 {credentials.mask(values[m][f[0]])} · 계좌 {credentials.mask_account(values[m][f[2]], values[m][f[3]])}")

    if args.from_env and ok_all:
        _print("\n키체인으로 옮겼습니다. 이제 .env 의 키 값은 지워도 됩니다 (환경변수가 키체인보다 먼저 쓰입니다).")
    _print("\n다음:")
    _print("  kispilot status                   등록 상태 확인")
    _print("  kispilot install claude-desktop   AI 클라이언트에 연결 (claude-code · cursor · vscode · gemini · codex)")
    _print("  kispilot ui                       웹 콘솔")
    _print("웹 콘솔이나 AI 클라이언트가 이미 켜져 있으면 다시 시작해야 새 키가 적용됩니다.")
    return 0 if ok_all else 1


def _token_info(mode: str) -> str:
    p = data_dir() / "access_token" / f"{mode}_token.json"
    if not p.exists():
        return "토큰 없음 (첫 조회 때 발급)"
    try:
        exp = json.loads(p.read_text(encoding="utf-8"))["access_token_token_expired"]
        left = datetime.strptime(exp, "%Y-%m-%d %H:%M:%S") - datetime.now()
        if left.total_seconds() <= 0:
            return "토큰 만료 (다음 조회 때 재발급)"
        return f"토큰 유효 · {int(left.total_seconds() // 3600)}시간 {int(left.total_seconds() % 3600 // 60)}분 남음"
    except Exception:
        return "토큰 파일을 읽지 못함"


def cmd_status(args: argparse.Namespace) -> int:
    from dotenv import find_dotenv, load_dotenv
    load_dotenv(find_dotenv(usecwd=True))
    src_label = {"env": "환경변수", "keyring": "키체인", None: "없음"}
    _print(f"kispilot {__version__}")
    _print(f"데이터 폴더   {data_dir()}")
    _print(f"OS 키체인     {credentials.keyring_backend() or '사용 불가'}")
    real_on = any(os.getenv(k, "").strip().lower() in ("1", "true", "yes", "on") for k in ("KIS_ALLOW_REAL_ORDERS", "KIS_MCP_ALLOW_REAL_ORDERS"))
    _print(f"MCP 실전 주문 {'켜짐 (2단계 확인)' if real_on else '꺼짐 (모의투자만)'}")
    for m, label in MODES.items():
        appkey_f, secret_f, cano_f, prdt_f = credentials.MODE_FIELDS[m]
        appkey = credentials.get(appkey_f)
        _print(f"\n[{label}]")
        _print(f"  앱키      {credentials.mask(appkey)}  ({src_label[credentials.source(appkey_f)]})")
        _print(f"  앱시크릿  {'등록됨' if credentials.get(secret_f) else '없음'}  ({src_label[credentials.source(secret_f)]})")
        _print(f"  계좌      {credentials.mask_account(credentials.get(cano_f), credentials.get(prdt_f)) or '없음'}")
        if appkey:
            _print(f"  {_token_info(m)}")
    if not any(credentials.get(credentials.MODE_FIELDS[m][0]) for m in MODES):
        _print("\n등록된 앱키가 없습니다 → `kispilot setup` 으로 등록하세요.")
    return 0


def cmd_logout(args: argparse.Namespace) -> int:
    modes = ["real", "paper"] if args.mode == "both" else [args.mode]
    if not args.yes:
        ans = input(f"{', '.join(MODES[m] for m in modes)} 키를 키체인에서 지우고 토큰을 폐기할까요? [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            _print("취소했습니다.")
            return 1
    for m in modes:
        try:  # 토큰 폐기는 키가 남아 있을 때만 가능하므로 먼저 한다
            from kispilot.api.oauth import kis_token
            kis_token.revoke_token(m)
            _print(f"  {MODES[m]}: 토큰 폐기")
        except Exception:
            pass
        for name in ("access_token", ):
            for fn in (f"{m}_token.json", f"{m}_websocket_key.json"):
                p = data_dir() / name / fn
                if p.exists():
                    p.unlink()
        removed = [f for f in credentials.MODE_FIELDS[m] if credentials.delete(f)]
        _print(f"  {MODES[m]}: 키체인 항목 {len(removed)}개 삭제")
    _print("완료. 환경변수나 .env 에 넣어 둔 값은 직접 지워야 합니다.")
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    from kispilot.app import main as app_main
    sys.argv = ["kispilot ui", "--host", args.host, "--port", str(args.port)] + (["--reload"] if args.reload else [])
    app_main.main()
    return 0


INSTALL_TARGETS = ["claude-desktop", "claude-code", "cursor", "vscode", "gemini", "codex"]


def cmd_install(args: argparse.Namespace) -> int:
    from kispilot import install
    if args.target == "claude-code":
        return install.install_code(args.name, args.allow_real_orders, args.dry_run, _print)
    if args.target == "codex":
        return install.install_codex(args.name, args.allow_real_orders, args.config, args.dry_run, _print)
    return install.install_json(args.target, args.name, args.allow_real_orders, args.config, args.dry_run, _print)


def cmd_uninstall(args: argparse.Namespace) -> int:
    from kispilot import install
    if args.target == "claude-code":
        return install.uninstall_code(args.name, _print)
    if args.target == "codex":
        return install.uninstall_codex(args.name, args.config, _print)
    return install.uninstall_json(args.target, args.name, args.config, _print)


def cmd_mcp(args: argparse.Namespace) -> int:
    if args.check:
        return _mcp_check()
    if sys.stdin.isatty():
        # 사람이 터미널에서 직접 실행한 경우. stdout 은 MCP 통신 전용이라 안내는 stderr 로만 낸다.
        print("kispilot MCP 서버가 실행 중입니다 (stdio). 화면에 아무것도 안 나오는 것이 정상입니다.\n"
              "이 명령은 Claude Desktop·Cursor·VS Code 같은 AI 클라이언트가 실행해서 씁니다.\n"
              "등록은 `kispilot install <대상>` 으로 합니다 (claude-desktop, claude-code, cursor, vscode, gemini, codex).\n"
              "동작 확인만 하려면 Ctrl+C 로 끄고 `kispilot mcp --check` 를 실행하세요.", file=sys.stderr, flush=True)
    from kispilot.mcp_server import server
    server.main()
    return 0


def _mcp_check() -> int:
    """MCP 서버를 실제로 띄우지 않고 도구 등록과 키 상태만 확인한다."""
    import asyncio

    from kispilot.api.oauth import kis_token
    from kispilot.mcp_server import server

    tools = asyncio.run(server.mcp.list_tools())
    modes = kis_token._available_modes()
    _print(f"MCP 서버 준비 완료 · 도구 {len(tools)}개")
    _print(f"앱키: {', '.join(MODES[m] for m in modes) if modes else '없음 → `kispilot setup` 으로 등록하세요 (검색·yfinance 도구는 키 없이도 동작)'}")
    _print(f"실전 주문: {'켜짐 (2단계 확인)' if server._ALLOW_REAL_ORDERS else '꺼짐 (모의투자만)'}")
    _print("\nAI 클라이언트에 등록:  kispilot install <대상>")
    _print("  대상: claude-desktop, claude-code, cursor, vscode, gemini, codex")
    return 0


def _commands_help(sub: argparse._SubParsersAction) -> str:
    """`kispilot --help` 아래에 붙일 명령별 인자·옵션 목록."""
    helps = {a.dest: a.help for a in sub._choices_actions}
    lines = ["명령별 옵션 (자세히: kispilot <명령> --help):"]
    for name, sp in sub.choices.items():
        lines.append(f"\n  kispilot {name}    {helps.get(name) or ''}")
        for a in sp._actions:
            if isinstance(a, argparse._HelpAction):
                continue
            if a.option_strings:
                flag = ", ".join(a.option_strings)
                if a.nargs != 0:
                    flag += " " + ("{" + ",".join(map(str, a.choices)) + "}" if a.choices else (a.metavar or a.dest.upper()))
            else:
                flag = "<" + a.dest + ">"
            text = a.help or ""
            if a.choices and not a.option_strings:
                text += f" ({', '.join(map(str, a.choices))})"
            if a.option_strings and a.nargs != 0 and a.default not in (None, argparse.SUPPRESS):
                text += f" (기본 {a.default})"
            lines.append(f"      {flag:<34} {text}".rstrip())
    lines += [
        "",
        "예:",
        "  kispilot setup                       앱키 등록 (처음 한 번)",
        "  kispilot ui --port 8080              웹 콘솔을 8080 포트로",
        "  kispilot install cursor --dry-run    Cursor 설정에 무엇이 들어갈지 미리 보기",
    ]
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="kispilot", description="KISPilot — 한국투자증권 Open API 에이전트 도구 (비공식)",
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("setup", help="앱키·계좌를 OS 키체인에 등록")
    s.add_argument("--mode", choices=["real", "paper", "both"], help="등록할 키 (생략하면 물어봄)")
    s.add_argument("--no-verify", action="store_true", help="토큰 발급으로 검증하지 않고 저장")
    s.add_argument("--from-env", action="store_true", help="환경변수/.env 의 값을 키체인으로 옮김")
    s.set_defaults(func=cmd_setup)

    sub.add_parser("status", help="등록 상태 확인").set_defaults(func=cmd_status)

    lo = sub.add_parser("logout", help="키체인에서 키 삭제 + 토큰 폐기")
    lo.add_argument("--mode", choices=["real", "paper", "both"], default="both", help="지울 키")
    lo.add_argument("-y", "--yes", action="store_true", help="확인 없이 진행")
    lo.set_defaults(func=cmd_logout)

    u = sub.add_parser("ui", help="웹 콘솔 실행")
    u.add_argument("--host", default="127.0.0.1", help="바인드 주소. 0.0.0.0 이면 다른 기기에서도 접속 (접속 키가 자동으로 켜짐)")
    u.add_argument("--port", type=int, default=8000, help="포트")
    u.add_argument("--reload", action="store_true", help="코드를 고치면 자동으로 다시 시작 (개발용)")
    u.set_defaults(func=cmd_ui)

    ins = sub.add_parser("install", help="AI 클라이언트에 MCP 서버 등록")
    ins.add_argument("target", choices=INSTALL_TARGETS, help="등록할 AI 클라이언트")
    ins.add_argument("--allow-real-orders", action="store_true", help="실전 주문 허용 (켜도 2단계 확인을 거침)")
    ins.add_argument("--name", default="kispilot", help="등록 이름")
    ins.add_argument("--config", help="설정 파일 경로를 직접 지정 (claude-code 제외)")
    ins.add_argument("--dry-run", action="store_true", help="바꿀 내용만 보여주고 저장하지 않음")
    ins.set_defaults(func=cmd_install)

    un = sub.add_parser("uninstall", help="AI 클라이언트에서 MCP 서버 등록 해제")
    un.add_argument("target", choices=INSTALL_TARGETS, help="해제할 AI 클라이언트")
    un.add_argument("--name", default="kispilot", help="등록 이름")
    un.add_argument("--config", help="설정 파일 경로를 직접 지정 (claude-code 제외)")
    un.set_defaults(func=cmd_uninstall)

    mc = sub.add_parser("mcp", help="MCP 서버 실행 (stdio — AI 클라이언트가 실행)")
    mc.add_argument("--check", action="store_true", help="서버를 띄우지 않고 도구 등록·키 상태만 확인")
    mc.set_defaults(func=cmd_mcp)

    p.epilog = _commands_help(sub)
    args = p.parse_args(argv)
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        _print("\n중단했습니다.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
