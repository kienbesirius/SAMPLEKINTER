# SubThread.py
# Lightweight Tkinter worker runner (no PIL, no extra deps)
# - Run heavy functions in a background thread
# - Deliver result/exception back to Tk main thread safely via root.after
# - Optional progress channel + cooperative cancel (if your function accepts these)

from __future__ import annotations

import queue
import threading
import time
import traceback
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Optional, Dict, Tuple


ProgressCallback = Callable[[Any], None]
SuccessCallback = Callable[[Any, Dict[str, Any]], None]
ErrorCallback = Callable[[str, Dict[str, Any]], None]
FinallyCallback = Callable[[str, Dict[str, Any]], None]
StartCallback = Callable[[Dict[str, Any]], None]


@dataclass(frozen=True)
class TaskHandle:
    """A handle you can keep to cancel cooperatively (if the worker supports it)."""
    task_id: str
    cancel_event: threading.Event


class SubThreadRunner:
    """
    Tkinter-safe background runner.

    Usage:
        runner = SubThreadRunner(root)
        handle = runner.submit(func, kwargs={...},
                               on_start=..., on_success=..., on_error=..., on_finally=...,
                               on_progress=...)
    """

    def __init__(self, root, poll_ms: int = 80):
        self.root = root
        self.poll_ms = int(poll_ms)

        self._q: "queue.Queue[Tuple[str, str, Any, Dict[str, Any]]]" = queue.Queue()
        self._lock = threading.Lock()
        self._seq = 0
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._polling_started = False

    # ---------------------------
    # Public API
    # ---------------------------
    def submit(
        self,
        func: Callable[..., Any],
        args: Tuple[Any, ...] = (),
        kwargs: Optional[Dict[str, Any]] = None,
        *,
        name: Optional[str] = None,
        on_start: Optional[StartCallback] = None,
        on_success: Optional[SuccessCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        on_finally: Optional[FinallyCallback] = None,
        on_progress: Optional[ProgressCallback] = None,
        inject_cancel_event: bool = True,
        inject_progress_cb: bool = True,
        daemon: bool = True,
    ) -> TaskHandle:
        """
        Run func(*args, **kwargs) in a background thread.

        Callbacks are executed on Tk main thread:
            on_start(meta)
            on_success(result, meta)
            on_error(traceback_str, meta)
            on_finally(status, meta)   # status: "ok" | "err" | "cancelled"

        Optional injection:
            - cancel_event (threading.Event)
            - progress_cb (callable)
        Only injected if func signature accepts those names.
        """
        if kwargs is None:
            kwargs = {}

        with self._lock:
            self._seq += 1
            task_id = f"task-{int(time.time()*1000)}-{self._seq}"
            cancel_event = threading.Event()

            meta: Dict[str, Any] = {
                "task_id": task_id,
                "name": name or getattr(func, "__name__", "task"),
                "func": func,
            }

            # store callbacks
            self._tasks[task_id] = {
                "meta": meta,
                "on_start": on_start,
                "on_success": on_success,
                "on_error": on_error,
                "on_finally": on_finally,
                "on_progress": on_progress,
                "cancel_event": cancel_event,
            }

        # start polling once
        self._ensure_polling()

        # prepare worker kwargs with safe injection
        wk_kwargs = dict(kwargs)
        if inject_cancel_event:
            self._try_inject_kw(func, wk_kwargs, "cancel_event", cancel_event)
        if inject_progress_cb:
            self._try_inject_kw(func, wk_kwargs, "progress_cb", lambda x: self._q.put((task_id, "progress", x, meta)))

        th = threading.Thread(
            target=self._worker,
            args=(task_id, func, args, wk_kwargs, meta, cancel_event),
            daemon=daemon,
            name=f"SubThreadRunner-{task_id}",
        )
        th.start()

        return TaskHandle(task_id=task_id, cancel_event=cancel_event)

    def cancel(self, handle: TaskHandle) -> None:
        """Cooperative cancel. Your worker must check cancel_event.is_set()."""
        handle.cancel_event.set()

    # ---------------------------
    # Internals
    # ---------------------------
    def _ensure_polling(self) -> None:
        if self._polling_started:
            return
        self._polling_started = True
        try:
            self.root.after(self.poll_ms, self._poll)
        except Exception:
            # root already destroyed
            self._polling_started = False

    def _try_inject_kw(self, func: Callable[..., Any], kw: Dict[str, Any], key: str, value: Any) -> None:
        # inject only if func has that parameter
        if key in kw:
            return
        try:
            sig = inspect.signature(func)
            if key in sig.parameters:
                kw[key] = value
        except Exception:
            # if we can't inspect, don't inject (avoid breaking unknown callables)
            return

    def _worker(
        self,
        task_id: str,
        func: Callable[..., Any],
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
        meta: Dict[str, Any],
        cancel_event: threading.Event,
    ) -> None:
        try:
            if cancel_event.is_set():
                self._q.put((task_id, "cancelled", None, meta))
                return

            result = func(*args, **kwargs)

            if cancel_event.is_set():
                self._q.put((task_id, "cancelled", None, meta))
            else:
                self._q.put((task_id, "ok", result, meta))
        except Exception:
            self._q.put((task_id, "err", traceback.format_exc(), meta))

    def _poll(self) -> None:
        # root destroyed => stop polling
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return

        try:
            while True:
                task_id, status, payload, meta = self._q.get_nowait()

                task = self._tasks.get(task_id)
                if not task:
                    continue  # already cleaned up

                # progress event (keep task alive)
                if status == "progress":
                    cb = task.get("on_progress")
                    if cb:
                        try:
                            cb(payload)
                        except Exception:
                            # don't crash UI because of progress callback
                            pass
                    continue

                # final status
                if status == "ok":
                    cb = task.get("on_success")
                    if cb:
                        cb(payload, meta)
                elif status == "cancelled":
                    # treat as finally only
                    pass
                else:  # "err"
                    cb = task.get("on_error")
                    if cb:
                        cb(payload, meta)

                cbf = task.get("on_finally")
                if cbf:
                    cbf(status, meta)

                # cleanup after final
                self._tasks.pop(task_id, None)

        except queue.Empty:
            pass

        # schedule next poll
        try:
            self.root.after(self.poll_ms, self._poll)
        except Exception:
            # root destroyed
            return
