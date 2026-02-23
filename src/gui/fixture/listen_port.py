# listen_port.py
from __future__ import annotations

import time
import threading
import queue
from dataclasses import dataclass
from collections import deque
from typing import Callable, Deque, List, Optional, Pattern, Tuple, Literal

import serial


# ----------------------------
# Data structures
# ----------------------------
@dataclass
class RxLine:
    seq: int
    t: float
    text: str


ReqKind = Literal["write", "clear_in", "clear_out", "flush"]


@dataclass
class IORequest:
    kind: ReqKind
    cmd: str = ""
    append_crlf: bool = True
    done: Optional[threading.Event] = None
    error: Optional[BaseException] = None


# ----------------------------
# Main class
# ----------------------------
class ListenPort:
    """
    ListenPort:
      - 1 thread I/O duy nhất: open/read/parse + drain tx queue để write/flush/reset buffers
      - GUI thread chỉ gọi API (thread-safe)
      - Có send_and_collect tương tự core_serial

    Notes:
      - Nếu bạn gọi send_and_collect trực tiếp trên Tk main thread => UI sẽ block.
        Nên gọi nó thông qua SubThreadRunner/SubProcessRunner hoặc thread riêng của bạn.

    Usage:
    from listen_port import ListenPort
    import re

    lp = ListenPort("COM3", 115200, log=print)
    lp.start()

    # gửi “fire-and-forget” (đã write+flush rồi mới return)
    lp.send("help")

    # gửi + đợi kết quả
    ok, best, lines = lp.send_and_collect(
        "ATE START",
        timeout=5.0,
        expect=re.compile(r"PASSED=\d"),
        idle_after_last_rx=0.5,
    )
    print(ok, best)
    print(lines)

    # reset/reconnect
    lp.reset()

    # stop hẳn
    lp.stop()

    """

    def __init__(
        self,
        port: str,
        baudrate: int,
        *,
        keep_lines: int = 2000,
        read_sleep: float = 0.005,
        decode: str = "latin-1",      # 1:1 dễ debug byte lạ
        encode: str = "utf-8",
        write_timeout: float = 1.0,
        open_timeout: float = 2.0,
        max_reqs_per_tick: int = 100,
        log: Optional[Callable[[str], None]] = None,
        on_rx: Optional[Callable[[str], None]] = None,  # callback mỗi khi có line RX
        dispatch: Optional[Callable[[Callable[[], None]], None]] = None, 
    ) -> None:
        self.port = str(port)
        self.baudrate = int(baudrate)

        self.keep_lines = int(keep_lines)
        self.read_sleep = float(read_sleep)
        self.decode = str(decode)
        self.encode = str(encode)
        self.write_timeout = float(write_timeout)
        self.open_timeout = float(open_timeout)
        self.max_reqs_per_tick = int(max_reqs_per_tick)

        self.log = log
        self.on_rx = on_rx
        self.dispatch = dispatch 

        # runtime
        self._ser: Optional[serial.Serial] = None

        self._stop_evt = threading.Event()
        self._ready_evt = threading.Event()

        # request queue for IO thread (write/clear/flush)
        self._req_q: "queue.Queue[IORequest]" = queue.Queue()

        # RX state
        self._rx_buf = bytearray()
        self._lines: Deque[RxLine] = deque(maxlen=self.keep_lines)
        self._seq = 0
        self._last_rx_time = 0.0
        self._data_evt = threading.Event()  # set when new line arrived

        # thread
        self._th: Optional[threading.Thread] = None
        self._lock_state = threading.Lock()  # protect start/stop/reset re-entrancy

    # ----------------------------
    # lifecycle
    # ----------------------------
    def start(self) -> None:
        with self._lock_state:
            if self._th and self._th.is_alive():
                return
            self._stop_evt.clear()
            self._ready_evt.clear()

            self._th = threading.Thread(target=self._io_loop, daemon=True, name=f"ListenPort-{self.port}")
            self._th.start()

        if not self._ready_evt.wait(timeout=self.open_timeout):
            raise RuntimeError(f"ListenPort: open port timeout: {self.port}@{self.baudrate}")

    def stop(self) -> None:
        with self._lock_state:
            self._stop_evt.set()
            th = self._th

        if th:
            th.join(timeout=1.0)

        self._close_serial()

        with self._lock_state:
            self._th = None
            self._ready_evt.clear()

    def reset(self, *, clear_lines: bool = True) -> None:
        """
        reset = stop -> clear state -> start lại (reconnect)
        """
        self.stop()
        # clear local buffers
        self._rx_buf = bytearray()
        self._last_rx_time = 0.0
        self._data_evt.clear()
        if clear_lines:
            self._lines.clear()
            self._seq = 0

        # drain pending requests
        try:
            while True:
                _ = self._req_q.get_nowait()
        except queue.Empty:
            pass

        self.start()

    def is_ready(self) -> bool:
        return self._ready_evt.is_set()

    # ----------------------------
    # rx helpers
    # ----------------------------
    def snapshot_seq(self) -> int:
        return self._seq

    def get_lines_since(self, seq0: int) -> List[str]:
        # copy list để tránh iteration dài trên deque đang thay đổi
        return [x.text for x in list(self._lines) if x.seq > seq0]

    # ----------------------------
    # IO actions (all executed by IO thread)
    # ----------------------------
    def clear_input_buffer(self) -> None:
        self._ensure_ready()
        self._enqueue_req(IORequest(kind="clear_in"), wait_done=True)

    def clear_output_buffer(self) -> None:
        self._ensure_ready()
        self._enqueue_req(IORequest(kind="clear_out"), wait_done=True)

    def flush(self) -> None:
        self._ensure_ready()
        self._enqueue_req(IORequest(kind="flush"), wait_done=True)

    def send(self, cmd: str, *, append_crlf: bool = True, wait_written: bool = True) -> None:
        """
        Đẩy lệnh vào IO thread để write+flush.
        - wait_written=True: đợi write+flush xong rồi return (an toàn cho send_and_collect)
        """
        self._ensure_ready()
        req = IORequest(kind="write", cmd=str(cmd), append_crlf=bool(append_crlf))
        self._enqueue_req(req, wait_done=wait_written)

        if self.log:
            self.log(f"[TX] {cmd!r}")

    def send_and_collect(
        self,
        cmd: str,
        *,
        timeout: float = 5.0,
        idle_after_last_rx: float = 0.6,
        expect: Optional[Pattern[str]] = None,
        reject: Optional[Pattern[str]] = None,
        append_crlf: bool = True,
        clear_before_send: bool = True,
        on_line: Optional[Callable[[str], None]] = None,  # <-- emit realtime (per-command)
    ) -> Tuple[bool, List[str]]:
        """
        Gom response theo từng command (dựa trên seq0), không phụ thuộc last_rx_time global.

        - clear_before_send: reset input buffer trước khi gửi (tránh dính rác cũ)
        - on_line: được gọi mỗi khi có line mới thuộc command (chạy ở thread đang gọi send_and_collect)
                 => nếu update Tk, nhớ dùng root.after(...)
        Return:
          (ok, lines)
            ok: nếu có expect -> ok = matched; nếu không expect -> ok = (có nhận được ít nhất 1 line)
            lines: toàn bộ line thuộc command
        """
        self._ensure_ready()

        if clear_before_send:
            self.clear_input_buffer()

        # mốc “bắt đầu command”
        seq0 = self.snapshot_seq()
        last_seen_seq = seq0

        self._data_evt.clear()

        # gửi lệnh (đợi write+flush xong)
        self.send(cmd, append_crlf=append_crlf, wait_written=True)

        t0 = time.perf_counter()
        matched = False
        got_any = False
        last_rx_in_cmd = 0.0

        out_lines: List[str] = []

        while True:
            now = time.perf_counter()
            if now - t0 >= timeout:
                break

            # lấy các line mới kể từ last_seen_seq (incremental)
            snap = list(self._lines)
            new_rx = [x for x in snap if x.seq > last_seen_seq]

            if new_rx:
                got_any = True
                last_seen_seq = new_rx[-1].seq
                last_rx_in_cmd = new_rx[-1].t

                for rx in new_rx:
                    # chỉ nhận line thuộc command: seq phải > seq0
                    if rx.seq > seq0:
                        out_lines.append(rx.text)

                        # emit realtime (per-command)
                        if on_line:
                            try:
                                on_line(rx.text)
                            except Exception:
                                pass

                        # check expect
                        if expect is not None and (not matched) and expect.search(rx.text):
                            matched = True
                        if reject is not None and reject.search(rx.text):
                            return False, out_lines

            # điều kiện kết thúc: chỉ áp dụng idle window SAU KHI đã có RX thuộc command
            # chỉ kết thúc theo idle window SAU KHI đã có RX thuộc command
            if got_any and (now - last_rx_in_cmd) >= idle_after_last_rx:
                ok = matched if expect is not None else got_any
                return ok, out_lines

            # đợi có RX mới (hoặc tick)
            self._data_evt.wait(timeout=0.01)
            self._data_evt.clear()

        # timeout
        ok = matched if expect is not None else got_any
        return ok, out_lines


    # ----------------------------
    # internal helpers
    # ----------------------------
    def _ensure_ready(self) -> None:
        if not self._ready_evt.wait(timeout=self.open_timeout):
            raise RuntimeError("ListenPort: port not ready")

    def _enqueue_req(self, req: IORequest, *, wait_done: bool) -> None:
        if wait_done:
            req.done = threading.Event()
        self._req_q.put(req)
        if wait_done and req.done:
            req.done.wait(timeout=self.write_timeout + 2.0)
            if req.error:
                raise RuntimeError(f"ListenPort request failed: {req.kind}: {req.error}")

    def _close_serial(self) -> None:
        try:
            if self._ser and self._ser.is_open:
                self._ser.close()
        except Exception:
            pass
        self._ser = None

    # def _emit_line(self, s: str) -> None:
    #     self._seq += 1
    #     self._last_rx_time = time.perf_counter()
    #     self._lines.append(RxLine(seq=self._seq, t=self._last_rx_time, text=s))

    #     # notify waiters
    #     self._data_evt.set()

    #     # callbacks
    #     if self.log:
    #         self.log(f"[RX] {s}")
    #     if self.on_rx:
    #         try:
    #             self.on_rx(s)
    #         except Exception:
    #             pass
        
    
    def _emit_line(self, s: str) -> None:
        self._seq += 1
        self._last_rx_time = time.perf_counter()
        self._lines.append(RxLine(seq=self._seq, t=self._last_rx_time, text=s))

        self._data_evt.set()

        # ---- callbacks (safe dispatch) ----
        disp = self.dispatch  # capture local

        lg = self.log
        if lg:
            try:
                if disp:
                    disp(lambda s=s, lg=lg: lg(f"[RX] {s}"))
                else:
                    lg(f"[RX] {s}")
            except Exception:
                pass

        cb = self.on_rx
        if cb:
            try:
                if disp:
                    disp(lambda s=s, cb=cb: cb(s))
                else:
                    cb(s)
            except Exception:
                pass

    def _open_serial(self) -> None:
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=0,               # non-blocking read
            write_timeout=self.write_timeout,
        )

    def _handle_req(self, req: IORequest) -> None:
        """
        Thực thi request trên IO thread.
        """
        try:
            ser = self._ser
            if ser is None or (not ser.is_open):
                raise RuntimeError("serial not open")

            if req.kind == "write":
                payload = req.cmd.rstrip("\r\n")
                if req.append_crlf:
                    payload += "\r\n"
                b = payload.encode(self.encode, errors="replace")
                ser.write(b)
                ser.flush()

            elif req.kind == "clear_in":
                try:
                    ser.reset_input_buffer()
                except Exception:
                    pass

            elif req.kind == "clear_out":
                try:
                    ser.reset_output_buffer()
                except Exception:
                    pass

            elif req.kind == "flush":
                try:
                    ser.flush()
                except Exception:
                    pass

        except BaseException as e:
            req.error = e
        finally:
            if req.done:
                req.done.set()

    def _io_loop(self) -> None:
        # open serial
        try:
            self._open_serial()
            self._ready_evt.set()
        except Exception as e:
            if self.log:
                self.log(f"[ERR] open {self.port}@{self.baudrate}: {e}")
            return

        assert self._ser is not None

        while not self._stop_evt.is_set():
            # 1) drain some IO requests (TX/clear/flush)
            drained = 0
            while drained < self.max_reqs_per_tick:
                try:
                    req = self._req_q.get_nowait()
                except queue.Empty:
                    break
                self._handle_req(req)
                drained += 1

            # 2) read incoming bytes
            try:
                n = self._ser.in_waiting
            except Exception:
                n = 0

            try:
                chunk = self._ser.read(n or 1)
            except Exception:
                chunk = b""

            if chunk:
                self._rx_buf += chunk

                # split by newline
                while b"\n" in self._rx_buf:
                    line, _, rest = self._rx_buf.partition(b"\n")
                    self._rx_buf = bytearray(rest)

                    s = line.decode(self.decode, errors="replace").replace("\r", "").strip()
                    if s:
                        self._emit_line(s)
            else:
                time.sleep(self.read_sleep)

        self._close_serial()

