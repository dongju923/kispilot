"""KIS API 호출 추적기.

http_session 의 response hook 이 매 호출마다 record(mode) 를 호출하면,
sliding-window 기반으로 최근 1초 호출 수를 mode 별로 집계한다.

용도: 대시보드 상단에 실전/모의 초당 호출 수를 표시해 KIS 한도(real 20/s,
paper 2/s) 압박 여부를 한눈에 보이게 함.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque


_WINDOW_SEC = 3.0


class _CallTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._real: Deque[float] = deque()
        self._paper: Deque[float] = deque()

    def record(self, mode: str) -> None:
        now = time.monotonic()
        d = self._paper if mode == "paper" else self._real
        with self._lock:
            d.append(now)

    def rates(self) -> dict:
        cutoff = time.monotonic() - _WINDOW_SEC
        with self._lock:
            while self._real and self._real[0] < cutoff:
                self._real.popleft()
            while self._paper and self._paper[0] < cutoff:
                self._paper.popleft()
            real_rate = round(len(self._real) / _WINDOW_SEC, 1)
            paper_rate = round(len(self._paper) / _WINDOW_SEC, 1)
        return {"real": real_rate, "paper": paper_rate}


tracker = _CallTracker()