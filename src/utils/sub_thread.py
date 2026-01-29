# SubThread.py
# Lightweight Tkinter worker runner (no PIL, no extra deps)
# - Run heavy functions in a background thread
# - Deliver result/exception back to Tk main thread safely via root.after
# - Optional progress channel + cooperative cancel (if your function accepts these)

from __future__ import annotations

import multiprocessing as mp
import sys

import queue
import threading
import time
import traceback
import inspect
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional, Tuple
from dataclasses import dataclass


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

# ---------------------------
# SubProcessRunner (CPU-bound safe)
# ---------------------------

_PROGRESS_SENTINEL = "__SUBPROCESS_RUNNER_PROGRESS__"

def _subprocess_worker_entry(task_id: str,
                             func,
                             args,
                             kwargs,
                             meta: dict,
                             out_q,
                             cancel_event) -> None:
    """
    Runs inside child process.
    - Replaces progress_cb sentinel with a real callback that posts to out_q.
    - Posts ("ok"/"err"/"cancelled") to out_q with task_id + meta.
    """
    try:
        # Build progress callback in the child (picklable-safe)
        if isinstance(kwargs, dict) and kwargs.get("progress_cb") == _PROGRESS_SENTINEL:
            def _progress_cb(payload):
                try:
                    out_q.put((task_id, "progress", payload, meta))
                except Exception:
                    pass
            kwargs["progress_cb"] = _progress_cb

        if cancel_event is not None and getattr(cancel_event, "is_set", None) and cancel_event.is_set():
            out_q.put((task_id, "cancelled", None, meta))
            return

        result = func(*args, **kwargs)

        if cancel_event is not None and getattr(cancel_event, "is_set", None) and cancel_event.is_set():
            out_q.put((task_id, "cancelled", None, meta))
        else:
            out_q.put((task_id, "ok", result, meta))

    except Exception:
        import traceback as _tb
        try:
            out_q.put((task_id, "err", _tb.format_exc(), meta))
        except Exception:
            pass


@dataclass(frozen=True)
class ProcessTaskHandle:
    task_id: str
    cancel_event: Any
    process: Any


class SubProcessRunner:
    """
    Tkinter-safe runner using multiprocessing.Process.
    Best for CPU-bound tasks (keeps Tk UI responsive by bypassing GIL).

    Notes:
    - func should be picklable (top-level function, not lambda/nested) for spawn.
    - On Windows (spawn), your app entry must be under if __name__ == "__main__".
    """

    def __init__(self, root, poll_ms: int = 50, start_method: Optional[str] = None):
        self.root = root
        self.poll_ms = int(poll_ms)

        if start_method is None:
            start_method = "spawn" if sys.platform.startswith("win") else "fork"

        self._ctx = mp.get_context(start_method)
        self._q = self._ctx.Queue()

        self._lock = threading.Lock()
        self._seq = 0
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._polling_started = False

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
    ) -> ProcessTaskHandle:
        if kwargs is None:
            kwargs = {}

        with self._lock:
            self._seq += 1
            task_id = f"task-{int(time.time()*1000)}-{self._seq}"
            cancel_event = self._ctx.Event()

            meta: Dict[str, Any] = {
                "task_id": task_id,
                "name": name or getattr(func, "__name__", "task"),
                "func_name": getattr(func, "__name__", "task"),
            }

            self._tasks[task_id] = {
                "meta": meta,
                "on_start": on_start,
                "on_success": on_success,
                "on_error": on_error,
                "on_finally": on_finally,
                "on_progress": on_progress,
                "cancel_event": cancel_event,
                "process": None,
            }

        self._ensure_polling()

        wk_kwargs = dict(kwargs)

        if inject_cancel_event:
            self._try_inject_kw(func, wk_kwargs, "cancel_event", cancel_event)

        # progress_cb must be created in the child process (avoid non-picklable lambdas)
        if inject_progress_cb:
            try:
                sig = inspect.signature(func)
                if "progress_cb" in sig.parameters and "progress_cb" not in wk_kwargs:
                    wk_kwargs["progress_cb"] = _PROGRESS_SENTINEL
            except Exception:
                pass

        p = self._ctx.Process(
            target=_subprocess_worker_entry,
            args=(task_id, func, args, wk_kwargs, meta, self._q, cancel_event),
            daemon=daemon,
            name=f"SubProcessRunner-{task_id}",
        )
        p.start()

        with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id]["process"] = p

        # Fire on_start on the Tk thread
        if on_start:
            try:
                self.root.after(0, lambda m=meta, cb=on_start: cb(m))
            except Exception:
                pass

        return ProcessTaskHandle(task_id=task_id, cancel_event=cancel_event, process=p)

    def cancel(self, handle: ProcessTaskHandle, force: bool = False) -> None:
        try:
            handle.cancel_event.set()
        except Exception:
            pass

        if force:
            try:
                if handle.process.is_alive():
                    handle.process.terminate()
            except Exception:
                pass
            task = self._tasks.get(handle.task_id)
            meta = task["meta"] if task else {"task_id": handle.task_id, "name": "task", "func_name": "task"}
            try:
                self._q.put((handle.task_id, "cancelled", None, meta))
            except Exception:
                pass

    def _ensure_polling(self) -> None:
        if self._polling_started:
            return
        self._polling_started = True
        try:
            self.root.after(self.poll_ms, self._poll)
        except Exception:
            self._polling_started = False

    def _try_inject_kw(self, func: Callable[..., Any], kw: Dict[str, Any], key: str, value: Any) -> None:
        if key in kw:
            return
        try:
            sig = inspect.signature(func)
            if key in sig.parameters:
                kw[key] = value
        except Exception:
            return

    def _poll(self) -> None:
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
                    continue

                if status == "progress":
                    cb = task.get("on_progress")
                    if cb:
                        try:
                            cb(payload)
                        except Exception:
                            pass
                    continue

                if status == "ok":
                    cb = task.get("on_success")
                    if cb:
                        cb(payload, meta)
                elif status == "err":
                    cb = task.get("on_error")
                    if cb:
                        cb(payload, meta)
                # cancelled => only finally

                cbf = task.get("on_finally")
                if cbf:
                    try:
                        cbf(status, meta)
                    except Exception:
                        pass

                proc = task.get("process")
                try:
                    if proc is not None:
                        proc.join(timeout=0.05)
                except Exception:
                    pass

                self._tasks.pop(task_id, None)

        except queue.Empty:
            pass
        except (EOFError, OSError):
            return

        try:
            self.root.after(self.poll_ms, self._poll)
        except Exception:
            return
        
@dataclass
class _QueuedTask:
    func: Callable[..., Any]
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    name: str
    on_start: Optional[StartCallback]
    on_success: Optional[SuccessCallback]
    on_error: Optional[ErrorCallback]
    on_finally: Optional[FinallyCallback]
    on_progress: Optional[ProgressCallback]

class SequentialTaskQueue:
    """
    - Submit nhiều task -> xếp hàng
    - Chỉ chạy 1 task mỗi lúc
    - Khi task kết thúc (ok/err/cancelled) -> tự start task kế tiếp
    """

    def __init__(self, *, root, runner) -> None:
        self.root = root
        self.runner = runner

        self._lock = threading.Lock()
        self._q: Deque[Tuple[str, _QueuedTask]] = deque()
        self._running_job_id: Optional[str] = None
        self._running_handle: Any = None

        self._seq = 0
        self._queued_cancel: set[str] = set()  # cancel trước khi start

    def submit(
        self,
        *,
        func: Callable[..., Any],
        args: Tuple[Any, ...] = (),
        kwargs: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        on_start: Optional[StartCallback] = None,
        on_success: Optional[SuccessCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        on_finally: Optional[FinallyCallback] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> str:
        """
        Returns: job_id (string) để bạn theo dõi/cancel.
        """
        if kwargs is None:
            kwargs = {}

        with self._lock:
            self._seq += 1
            job_id = f"job-{int(time.time()*1000)}-{self._seq}"
            t = _QueuedTask(
                func=func,
                args=args,
                kwargs=dict(kwargs),
                name=name or getattr(func, "__name__", "task"),
                on_start=on_start,
                on_success=on_success,
                on_error=on_error,
                on_finally=on_finally,
                on_progress=on_progress,
            )
            self._q.append((job_id, t))

        self._kick()
        return job_id

    def cancel(self, job_id: str, *, force: bool = False) -> None:
        """
        - Nếu job chưa chạy: remove khỏi queue.
        - Nếu đang chạy: gọi runner.cancel(handle).
        """
        with self._lock:
            # running?
            if self._running_job_id == job_id and self._running_handle is not None:
                handle = self._running_handle
            else:
                handle = None
                # remove from queue
                self._queued_cancel.add(job_id)

        if handle is not None:
            # cancel running task
            if hasattr(self.runner, "cancel"):
                try:
                    # SubProcessRunner.cancel(handle, force=...)
                    self.runner.cancel(handle, force=force)  # type: ignore[arg-type]
                except TypeError:
                    # SubThreadRunner.cancel(handle)
                    self.runner.cancel(handle)  # type: ignore[arg-type]
            return

        # nếu là queued-cancel, nó sẽ được skip khi start_next()

    def _kick(self) -> None:
        # đảm bảo start_next chạy trên Tk main thread
        try:
            self.root.after(0, self._start_next_if_idle)
        except Exception:
            pass

    def _start_next_if_idle(self) -> None:
        with self._lock:
            if self._running_job_id is not None:
                return  # đang chạy rồi
        self._start_next()

    def _start_next(self) -> None:
        # pop 1 job, skip những job đã bị cancel trước khi start
        while True:
            with self._lock:
                if not self._q:
                    self._running_job_id = None
                    self._running_handle = None
                    return

                job_id, task = self._q.popleft()

                if job_id in self._queued_cancel:
                    self._queued_cancel.remove(job_id)
                    # gọi finally(cancelled) cho thống nhất (optional)
                    if task.on_finally:
                        try:
                            task.on_finally("cancelled", {"task_id": job_id, "name": task.name})
                        except Exception:
                            pass
                    continue

                self._running_job_id = job_id

            # fire on_start (SubThreadRunner của bạn hiện không fire on_start)
            meta = {"task_id": job_id, "name": task.name}
            if task.on_start:
                try:
                    task.on_start(meta)
                except Exception:
                    pass

            # wrap callbacks để tự kéo job tiếp theo
            def _on_success(result: Any, _meta: Dict[str, Any]) -> None:
                if task.on_success:
                    try:
                        task.on_success(result, _meta)
                    except Exception:
                        pass

            def _on_error(tb: str, _meta: Dict[str, Any]) -> None:
                if task.on_error:
                    try:
                        task.on_error(tb, _meta)
                    except Exception:
                        pass

            def _on_finally(status: str, _meta: Dict[str, Any]) -> None:
                if task.on_finally:
                    try:
                        task.on_finally(status, _meta)
                    except Exception:
                        pass
                # mark idle + start next
                with self._lock:
                    self._running_job_id = None
                    self._running_handle = None
                self._kick()

            # NOTE:
            # - ta pass on_start=None vào runner để tránh double-call (SubProcessRunner có on_start)
            # - meta runner trả về có thể khác; mình dùng meta của runner luôn cho consistency
            handle = self.runner.submit(
                func=task.func,
                args=task.args,
                kwargs=task.kwargs,
                name=task.name,
                on_start=None,
                on_success=_on_success,
                on_error=_on_error,
                on_finally=_on_finally,
                on_progress=task.on_progress,
            )
            with self._lock:
                self._running_handle = handle
            return
