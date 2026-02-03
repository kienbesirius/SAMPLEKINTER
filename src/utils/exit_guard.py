# src/utils/exit_guard.py
from __future__ import annotations

import signal
import sys
import threading
import time
from typing import Callable, Optional


class ExitGuard:
    """
    Chặn thoát "nhẹ" trong N giây đầu (window close, Ctrl+C, SIGTERM... nếu bắt được).
    Không thể chặn force-kill (Windows End Task / Linux kill -9).
    """
    def __init__(self, seconds: float = 10.0, on_blocked: Optional[Callable[[str], None]] = None) -> None:
        self.seconds = float(seconds)
        self._start = time.monotonic()
        self._allowed = threading.Event()
        self._on_blocked = on_blocked or (lambda msg: print(msg, file=sys.stderr))

        t = threading.Timer(self.seconds, self._allowed.set)
        t.daemon = True
        t.start()

    def allowed(self) -> bool:
        return self._allowed.is_set()

    def remaining(self) -> float:
        if self.allowed():
            return 0.0
        return max(0.0, self.seconds - (time.monotonic() - self._start))

    def _signal_handler(self, signum, frame) -> None:
        if not self.allowed():
            self._on_blocked(f"[guard] Tool đang khởi tạo, chưa cho thoát. Còn ~{self.remaining():.1f}s")
            return
        raise SystemExit(0)

    def install_signals(self) -> None:
        # Tùy OS mà có/không có các signal này
        for name in ("SIGINT", "SIGTERM", "SIGHUP"):
            sig = getattr(signal, name, None)
            if sig is None:
                continue
            try:
                signal.signal(sig, self._signal_handler)
            except Exception:
                # Ví dụ: hạn chế trên 1 số runtime / thread
                pass
