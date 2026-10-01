"""KIS 실시간(웹소켓) 중계 허브.

KIS 는 앱키 하나당 웹소켓 접속을 하나만 허용한다(두 번째 접속은 OPSP8996 ALREADY IN USE appkey).
그래서 서버가 접속 하나를 유지하면서, 화면들이 요청한 (종류, 종목) 구독을 참조 수로 관리하고
받은 데이터를 해당 구독을 가진 브라우저 스트림(SSE)으로 나눠 보낸다.

  - 브라우저 연결이 끊기면(페이지 이동·탭 닫기) 그 구독의 참조 수를 줄이고, 0 이 된 구독은
    UNSUB_GRACE 초 뒤에 KIS 에서 해제한다. 그 사이에 같은 구독이 다시 오면(예: 종목 → 주문 화면) 유지한다.
  - 구독이 하나도 없는 상태가 IDLE_CLOSE 초 이어지면 KIS 접속을 닫는다.
  - 1세션 최대 41건. 넘치는 구독은 받지 않고 브라우저에 알린다.

종류(kind): ccnl(체결가) · book(호가) · member(회원사) · program(프로그램매매) — 모두 실전 앱키 사용.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict
from typing import Optional

import websockets

from kispilot.api.config import WS_DOMAIN
from kispilot.api.oauth import kis_token
from kispilot.api.realtime import (
    realtime_asking_price_total,
    realtime_ccnl_total,
    realtime_member_total,
    realtime_program_trade_total,
)

KINDS = {
    "ccnl": realtime_ccnl_total,
    "book": realtime_asking_price_total,
    "member": realtime_member_total,
    "program": realtime_program_trade_total,
}
_TR_TO_KIND = {m._TR_ID: k for k, m in KINDS.items()}

MAX_TOPICS = 41
UNSUB_GRACE = 10.0
IDLE_CLOSE = 60.0
RETRY_IN_USE = 30.0

log = logging.getLogger("uvicorn.error")

Topic = tuple[str, str]  # (kind, code)
CLOSE = "__close__"      # 서버 종료 시 브라우저 스트림을 끝내라는 내부 신호


class Client:
    """브라우저 스트림 하나. 받은 이벤트를 큐에 쌓고 SSE 핸들러가 꺼내 보낸다."""

    def __init__(self, topics: set[Topic]):
        self.topics = topics
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=500)

    def push(self, event: str, data: dict) -> None:
        if self.queue.full():  # 느린 브라우저: 오래된 것부터 버린다
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self.queue.put_nowait((event, data))


class Hub:
    def __init__(self) -> None:
        self.clients: set[Client] = set()
        self.refs: dict[Topic, int] = {}
        self.unsub_at: dict[Topic, float] = {}   # 참조 0 이 된 구독의 해제 예정 시각
        self.active: set[Topic] = set()          # KIS 에 실제로 구독된 것
        self.status = {"state": "idle", "message": ""}
        self._ws = None
        self._task: Optional[asyncio.Task] = None
        self._key: Optional[str] = None
        self._idle_since = time.monotonic()
        self._closing = False

    # ── 브라우저 쪽 ─────────────────────────────────────────

    def add(self, topics: set[Topic]) -> Client:
        wanted = self._wanted()
        accepted, rejected = set(), []
        for t in sorted(topics):
            if t in wanted or len(wanted) < MAX_TOPICS:
                accepted.add(t)
                wanted.add(t)
            else:
                rejected.append(t)
        client = Client(accepted)
        self.clients.add(client)
        for t in accepted:
            self.refs[t] = self.refs.get(t, 0) + 1
            self.unsub_at.pop(t, None)
        client.push("status", self.status)
        if rejected:
            client.push("status", {"state": "limit", "message": f"실시간 구독 한도({MAX_TOPICS}건) 초과로 {len(rejected)}건은 제외했습니다."})
        self._ensure_running()
        return client

    def remove(self, client: Client) -> None:
        if client not in self.clients:
            return
        self.clients.discard(client)
        now = time.monotonic()
        for t in client.topics:
            n = self.refs.get(t, 0) - 1
            if n > 0:
                self.refs[t] = n
            else:
                self.refs.pop(t, None)
                self.unsub_at[t] = now + UNSUB_GRACE

    def snapshot(self) -> dict:
        return {
            "status": self.status,
            "clients": len(self.clients),
            "subscribed": sorted(f"{k}:{c}" for k, c in self.active),
            "pending_unsubscribe": sorted(f"{k}:{c}" for k, c in self.unsub_at),
        }

    async def close(self) -> None:
        """서버 종료 시: 구독을 모두 해제하고 웹소켓을 정상 종료 프레임으로 닫는다.

        KIS 는 비정상 종료(해제 없이 끊김)가 반복되면 앱키 실시간 사용을 일시 제한하므로,
        종료 신호를 받자마자(main.py) 이 함수를 먼저 부른다. 여러 번 불려도 안전하다.
        """
        if self._closing:
            return
        self._closing = True
        for c in list(self.clients):  # 브라우저 스트림도 바로 끝낸다 (재접속은 브라우저가 알아서)
            c.push(CLOSE, {})
        task, self._task = self._task, None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                for kind, code in sorted(self.active):
                    await ws.send(KINDS[kind]._subscribe_msg(self._key, code, "2"))
                await ws.close()
                log.info("[realtime] 구독 %d건 해제 후 KIS 웹소켓 정상 종료", len(self.active))
            except Exception as e:
                log.warning("[realtime] 종료 중 오류: %s: %s", type(e).__name__, e)
        self.active.clear()

    # ── 내부 ────────────────────────────────────────────────

    def _wanted(self) -> set[Topic]:
        return set(self.refs) | set(self.unsub_at)

    def _ensure_running(self) -> None:
        # 구독 변경은 수신 대기(1초)가 끝날 때마다 _sync() 에서 반영된다.
        if self._closing:
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run(), name="kis-realtime-hub")

    def _broadcast_status(self, state: str, message: str = "") -> None:
        self.status = {"state": state, "message": message}
        for c in list(self.clients):
            c.push("status", self.status)

    async def _disconnect(self) -> None:
        ws, self._ws = self._ws, None
        self.active.clear()
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass

    async def _connect(self) -> None:
        if self._key is None:
            self._key = await asyncio.to_thread(kis_token._issue_websocket_key, "real")
        # 어느 TR 경로로 붙어도 한 접속에서 여러 TR 을 구독할 수 있다.
        self._ws = await websockets.connect(WS_DOMAIN["real"] + realtime_ccnl_total.URL, ping_interval=None)
        self.active.clear()
        log.info("[realtime] KIS 웹소켓 접속")

    async def _send(self, topic: Topic, tr_type: str) -> None:
        kind, code = topic
        await self._ws.send(KINDS[kind]._subscribe_msg(self._key, code, tr_type))
        if tr_type == "1":
            self.active.add(topic)
        else:
            self.active.discard(topic)
        log.info("[realtime] %s %s:%s", "구독" if tr_type == "1" else "해제", kind, code)

    async def _sync(self) -> None:
        now = time.monotonic()
        for t, at in list(self.unsub_at.items()):
            if at <= now:
                self.unsub_at.pop(t, None)
        wanted = self._wanted()
        for t in sorted(self.active - wanted):
            await self._send(t, "2")
        for t in sorted(wanted - self.active):
            await self._send(t, "1")

    async def _run(self) -> None:
        backoff = 2.0
        while True:
            try:
                if not self._wanted():
                    if self._ws is not None and time.monotonic() - self._idle_since > IDLE_CLOSE:
                        await self._disconnect()
                        self._broadcast_status("idle")
                        log.info("[realtime] 구독이 없어 KIS 접속 종료")
                    if self._ws is None:
                        self._task = None
                        return
                else:
                    self._idle_since = time.monotonic()

                if self._ws is None:
                    self._broadcast_status("connecting", "KIS 실시간 접속 중…")
                    await self._connect()
                    backoff = 2.0
                await self._sync()
                if self.status["state"] != "live" and self.active:
                    self._broadcast_status("live")

                try:
                    msg = await asyncio.wait_for(self._ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                await self._handle(msg)

            except asyncio.CancelledError:
                raise
            except _InUse:
                await self._disconnect()
                self._broadcast_status("error", "같은 앱키로 다른 프로그램(MCP 서버 등)이 실시간 접속 중입니다. 30초 뒤 다시 시도합니다.")
                await asyncio.sleep(RETRY_IN_USE)
            except _BadKey:
                self._key = None
                await self._disconnect()
            except Exception as e:  # 접속 끊김 등 → 다시 접속
                log.warning("[realtime] 접속 오류: %s: %s", type(e).__name__, e)
                await self._disconnect()
                self._broadcast_status("connecting", f"재접속 대기 ({type(e).__name__})")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def _handle(self, msg: str) -> None:
        if not msg:
            return
        if msg[0] in ("0", "1"):
            parts = msg.split("|", 3)
            kind = _TR_TO_KIND.get(parts[1]) if len(parts) == 4 else None
            if kind is None:
                return
            for row in KINDS[kind]._parse(int(parts[2]), parts[3]):
                data = asdict(row)
                topic = (kind, data.get("mksc_shrn_iscd") or "")
                for c in list(self.clients):
                    if topic in c.topics:
                        c.push(kind, data)
            return

        try:
            obj = json.loads(msg)
        except json.JSONDecodeError:
            return
        header = obj.get("header", {})
        if header.get("tr_id") == "PINGPONG":
            await self._ws.send(msg)
            return
        body = obj.get("body", {})
        code = body.get("msg_cd", "")
        if body.get("rt_cd") in (None, "0"):
            return
        log.warning("[realtime] KIS 거부: %s %s (%s)", code, body.get("msg1"), header.get("tr_key"))
        if code == "OPSP8996":
            raise _InUse()
        if "approval" in (body.get("msg1") or "").lower():
            raise _BadKey()
        self._broadcast_status("warn", f"[{header.get('tr_key', '')}] {body.get('msg1', '')}")


class _InUse(Exception):
    pass


class _BadKey(Exception):
    pass


hub = Hub()
