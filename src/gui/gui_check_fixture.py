
from __future__ import annotations
import hashlib
import os
import re
import sys
import time
import threading
import math
import tkinter as tk
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Sequence
from typing import Callable, Optional, Tuple, Pattern
from src.gui.gui279_perfect_squares import count_perfect_squares
from src.platform import dpi
from src.gui.asset import load_assets 
from src.utils import sub_thread 
from src.utils.resource_path import RESOURCE_PATH, FONT_PATH, ICONS_PATH, app_dir
from src.utils.buffer_logger import build_log_buffer
from src.gui.widgets.button import bind_canvas_button
from src.gui.widgets.entry import bind_canvas_entry
from src.gui.widgets.text_area import bind_canvas_text_area
from src.gui.widgets.text import bind_canvas_text
from src.gui.widgets.fixture_check_slot_test import bind_fixture_check_slot_test
from src.gui.widgets.fixture_circle_status import bind_fixture_circle_com_status
from src.gui.widgets.paint_asset import bind_canvas_asset
from src.gui.widgets.guide_panel import GuidePanel, GuideStep
from src.gui.widgets.canvas_log_widget import bind_canvas_log_widget
from src.utils.enable_startup import enable_startup, disable_startup, is_startup_enabled
from src.gui.widgets.rect_panel import bind_center_rect_panel, CenterRectStyle
from src.gui.fixture.fill_multiple_monitor import fullscreen_on_monitor, get_monitors, monitor_from_point
from src.gui.fixture.get_fixture_port import get_fixture_port, parse_fixture_port_text, _LE_TO_ENDING
from src.gui.fixture.get_serial_list import get_serial_ports
from src.gui.fixture.listen_port import ListenPort
from src.utils.config_go import load_fixture_cfg, choose_slot_font, reset_slot_status_section_to_idle, update_ini_slot_status, load_slot_status_from_ini, SlotStatus, _ALLOWED_STATUS, update_ini_fixture_section, update_ini_manual_slot_info, update_ini_slot_guide, update_ini_slot_image
import concurrent.futures as cf

from src.utils.config_go import (
    load_fixture_cfg, choose_slot_font, load_slot_status_from_ini,
    get_test_plan, apply_test_plan_to_config_ini,
)
from src.gui.widgets.dialog import ModalOverlay
import tkinter.font as tkfont
from src.watchdog.watchdog_gui import wd_register, wd_heartbeat, wd_complete
from src.watchdog.watchdog_gui import ensure_watchdog_running_auto
from collections import deque
from src.utils.config_go import load_station_cfg
@dataclass
class GuideCase:
    """Một case kiểm tra gắn với 1 slot trong luồng GuidePanel."""
    slot_id: int
    slot_label: str
    title: str
    image_key: str
    cmd: str
    expect: Optional[Pattern[str]] = None
    reject: Optional[Pattern[str]] = None


# # CORE-1: Getting fixture port
# def obtaining_fixture_com(emit=print, cancel_event: threading.Event=None, progress_cb=None):
#     """
#     Lấy cổng COM của thiết bị fixture.
#     Trả về chuỗi tên cổng (vd: "COM3") hoặc None nếu không tìm thấy.
#     progress_cb: Callable[[str], None] - callback để báo tiến trình (nếu cần)
#     cancel_event: threading.Event - sự kiện để hủy bỏ quá trình tìm kiếm
#     """
#     cfg_path = Path(app_dir()) / "config.ini"
#     fx = load_fixture_cfg(cfg_path)

#     try:
#         def _progress(msg: str, *, port: str = "", baudrate: int = 0, ending_line: str = ""):
#             if progress_cb:
#                 progress_cb({
#                     "message": msg,
#                     "port": port,
#                     "baudrate": baudrate,
#                     "ending_line": ending_line,
#                 })
        
#         # 1) ưu tiên cache trong config
#         if fx.port and fx.port.upper() != "COMX":
#             _progress(f"Checking cached fixture port: {fx.port} ...",
#                       port=fx.port, baudrate=fx.baudrate, ending_line=fx.ending_line)

#             try:
#                 r = get_fixture_port(
#                     fx.port,
#                     baudrates=[fx.baudrate],
#                 )
#                 r = parse_fixture_port_text(r)
#                 if r:
#                     emit("Found fixture from config:", fx.port)
#                     # (optional) refresh cache theo kết quả thực tế nếu bạn đã mở rộng ProbeResult
#                     try:
#                         update_ini_fixture_section(
#                             cfg_path,
#                             port=r.port,
#                             baudrate=getattr(r.baudrate, "baudrate", fx.baudrate),
#                             ending_line=getattr(r.line_ending, "ending_line", fx.ending_line),
#                             timeout=fx.timeout,
#                         )
#                     except Exception:
#                         pass

#                     _progress("Found fixture (cached).",
#                             port=r.port,
#                             baudrate=getattr(r, "baudrate", fx.baudrate),
#                             ending_line=getattr(r, "ending_line", fx.ending_line))
#                     return r.port
#             except Exception as e:
#                 emit(f"Error checking cached port {fx.port}: {e}")
#                 r = None
                
#                 _progress(f"Cached port not fixture, fallback scanning...", port=fx.port,
#                         baudrate=fx.baudrate, ending_line=fx.ending_line)
                

#         ports = get_serial_ports()
#         for port in ports:
#             if cancel_event and cancel_event.is_set():
#                 emit("Obtaining COM cancelled.")
#                 return "COMX"
#             if progress_cb:
#                 progress_cb({"message": f"Checking {port}..."})
#             found = get_fixture_port(port)
            
#             if found:
#                 parsed = parse_fixture_port_text(found)
#                 emit("Found fixture on COM:", port)
#                 if progress_cb:
#                     progress_cb({
#                         "message": f"Found: {found}...",
#                         "port": parsed.port,
#                         "baudrate": parsed.baudrate,
#                         "ending_line": parsed.line_ending    
#                     })

#                 # 3) ghi cache vào config để lần sau nhanh
#                 update_ini_fixture_section(
#                     cfg_path,
#                     port=port,
#                     baudrate=getattr(r, "baudrate", parsed.baudrate),
#                     ending_line=getattr(r, "ending_line", parsed.line_ending),
#                     timeout=fx.timeout,
#                 )

#                 _progress("Found fixture (scanned).",
#                           port=port,
#                           baudrate=getattr(r, "baudrate", parsed.baudrate),
#                           ending_line=getattr(r, "ending_line", parsed.line_ending))
#                 return port
#             time.sleep(0.1)  # giả lập delay kiểm tra

#         emit("No fixture COM found.")
#         return "COMX"
#     except Exception as e:
#         emit(f"Found exception on obtaining COM ---")
#         emit(str(e))
#         return "COMX"

def obtaining_fixture_com(
    emit=print,
    cancel_event: threading.Event = None,
    progress_cb=None,
    *,
    max_workers: int = 4,
    retry_rounds: int = 10,
    retry_delay_s: float = 2.5,
    do_slow_fallback_last_round: bool = True,
):
    """
    Return: "COMx" hoặc "COMX" nếu không tìm thấy
    - scan song song max_workers port
    - found -> return ngay (không chờ tasks khác)
    - auto retry nếu fail (phòng COM bị chiếm dụng tạm thời)
    """
    cfg_path = Path(app_dir()) / "config.ini"
    fx = load_fixture_cfg(cfg_path)

    stop_evt = threading.Event()  # stop nội bộ khi found (cooperative)

    def is_stopped() -> bool:
        return stop_evt.is_set() or (cancel_event is not None and cancel_event.is_set())

    def _progress(msg: str, *, port: str = "", baudrate: int = 0, ending_line: str = ""):
        if progress_cb:
            progress_cb({
                "message": msg,
                "port": port,
                "baudrate": baudrate,
                "ending_line": ending_line,
            })

    # FAST params (tối ưu thời gian)
    fx_timeout = float(getattr(fx, "timeout", 0.5) or 0.5)
    fast_wait = min(0.35, max(0.15, fx_timeout))  # không quá nhỏ để tránh false negative
    fast_probe_cmds = ["?", "help", "HELP", "SHOW_COMMAND"]
    fast_kwargs = dict(
        baudrates=[fx.baudrate],
        per_cmd_wait_s=fast_wait,
        probe_cmds=fast_probe_cmds,
    )

    def _write_cache(parsed):
        # update_ini_fixture_section cần token "CRLF/LF/CR/NONE"
        ending_token = _LE_TO_ENDING.get(parsed.line_ending, "CRLF")
        try:
            update_ini_fixture_section(
                cfg_path,
                port=parsed.port,
                baudrate=parsed.baudrate,
                ending_line=ending_token,
                timeout=fx.timeout,
            )
        except Exception:
            pass

    def _try_cached() -> str | None:
        if not fx.port or fx.port.upper() == "COMX":
            return None

        _progress(
            f"Checking cached fixture port: {fx.port} ...",
            port=fx.port, baudrate=fx.baudrate, ending_line=fx.ending_line
        )

        try:
            found_txt = get_fixture_port(fx.port, **fast_kwargs)
            if not found_txt:
                return None

            parsed = parse_fixture_port_text(found_txt)
            emit("Found fixture from config:", parsed.port)
            _write_cache(parsed)

            _progress("Found fixture (cached).", port=parsed.port, baudrate=parsed.baudrate, ending_line=parsed.line_ending)
            return parsed.port

        except Exception as e:
            emit(f"Error checking cached port {fx.port}: {e}")
            return None

    def _scan_ports_parallel(ports: list[str], *, kwargs: dict) -> str | None:
        if not ports:
            return None

        max_w = min(max_workers, len(ports))
        executor = cf.ThreadPoolExecutor(max_workers=max_w)
        futures = {}
        found_port = None

        def worker(port: str):
            if is_stopped():
                return (port, None)
            _progress(f"Checking {port}...", port=port, baudrate=fx.baudrate, ending_line=fx.ending_line)
            try:
                txt = get_fixture_port(port, **kwargs)
                return (port, txt)
            except Exception as e:
                emit(f"[scan] {port} error: {e}")
                return (port, None)

        try:
            for p in ports:
                futures[executor.submit(worker, p)] = p

            for fut in cf.as_completed(futures):
                if is_stopped():
                    break

                port = futures[fut]
                try:
                    _p, found_txt = fut.result()
                except Exception as e:
                    emit(f"[scan] future error on {port}: {e}")
                    continue

                if not found_txt:
                    continue

                # FOUND
                stop_evt.set()
                try:
                    parsed = parse_fixture_port_text(found_txt)
                except Exception as e:
                    emit(f"parse_fixture_port_text failed: {e}")
                    found_port = port
                    break

                emit("Found fixture on COM:", parsed.port)
                if progress_cb:
                    progress_cb({
                        "message": f"Found: {found_txt}",
                        "port": parsed.port,
                        "baudrate": parsed.baudrate,
                        "ending_line": parsed.line_ending,
                    })

                _write_cache(parsed)
                _progress("Found fixture (scanned).", port=parsed.port, baudrate=parsed.baudrate, ending_line=parsed.line_ending)

                found_port = parsed.port

                # cancel futures chưa chạy
                for other in futures:
                    other.cancel()

                # QUAN TRỌNG: shutdown(wait=False) để return ngay, không bị chờ
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    executor.shutdown(wait=False)
                return found_port

            # không tìm thấy -> phải chờ kết thúc sạch để retry không bị “đè task”
            executor.shutdown(wait=True)
            return None

        finally:
            # nếu có exception nào đó mà chưa shutdown
            # (shutdown nhiều lần cũng không sao)
            try:
                if found_port is None:
                    executor.shutdown(wait=True)
            except Exception:
                pass

    # =========================
    # MAIN FLOW + RETRY
    # =========================
    if cancel_event and cancel_event.is_set():
        emit("Obtaining COM cancelled.")
        return "COMX"

    for round_idx in range(max(1, int(retry_rounds))):
        # reset stop flag mỗi vòng
        stop_evt.clear()

        if round_idx > 0:
            _progress(f"Retry scanning... ({round_idx+1}/{retry_rounds})")
            # sleep có kiểm tra cancel
            t_end = time.monotonic() + float(retry_delay_s)
            while time.monotonic() < t_end:
                if cancel_event and cancel_event.is_set():
                    emit("Obtaining COM cancelled.")
                    return "COMX"
                time.sleep(0.05)

        # 1) cached
        cached = _try_cached()
        if cached:
            return cached

        # 2) refresh ports list mỗi vòng (vì có thể COM vừa xuất hiện)
        ports = list(get_serial_ports() or [])
        if fx.port and fx.port in ports:
            ports.remove(fx.port)

        if not ports:
            emit("No serial ports found.")
            continue  # vẫn retry vì port có thể xuất hiện sau

        # 3) FAST scan song song
        found = _scan_ports_parallel(ports, kwargs=fast_kwargs)
        if found:
            return found

        # 4) SLOW fallback (chỉ làm ở vòng cuối để khỏi kéo dài retry)
        if do_slow_fallback_last_round and (round_idx == retry_rounds - 1):
            if cancel_event and cancel_event.is_set():
                emit("Obtaining COM cancelled.")
                return "COMX"
            found = _scan_ports_parallel(ports, kwargs={})  # default get_fixture_port (cover rộng hơn)
            if found:
                return found

    emit("No fixture COM found.")
    return "COMX"

# Keep the window always on top (works on Windows and many Tk backends)
def topmost_window(root):
    try:
        root.attributes("-topmost", True)
    except Exception:
        try:
            root.wm_attributes("-topmost", 1)
        except Exception:
            pass


def topmost_window(win: tk.Misc, on: bool = True, *, reassert: bool = True):
    val = True if on else False

    # 1) set topmost
    try:
        win.attributes("-topmost", val)
    except Exception:
        try:
            win.wm_attributes("-topmost", 1 if on else 0)
        except Exception:
            pass

    # 2) lift (focus_force đôi khi gây khó chịu / lỗi trên Linux, nên optional)
    try:
        win.lift()
    except Exception:
        pass

    # 3) Re-assert đúng 2 lần (KHÔNG gọi lại topmost_window)
    if reassert:
        # tránh schedule trùng nếu gọi nhiều lần
        try:
            if getattr(win, "_topmost_after_ids", None):
                for _id in win._topmost_after_ids:
                    try:
                        win.after_cancel(_id)
                    except Exception:
                        pass
        except Exception:
            pass

        win._topmost_after_ids = []

        def _reassert_once():
            # window đã bị destroy thì thôi
            try:
                if not win.winfo_exists():
                    return
            except Exception:
                return

            try:
                win.attributes("-topmost", val)
            except Exception:
                try:
                    win.wm_attributes("-topmost", 1 if on else 0)
                except Exception:
                    pass
            try:
                win.lift()
            except Exception:
                pass

        try:
            win._topmost_after_ids.append(win.after(50, _reassert_once))
            win._topmost_after_ids.append(win.after(200, _reassert_once))
        except Exception:
            pass

# Set application icon
def set_app_icon(root):
    icon_path = load_assets.ICON_ASSET.get("check_fixture_icon", ICONS_PATH / "delphi-svgrepo-com.ico")
    if not icon_path.exists():
        icon_path = app_dir() / "delphi-svgrepo-com.ico"
    try:
        root.iconbitmap(default=str(icon_path))
    except Exception as e:
        print(f"Không thể đặt icon ứng dụng: {e}")

# Set default font for the application
def set_default_font(font: tkfont.Font):
    tkfont.nametofont("TkDefaultFont").configure(
        family=font.actual("family"),
        size=font.actual("size"),
        weight=font.actual("weight"),
        slant=font.actual("slant"),
    )

def apply_fullscreen_and_capture_size(root: tk.Misc) -> tuple[int, int]:
    """
    Bật fullscreen (fallback zoomed/geometry) rồi trả về (w, h) thực tế
    sau khi WM áp kích thước.
    """
    # 1) thử fullscreen thật
    try:
        root.attributes("-fullscreen", True)
        root.update_idletasks()
        root.update()
        w, h = root.winfo_width(), root.winfo_height()
        if w > 1 and h > 1:
            return w, h
    except Exception:
        pass

    # 2) fallback maximize/zoom
    try:
        root.state("zoomed")  # Windows ok
        root.update_idletasks()
        root.update()
        w, h = root.winfo_width(), root.winfo_height()
        if w > 1 and h > 1:
            return w, h
    except Exception:
        pass

    # 3) fallback: geometry theo screen
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{sw}x{sh}+0+0")
    root.update_idletasks()
    root.update()
    return root.winfo_width(), root.winfo_height()

LogColor = Literal["white", "red", "green", "yellow", "blue"]

@dataclass
class ScreenContext:
    win: tk.Misc
    canvas: tk.Canvas
    items: Dict[str, int] = field(default_factory=dict)   # key -> canvas item id
    local: Dict[str, Any] = field(default_factory=dict)   # hover, etc.
    name: str = "screen"


class SharedUIState:
    def __init__(self):
        self.disabled: set[str] = set()
        self.pressed: set[str] = set()
        self.last_action: str = ""

class AppGUI:
    dpi.set_dpi_awareness()
    def create_extra_windows(self):
    
        for w in list(self.roots_extra):
            try:
                w.destroy()
            except Exception:
                pass
        self.roots_extra.clear()

        for idx, monitor in enumerate(self.other_windows, start=2):
            try:
                win = tk.Toplevel(self.root)
                win.title(f"GUI Tkinter")
                
                win._btn_pressed = {}
                win._btn_disabled = {}

                fullscreen_on_monitor(win, monitor)

                win.update_idletasks()
                win.update()

                def monitor_rect(monitor) -> tuple[int, int, int, int]:
                    """
                    Return (x, y, w, h) from a monitor object/dict.
                    """
                    if isinstance(monitor, dict):
                        x = int(monitor.get("x", 0))
                        y = int(monitor.get("y", 0))
                        w = int(monitor.get("width", monitor.get("w", 0)))
                        h = int(monitor.get("height", monitor.get("h", 0)))
                        return x, y, w, h

                    x = int(getattr(monitor, "x", 0))
                    y = int(getattr(monitor, "y", 0))
                    w = int(getattr(monitor, "width", getattr(monitor, "w", 0)))
                    h = int(getattr(monitor, "height", getattr(monitor, "h", 0)))
                    return x, y, w, h

                # Lấy size monitor trực tiếp
                # _, _, sw, sh = monitor_rect(monitor)
                sw, sh = int(monitor.width), int(monitor.height)
                
                canvas = tk.Canvas(win, bg=self.background_color, highlightthickness=0)
                canvas.pack(fill=tk.BOTH, expand=True)

                # sw, sh = win.winfo_width(), win.winfo_height()
                win._widgets = self._build_gui(win=win, canvas=canvas, sw=sw, sh=sh)
                # win.protocol("WM_DELETE_WINDOW", lambda w=win: self._guarded_close(w))

                # # Nuốt Alt+F4 cho đúng target là cửa sổ này
                # win.bind("<Alt-KeyPress-F4>", lambda e, w=win: (self._guarded_close(w), "break"))
                # win.bind("<Alt-F4>",          lambda e, w=win: (self._guarded_close(w), "break"))
                self._install_close_guard_for_window(win)

                self.roots_extra.append(win)

                topmost_window(win, True)
            except Exception:
                pass
            
    def __init__(self, root: tk.Tk):
        # Build log buffer
        self.is_admin = False
        self.startup_enabled = is_startup_enabled()
        self.cfg_path = app_dir() / "config.ini"
        self.status_map = load_slot_status_from_ini(self.cfg_path)

        self.log_buffer_max_lines = 500
        self.logger, self.log_buffer = build_log_buffer(max_buffer=self.log_buffer_max_lines)
        self.emit_msg = self.logger.info
        self._log_lock = getattr(self.logger, "_log_lock", threading.Lock())

        self.listenport = None
        self.current_com_response = ""

        self.cv_img_width, self.cv_img_height = 0, 0

        # Task management (no use)
        self._task_handler = None
        self._running = False

        self.root = root
        self.background_color = "#652200"
        
        # Get monitors
        # self.monitors = get_monitors()
        self.monitors = get_monitors(self.root)

        self.roots_extra: list[tk.Toplevel] = []
        # Get current monitors by pointer 
        px, py = root.winfo_pointerx(), root.winfo_pointery()
        current = monitor_from_point(self.monitors, px, py)

        # Fallback to primary or first monitor
        if current is None:
            current = next((m for m in self.monitors if m.is_primary), self.monitors[0])

        self.current_window = current

        others = [m for m in self.monitors if m != current]

        self.other_windows = others 

        # Init Runner 
        self.runner = sub_thread.SubProcessRunner(self.root)

        self.taskq = sub_thread.SequentialTaskQueue(root=self.root, runner=self.runner)

        # For sending commands
        self.io_runner = sub_thread.SubThreadRunner(self.root)
        self.io_taskq = sub_thread.SequentialTaskQueue(root=self.root, runner=self.io_runner)

        # Setting root
        self.root.title("GUI Tkinter")

        self.screen_width, self.screen_height = apply_fullscreen_and_capture_size(self.root)

        
        try:
            # true fullscreen (no window decorations)
            self.root.attributes("-fullscreen", True)
        except Exception:
            # fallback to maximized window where fullscreen isn't supported
            try:
                self.root.state('zoomed')
            except Exception:
                # last fallback: set geometry to screen size
                self.root.geometry(f"{self.screen_width}x{self.screen_height}")
        self.tektur_font = tkfont.Font(family="Tektur", size=11)
        set_default_font(self.tektur_font)
        set_app_icon(self.root)
        topmost_window(self.root)

        # Main Canvas (use screen size when fullscreen)
        self._canvas = tk.Canvas(self.root, bg=self.background_color, highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._btn_pressed = {}
        self._btn_disabled = {}

        # self.assets = load_assets.tk_load_image_resources()
        self.assets = load_assets.tk_load_image_resources(self.root)
        # Apply fullscreen on current monitor
        fullscreen_on_monitor(self.root, self.current_window)

        # TODO: Create UI for testing fixture
        self.widgets_main = self._build_gui(win=self.root,
            canvas=self._canvas,
            sw=self.screen_width,
            sh=self.screen_height,)
        
        self._init_guide_flow()

        self.create_extra_windows()

        self._resolve_COM()

        self._refresh_gui()

        self.install_close_lock()

        self.map_fixture = {
            "block_sensor_top_left": "fixture_sensor_top_left_guide_240x240",
            "block_sensor_top_right": "fixture_sensor_top_right_guide_240x240",
            "block_sensor_bottom_left": "fixture_sensor_bottom_left_guide_240x240",
            "block_sensor_bottom_right": "fixture_sensor_bottom_right_guide_240x240",
            "force_stop": "fixture_stop_guide_240x240",
        }

        for win in self._iter_windows():
            self.toggle_startup(win=win)

        self._wd_closing = False
        self._allow_app_exit = False
        self._wd_run_id = f"{os.getpid()}-{int(time.time())}"

        # register + start heartbeat (2s/lần, watchdog timeout 10s)
        self._wd_do_register()
        self._wd_start_heartbeat(interval_ms=2000)
        # Logout the width height screen
        self._update_logs_panel(f"screen_width: {self.screen_width} | screen_height: {self.screen_height}", "green")
        self._update_logs_panel(f"canvas_width: {self._canvas.winfo_width()} | canvas_height: {self._canvas.winfo_height()}", "green")
        self._start_com_guard(interval_ms=3000)
        

    def _wd_do_register(self) -> None:
        pid = os.getpid()
        if getattr(sys, "frozen", False):
            argv = [sys.executable, *sys.argv[1:]]
        else:
            argv = [sys.executable, os.path.abspath(sys.argv[0]), *sys.argv[1:]]
        self._update_logs_panel(f"argv: {argv}", "green")
        cwd = os.getcwd()

        def _after_ensure(_result, _meta):
            ok = wd_register(pid=pid, run_id=self._wd_run_id, app_argv=argv, cwd=cwd)
            self._update_logs_panel("[watchdog] registered" if ok else "[watchdog] register failed",
                                    "green" if ok else "yellow")

        self.io_taskq.submit(
            func=ensure_watchdog_running_auto,
            kwargs={"log_dir": app_dir() / "logs" / "watchdog", "log_callback": self._wd_log},
            name="Ensure Watchdog Running",
            on_start=self._task_start_cb,
            on_success=_after_ensure,
            on_error=self._task_error_cb,
            on_finally=self._task_finally_cb,
            on_progress=self._task_progress_cb,
        )

    def _wd_start_heartbeat(self, interval_ms: int = 2000) -> None:
        self._wd_hb_ms = int(interval_ms)

        def _tick():
            if self._wd_closing:
                return
            try:
                wd_heartbeat(pid=os.getpid(), run_id=self._wd_run_id)
            except Exception:
                pass
            try:
                self.root.after(self._wd_hb_ms, _tick)
            except Exception:
                pass

        try:
            self.root.after(self._wd_hb_ms, _tick)
        except Exception:
            pass

    def _wd_send_complete(self) -> None:
        try:
            wd_complete(pid=os.getpid(), run_id=self._wd_run_id)
        except Exception:
            pass

    # IMPORTANT: bypass close-guard when app closes by itself
    def _shutdown_app_now(self) -> None:
        self._wd_closing = True
        self._allow_app_exit = True

        # destroy extra windows first
        try:
            for w in list(getattr(self, "roots_extra", [])):
                try:
                    w.destroy()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            try:
                self.root.quit()
            except Exception:
                pass

    # TODO: Create UI for testing fixture
    def _build_gui(self, *, win: tk.Misc, canvas: tk.Canvas, sw: int, sh: int):
        # layout
        x_axis = sw // 2
        y_axis = sh // 2

        self.fx_cfg = load_fixture_cfg(app_dir()/"config.ini")

        # --- COM status (dock origin) ---
        com1 = bind_fixture_circle_com_status(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="com_status",
            x=-2, y=0,          # (x,y) là gốc DOCK theo logic bạn mới muốn
            label="COM1",
            status="stand_by",
        )
        com1.set_disabled(True)
        
        widgets: Dict[str, Any] = {
            "com1": com1,
        }
        
        y0 = int((y_axis // 2) * 0.8)       # row 1 y
        x0 = int(x_axis * 0.1)              # origin x
        slot_gap = self.assets["fixture_slot_test"].width() * 0.5  # giữ đúng như code bạn

        for i in range(1, 13):
            row = (i - 1) // 4
            col = (i - 1) % 4
            x = x0 + col * slot_gap
            y = y0 + row * slot_gap

            text = self.fx_cfg.slot_text.get(i, "")
            slot = bind_fixture_check_slot_test(
                root=win,
                canvas=canvas,
                assets=self.assets,
                tag=f"slot{i}_status",
                x=x, y=y,
                status=self.status_map.get(i, "idle"),
                text=text,
                text_font=self.tektur_font,
                command=lambda idx=i, w=win: self.show_manual_config_command(win=w, slot_idx=idx),
                is_admin=self.is_admin,
            )

            widgets[f"slot{i}"] = slot

        # # Paint arrow
        # x += slot_gap*2
        # y -= slot_gap
        # arrow = bind_canvas_asset(
        #     root=win,
        #     canvas=canvas,
        #     assets=self.assets,
        #     tag="arrow_indicator",
        #     x=x, y=y,
        #     anchor="center",
        #     right_key="fixture_arrow_to_right",
        #     state="normal",
        # )

        # widgets[f"arrow"] = arrow

        # x += slot_gap*1.5 + self.assets["fixture_info_frame_bg"].width() / 2

        # Setup at bottom right of the win
        bottom_x = sw - (self.assets["fixture_info_frame_bg"].width() // 2) - 8
        bottom_y = sh - (self.assets["fixture_info_frame_bg"].height() // 2) - 8
        logs = bind_canvas_log_widget(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="logs_panel",
            x=bottom_x, y=bottom_y,
            bg_key="fixture_info_frame_bg",
            anchor="center",
            ui_max_lines=100,
            buf_max_lines=500,
        )
        widgets["logs"] = logs


        # --- NEW: Probe logs (bottom-left) ---
        probe_x = (self.assets["fixture_info_frame_bg"].width() // 2) + 8
        probe_y = bottom_y
        probe_logs = bind_canvas_log_widget(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="probe_logs_panel",
            x=probe_x, y=probe_y,
            bg_key="fixture_info_frame_bg",
            anchor="center",
            ui_max_lines=80,
            buf_max_lines=300,
        )
        widgets["probe_logs"] = probe_logs


        # Create a Text line Powered by Bế Chí Kiên above the log panel
        credit_x_axis = sw - (self.assets["fixture_info_frame_bg"].width())
        credit_y_axis = sh - (self.assets["fixture_info_frame_bg"].height()) - 24
        
        credit = canvas.create_text(credit_x_axis, credit_y_axis, text=("Powered by bechjkjen"), font=("Tektur", 12, "bold"), fill="#FFB14A", anchor="nw")
        
        credit_y_axis -= 24
        mode_oper = bind_canvas_text(
            root=win,
            canvas=canvas,
            tag="mode_oper",
            x=credit_x_axis,
            y=credit_y_axis,
            text=("ADMIN" if self.is_admin else "OPER"),
            text_font=("Tektur", 12, "bold"),
            fill=("#FFE37A" if self.is_admin else "white"),
            active_fill="#FFD24A",
            disabled_fill="#CFCFCF",
            cooldown_ms=1250,
            anchor="nw",
            command=lambda w=win: self.show_admin_auth_dialog(win=w),
        )

        credit_y_axis -= 24
        startup_toggle = bind_canvas_text(
            root=win,
            canvas=canvas,
            tag="startup_toggle",
            x=credit_x_axis,
            y=credit_y_axis,
            text=("STARTUP: ON" if self.startup_enabled else "STARTUP: OFF"),
            text_font=("Tektur", 12, "bold"),
            fill=("#7CFF7C" if self.startup_enabled else "white"),
            active_fill="#FFD24A",
            disabled_fill="#CFCFCF",
            cooldown_ms=1250,
            anchor="nw",
            command=(lambda w=win: self.toggle_startup(win=w)) if self.is_admin else None,
        )
        widgets["startup_toggle"] = startup_toggle

        credit_y_axis -= 24
        admin_stop = bind_canvas_text(
            root=win,
            canvas=canvas,
            tag="admin_stop",
            x=credit_x_axis,
            y=credit_y_axis,
            text=("ADMIN - TERMINATE"),
            text_font=("Tektur", 12, "bold"),
            fill=("#E1163F"),
            active_fill="#FFD24A",
            disabled_fill="#CFCFCF",
            cooldown_ms=1250,
            anchor="nw",
            command=(lambda w=win: self.admin_terminate(win=w)),
        )

        widgets["admin_stop"] = admin_stop

        credit_y_axis -= 24
        selected_station = bind_canvas_text(
            root=win,
            canvas=canvas,
            tag="select_station",
            x=credit_x_axis,
            y=credit_y_axis,
            text=("Station: "),
            text_font=("Tektur", 12, "bold"),
            fill=("#7CFF7C"),
            active_fill="#FFFFFF",
            disabled_fill="#CFCFCF",
            cooldown_ms=1250,
            anchor="nw",
            command=(lambda w=win: self.select_station(win=w)),
        )
        
        self._init_station_text(selected_station)

        widgets["selected_station"] = selected_station

        credit_y_axis -= 24
        selected_project = bind_canvas_text(
            root=win,
            canvas=canvas,
            tag="selected_project",
            x=credit_x_axis,
            y=credit_y_axis,
            text=("Project: "),
            text_font=("Tektur", 12, "bold"),
            fill=("#7CFF7C"),
            active_fill="#FFFFFF",
            disabled_fill="#CFCFCF",
            cooldown_ms=1250,
            anchor="nw",
            command=(lambda w=win: self.selected_project(win=w)),
        )
        
        self._init_project_text(selected_project)

        widgets["selected_project"] = selected_project

        credit_y_axis -= 24
        selected_process = bind_canvas_text(
            root=win,
            canvas=canvas,
            tag="selected_process",
            x=credit_x_axis,
            y=credit_y_axis,
            text=("Process: "),
            text_font=("Tektur", 12, "bold"),
            fill=("#7CFF7C"),
            active_fill="#FFFFFF",
            disabled_fill="#CFCFCF",
            cooldown_ms=1250,
            anchor="nw",
            command=(lambda w=win: self.selected_process(win=w)),
        )
        
        self._init_process_text(selected_process)

        widgets["selected_process"] = selected_process


        fixture_dummy = bind_canvas_asset(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="fixture_dummy",
            x=sw-240, y=0,
            anchor="nw",
            right_key="fixture_240x240",
            state="normal",
        )

        widgets[f"fixture_dummy"] = fixture_dummy
        
        widgets["credit"] = credit
        widgets["mode_oper"] = mode_oper

        # avoid = ["com_status", "logs_panel"] + [f"slot{i}_status" for i in range(1, 13)]
        avoid = ["com_status", "logs_panel", "probe_logs_panel"] + [f"slot{i}_status" for i in range(1, 13)]

        center_panel = bind_center_rect_panel(
            root=win,
            canvas=canvas,
            tag="center_panel",
            avoid=avoid,
            style=CenterRectStyle(
                outline="#FFB14A",
                width=3,
                fill="#471800",          # hoặc "#000000" + stipple="gray25" nếu muốn kiểu mờ
                stipple="",
                inner_pad=16,
            ),
            pad_screen=18,
            pad_avoid=16,
            min_size=(520, 320),
            keep_ratio=None,     # hoặc 16/9 nếu muốn khung “đẹp” theo tỉ lệ
        )

        center_panel.set_title("HƯỚNG DẪN KIỂM TRA FIXTURE")
        widgets["center_panel"] = center_panel

        guide = GuidePanel(
            root=win,
            center_panel=center_panel,
            assets=self.assets,
            tag="fixture_guide",
            on_done=None,
            on_confirm=self._on_guide_confirm,
            auto_hide_on_done=False,
        )

        guide.start()

        def _after_layout_init_preview():
            # nếu multi-window, lấy MAX để preload theo size lớn nhất
            self.cv_img_width = max(int(getattr(self, "cv_img_width", 0)), sw*0.7)
            self.cv_img_height = max(int(getattr(self, "cv_img_height", 0)), sh*0.8)

            # build preview steps sau khi đã có cv_img_w/h đúng
            guide.set_steps(self._build_guide_preview_steps())
            guide.goto(0)

        # chạy sau khi Tk layout xong
        win.after_idle(_after_layout_init_preview)

        widgets["guide"] = guide
        # Dialog must be always last to create 
        modal = ModalOverlay(win)
        widgets["modal"] = modal

        return widgets
    
    # def _init_station_text(self, text_station):
    #     from pathlib import Path
        

    #     cfg_path = Path(app_dir()) / "config.ini"
    #     selected_name, stations, mp = load_station_cfg(cfg_path)

    #     # chọn hợp lệ
    #     name = selected_name
    #     if not name or (name not in mp):
    #         name = stations[0].name if stations else ""
    #         # nếu muốn persist luôn default:
    #         if name:
    #             try:
    #                 self._ini_set_selected_station(name)
    #             except Exception:
    #                 pass
                
    #     text_station.configure(text=f"Station: {name}" if name else "Station: (none)")

    def _read_selected_station_raw(self, cfg_path: Path) -> str:
        import configparser
        cfg = configparser.ConfigParser(strict=False)
        cfg.read(str(cfg_path), encoding="utf-8")
        return cfg.get("STATION", "selected_station", fallback="").strip()
    
    def _init_station_text(self, text_station):
        cfg_path = Path(app_dir()) / "config.ini"
        name = self._read_selected_station_raw(cfg_path)
        text_station.configure(text=f"Station: {name}" if name else "Station: (none)")
    


    def _read_selected_project_raw(self, cfg_path: Path) -> str:
        import configparser
        cfg = configparser.ConfigParser(strict=False)
        cfg.read(str(cfg_path), encoding="utf-8")
        return cfg.get("STATION", "selected_project", fallback="").strip()

    def _read_selected_process_raw(self, cfg_path: Path) -> str:
        import configparser
        cfg = configparser.ConfigParser(strict=False)
        cfg.read(str(cfg_path), encoding="utf-8")
        return cfg.get("STATION", "selected_process", fallback="").strip()

    def _init_project_text(self, text_project):
        cfg_path = Path(app_dir()) / "config.ini"
        name = self._read_selected_project_raw(cfg_path)
        disp = name if name else "(ALL)"
        text_project.configure(text=f"Project: {disp}")

    def _init_process_text(self, text_process):
        cfg_path = Path(app_dir()) / "config.ini"
        name = self._read_selected_process_raw(cfg_path)
        disp = name if name else "(ALL)"
        text_process.configure(text=f"Process: {disp}")


    def _reload_from_config_and_render(self):
        cfg_path = self.cfg_path

        # 1) reload data model từ config.ini
        self.fx_cfg = load_fixture_cfg(str(cfg_path))
        self.status_map = load_slot_status_from_ini(cfg_path)

        # 2) update station label (đọc raw từ ini)
        st_name = self._read_selected_station_raw(cfg_path)
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            t = ws.get("selected_station")
            if t:
                t.configure(text=f"Station: {st_name}" if st_name else "Station: (none)")

        # 2b) update project/process labels (đọc raw từ ini)
        proj_name = self._read_selected_project_raw(cfg_path)
        proc_name = self._read_selected_process_raw(cfg_path)
        proj_disp = proj_name if proj_name else "(ALL)"
        proc_disp = proc_name if proc_name else "(ALL)"

        for w in self._iter_windows():
            ws = self._get_widgets(w)
            tp = ws.get("selected_project")
            if tp:
                tp.configure(text=f"Project: {proj_disp}")
            tpr = ws.get("selected_process")
            if tpr:
                tpr.configure(text=f"Process: {proc_disp}")

        # 3) update slot widgets
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            for i in range(1, 13):
                slotw = ws.get(f"slot{i}")
                if not slotw:
                    continue
                text = (self.fx_cfg.slot_text.get(i, "") or "")
                font = choose_slot_font(text)
                try:
                    slotw.configure(text=text, font=font)
                except Exception:
                    try:
                        slotw.configure(text=text)
                    except Exception:
                        pass

        # 4) update status UI theo ini
        self.reload_slot_status()

        # 5) rebuild guide preview từ config
        self._guide_reset()
        
    def _fixture_dummy_key_for_case(self, case: GuideCase | None) -> str:
        if not case:
            return "fixture_240x240"

        label = (case.slot_label or "").upper()
        cmd = (case.cmd or "").upper()

        if "SENSOR TOP LEFT" in label:
            return self.map_fixture.get("block_sensor_top_left", "fixture_240x240")
        if "SENSOR TOP RIGHT" in label:
            return self.map_fixture.get("block_sensor_top_right", "fixture_240x240")
        if "SENSOR BOT LEFT" in label or "SENSOR BOTTOM LEFT" in label:
            return self.map_fixture.get("block_sensor_bottom_left", "fixture_240x240")
        if "SENSOR BOT RIGHT" in label or "SENSOR BOTTOM RIGHT" in label:
            return self.map_fixture.get("block_sensor_bottom_right", "fixture_240x240")

        if "FORCE STOP" in cmd:
            return self.map_fixture.get("force_stop", "fixture_240x240")

        return "fixture_240x240"


    def _set_fixture_dummy_key_all(self, key: str) -> None:
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            fd = ws.get("fixture_dummy")
            if not fd:
                continue
            try:
                fd.configure(key=key)   # <-- đổi ảnh (auto scale _0.5/_0.75 nếu có)
            except Exception:
                pass

    def _guide_done(self):
        # Step cuối xong thì bạn làm gì tuỳ ý:
        self.reset_slot_status()
        self._update_logs_panel("Guide completed.", "green")
        self._update_logs_panel("Guide completed.", "green")

        # 1) notify watchdog
        self._wd_send_complete()

        self.io_taskq.submit(
            func=self._shutdown_app_now,
            kwargs={},
            name="shutdown",
            on_start=self._task_start_cb,
            on_success=None,
            on_error=None,
            on_finally=None,
            on_progress=self._task_progress_cb,
        )

    def _flow_gui(self):
        pass

    def _draw_guide(self, canvas: tk.Canvas):
        pass 
    
    def admin_terminate(self, win=None):
        if not getattr(self, "is_admin", False):
            return

        # chặn mọi callback UI (resize/after/pump...)
        self._is_shutting_down = True

        # (optional) nếu bạn có after job id của guide resize/pump thì cancel ở đây

        for w in self._iter_windows():
            for fn in (
                lambda: w.attributes("-topmost", False),
                lambda: w.attributes("-fullscreen", False),
            ):
                try: fn()
                except Exception: pass
            try: w.state("normal")
            except Exception: pass
            try: w.update_idletasks()
            except Exception: pass
            # đừng gọi w.update() lúc đang shutdown (nó kích hoạt thêm event)
            # try: w.update()
            # except Exception: pass

        # gọi guide_done sau khi đã set flag
        try:
            self._guide_done()
            
        except Exception:
            pass


        # rồi off app luôn (nếu bạn muốn terminate thật)
        # self._kill_app_windows()
        self.taskq.submit(
            func=self._shutdown_app_now,
            kwargs={},
            name="shutdown",
            on_start=self._task_start_cb,
            on_success=None,
            on_error=None,
            on_finally=None,
            on_progress=self._task_progress_cb,
        )
        self._shutdown_app_now()


    def show_reset_confirm(self, win: tk.Misc | None = None):
        win = win or self.root
        modal = self._get_modal(win)
        if not modal:
            return

        modal.clear_dialog()

        # build nội dung dialog (đặt trong modal.dialog là 1 Frame)
        box = tk.Frame(modal.dialog, bg="#222222")
        box.pack(padx=24, pady=18)

        tk.Label(
            box, text="Reset toàn bộ 12 slot về idle?",
            fg="white", bg="#222222",
            font=("Tektur", 14, "bold"),
        ).pack(pady=(0, 12))

        row = tk.Frame(box, bg="#222222")
        row.pack()

        def _cancel():
            modal.hide()
            self._restore_focus_after_modal(win)

        def _ok():
            modal.hide()
            self._restore_focus_after_modal(win)
            # self.reset_slot_status()   # gọi task reset của bạn

        tk.Button(row, text="Cancel", command=_cancel, width=10).pack(side="left", padx=8)
        tk.Button(row, text="OK", command=_ok, width=10).pack(side="left", padx=8)

        modal.show(dim_level=0.45)

    def show_manual_config_command(self, *, win: tk.Misc | None = None, slot_idx: int = 1):
        from pathlib import Path
        import tkinter as tk

        # dùng đúng widget có sẵn
        from src.gui.widgets.entry import bind_canvas_entry
        from src.gui.widgets.button import bind_canvas_button

        win = win or self.root
        modal = self._get_modal(win)
        if not modal:
            return

        self.fx_cfg = load_fixture_cfg(app_dir()/"config.ini")

        # lấy dữ liệu slot hiện tại
        slot_test = self.fx_cfg.slot_text.get(slot_idx, "")
        slot_cmd0 = self.fx_cfg.slot_command.get(slot_idx, "")

        modal.clear_dialog()

        # -------- dialog canvas (nằm trong modal.dialog Frame) --------
        dialog_bg_key = (
            "fixture_info_frame_bg_480"
            if "fixture_info_frame_bg_480" in self.assets
            else ("fixture_info_frame_bg" if "fixture_info_frame_bg" in self.assets else "")
        )
        bg_img = self.assets.get(dialog_bg_key)
        W = int(bg_img.width()) if bg_img else 720
        H = int(bg_img.height()) if bg_img else 420

        cv = tk.Canvas(
            modal.dialog,
            width=W,
            height=H,
            highlightthickness=0,
            bd=0,
            bg="#222222",
        )
        cv.pack(padx=0, pady=0)

        # cực quan trọng: để bind_canvas_button() lấy đúng winfo_width() khi auto scale fixture_* keys
        try:
            modal.dialog.update_idletasks()
            cv.update_idletasks()
        except Exception:
            pass

        # background image (nếu có)
        if bg_img:
            bg_id = cv.create_image(W // 2, H // 2, image=bg_img)
            cv.tag_lower(bg_id)
        else:
            cv.create_rectangle(0, 0, W, H, fill="#222222", outline="")

        # -------- title + labels --------
        title_font = ("Tektur", 16, "bold")
        label_font = ("Tektur", 12, "bold")
        value_font = ("Tektur", 12)

        cv.create_text(W // 2, 38, text="MANUAL SLOT COMMAND",
                    font=title_font, fill="white", anchor="center")

        xL  = 48
        y1  = 95
        gap = 26

        # helper pick skins
        def _pick_entry_key(*keys: str, fallback: str) -> str:
            for k in keys:
                if k in self.assets:
                    return k
            return fallback

        normal_k = _pick_entry_key("entry_wide_3_normal", "entry_wide_2_normal", "entry_normal", fallback="entry_normal")
        focus_k  = _pick_entry_key("entry_wide_3_focused", "entry_wide_2_focused", "entry_focused", fallback="entry_focused")
        dis_k    = _pick_entry_key("entry_wide_3_disabled", "entry_wide_2_disabled", "entry_disabled", fallback="entry_disabled")

        # lấy chiều cao entry để spacing “ăn khớp” asset (nếu có)
        entry_img = self.assets.get(normal_k)
        # entry_h   = int(entry_img.height()) if entry_img else 44

        # ===== ROWS (map lại toạ độ) =====
        y_num_line      = y1
        y_test_line     = y1 + gap                   # giữ nguyên dòng vàng SLOT TEST
        y_cmd_label     = y_test_line + gap

        btn_y = H - 52
        btn_gap = 160
        cx = W // 2

        entry_img = self.assets.get(normal_k)
        entry_img_h = int(entry_img.height()) if entry_img else 64
        y_cmd_entry  = btn_y - (entry_img_h // 2) - 22
        y_test_entry = y_cmd_entry - entry_img_h - 14

        entry_x = W // 2
        value_x = xL + 170

        # --- SLOT NUMBER line (giữ nguyên) ---
        cv.create_text(xL, y_num_line, text="SLOT NUMBER:", font=label_font, fill="white", anchor="w")
        cv.create_text(value_x, y_num_line, text=str(slot_idx), font=value_font, fill="#FFE37A", anchor="w")

        # --- SLOT TEST display line (GIỮ nguyên text vàng cho chuyên nghiệp) ---
        cv.create_text(xL, y_test_line, text="SLOT TEST:", font=label_font, fill="white", anchor="w")
        cv.create_text(value_x, y_test_line, text=(slot_test or "(empty)"), font=value_font, fill="#FFE37A", anchor="w")

        # --- SLOT COMMAND label + entry (đẩy xuống dưới) ---
        cv.create_text(xL, y_cmd_label, text="SLOT COMMAND:", font=label_font, fill="white", anchor="w")
        cv.create_text(value_x, y_cmd_label, text=(slot_cmd0 or "(empty)"), font=value_font, fill="#FFE37A", anchor="w")

        # --- SLOT TEST edit entry (nằm dưới, không đụng dòng vàng) ---
        txt_entry = bind_canvas_entry(
            root=modal.dialog,
            canvas=cv,
            assets=self.assets,
            x=entry_x,
            y=y_test_entry,
            name=f"slot_test_{slot_idx}",          # ✅ đổi name, tránh trùng
            field_label="Cập nhật slot test",
            field_label_fill="white",
            placeholder="Nhập SLOT_TEST...",
            font=getattr(self, "tektur_font", None),
            auto_skin_by_label=False,
            normal=normal_k,
            focus=focus_k,
            disabled_status=dis_k,
            state="normal",
        )
        txt_entry.set(slot_test or "")

        cmd_entry = bind_canvas_entry(
            root=modal.dialog,
            canvas=cv,
            assets=self.assets,
            x=entry_x,
            y=y_cmd_entry,
            name=f"slot_cmd_{slot_idx}",
            field_label="Cập nhật slot cmd",
            field_label_fill="white",
            placeholder="Nhập SLOT_COMMAND...",
            font=getattr(self, "tektur_font", None),
            auto_skin_by_label=False,
            normal=normal_k,
            focus=focus_k,
            disabled_status=dis_k,
            state="normal",
        )
        cmd_entry.set(slot_cmd0 or "")

        # -------- buttons (dùng bind_canvas_button) --------

        # pick button skins an toàn (fallback về default keys)
        def _pick_btn_key(*keys: str, fallback: str) -> str:
            for k in keys:
                if k in self.assets:
                    return k
            return fallback

        def _set_btn_visible(btn, visible: bool):
            # CanvasButton có img_id/text_id public :contentReference[oaicite:3]{index=3}
            st = "normal" if visible else "hidden"
            try:
                cv.itemconfig(btn.img_id, state=st)
            except Exception:
                pass
            try:
                cv.itemconfig(btn.text_id, state=st)
            except Exception:
                pass

        def _move_btn(btn, x: int, y: int):
            try:
                cv.coords(btn.img_id, x, y)
                cv.coords(btn.text_id, x, y)
            except Exception:
                pass

        def _cancel():
            modal.hide()
            self._restore_focus_after_modal(win)

        def _confirm():
            new_test = (txt_entry.get() or "").strip()
            new_cmd = (cmd_entry.get() or "").strip()
            modal.hide()
            self._restore_focus_after_modal(win)

            # TODO: save ini sau - giờ log để verify GUI
            try:
                update_ini_manual_slot_info(
                    self.cfg_path,
                    slot_idx=slot_idx,
                    slot_test=new_test,
                    slot_cmd=new_cmd,
                    slot_cmd_section="SLOT_COMMAND",  # hoặc "SLOT_CMD" nếu bạn đặt thế
                )
                self._update_logs_panel(
                    f"[manual] slot{slot_idx} SLOT_TEST='{new_test}' SLOT_COMMAND='{new_cmd}' (saved)",
                    "yellow",
                )
            except Exception as e:
                self._update_logs_panel(f"[manual] save ini failed: {e}", "red")
            finally:
                # reload slot text/command
                self.fx_cfg = load_fixture_cfg(app_dir()/"config.ini")
                new_test = self.fx_cfg.slot_text.get(slot_idx, "")
                new_cmd = self.fx_cfg.slot_command.get(slot_idx, "")
                # cập nhật lại slot test text trên nút: broadcasting
                for win in self._iter_windows():
                    slot = self._get_widgets(win).get(f"slot{slot_idx}")
                    if slot:
                        # CConfigure text and text size
                        slot.configure(text=new_test, font=choose_slot_font(new_test))
                        # slot.set_text(new_test)
                        self.reload_slot_status()

                    self._update_logs_panel(
                        f"[manual] slot{slot_idx} reloaded SLOT_TEST='{new_test}' SLOT_COMMAND='{new_cmd}'",
                        "green",
                    )

        # Confirm: mặc định ẩn, chỉ hiện khi dirty
        btn_confirm = bind_canvas_button(
            root=modal.dialog,
            canvas=cv,
            assets=self.assets,
            tag=f"dlg_cmd_confirm_{slot_idx}",
            x=cx - btn_gap // 2,
            y=btn_y,
            normal_status=_pick_btn_key("fixture_button_confirm_normal", "button_normal", fallback="button_normal"),
            hover_status=_pick_btn_key("fixture_button_confirm_hover", "button_hover", fallback="button_hover"),
            active_status=_pick_btn_key("fixture_button_confirm_pressed", "fixture_button_confirm_active", "button_active", fallback="button_active"),
            disabled_status=_pick_btn_key("fixture_button_confirm_disabled", "button_disabled", fallback="button_disabled"),
            text="",
            text_font=getattr(self, "tektur_font", None),
            command=_confirm,
            cooldown_ms=900,
        )
        _set_btn_visible(btn_confirm, False)

        # Cancel: luôn hiện
        btn_cancel = bind_canvas_button(
            root=modal.dialog,
            canvas=cv,
            assets=self.assets,
            tag=f"dlg_cmd_cancel_{slot_idx}",
            x=cx,                       # khi chưa dirty -> cancel ở giữa
            y=btn_y,
            normal_status=_pick_btn_key("fixture_button_cancel_normal", "button_normal", fallback="button_normal"),
            hover_status=_pick_btn_key("fixture_button_cancel_hover", "button_hover", fallback="button_hover"),
            active_status=_pick_btn_key("fixture_button_cancel_pressed", "fixture_button_cancel_active", "button_active", fallback="button_active"),
            disabled_status=_pick_btn_key("fixture_button_cancel_disabled", "button_disabled", fallback="button_disabled"),
            text="",
            text_font=getattr(self, "tektur_font", None),
            command=_cancel,
            cooldown_ms=900,
        )

        # Enter = confirm nếu dirty
        def _on_submit(_text: str):
            if (cmd_entry.get() or "") != (slot_cmd0 or ""):
                _confirm()

        cmd_entry.configure(on_submit=_on_submit)

        def _apply_dirty():
            # dirty cmd_entry
            dirty = ((cmd_entry.get() or "") != (slot_cmd0 or ""))
            # dirty txt_entry
            dirty_txt = ((txt_entry.get() or "") != (slot_test) or "")

            _set_btn_visible(btn_confirm, dirty_txt or dirty)
            
            if dirty or dirty_txt:
                _move_btn(btn_cancel, cx + btn_gap // 2, btn_y)
            else: 
                _move_btn(btn_cancel, cx, btn_y)

        # trace thay đổi entry để show/hide confirm
        try:
            cmd_entry.var.trace_add("write", lambda *_: _apply_dirty())
            txt_entry.var.trace_add("write", lambda *_: _apply_dirty())
        except Exception:
            pass
        _apply_dirty()

        # Show modal + focus entry
        modal.show(dim_level=0.45)   # giống show_reset_confirm :contentReference[oaicite:4]{index=4}
        try:
            win.after(50, cmd_entry.focus_set)
        except Exception:
            pass

    

    # ---------------------------
    # Admin Authentication (OPER <-> ADMIN)
    # ---------------------------
    def _admin_mode_label(self) -> str:
        return "ADMIN" if self.is_admin else "OPER"

    def _get_admin_secret(self) -> str:
        return "1..."

    def _verify_admin_password(self, pw: str) -> bool:
        secret = self._get_admin_secret()
        return pw == secret

    def _broadcast_admin_mode(self) -> None:
        """
        Broadcast is_admin xuống:
          - mode_oper button text
          - slot command (cho phép click chỉnh sửa)
          - slot hover gating (nếu widget support)
        """
        for w in self._iter_windows():
            ws = self._get_widgets(w)

            # update mode button text
            btn = ws.get("mode_oper")
            if btn:
                try:
                    btn.configure(text=self._admin_mode_label())
                except Exception:
                    pass

            # update slots
            for i in range(1, 13):
                slot = ws.get(f"slot{i}")
                if not slot:
                    continue

                cmd = (lambda idx=i, win=w: self.show_manual_config_command(win=win, slot_idx=idx)) if self.is_admin else None

                try:
                    slot.configure(command=cmd)
                except Exception:
                    try:
                        slot.command = cmd
                    except Exception:
                        pass

                # gate hover fx if supported
                try:
                    slot.configure(is_admin=self.is_admin)
                    self._broadcast_startup_state()
                except Exception:
                    try:
                        setattr(slot, "is_admin", self.is_admin)
                    except Exception:
                        pass

    def _restore_focus_after_modal(self, win):
        try:
            ws = self._get_widgets(win)
            guide = ws.get("fixture_guide") or ws.get("guide")  # tùy bạn đang lưu key gì
            if guide and hasattr(guide, "focus_default"):
                win.after(0, guide.focus_default)
                return
        except Exception:
            pass

        # fallback: focus về window
        try:
            win.after(0, win.focus_force)
        except Exception:
            pass
                
                
    def show_admin_auth_dialog(self, *, win: tk.Misc | None = None) -> None:
        """
        Dialog canvas-style: nhập mật khẩu -> toggle self.is_admin -> broadcast lại slots.
        """

        if self.is_admin:
            # đang là admin, hỏi có muốn chuyển về oper không
            self.is_admin = False
            self._broadcast_admin_mode()
            try:
                self._update_logs_panel(f"[admin] mode -> {self._admin_mode_label()}", "yellow")
            except Exception:
                pass
            return
        
        win = win or self.root
        modal = self._get_modal(win)
        if not modal:
            return

        modal.clear_dialog()

        box = tk.Frame(modal.dialog, bg="#222222")
        box.pack(fill="both", expand=True)

        # -------- dialog canvas (nằm trong modal.dialog Frame) --------
        dialog_bg_key = (
            "fixture_info_frame_bg_480"
            if "fixture_info_frame_bg_480" in self.assets
            else ("fixture_info_frame_bg" if "fixture_info_frame_bg" in self.assets else "")
        )
        bg_img = self.assets.get(dialog_bg_key)
        W = int(bg_img.width()) if bg_img else 720
        H = int(bg_img.height()) if bg_img else 420
        cv = tk.Canvas(
            modal.dialog,
            width=W,
            height=H,
            highlightthickness=0,
            bd=0,
            bg="#222222",
        )
        cv.pack(padx=0, pady=0)

        # cực quan trọng: để bind_canvas_button() lấy đúng winfo_width() khi auto scale fixture_* keys
        try:
            modal.dialog.update_idletasks()
            cv.update_idletasks()
        except Exception:
            pass

        # background image (nếu có)
        if bg_img:
            bg_id = cv.create_image(W // 2, H // 2, image=bg_img)
            cv.tag_lower(bg_id)
        else:
            cv.create_rectangle(0, 0, W, H, fill="#222222", outline="")

        title_font = ("Tektur", 16, "bold")
        label_font = ("Tektur", 12, "bold")
        value_font = ("Tektur", 12)

        cv.create_text(
            W // 2, 42,
            text="ADMIN AUTHENTICATION",
            font=title_font,
            fill="white",
            anchor="center",
        )

        cv.create_text(
            W // 2, 78,
            text=f"Current Mode: {self._admin_mode_label()}",
            font=value_font,
            fill="#FFE37A",
            anchor="center",
        )

        # Password label
        cv.create_text(68, 140, text="MẬT KHẨU:", font=label_font, fill="white", anchor="w")

        # Entry (masked)
        pw_entry = bind_canvas_entry(
            root=modal.dialog,
            canvas=cv,
            assets=self.assets,
            x=W // 2,
            y=192,
            field_label="Admin",
            field_label_fill="#FFE37A",
            name="admin_password",
            # auto_skin_by_label=False,
            placeholder="Nhập mật khẩu...",
            font=("Tektur", 12),
            state="normal",
            password=True,          # ✅ NEW: bật mask
            password_char="•",      # ✅ NEW: ký tự mask (tuỳ)
        )

        # Error text (hidden by default)
        err_id = cv.create_text(
            W // 2, 238,
            text="",
            font=("Tektur", 11, "bold"),
            fill="#FF5C5C",
            anchor="center",
        )

        def _set_err(msg: str):
            try:
                cv.itemconfig(err_id, text=msg)
            except Exception:
                pass
        
        
        def _confirm(pw: str = ""):
            pw = (pw or pw_entry.get() or "").strip()
            if not self._verify_admin_password(pw):
                _set_err("Sai mật khẩu.")
                return

            # toggle admin
            self.is_admin = not self.is_admin
            self._broadcast_admin_mode()

            try:
                self._update_logs_panel(f"[admin] mode -> {self._admin_mode_label()}", "yellow")
            except Exception:
                pass
            
            # pw_entry.clear()
            # modal.hide()
            pw_entry.clear()
            _close_modal()

        # --- FIX: Enter binding scope + cleanup (Ubuntu/Windows, multi-window safe) ---
        _dlg = modal.dialog  # Frame/Toplevel container used by modal
        _bind_ids: list[tuple[str, str]] = []  # (sequence, funcid)

        def _bind_dlg(seq: str, fn):
            try:
                fid = _dlg.bind(seq, fn, add="+")
            except TypeError:
                fid = _dlg.bind(seq, fn)
            _bind_ids.append((seq, fid))

        def _unbind_all():
            for seq, fid in _bind_ids:
                try:
                    _dlg.unbind(seq, fid)
                except Exception:
                    pass
            _bind_ids.clear()

        def _close_modal():
            # unbind enter hooks to avoid "sticky enter" after closing
            _unbind_all()
            try:
                modal.hide()
                self._restore_focus_after_modal(win)
            except Exception:
                pass
            # return focus to the window that opened dialog
            try:
                win.focus_force()
            except Exception:
                try:
                    self.root.focus_force()
                except Exception:
                    pass

        def _on_enter(event=None):
            # Always confirm on Enter in this dialog
            _confirm()
            return "break"

        def _on_escape(event=None):
            _cancel()
            return "break"

        # bind both Enter keys + Esc on the dialog container (not global)
        _bind_dlg("<Return>", _on_enter)
        _bind_dlg("<KP_Enter>", _on_enter)
        _bind_dlg("<Escape>", _on_escape)

        def _cancel():
            # modal.hide()
            _close_modal()

        # Enter submit
        try:
            pw_entry.configure(on_submit=lambda s: _confirm(s))
        except Exception:
            pass

        # Buttons
        cx = W // 2
        by = H - 58

        btn_cancel = bind_canvas_button(
            root=win,
            canvas=cv,
            assets=self.assets,
            normal_status="fixture_button_cancel_normal",
            hover_status="fixture_button_cancel_hover",
            active_status="fixture_button_cancel_pressed",
            disabled_status="fixture_button_cancel_disabled",
            tag="admin_cancel_button",
            x=cx - 120,
            y=by,
            text="",
            cooldown_ms=250,
            command=_cancel,
        )

        btn_confirm = bind_canvas_button(
            root=win,
            canvas=cv,
            assets=self.assets,
            normal_status="fixture_button_confirm_normal",
            hover_status="fixture_button_confirm_hover",
            active_status="fixture_button_confirm_pressed",
            disabled_status="fixture_button_confirm_disabled",
            tag="admin_confirm_button",
            x=cx + 120,
            y=by,
            text="",
            cooldown_ms=250,
            command=_confirm,
        )

        # make sure buttons are on top
        try:
            cv.tag_raise(btn_cancel.img_id)
            cv.tag_raise(btn_confirm.img_id)
        except Exception:
            pass

        # focus password
        try:
            pw_entry.focus_set()
        except Exception:
            try:
                pw_entry.widget.focus_set()
            except Exception:
                pass
        
        modal.dialog.focus_set()
        modal.show(dim_level=0.45)

    # aliases for existing bind in _build_gui (project/process text click)
    def selected_process(self, win: tk.Misc | None = None):
        return self.select_process(win=win)

    def selected_project(self, win: tk.Misc | None = None):
        return self.select_project(win=win)

    def select_process(self, win: tk.Misc | None = None):
        import tkinter as tk
        from pathlib import Path
        from src.utils.config_go import (
            list_test_plan_processes,
            list_test_plan_projects,
            update_ini_selected_process,
            update_ini_selected_project,
        )

        win = win or self.root
        modal = self._get_modal(win)
        if not modal:
            return

        cfg_path = Path(app_dir()) / "config.ini"

        ALL = "(ALL)"
        processes = list_test_plan_processes(cfg_path)
        items = [ALL] + processes

        selected_raw = self._read_selected_process_raw(cfg_path)
        base_selected = selected_raw if (selected_raw in items) else ALL

        # ===== THEME =====
        BG = "#111111"
        PANEL = "#1A1A1A"
        ITEM_BG = "#000000"
        ITEM_HOVER = "#222222"
        SEL_BG = "#FFD24A"
        SEL_FG = "#471800"
        TXT = "white"

        modal.clear_dialog()

        # ===== Dialog Canvas =====
        dlg_w, dlg_h = 520, 430
        dlg_canvas = tk.Canvas(
            modal.dialog, width=dlg_w, height=dlg_h,
            bg=PANEL, highlightthickness=0, bd=0
        )
        dlg_canvas.pack(padx=18, pady=14)

        dlg_canvas.create_text(
            dlg_w // 2, 28,
            text="Chọn Process",
            fill="white",
            font=("Tektur", 16, "bold"),
            anchor="n",
        )

        list_frame = tk.Frame(dlg_canvas, bg=PANEL)
        dlg_canvas.create_window(
            dlg_w // 2, 70,
            window=list_frame,
            anchor="n",
            width=dlg_w - 36,
            height=300,
        )

        list_wrap = tk.Frame(list_frame, bg=PANEL)
        list_wrap.pack(fill="both", expand=True)

        cv_list = tk.Canvas(
            list_wrap,
            width=dlg_w - 60,
            height=300,
            bg=BG,
            highlightthickness=0,
            bd=0,
        )
        sb = tk.Scrollbar(list_wrap, orient="vertical", command=cv_list.yview)
        cv_list.configure(yscrollcommand=sb.set)

        cv_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y", padx=(8, 0))

        inner = tk.Frame(cv_list, bg=BG)
        inner_id = cv_list.create_window((0, 0), window=inner, anchor="nw")

        def _sync_width(_e=None):
            try:
                cv_list.itemconfigure(inner_id, width=cv_list.winfo_width())
            except Exception:
                pass

        def _sync_scrollregion(_e=None):
            cv_list.configure(scrollregion=cv_list.bbox("all"))

        inner.bind("<Configure>", _sync_scrollregion)
        cv_list.bind("<Configure>", _sync_width)

        # mousewheel
        def _on_mousewheel(e):
            if getattr(e, "delta", 0):
                cv_list.yview_scroll(int(-1 * (e.delta / 120)), "units")
            return "break"

        def _on_linux_up(_e):
            cv_list.yview_scroll(-2, "units")
            return "break"

        def _on_linux_dn(_e):
            cv_list.yview_scroll(+2, "units")
            return "break"

        cv_list.bind_all("<MouseWheel>", _on_mousewheel)
        cv_list.bind_all("<Button-4>", _on_linux_up)
        cv_list.bind_all("<Button-5>", _on_linux_dn)

        cur = {"name": base_selected}
        item_refs = {}

        def _apply_style(name: str):
            for n, (fr, lb) in item_refs.items():
                if n == name:
                    fr.configure(bg=SEL_BG)
                    lb.configure(bg=SEL_BG, fg=SEL_FG)
                else:
                    fr.configure(bg=ITEM_BG)
                    lb.configure(bg=ITEM_BG, fg=TXT)

        dirty = {"on": False}
        btn_confirm = None
        btn_cancel = None
        btn_gap = 170
        btn_y = dlg_h - 30
        cx = dlg_w // 2

        def _set_btn_visible(btn, on: bool):
            try:
                if hasattr(btn, "set_state"):
                    btn.set_state("normal" if on else "hidden")
                elif hasattr(btn, "show") and hasattr(btn, "hide"):
                    btn.show() if on else btn.hide()
                else:
                    state = "normal" if on else "hidden"
                    try:
                        dlg_canvas.itemconfig(btn, state=state)
                    except Exception:
                        pass
            except Exception:
                pass

        def _set_dirty(on: bool):
            if dirty["on"] == on:
                return
            dirty["on"] = on
            if btn_confirm is not None:
                _set_btn_visible(btn_confirm, on)

            if btn_cancel is not None:
                x = (cx + btn_gap // 2) if on else cx
                if hasattr(btn_cancel, "move_to"):
                    btn_cancel.move_to(x, btn_y)

            if btn_confirm is not None and on:
                if hasattr(btn_confirm, "move_to"):
                    btn_confirm.move_to(cx - btn_gap // 2, btn_y)

        def _choose(name: str):
            cur["name"] = name
            _apply_style(name)
            _set_dirty(name != base_selected)

        def _mk_item(name: str):
            fr = tk.Frame(inner, bg=ITEM_BG, highlightthickness=0)
            fr.pack(fill="x", padx=10, pady=4)

            lb = tk.Label(
                fr,
                text=name,
                bg=ITEM_BG,
                fg=TXT,
                font=("Tektur", 12, "bold"),
                anchor="w",
                padx=12,
                pady=8,
            )
            lb.pack(fill="x")

            def _enter(_e=None):
                if cur["name"] != name:
                    fr.configure(bg=ITEM_HOVER)
                    lb.configure(bg=ITEM_HOVER)

            def _leave(_e=None):
                if cur["name"] != name:
                    fr.configure(bg=ITEM_BG)
                    lb.configure(bg=ITEM_BG)

            def _click(_e=None):
                _choose(name)

            for w in (fr, lb):
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                w.bind("<Button-1>", _click)

            item_refs[name] = (fr, lb)

        if not items:
            tk.Label(
                inner,
                text="(Không tìm thấy process trong test_plan/)",
                fg="white",
                bg=BG,
                font=("Tektur", 12, "bold"),
            ).pack(padx=12, pady=12)
        else:
            for nm in items:
                _mk_item(nm)
            _apply_style(cur["name"])
            _set_dirty(False)

        def _cancel():
            try:
                cv_list.unbind_all("<MouseWheel>")
                cv_list.unbind_all("<Button-4>")
                cv_list.unbind_all("<Button-5>")
            except Exception:
                pass
            modal.hide()
            self._restore_focus_after_modal(win)

        def _confirm():
            chosen = (cur.get("name") or ALL).strip()
            val = "" if chosen == ALL else chosen

            try:
                update_ini_selected_process(cfg_path, val)

                # nếu đổi process làm project hiện tại không tồn tại -> clear project
                if val:
                    proj_raw = self._read_selected_project_raw(cfg_path)
                    if proj_raw:
                        prjs = list_test_plan_projects(cfg_path, process_filter=val)
                        if proj_raw not in prjs:
                            update_ini_selected_project(cfg_path, "")

                self._reload_from_config_and_render()
                self._update_logs_panel(f"[filter] selected_process='{val or 'ALL'}'", "green")
            except Exception as e:
                self._update_logs_panel(f"[filter] save selected_process failed: {e}", "red")
                return

            _cancel()

        btn_confirm = bind_canvas_button(
            root=modal.dialog,
            canvas=dlg_canvas,
            assets=self.assets,
            tag="dlg_process_confirm",
            x=cx - btn_gap,
            y=btn_y,
            normal_status="fixture_button_confirm_normal",
            hover_status="fixture_button_confirm_hover",
            active_status="fixture_button_confirm_pressed",
            disabled_status="fixture_button_confirm_disabled",
            text="",
            text_font=getattr(self, "tektur_font", None),
            command=_confirm,
            cooldown_ms=900,
        )
        _set_btn_visible(btn_confirm, False)

        btn_cancel = bind_canvas_button(
            root=modal.dialog,
            canvas=dlg_canvas,
            assets=self.assets,
            tag="dlg_process_cancel",
            x=cx,
            y=btn_y,
            normal_status="fixture_button_cancel_normal",
            hover_status="fixture_button_cancel_hover",
            active_status="fixture_button_cancel_pressed",
            disabled_status="fixture_button_cancel_disabled",
            text="",
            text_font=getattr(self, "tektur_font", None),
            command=_cancel,
            cooldown_ms=900,
        )

        modal.show(dim_level=0.45)

    def select_project(self, win: tk.Misc | None = None):
        import tkinter as tk
        from pathlib import Path
        from src.utils.config_go import (
            list_test_plan_projects,
            update_ini_selected_project,
        )

        win = win or self.root
        modal = self._get_modal(win)
        if not modal:
            return

        cfg_path = Path(app_dir()) / "config.ini"

        # nếu process đã chọn -> ưu tiên list project trong process để giảm danh sách
        proc_raw = self._read_selected_process_raw(cfg_path)
        projects = list_test_plan_projects(cfg_path, process_filter=proc_raw) if proc_raw else list_test_plan_projects(cfg_path)

        ALL = "(ALL)"
        items = [ALL] + projects

        selected_raw = self._read_selected_project_raw(cfg_path)
        base_selected = selected_raw if (selected_raw in items) else ALL

        # ===== THEME =====
        BG = "#111111"
        PANEL = "#1A1A1A"
        ITEM_BG = "#000000"
        ITEM_HOVER = "#222222"
        SEL_BG = "#FFD24A"
        SEL_FG = "#471800"
        TXT = "white"

        modal.clear_dialog()

        dlg_w, dlg_h = 520, 430
        dlg_canvas = tk.Canvas(
            modal.dialog, width=dlg_w, height=dlg_h,
            bg=PANEL, highlightthickness=0, bd=0
        )
        dlg_canvas.pack(padx=18, pady=14)

        dlg_canvas.create_text(
            dlg_w // 2, 28,
            text="Chọn Project",
            fill="white",
            font=("Tektur", 16, "bold"),
            anchor="n",
        )

        list_frame = tk.Frame(dlg_canvas, bg=PANEL)
        dlg_canvas.create_window(
            dlg_w // 2, 70,
            window=list_frame,
            anchor="n",
            width=dlg_w - 36,
            height=300,
        )

        list_wrap = tk.Frame(list_frame, bg=PANEL)
        list_wrap.pack(fill="both", expand=True)

        cv_list = tk.Canvas(
            list_wrap,
            width=dlg_w - 60,
            height=300,
            bg=BG,
            highlightthickness=0,
            bd=0,
        )
        sb = tk.Scrollbar(list_wrap, orient="vertical", command=cv_list.yview)
        cv_list.configure(yscrollcommand=sb.set)

        cv_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y", padx=(8, 0))

        inner = tk.Frame(cv_list, bg=BG)
        inner_id = cv_list.create_window((0, 0), window=inner, anchor="nw")

        def _sync_width(_e=None):
            try:
                cv_list.itemconfigure(inner_id, width=cv_list.winfo_width())
            except Exception:
                pass

        def _sync_scrollregion(_e=None):
            cv_list.configure(scrollregion=cv_list.bbox("all"))

        inner.bind("<Configure>", _sync_scrollregion)
        cv_list.bind("<Configure>", _sync_width)

        def _on_mousewheel(e):
            if getattr(e, "delta", 0):
                cv_list.yview_scroll(int(-1 * (e.delta / 120)), "units")
            return "break"

        def _on_linux_up(_e):
            cv_list.yview_scroll(-2, "units")
            return "break"

        def _on_linux_dn(_e):
            cv_list.yview_scroll(+2, "units")
            return "break"

        cv_list.bind_all("<MouseWheel>", _on_mousewheel)
        cv_list.bind_all("<Button-4>", _on_linux_up)
        cv_list.bind_all("<Button-5>", _on_linux_dn)

        cur = {"name": base_selected}
        item_refs = {}

        def _apply_style(name: str):
            for n, (fr, lb) in item_refs.items():
                if n == name:
                    fr.configure(bg=SEL_BG)
                    lb.configure(bg=SEL_BG, fg=SEL_FG)
                else:
                    fr.configure(bg=ITEM_BG)
                    lb.configure(bg=ITEM_BG, fg=TXT)

        dirty = {"on": False}
        btn_confirm = None
        btn_cancel = None
        btn_gap = 170
        btn_y = dlg_h - 30
        cx = dlg_w // 2

        def _set_btn_visible(btn, on: bool):
            try:
                if hasattr(btn, "set_state"):
                    btn.set_state("normal" if on else "hidden")
                elif hasattr(btn, "show") and hasattr(btn, "hide"):
                    btn.show() if on else btn.hide()
                else:
                    state = "normal" if on else "hidden"
                    try:
                        dlg_canvas.itemconfig(btn, state=state)
                    except Exception:
                        pass
            except Exception:
                pass

        def _set_dirty(on: bool):
            if dirty["on"] == on:
                return
            dirty["on"] = on
            if btn_confirm is not None:
                _set_btn_visible(btn_confirm, on)

            if btn_cancel is not None:
                x = (cx + btn_gap // 2) if on else cx
                if hasattr(btn_cancel, "move_to"):
                    btn_cancel.move_to(x, btn_y)

            if btn_confirm is not None and on:
                if hasattr(btn_confirm, "move_to"):
                    btn_confirm.move_to(cx - btn_gap // 2, btn_y)

        def _choose(name: str):
            cur["name"] = name
            _apply_style(name)
            _set_dirty(name != base_selected)

        def _mk_item(name: str):
            fr = tk.Frame(inner, bg=ITEM_BG, highlightthickness=0)
            fr.pack(fill="x", padx=10, pady=4)

            lb = tk.Label(
                fr,
                text=name,
                bg=ITEM_BG,
                fg=TXT,
                font=("Tektur", 12, "bold"),
                anchor="w",
                padx=12,
                pady=8,
            )
            lb.pack(fill="x")

            def _enter(_e=None):
                if cur["name"] != name:
                    fr.configure(bg=ITEM_HOVER)
                    lb.configure(bg=ITEM_HOVER)

            def _leave(_e=None):
                if cur["name"] != name:
                    fr.configure(bg=ITEM_BG)
                    lb.configure(bg=ITEM_BG)

            def _click(_e=None):
                _choose(name)

            for w in (fr, lb):
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                w.bind("<Button-1>", _click)

            item_refs[name] = (fr, lb)

        if not items:
            tk.Label(
                inner,
                text="(Không tìm thấy project trong test_plan/)",
                fg="white",
                bg=BG,
                font=("Tektur", 12, "bold"),
            ).pack(padx=12, pady=12)
        else:
            for nm in items:
                _mk_item(nm)
            _apply_style(cur["name"])
            _set_dirty(False)

        def _cancel():
            try:
                cv_list.unbind_all("<MouseWheel>")
                cv_list.unbind_all("<Button-4>")
                cv_list.unbind_all("<Button-5>")
            except Exception:
                pass
            modal.hide()
            self._restore_focus_after_modal(win)

        def _confirm():
            chosen = (cur.get("name") or ALL).strip()
            val = "" if chosen == ALL else chosen

            try:
                update_ini_selected_project(cfg_path, val)
                self._reload_from_config_and_render()
                self._update_logs_panel(f"[filter] selected_project='{val or 'ALL'}'", "green")
            except Exception as e:
                self._update_logs_panel(f"[filter] save selected_project failed: {e}", "red")
                return

            _cancel()

        btn_confirm = bind_canvas_button(
            root=modal.dialog,
            canvas=dlg_canvas,
            assets=self.assets,
            tag="dlg_project_confirm",
            x=cx - btn_gap,
            y=btn_y,
            normal_status="fixture_button_confirm_normal",
            hover_status="fixture_button_confirm_hover",
            active_status="fixture_button_confirm_pressed",
            disabled_status="fixture_button_confirm_disabled",
            text="",
            text_font=getattr(self, "tektur_font", None),
            command=_confirm,
            cooldown_ms=900,
        )
        _set_btn_visible(btn_confirm, False)

        btn_cancel = bind_canvas_button(
            root=modal.dialog,
            canvas=dlg_canvas,
            assets=self.assets,
            tag="dlg_project_cancel",
            x=cx,
            y=btn_y,
            normal_status="fixture_button_cancel_normal",
            hover_status="fixture_button_cancel_hover",
            active_status="fixture_button_cancel_pressed",
            disabled_status="fixture_button_cancel_disabled",
            text="",
            text_font=getattr(self, "tektur_font", None),
            command=_cancel,
            cooldown_ms=900,
        )

        modal.show(dim_level=0.45)

    def select_station(self, win: tk.Misc | None = None):
        import tkinter as tk
        from pathlib import Path
        from src.utils.config_go import load_station_cfg

        win = win or self.root
        modal = self._get_modal(win)
        if not modal:
            return

        cfg_path = Path(app_dir()) / "config.ini"
        _selected_name, stations, station_map = load_station_cfg(cfg_path)

        selected_raw = self._read_selected_station_raw(cfg_path)
        base_selected = selected_raw if (selected_raw in station_map) else ""   # quan trọng!
        

        # ===== THEME =====
        BG = "#111111"
        PANEL = "#1A1A1A"
        ITEM_BG = "#000000"
        ITEM_HOVER = "#222222"
        SEL_BG = "#FFD24A"
        SEL_FG = "#471800"
        TXT = "white"

        modal.clear_dialog()

        # ===== Dialog Canvas (để đặt title + buttons theo style assets) =====
        dlg_w, dlg_h = 520, 430
        dlg_canvas = tk.Canvas(
            modal.dialog, width=dlg_w, height=dlg_h,
            bg=PANEL, highlightthickness=0, bd=0
        )
        dlg_canvas.pack(padx=18, pady=14)

        # Title
        dlg_canvas.create_text(
            dlg_w // 2, 28,
            text="Danh sách trạm fixture",
            fill="white",
            font=("Tektur", 16, "bold"),
            anchor="n",
        )

        # ===== list frame nằm trong canvas =====
        list_frame = tk.Frame(dlg_canvas, bg=PANEL)
        list_frame_id = dlg_canvas.create_window(
            dlg_w // 2, 70,
            window=list_frame,
            anchor="n",
            width=dlg_w - 36,
            height=300,
        )

        # ============ Scroll list (custom list) ============
        list_wrap = tk.Frame(list_frame, bg=PANEL)
        list_wrap.pack(fill="both", expand=True)

        cv_list = tk.Canvas(
            list_wrap,
            width=dlg_w - 60,
            height=300,
            bg=BG,
            highlightthickness=0,
            bd=0,
        )
        sb = tk.Scrollbar(list_wrap, orient="vertical", command=cv_list.yview)
        cv_list.configure(yscrollcommand=sb.set)

        cv_list.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y", padx=(8, 0))

        inner = tk.Frame(cv_list, bg=BG)
        inner_id = cv_list.create_window((0, 0), window=inner, anchor="nw")

        def _sync_width(_e=None):
            try:
                cv_list.itemconfigure(inner_id, width=cv_list.winfo_width())
            except Exception:
                pass

        def _sync_scrollregion(_e=None):
            cv_list.configure(scrollregion=cv_list.bbox("all"))

        inner.bind("<Configure>", _sync_scrollregion)
        cv_list.bind("<Configure>", _sync_width)

        # mousewheel scroll
        def _on_mousewheel(e):
            if getattr(e, "delta", 0):
                cv_list.yview_scroll(int(-1 * (e.delta / 120)), "units")
            return "break"
        def _on_linux_up(_e): cv_list.yview_scroll(-2, "units"); return "break"
        def _on_linux_dn(_e): cv_list.yview_scroll(+2, "units"); return "break"

        cv_list.bind_all("<MouseWheel>", _on_mousewheel)
        cv_list.bind_all("<Button-4>", _on_linux_up)
        cv_list.bind_all("<Button-5>", _on_linux_dn)

        # ===== Build items =====
        # cur = {"name": base_selected}
        cur = {"name": base_selected or (stations[0].name if stations else "")}
        item_refs = {}

        def _apply_style(name: str):
            for n, (fr, lb) in item_refs.items():
                if n == name:
                    fr.configure(bg=SEL_BG)
                    lb.configure(bg=SEL_BG, fg=SEL_FG)
                else:
                    fr.configure(bg=ITEM_BG)
                    lb.configure(bg=ITEM_BG, fg=TXT)

        # ---- dirty UI ----
        dirty = {"on": False}
        btn_confirm = None
        btn_cancel = None
        btn_gap = 170           # giãn 2 nút ra chút
        btn_y   = dlg_h - 30    # kéo xuống sát đáy dialog hơn (tùy bạn 26~36)
        cx      = dlg_w // 2

        def _set_btn_visible(btn, on: bool):
            try:
                # bind_canvas_button thường trả dict hoặc object có set_state/hide/show
                if hasattr(btn, "set_state"):
                    btn.set_state("normal" if on else "hidden")
                elif hasattr(btn, "show") and hasattr(btn, "hide"):
                    btn.show() if on else btn.hide()
                else:
                    # fallback: nếu btn là list item ids/tags
                    state = "normal" if on else "hidden"
                    try:
                        dlg_canvas.itemconfig(btn, state=state)
                    except Exception:
                        pass
            except Exception:
                pass

        def _set_dirty(on: bool):
            if dirty["on"] == on:
                return
            dirty["on"] = on

            # Confirm chỉ hiện khi dirty
            if btn_confirm is not None:
                _set_btn_visible(btn_confirm, on)

            # Cancel: dirty -> sang phải, không dirty -> giữa
            if btn_cancel is not None:
                x = (cx + btn_gap // 2) if on else cx
                if hasattr(btn_cancel, "move_to"):
                    btn_cancel.move_to(x, btn_y)

            # Confirm: dirty -> bên trái
            if btn_confirm is not None and on:
                if hasattr(btn_confirm, "move_to"):
                    btn_confirm.move_to(cx - btn_gap // 2, btn_y)

        def _choose(name: str):
            cur["name"] = name
            _apply_style(name)
            _set_dirty(name != base_selected)

        def _mk_item(name: str):
            fr = tk.Frame(inner, bg=ITEM_BG, highlightthickness=0)
            fr.pack(fill="x", padx=10, pady=4)

            lb = tk.Label(
                fr,
                text=name,
                bg=ITEM_BG,
                fg=TXT,
                font=("Tektur", 12, "bold"),
                anchor="w",
                padx=12,
                pady=8,
            )
            lb.pack(fill="x")

            def _enter(_e=None):
                if cur["name"] != name:
                    fr.configure(bg=ITEM_HOVER)
                    lb.configure(bg=ITEM_HOVER)

            def _leave(_e=None):
                if cur["name"] != name:
                    fr.configure(bg=ITEM_BG)
                    lb.configure(bg=ITEM_BG)

            def _click(_e=None):
                _choose(name)

            for w in (fr, lb):
                w.bind("<Enter>", _enter)
                w.bind("<Leave>", _leave)
                w.bind("<Button-1>", _click)

            item_refs[name] = (fr, lb)

        if not stations:
            tk.Label(
                inner,
                text="(Không có station trong config.ini)",
                fg="white",
                bg=BG,
                font=("Tektur", 12, "bold"),
            ).pack(padx=12, pady=12)
        else:
            for st in stations:
                _mk_item(st.name)
            _apply_style(cur["name"])
            _set_dirty(False)

        # ===== Buttons (bind_canvas_button) =====
        # bạn đang có _pick_btn_key / bind_canvas_button ở scope class -> dùng luôn
        def _cancel():
            try:
                cv_list.unbind_all("<MouseWheel>")
                cv_list.unbind_all("<Button-4>")
                cv_list.unbind_all("<Button-5>")
            except Exception:
                pass
            modal.hide()
            self._restore_focus_after_modal(win)

        def _confirm():
            name = cur["name"]
            if not name:
                _cancel()
                return

            plan = get_test_plan(cfg_path, name)
            if not plan:
                self._update_logs_panel(f"[station] test plan '{name}' invalid / not found", "red")
                return

            try:
                apply_test_plan_to_config_ini(cfg_path, plan, write_expect_reject=True)
            except Exception as e:
                self._update_logs_panel(f"[station] apply plan failed: {e}", "red")
                return

            # reload config -> render lại GUI
            self._reload_from_config_and_render()
            _cancel()
            # name = cur["name"]
            
            # if name:
            #     st = station_map.get(name)
            #     if not st:
            #         _cancel()
            #         return
            #     # update label Station ngay
            #     try:
            #         for w in self._iter_windows():
            #             ws = self._get_widgets(w)
            #             t = ws.get("selected_station")
            #             if t:
            #                 t.configure(text=f"Station: {name}")
            #     except Exception:
            #         pass

            #     # lưu ini
            #     try:
            #         self._ini_set_selected_station(name)
            #     except Exception:
            #         pass

            #     try:
            #         self._update_ini_selected_station(cfg_path, name)
            #         # 2) write slot_test + slot_cmd into ini
            #         for i in range(1, 13):
            #             update_ini_manual_slot_info(
            #                 cfg_path,
            #                 slot_idx=i,
            #                 slot_test=st.slot_test.get(i, ""),
            #                 slot_cmd=st.slot_command.get(i, ""),
            #             )
            #             update_ini_slot_guide(
            #                 cfg_path,
            #                 slot_idx=i,
            #                 guide_text=st.slot_guide.get(i, ""),
            #             )
            #             update_ini_slot_image(cfg_path, slot_idx=i, image_key=st.slot_image.get(i, ""))
            #     except Exception:
            #         pass

            #     # 3) reset SLOT_STATUS to idle/item according to SLOT_TEST
            #     try:
            #         reset_slot_status_section_to_idle(cfg_path)
            #     except Exception:
            #         pass
                
            #     # 4) reload fixture cfg & refresh slot widgets text/font/status
            #     self.fx_cfg = load_fixture_cfg(cfg_path)

            #     # update each window slots UI
            #     for w in self._iter_windows():
            #         wws = self._get_widgets(w)
            #         if not wws:
            #             continue
            #         for i in range(1, 13):
            #             slotw = wws.get(f"slot{i}")
            #             if not slotw:
            #                 continue
            #             text = self.fx_cfg.slot_text.get(i, "")
            #             font = choose_slot_font(text)
            #             try:
            #                 slotw.configure(text=text, font=font)
            #             except Exception:
            #                 try:
            #                     slotw.configure(text=text)
            #                 except Exception:
            #                     pass
                
            #     # 5) rebuild guide preview steps based on new config.ini
            #     self._guide_reset()  # sẽ build lại preview + goto step 0

            #     self._guide_rebuild_preview_all()

            # _cancel()

        # Confirm: mặc định ẩn, chỉ hiện khi dirty
        btn_confirm = bind_canvas_button(
            root=modal.dialog,
            canvas=dlg_canvas,
            assets=self.assets,
            tag=f"dlg_station_confirm",
            x=cx - btn_gap,
            y=btn_y,
            normal_status="fixture_button_confirm_normal",
            hover_status="fixture_button_confirm_hover",
            active_status="fixture_button_confirm_pressed",
            disabled_status="fixture_button_confirm_disabled",
            text="",
            text_font=getattr(self, "tektur_font", None),
            command=_confirm,
            cooldown_ms=900,
        )
        _set_btn_visible(btn_confirm, False)  # hidden by default

        # Cancel: luôn hiện (dirty=False -> ở giữa)
        btn_cancel = bind_canvas_button(
            root=modal.dialog,
            canvas=dlg_canvas,
            assets=self.assets,
            tag=f"dlg_station_cancel",
            x=cx,
            y=btn_y,
            normal_status="fixture_button_cancel_normal",
            hover_status="fixture_button_cancel_hover",
            active_status="fixture_button_cancel_pressed",
            disabled_status="fixture_button_cancel_disabled",
            text="",
            text_font=getattr(self, "tektur_font", None),
            command=_cancel,
            cooldown_ms=900,
        )

        modal.show(dim_level=0.45)
        
    def _get_modal(self, win: tk.Misc) -> "ModalOverlay | None":
        ws = self._get_widgets(win)
        return ws.get("modal")

    def _refresh_gui(self):
        # nếu queue bận, bỏ qua lần này (3s sau thử lại)
        if not self.taskq.is_busy():
            self.reload_slot_status()

        self.root.after(3000, self._refresh_gui)
    
    # ====== ADD into class AppGUI ======
    def _apply_com_ui_all(self, *, status: str, label: str | None = None) -> None:
        """Broadcast status/label xuống tất cả window (com1 widget)."""
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            com1 = ws.get("com1")
            if not com1:
                continue
            if label is not None:
                try:
                    com1.set_label(label)
                except Exception:
                    pass
            try:
                com1.set_status(status)   # supports "stand_by", "listening", "not_found":contentReference[oaicite:2]{index=2}
            except Exception:
                pass
            try:
                com1.set_disabled(True)
            except Exception:
                pass


    def _start_com_guard(self, interval_ms: int = 3000) -> None:
        """Kick loop mỗi 3s để đảm bảo COM luôn active."""
        self._com_guard_ms = int(interval_ms)
        self._com_guard_after_id = None
        self._com_scan_inflight = False

        # trạng thái mặc định theo yêu cầu bạn
        if not hasattr(self, "com_status"):
            self.com_status = "stand_by"

        # chạy ngay 1 nhịp
        try:
            self._com_guard_after_id = self.root.after(0, self._com_guard_tick)
        except Exception:
            pass


    def _com_guard_tick(self) -> None:
        """Mỗi nhịp 3s: nếu không listening -> (stand_by) -> obtain COM."""
        self._com_guard_after_id = None

        # nếu app đang đóng/shutdown thì dừng
        if getattr(self, "_wd_closing", False) or getattr(self, "_is_shutting_down", False):
            return

        st = (getattr(self, "com_status", "") or "").strip().lower()

        self._update_logs_panel(f"Kiểm tra COM mỗi 3 giây...", "blue")
        # Nếu đang listening thì thôi
        if st == "listening":
            # (optional) nếu listenport đã chết mà com_status vẫn listening, coi như mất COM
            lp = getattr(self, "listenport", None)
            if lp is not None and hasattr(lp, "is_ready"):
                try:
                    if not lp.is_ready():
                        self.com_status = "stand_by"
                        st = "stand_by"
                except Exception:
                    pass
            if st == "listening":
                try:
                    self._com_guard_after_id = self.root.after(self._com_guard_ms, self._com_guard_tick)
                except Exception:
                    pass
                return

        # Nếu đang stand_by và scan đang chạy -> return (đợi result)
        if st == "stand_by" and getattr(self, "_com_scan_inflight", False):
            try:
                self._com_guard_after_id = self.root.after(self._com_guard_ms, self._com_guard_tick)
            except Exception:
                pass
            return

        # Không listening -> set stand_by và start scan
        self.com_status = "stand_by"
        self._com_scan_inflight = True
        self._apply_com_ui_all(status="stand_by")

        try:
            # gọi scan (nó submit vào io_taskq)
            self._resolve_COM()
        except Exception as e:
            self._com_scan_inflight = False
            try:
                self._update_logs_panel(f"[com-guard] start obtain COM failed: {e}", "red")
            except Exception:
                pass

        # schedule nhịp kế tiếp
        try:
            self._com_guard_after_id = self.root.after(self._com_guard_ms, self._com_guard_tick)
        except Exception:
            pass
        
    # Resolve COM port
    # ====== MODIFY your existing _resolve_COM to avoid double-submit ======
    def _resolve_COM(self):
        # nếu đang scan rồi thì thôi (để match logic stand_by -> wait)
        if getattr(self, "_com_scan_inflight", False):
            return

        self._com_scan_inflight = True
        self.com_status = "stand_by"
        self._apply_com_ui_all(status="stand_by")

        self.io_taskq.submit(
            func=obtaining_fixture_com,
            kwargs={},
            name="Obtain fixture COM",
            on_start=self._task_start_cb,
            on_success=lambda result, meta: self._resolve_COM_task_finished(result, meta),
            on_error=lambda err, meta: self._resolve_COM_task_error(err, meta),
            on_finally=self._task_finally_cb,
            on_progress=self._task_progress_cb,
        )
    
    def _resolve_COM_task_error(self, err, meta):
        # scan fail -> quay lại stand_by để vòng sau scan tiếp
        self._com_scan_inflight = False
        self.com_status = "stand_by"
        self._apply_com_ui_all(status="stand_by")
        # giữ error handler cũ của bạn
        try:
            self._task_error_cb(err, meta)
        except Exception:
            pass

    # ====== MODIFY your existing _resolve_COM_task_finished ======
    def _resolve_COM_task_finished(self, result: str, _meta):
        # scan xong
        self._com_scan_inflight = False

        # update label trước
        self._apply_com_ui_all(status="stand_by", label=result)

        # stop listenport cũ (nếu có)
        if getattr(self, "listenport", None):
            try:
                self.listenport.stop()
            except Exception:
                pass
            self.listenport = None

        # clear probe logs (như code bạn đang làm)
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            pl = ws.get("probe_logs")
            if pl:
                try:
                    pl.clear()
                except Exception:
                    pass

        # nếu chưa tìm được COM -> giữ stand_by (để vòng sau scan tiếp)
        if (result or "").upper() == "COMX":
            self.com_status = "stand_by"
            self._apply_com_ui_all(status="stand_by", label="COMX")
            return

        # start ListenPort
        try:
            dispatch = lambda fn: self.root.after(0, fn)
            self.listenport = ListenPort(
                port=result,
                baudrate=self.baudrate,
                log=self.emit_msg,
                on_rx=lambda s: self._update_logs_panel(f"RX: {s}", "white"),
                dispatch=dispatch,
            )
            self.listenport.start()
            self.com_status = "listening"
            self._apply_com_ui_all(status="listening", label=result)

            # (optional) warmup
            self.send_to_com(cmd="help", on_start=self._task_start_cb, on_success=None, on_error=None, on_finally=None)
            self.send_to_com(cmd="?", on_start=self._task_start_cb, on_success=None, on_error=None, on_finally=None)

            self._update_logs_panel(f"ListenPort started on {result}", "green")
            return
        except Exception as e:
            self._update_logs_panel(f"Error starting ListenPort: {e}", "red")

        # fail to start -> quay lại stand_by để vòng sau scan tiếp
        self.com_status = "stand_by"
        self._apply_com_ui_all(status="stand_by", label=result)

    def send_to_com(self, cmd: str, on_start, on_success, on_error, on_finally, expect=None, reject=None, take_no_response_as_expect=False):
        def _do():
            if not self.listenport:
                raise RuntimeError("ListenPort not initialized")
            dispatch = lambda fn: self.root.after(0, fn)
            ok, lines = self.listenport.send_and_collect(
                cmd=cmd,
                append_crlf=True, 
                expect=expect,
                reject=reject,
                on_line=lambda s: dispatch(lambda: self._update_logs_panel(f"RX: {s}", "yellow")),
                take_no_response_as_expect=take_no_response_as_expect,
            )
            return ok, lines

        def _ok(result, _meta):
            ok, lines = result
            self._update_logs_panel(f"TX: {cmd} | RX lines: {len(lines)}", "blue")
            self._update_probe_logs_panel(f"{cmd}: {lines}", "green")
            if lines:
                self._update_logs_panel(f"RX last: {lines[-1]}", "green" if ok else "yellow")

        # Check callable
        if not callable(on_start):
            on_start = self._task_start_cb
        if not callable(on_success):
            on_success = _ok
        if not callable(on_error):
            on_error = self._task_error_cb
        if not callable(on_finally):
            on_finally = self._task_finally_cb

        self.io_taskq.submit(
            func=_do,
            name="Send to COM",
            on_start=on_start,
            on_success=on_success,
            on_error=on_error,
            on_finally=on_finally,
        )


    def reset_slot_status(self):
        def _do():
            reset_slot_status_section_to_idle(self.cfg_path)
            return True

        def _ok(_result, _meta):
            # sau reset thì reload UI (enqueue tiếp cũng OK, vì taskq serial)
            self.reload_slot_status()

        # On windows must pass the func directly
        self.io_taskq.submit(
            func=reset_slot_status_section_to_idle,
            kwargs={"ini_path": self.cfg_path},
            name="Reset Slots",
            on_start=self._task_start_cb,
            on_success=lambda _result, _meta: self.reload_slot_status(),
            on_error=self._task_error_cb,
            on_finally=self._task_finally_cb,
            on_progress=self._task_progress_cb,
        )

    def reload_slot_status(self):
        def _do():
            return load_slot_status_from_ini(self.cfg_path)

        def _ok(status_map, _meta):
            self.status_map = status_map
            for slot_id, status in self.status_map.items():
                for w in self._iter_windows():
                    ws = self._get_widgets(w)
                    slot = ws.get(f"slot{slot_id}")
                    if slot:
                        slot.set_status(status)  # UI update: chạy trên main thread (callback)

        self.io_taskq.submit(
            func=load_slot_status_from_ini,
            kwargs={"ini_path": self.cfg_path},
            name="Reload Slots",
            on_start=self._task_start_cb,
            on_success=lambda status_map, _meta: _ok(status_map, _meta),
            on_error=self._task_error_cb,
            on_finally=self._task_finally_cb,
            on_progress=self._task_progress_cb,
        )

    def update_slot_status(self, slot_id: int = 1, status: str = "idle") -> None:
        def _do():
            st = str(status).strip().lower()
            if st not in _ALLOWED_STATUS:
                raise ValueError(f"Invalid status: {status!r}. Allowed: {sorted(_ALLOWED_STATUS)}")
            if not (1 <= slot_id <= 12):
                raise ValueError(f"slot_idx out of range: {slot_id}")

            update_ini_slot_status(self.cfg_path, slot_id, st)
            return load_slot_status_from_ini(self.cfg_path)

        def _ok(status_map, _meta):
            self.status_map = status_map
            new_status = self.status_map.get(slot_id, "idle")
            for w in self._iter_windows():
                ws = self._get_widgets(w)
                slot = ws.get(f"slot{slot_id}")
                if slot:
                    slot.set_status(new_status)

        self.io_taskq.submit(
            func=_do,
            kwargs={},
            name=f"Update slot{slot_id}",
            on_start=self._task_start_cb,
            on_success=_ok,
            on_error=self._task_error_cb,
            on_finally=self._task_finally_cb,
            on_progress=self._task_progress_cb,
        )

    # Broadcasting event 
    def _get_widgets(self, win: tk.Misc) -> dict:
        if win is self.root:
            return self.widgets_main
        return getattr(win, "_widgets", {})

    def _iter_windows(self):
        # root + tất cả extra windows còn tồn tại
        yield self.root
        for w in list(self.roots_extra):
            try:
                if w.winfo_exists():
                    yield w
            except Exception:
                pass

    ### Pump log buffer to UI through emit_msg to the log.info
    def _update_logs_panel(self, msg: str, color: LogColor = "white"):
        self.emit_msg(msg)

        with self._log_lock:
            # get last line
            line = self.log_buffer[-1:]
        if line:
            # iter window and update log
            for w in self._iter_windows():
                ws = self._get_widgets(w)
                logs = ws.get("logs")
                if logs:
                    logs.emit(line[0], color)  # màu trắng mặc định

    def _update_probe_logs_panel(self, msg: str, color: LogColor = "white"):
        """Panel riêng (góc trái dưới): chỉ dùng cho RX khi dò/kiểm tra COM fixture."""
        txt = str(msg).rstrip("\n")
        if not txt:
            return

        for w in self._iter_windows():
            ws = self._get_widgets(w)
            pl = ws.get("probe_logs")
            if pl:
                try:
                    pl.emit(txt, color)
                except Exception:
                    pass

    ### Runner Callback
    def _task_start_cb(self, meta):
        name = meta["name"]

        if "RELOAD" in name.upper():
            return None
        self._update_logs_panel(f"{name}...", "yellow")

    def _task_progress_cb(self, payload):
        if not isinstance(payload, dict):
            return

        # --- PROBE RX (panel riêng) ---
        if payload.get("kind") == "fixture_probe_rx":
            port = str(payload.get("port", ""))
            label = str(payload.get("label", "RX"))
            rx = str(payload.get("rx", "") or "").strip("\n")
            if rx:
                self._update_probe_logs_panel(f"[{label}] {port}", "yellow")
                for ln in rx.splitlines():
                    self._update_probe_logs_panel(ln, "white")
            return

        # --- progress thường (an toàn nếu thiếu key) ---
        msg = payload.get("message")
        if msg:
            self._update_logs_panel(str(msg))

        port = payload.get("port", "")
        baudrate = payload.get("baudrate", "")
        ending_line = payload.get("ending_line", "")

        if port:
            self.port = port
            self._update_logs_panel(f"port: {port}")
        if baudrate:
            self.baudrate = baudrate
            self._update_logs_panel(f"baudrate: {baudrate}")
        if ending_line:
            self.ending_line = ending_line
            self._update_logs_panel(f"ending_line: {ending_line}")

    def _task_error_cb(self, payload, meta):
        self._update_logs_panel(f"Error: {payload}", color="red")
        self._update_logs_panel(f"FAILED: {meta}", color="red")

    def _task_finally_cb(self, status:str, meta:dict):
        self._running = False
        self._task_handler = None
        if status == "cancelled":
            self._update_logs_panel("Cancelled by the user.")
        
        name = meta["name"]

        if "RELOAD" in name.upper():
            return None
        
        if status.lower() == "ok":
            self._update_logs_panel(f"{name} ~ END", "yellow")

    def _close_all_windows(self, source_win: tk.Misc | None = None):
        ok, reason = self._can_close_now()
        if not ok:
            self._emit_guard(f"[guard] Block close: {reason}")
            return

        # chống re-entrant
        if getattr(self, "_is_closing_all", False):
            return
        self._is_closing_all = True

        try:
            self.runner.stop_all()
        except Exception:
            pass

        for w in list(self.roots_extra):
            try:
                if w.winfo_exists():
                    w.destroy()
            except Exception:
                pass
        self.roots_extra.clear()

        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except Exception:
            pass


    def _emit_guard(self, msg: str):
        try:
            self._update_logs_panel(msg, "yellow")
        except Exception:
            print(msg)

    def _iter_available_slots_and_states(self) -> List[Tuple[int, str]]:
        """
        Slot cần check = slot có SLOT_TEST (fx_cfg.slot_text[slot] != "")
        Bỏ qua slot status == 'idle' (slot không có gì để check / không active).
        Nguồn status lấy từ self.status_map (được reload từ load_slot_status_from_ini).
        """
        # 1) load fixture cfg (SLOT_TEST)
        fx = getattr(self, "fx_cfg", None)
        if fx is None:
            try:
                fx = self.fx_cfg = load_fixture_cfg(self.cfg_path)
            except Exception:
                return []  # không đọc được config => coi như không có gì cần check

        # 2) status map
        sm = getattr(self, "status_map", None)
        if not isinstance(sm, dict):
            try:
                sm = self.status_map = load_slot_status_from_ini(self.cfg_path)
            except Exception:
                sm = {}

        out: List[Tuple[int, str]] = []
        for slot_id in range(1, 13):
            # chỉ check slot có SLOT_TEST
            label = (fx.slot_text.get(slot_id, "") or "").strip()
            if not label:
                continue

            st = (sm.get(slot_id, "idle") or "idle")
            stn = _norm_state(st)

            # bỏ qua idle đúng yêu cầu
            if stn == "idle":
                continue

            out.append((slot_id, st))
        return out

    # --- 3) điều kiện cho phép đóng ---
    def _can_close_now(self) -> Tuple[bool, str]:
        """
        Rule:
        - Nếu chưa có slot info -> cho tắt (True)
        - Nếu có slot đang TESTING -> chặn
        - Nếu có slot FAIL -> chặn
        - Còn lại (tất cả IDLE hoặc PASS) -> cho tắt
        """
        pairs = self._iter_available_slots_and_states()
        if not pairs:
            return True, "no slots / not initialized"

        testing = [sid for sid, st in pairs if _is_testing(st)]
        failing = [sid for sid, st in pairs if _is_fail(st)]
        idle = [sid for sid, st in pairs if _is_idle(st)]

        if testing:
            return False, f"slots testing: {testing}"
        if failing:
            return False, f"slots failed: {failing}"
        if idle:
            return False, f"slots idle: {idle}"

        # nếu muốn “phải PASS hết” (không tính IDLE) thì bật check dưới:
        # not_pass = [sid for sid, st in pairs if not _is_pass(st)]
        # if not_pass:
        #     return False, f"slots not passed: {not_pass}"

        return True, "all idle/pass"
    
    # --- 4) guarded close mới ---
    def _guarded_close_by_slots(self, win):

        if getattr(self, "_allow_app_exit", False):
            try:
                win.destroy()
            except Exception:
                pass
            return
        
        ok, reason = self._can_close_now()
        if ok:
            try:
                win.destroy()
            except Exception:
                try:
                    self.root.destroy()
                except Exception:
                    pass
            return

        # chặn đóng + log/notify
        try:
            self._update_logs_panel(f"[guard] Block close: {reason}", "yellow")
        except Exception:
            print("[guard] Block close:", reason)

        # nếu bạn có dialog canvas đẹp thì gọi ở đây (tùy project)
        # self.show_toast("Không thể tắt khi đang TESTING/FAIL", color="yellow")


    # --- 5) install_close_lock: giờ là install guard theo slot ---
    def install_close_lock(self):
        
        # apply cho root + toàn bộ extra windows
        for w in self._iter_windows():
            self._install_close_guard_for_window(w)


    def _install_close_guard_for_window(self, win: tk.Misc):
        win.protocol("WM_DELETE_WINDOW", lambda w=win: self._close_all_windows(w))

        # override (không add="+") để đè bind cũ trong create_extra_windows
        win.bind("<Alt-KeyPress-F4>", lambda e, w=win: (self._close_all_windows(w), "break"))
        win.bind("<Alt-F4>",          lambda e, w=win: (self._close_all_windows(w), "break"))

    # def install_close_lock(self, seconds: float = 10.0):
    #     self._close_lock_until = time.monotonic() + float(seconds)

    #     # lock cả root
    #     self.root.protocol("WM_DELETE_WINDOW", lambda: self._guarded_close(self.root))
    #     self.root.bind_all("<Alt-KeyPress-F4>", lambda e: (self._guarded_close(self._focused_window()), "break"), add="+")
    #     self.root.bind_all("<Alt-F4>",         lambda e: (self._guarded_close(self._focused_window()), "break"), add="+")

    #     # mở khóa sau 10s
    #     self.root.after(int(seconds * 1000), self._unlock_close_lock)

    def _unlock_close_lock(self):
        self._close_lock_until = 0.0
        self._emit_guard("[guard] Hết 10s, có thể tắt bình thường.")

    def _is_close_locked(self) -> bool:
        return time.monotonic() < getattr(self, "_close_lock_until", 0.0)

    def _remaining_lock(self) -> float:
        until = getattr(self, "_close_lock_until", 0.0)
        if until <= 0:
            return 0.0
        return max(0.0, until - time.monotonic())

    def _focused_window(self):
        # window đang focus (root hoặc 1 toplevel)
        try:
            w = self.root.focus_get()
            return (w.winfo_toplevel() if w is not None else self.root)
        except Exception:
            return self.root

    def _guarded_close(self, win):
        if self._is_close_locked():
            # TODO: Thay thì stalling thời gian chờ
            # Kiêm tra fixture cần đảm bảo các slot test có trạng thái là pass để có thể tắt được - tích hợp sau. 
            # Hiện tại chỉ chặn tắt trong 10s đầu
            self._emit_guard(f"[guard] Chưa thể tắt trong 10s đầu. Còn ~{self._remaining_lock():.1f}s")
            return
        # cho phép đóng theo logic bạn đang có
        self._close_all_windows(win)


    # ----------------------------
    # GUIDE FLOW (theo slot + retry)
    # ----------------------------

    # Dùng khi chọn station
    def _update_ini_selected_station(self, ini_path: Path, station_name: str) -> None:
        import re

        raw = ini_path.read_bytes() if ini_path.exists() else b""
        newline = "\r\n" if b"\r\n" in raw else "\n"
        lines = (raw.decode("utf-8", errors="replace").splitlines() if raw else [])

        section_re = re.compile(r"^\s*\[([^\]]+)\]\s*$")
        kv_re = re.compile(r"^(\s*)(selected_station)(\s*=\s*)(.*?)(\s*)$", re.IGNORECASE)

        # tìm bounds [STATION]
        start = end = None
        for i, ln in enumerate(lines):
            m = section_re.match(ln)
            if not m:
                continue
            name = m.group(1).strip()
            if start is None and name.upper() == "STATION":
                start = i + 1
                continue
            if start is not None:
                end = i
                break
        if start is None:
            if lines and lines[-1].strip() != "":
                lines.append("")
            lines.append("[STATION]")
            start = len(lines)
            end = len(lines)
        if end is None:
            end = len(lines)

        found = False
        new_sec = []
        for ln in lines[start:end]:
            m = kv_re.match(ln)
            if m:
                indent, key, eq, _old, trail = m.groups()
                new_sec.append(f"{indent}{key}{eq}{station_name}{trail}")
                found = True
            else:
                new_sec.append(ln)

        if not found:
            if new_sec and new_sec[-1].strip() != "":
                new_sec.append("")
            new_sec.append(f"selected_station={station_name}")

        out_lines = lines[:start] + new_sec + lines[end:]
        ini_path.write_text(newline.join(out_lines) + newline, encoding="utf-8")
        
    def _guide_set_confirm_enabled_all(self, enabled: bool) -> None:
        """
        Cố gắng disable/hide confirm button của GuidePanel ở tất cả window.
        Không biết nội bộ GuidePanel expose gì, nên thử nhiều kiểu.
        """
        for gp in self._iter_guide_panels():
            try:
                # ưu tiên method nếu GuidePanel có
                if hasattr(gp, "set_confirm_enabled"):
                    gp.set_confirm_enabled(enabled)   # type: ignore[attr-defined]
                    continue
                if hasattr(gp, "set_confirm_visible"):
                    gp.set_confirm_visible(enabled)   # type: ignore[attr-defined]
                    continue

                # fallback: nếu có button object bên trong
                for name in ("confirm_btn", "btn_confirm", "button_confirm"):
                    btn = getattr(gp, name, None)
                    if btn is None:
                        continue
                    # CanvasButton thường có set_disabled(...)
                    if hasattr(btn, "set_disabled"):
                        btn.set_disabled(not enabled)  # type: ignore[attr-defined]
                    # hoặc configure(state=...)
                    elif hasattr(btn, "configure"):
                        btn.configure(state=("normal" if enabled else "disabled"))
                    break
            except Exception:
                pass


    def _guide_rebuild_preview_all(self) -> None:
        """
        Rebuild preview steps từ config.ini hiện tại và apply cho tất cả GuidePanel.
        """
        steps = self._build_guide_preview_steps()
        self._guide_apply_steps_all_windows(steps, start_index=0)
        self._guide_goto_all(0)

    def _init_guide_flow(self):
        # trạng thái luồng guide (điều khiển theo slot, retry tối đa)
        self._guide_busy: bool = False
        self._guide_done_mode: str = "restart"  # "exit" | "restart"

        self._guide_running: bool = False
        self._guide_max_attempts: int = 3

        # Plan sẽ được build lại mỗi lần bấm "BẮT ĐẦU"
        self._guide_plan: list[GuideCase] = []
        self._guide_attempts: dict[int, int] = {}
        self._guide_current_step: int = 0  # 0 = welcome, 1..N = slot steps, N+1 = done

    def _iter_guide_panels(self):
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            gp = ws.get("guide")
            if gp is not None:
                yield gp

    def _guide_goto_all(self, idx: int) -> None:
        for gp in self._iter_guide_panels():
            try:
                gp.goto(idx)
            except Exception:
                pass

    def _guide_set_content_all(
        self,
        *,
        title: Optional[str] = None,
        image_key: Optional[str] = None,
        confirm_text: Optional[str] = None,
        title_fill: Optional[str] = None,   # NEW
    ) -> None:
        for gp in self._iter_guide_panels():
            try:
                gp.set_content(title=title, image_key=image_key, confirm_text=confirm_text, title_fill=title_fill)
            except Exception:
                pass

    def _guide_set_busy_all(self, busy: bool, *, text: Optional[str] = None) -> None:
        for gp in self._iter_guide_panels():
            try:
                gp.set_busy(busy, text=text)
            except Exception:
                pass

    def _guide_make_case(self, slot_id: int, slot_label: str, slot_cmd0: str, guide_text: str = "", image_key: str = "", expect_regex: str = "NG", reject_regex: str = "OK") -> GuideCase:
        label = (slot_label or "").strip().upper()
        cmd0 = (slot_cmd0 or "").strip()
        guide = (guide_text or "").strip()
        img = (image_key or "").strip() or "fixture_240x240"
        # --- choose cmd ---
        cmd = cmd0
        if not cmd:
            if label in ("IN", "IN CLOSE", "CLOSE", "CLOSE FIXTURE"):
                cmd = "IN CLOSE"
            elif label in ("OUT", "OUT OPEN", "OPEN", "OPEN FIXTURE"):
                cmd = "OUT OPEN"
            elif "FORCE" in label or "STOP" in label:
                cmd = "FORCE STOP"
            elif "RESET" in label:
                cmd = "RESET"
            elif "SENSOR" in label:
                cmd = "SENSOR"
            else:
                cmd = label or "IN CLOSE"

        print(f"Making guide case for Slot{slot_id}: label={label!r}, cmd0={cmd0!r}, img={img!r}")


        # --- choose expect + image + title ---
        # img = "fixture_240x240"
        title = f"[Slot{slot_id}] {label or 'CHECK'}"
        # nếu ini có guide -> ưu tiên dùng
        if guide:
            title = f"[Slot{slot_id}] {guide}"
        expect: Optional[Pattern[str]] = None
        reject: Optional[Pattern[str]] = None


        # --- compile expect/reject from config ---
        def _compile_pat(s: str, *, fallback: str) -> Optional[Pattern[str]]:
            s = (s or "").strip()
            if not s:
                return None
            try:
                return re.compile(s)
            except re.error:
                # fallback an toàn nếu regex lỗi
                try:
                    return re.compile(fallback, re.I)
                except re.error:
                    return None

        # Mặc định: config bạn hay dùng (?i) trong pattern, nên compile() là đủ.
        # Nếu user chỉ đưa "NG" thì compile("NG") là OK, match substring.
        expect = _compile_pat(expect_regex, fallback=r"(?i)\bNG\b")
        reject = _compile_pat(reject_regex, fallback=r"(?i)\bOK\b")

        print(
            f"Making guide case for Slot{slot_id}: "
            f"label={label!r}, cmd={cmd!r}, "
            f"expect={expect_regex!r}, reject={reject_regex!r}"
        )

        ## TODO: CATCH patterns
        # OK_WORDS = ["ok", "pass", "passed", "success", "done"]
        # expect = re.compile(r"\b(?:%s)\b" % "|".join(map(re.escape, OK_WORDS)), re.I)
        # reject = re.compile(r"\b(?:OK|ok|True|true|closed|CLOSED|Closed)\b", re.I)
        # up_cmd = cmd.strip().upper()

        # if "SENSOR TOP LEFT" in label:
        #     img = "guide_sensor_top_left"
        #     title = f"[Slot{slot_id}] Hãy dùng công cụ che Cảm Biến góc trên trái ở cửa vào Fixture.\nBấm xác nhận để kiểm tra!"
        #     # expect = re.compile(r"ok", re.I)
        #     ## TODO: CATCH patterns
        #     expect = re.compile(r"\b(?:no\s+product1!|PRODUCT_NG|FIX_SAFE_NG|CLOSE_NG|error|sensor\s+error|NG)\b", re.I)
        #     reject = re.compile(r"\b(?:OK|ok|READY|close|CLOSED|Closed)\b", re.I)
        # elif "SENSOR TOP RIGHT" in label:
        #     img = "guide_sensor_top_right"
        #     title = f"[Slot{slot_id}] Hãy dùng công cụ che Cảm Biến góc trên phải ở cửa vào Fixture.\nBấm xác nhận để kiểm tra!"
        #     ## TODO: CATCH patterns
        #     expect = re.compile(r"\b(?:no\s+product1!|PRODUCT_NG|FIX_SAFE_NG|CLOSE_NG|error|sensor\s+error|NG)\b", re.I)
        #     reject = re.compile(r"\b(?:OK|ok|READY|close|CLOSED|Closed)\b", re.I)
        # elif "SENSOR BOT LEFT" in label:
        #     img = "guide_sensor_bottom_left"
        #     title = f"[Slot{slot_id}] Hãy dùng công cụ che Cảm Biến góc dưới trái ở cửa vào Fixture.\nBấm xác nhận để kiểm tra!"
        #     # theo dummy fixture bạn đã mô tả: có thể trả STOPPED/NG/timeout/EMC
        #     expect = re.compile(r"\b(?:no\s+product1!|PRODUCT_NG|FIX_SAFE_NG|CLOSE_NG|error|sensor\s+error|NG)\b", re.I)
        #     reject = re.compile(r"\b(?:OK|ok|READY|close|CLOSED|Closed)\b", re.I)
        # elif "SENSOR BOT RIGHT" in label:
        #     img = "guide_sensor_bottom_right"
        #     title = f"[Slot{slot_id}] Hãy dùng công cụ che Cảm Biến góc dưới phải ở cửa vào Fixture.\nBấm xác nhận để kiểm tra!"
        #     expect = re.compile(r"\b(?:no\s+product1!|PRODUCT_NG|FIX_SAFE_NG|CLOSE_NG|error|sensor\s+error|NG)\b", re.I)
        #     reject = re.compile(r"\b(?:OK|ok|READY|close|CLOSED|Closed)\b", re.I)
        # elif "SENSOR" in up_cmd:
        #     img = "guide_close_fixture"
        #     title = f"[Slot{slot_id}] Hãy dùng công cụ che SENSOR ở cửa vào Fixture.\nBấm xác nhận để kiểm tra!"
        #     expect = re.compile(r"\b(?:no\s+product1!|PRODUCT_NG|FIX_SAFE_NG|CLOSE_NG|error|sensor\s+error|NG)\b", re.I)
        #     reject = re.compile(r"\b(?:OK|ok|READY|close|CLOSED|Closed)\b", re.I)

        # elif "STOP" in label or "FORCE STOP" in label:
        #     img = "fixture_stop_guide_240x240"
        #     title = f"[Slot{slot_id}] Hãy nhấn nút FORCE STOP - DỪNG KHẨN CẤP.\nBấm xác nhận để kiểm tra!"
        #     expect = re.compile(r"\b(?:not\s+ok|fail(?:ed)?|ng|error|timeout|EMC|emc|STOPPED|STOP_ON|STOP!|HOLD_ON|stop|E_STOP|RASTER_ERROR|NG)\b", re.I)
        #     # expect = re.compile(r"OK", re.I)
        #     # reject = re.compile(r"\b(?:OK|ok)\b", re.I)

        return GuideCase(
            slot_id=slot_id,
            slot_label=label,
            title=title,
            image_key=img,
            cmd=cmd,
            expect=expect,
            reject=reject,
        )

    def _ini_set_selected_station(self, station_name: str) -> None:
        """Update [STATION].selected_station trong config.ini."""
        import configparser
        from pathlib import Path

        cfg_path = Path(app_dir()) / "config.ini"
        cfg = configparser.ConfigParser(strict=False)
        cfg.read(str(cfg_path), encoding="utf-8")

        if not cfg.has_section("STATION"):
            cfg.add_section("STATION")

        cfg.set("STATION", "selected_station", station_name)

        with open(cfg_path, "w", encoding="utf-8") as f:
            cfg.write(f)
            
    # def _guide_build_plan(self) -> list[GuideCase]:
    #     """Đọc config.ini và build plan các slot có nội dung test."""
    #     try:
    #         self.fx_cfg = load_fixture_cfg(app_dir() / "config.ini")
    #     except Exception:
    #         pass

    #     plan: list[GuideCase] = []
    #     fx = getattr(self, "fx_cfg", None)
    #     if fx is not None:
    #         for slot_id in range(1, 13):
    #             lbl = (fx.slot_text.get(slot_id, "") or "").strip()
                
    #             if not lbl:
    #                 continue
    #             cmd0 = (fx.slot_command.get(slot_id, "") or "").strip()
    #             guide = (fx.slot_guide.get(slot_id, "") or "").strip()
    #             img = (fx.slot_image.get(slot_id, "") or "").strip()
                
    #             # lấy station hiện tại
    #             selected, stations, station_map = load_station_cfg(self.cfg_path)
    #             st = station_map.get(selected or "")
    #             expect_s = ""
    #             reject_s = ""
    #             if st:
    #                 up_label = (lbl or "").upper()
    #                 up_cmd = (cmd0 or "").upper()

    #                 if "STOP" in up_label or "FORCE" in up_label:
    #                     expect_s = st.cmds.get("stop_expect", "")
    #                     reject_s = st.cmds.get("stop_reject", "")
    #                 elif "SENSOR" in up_label:
    #                     expect_s = st.cmds.get("sensor_expect", "")
    #                     reject_s = st.cmds.get("sensor_reject", "")
    #                 elif "RASTER" in up_cmd or "RASTER" in up_label:
    #                     expect_s = st.cmds.get("raster_expect", "")
    #                     reject_s = st.cmds.get("raster_reject", "")
    #                 else:
    #                     expect_s = st.cmds.get("expect", "")
    #                     reject_s = st.cmds.get("reject", "")
                        
    #             plan.append(self._guide_make_case(slot_id, lbl, cmd0,guide_text=guide, image_key=img, 
    #                 expect_regex=expect_s,
    #                 reject_regex=reject_s,))

    #     # fallback tối thiểu (để không crash UI)
    #     if not plan:
    #         plan = [self._guide_make_case(1, "IN", "IN CLOSE")]

    #     return plan
    
    def _guide_build_plan(self) -> list[GuideCase]:
        """Đọc config.ini và build plan các slot có nội dung test.
        Guide chỉ đọc pattern từ config.ini (SLOT_EXPECT/SLOT_REJECT), không đọc CSV.
        """
        def _is_tp_filename(s: str) -> bool:
            s = (s or "").strip().lower()
            return s.endswith((".png", ".gif", ".ppm", ".pgm"))

        # --- preload testplan images (nếu SLOT_IMAGE là filename) ---
        tp_map: dict[str, str] = {}
        tp_map_l: dict[str, Any] = {}   # ✅ để trống trước

        import configparser

        # 1) reload fixture cfg (slot_text/cmd/guide/img) từ config.ini như cũ
        try:
            self.fx_cfg = load_fixture_cfg(self.cfg_path)
        except Exception:
            pass

        # 2) đọc trực tiếp config.ini để lấy SLOT_EXPECT / SLOT_REJECT
        cfg = configparser.ConfigParser(strict=False)
        try:
            cfg.read(str(self.cfg_path), encoding="utf-8")
        except Exception:
            pass

        def _slot_pat(section: str, slot_id: int) -> str:
            if not cfg.has_section(section):
                return ""
            return (cfg.get(section, f"slot{slot_id}", fallback="") or "").strip()

        # (optional) fallback config-only: đọc station section trong ini (KHÔNG gọi load_station_cfg)
        selected_station = (cfg.get("STATION", "selected_station", fallback="") or "").strip()
        st_sec = f"STATION_{selected_station}" if selected_station else ""

        
        
        def _st_pat(key: str) -> str:
            if st_sec and cfg.has_section(st_sec):
                return (cfg.get(st_sec, key, fallback="") or "").strip()
            return ""

        plan: list[GuideCase] = []
        fx = getattr(self, "fx_cfg", None)

        if fx is not None:
            try:
                # selected_station bạn đã đọc ở trên rồi:
                # selected_station = (cfg.get("STATION", "selected_station", fallback="") or "").strip()

                def _log_img(msg: str):
                    try:
                        if getattr(self, "widgets_main", None):
                            self._update_logs_panel(msg, "yellow")
                        else:
                            print(msg)
                    except Exception:
                        print(msg)

                tp_dir = Path(self.cfg_path).resolve().parent / "test_plan"
                if selected_station and tp_dir.is_dir():
                    tp_files: list[str] = []
                    for i in range(1, 13):
                        v = (fx.slot_image.get(i, "") or "").strip()
                        if _is_tp_filename(v):
                            tp_files.append(v)
                            print(v)
                    if tp_files:
                        tp_map = load_assets.preload_testplan_images(
                            root=self.root,
                            assets=self.assets,                 # <-- append vào dict này
                            test_plan_dir=tp_dir,
                            station_name=selected_station,
                            image_filenames=tp_files,
                            log=lambda m: _log_img(m),
                            batch_ms=1,
                            max_per_tick=999,                   # để load “gần như ngay” cho guide preview
                            force_reload=True,
                            cv_img_w=self.cv_img_width,
                            cv_img_h=self.cv_img_height,
                        )

                    tp_map_l = {k.lower(): v for k, v in (tp_map or {}).items()}

            except Exception as e:
                _log_img(f"[img] preload exception: {e}")
            
            for slot_id in range(1, 13):
                lbl = (fx.slot_text.get(slot_id, "") or "").strip()
                if not lbl:
                    continue

                cmd0 = (fx.slot_command.get(slot_id, "") or "").strip()
                guide = (fx.slot_guide.get(slot_id, "") or "").strip()
                img0 = (fx.slot_image.get(slot_id, "") or "").strip()

                if _is_tp_filename(img0):
                    img = tp_map_l.get(img0.lower(), "fixture_240x240")  # fallback nếu thiếu file
                else:
                    img = img0 or "fixture_240x240"
                
                print("=== Debug images ===")

                print(f"img: {img}")
                print(f"img0: {img0}")

                print("selected_station=", selected_station)

                print("tp_files=", tp_files)

                print("tp_map keys=", list(tp_map_l.keys())[:5], "…")

                
                print("=== End Debug images ===")
                # ✅ Ưu tiên per-slot pattern từ config.ini
                expect_s = _slot_pat("SLOT_EXPECT", slot_id)
                reject_s = _slot_pat("SLOT_REJECT", slot_id)

                # Nếu slot chưa có pattern -> fallback theo station section trong config.ini (nếu có),
                # còn không thì dùng mặc định "NG"/"OK"
                if not expect_s and not reject_s:
                    up_label = (lbl or "").upper()
                    up_cmd = (cmd0 or "").upper()

                    if "STOP" in up_label or "FORCE" in up_label:
                        expect_s = _st_pat("stop_expect") or _st_pat("expect") or "NG"
                        reject_s = _st_pat("stop_reject") or _st_pat("reject") or "OK"
                    elif "SENSOR" in up_label:
                        expect_s = _st_pat("sensor_expect") or _st_pat("expect") or "NG"
                        reject_s = _st_pat("sensor_reject") or _st_pat("reject") or "OK"
                    elif "RASTER" in up_cmd or "RASTER" in up_label:
                        expect_s = _st_pat("raster_expect") or _st_pat("expect") or "NG"
                        reject_s = _st_pat("raster_reject") or _st_pat("reject") or "OK"
                    else:
                        expect_s = _st_pat("expect") or "NG"
                        reject_s = _st_pat("reject") or "OK"
                else:
                    # nếu chỉ thiếu 1 vế thì bù default
                    expect_s = expect_s or "NG"
                    reject_s = reject_s or "OK"

                plan.append(
                    self._guide_make_case(
                        slot_id, lbl, cmd0,
                        guide_text=guide,
                        image_key=img,
                        expect_regex=expect_s,
                        reject_regex=reject_s,
                    )
                )

        # fallback tối thiểu (để không crash UI)
        if not plan:
            plan = [self._guide_make_case(1, "IN", "IN CLOSE")]

        return plan

    def _guide_patch_step_all(self, idx: int, *, title=None, image_key=None, confirm_text=None, title_fill=None):
        for gp in self._iter_guide_panels():
            try:
                if not gp.steps:
                    continue
                i = max(0, min(int(idx), len(gp.steps) - 1))
                st = gp.steps[i]
                gp.steps[i] = type(st)(
                    title=title if title is not None else st.title,
                    image_key=image_key if image_key is not None else st.image_key,
                    confirm_text=confirm_text if confirm_text is not None else st.confirm_text,
                    title_fill=title_fill if title_fill is not None else getattr(st, "title_fill", None),  # NEW
                )
            except Exception:
                pass


    def _guide_build_steps(self, plan: Sequence[GuideCase]) -> list[GuideStep]:
        steps: list[GuideStep] = []

        # welcome
        steps.append(
            GuideStep(
                title="Bấm BẮT ĐẦU để bắt đầu kiểm tra fixture.",
                image_key="fixture_240x240",
                confirm_text="BẮT ĐẦU",
            )
        )

        # slot steps
        for c in plan:
            steps.append(
                GuideStep(
                    title=c.title,
                    image_key=c.image_key,
                    confirm_text="XÁC NHẬN",
                )
            )

        # # done step (dùng cho cả PASS ALL hoặc FAIL FINAL)
        steps.append(
            GuideStep(
                title="Kết thúc. Bấm BẮT ĐẦU LẠI để chạy lại.",
                image_key="fixture_fail_to_check_240x240",
                confirm_text="BẮT ĐẦU LẠI",
            )
        )
        return steps

    def _build_guide_preview_steps(self) -> list[GuideStep]:
        # preview = welcome + slot steps + done (dựa theo config hiện tại)
        plan = self._guide_build_plan()
        return self._guide_build_steps(plan)

    def _guide_apply_steps_all_windows(self, steps: Sequence[GuideStep], *, start_index: int = 0) -> None:
        for gp in self._iter_guide_panels():
            try:
                gp.set_steps(steps, start_index=start_index)
                gp.start()
            except Exception:
                pass

    def _guide_reset(self) -> None:
        self.reset_slot_status()
        self._guide_busy = False
        self._guide_running = False
        self._guide_plan = []
        self._guide_attempts = {}
        self._guide_current_step = 0

        steps = self._build_guide_preview_steps()
        self._guide_apply_steps_all_windows(steps, start_index=0)
        self._guide_goto_all(0)

    def _guide_start_run(self) -> None:
        # rebuild plan + steps từ config mỗi lần start
        self._guide_plan = self._guide_build_plan()

        first_case = self._guide_plan[0]
        self._set_fixture_dummy_key_all(self._fixture_dummy_key_for_case(first_case))

        self._guide_attempts = {c.slot_id: 0 for c in self._guide_plan}
        steps = self._guide_build_steps(self._guide_plan)

        self._guide_apply_steps_all_windows(steps, start_index=0)

        self._guide_running = True
        self._guide_current_step = 1

        # enter slot đầu tiên: set TESTING + show guide step1
        self._guide_goto_all(1)
        try:
            first_slot = self._guide_plan[0].slot_id
            self.update_slot_status(first_slot, "testing")
            # self.reset_slot_status()
        except Exception:
            pass

    def _get_active_guide_panel(self):
        # window đang click button confirm thường sẽ là window đang focus
        win = self._focused_window()
        ws = self._get_widgets(win)
        gp = ws.get("guide")

        # fallback về main nếu vì lý do nào đó không tìm thấy
        if gp is None:
            gp = self.widgets_main.get("guide")
        return gp


    def _slot_display_name(self, slot_id: int) -> str:
        # 1) ưu tiên từ fixture_cfg (config.ini)
        try:
            cfg = getattr(self, "fixture_cfg", None)
            if cfg and getattr(cfg, "slot_text", None):
                v = cfg.slot_text.get(int(slot_id))
                if v and str(v).strip():
                    return str(v).strip()
        except Exception:
            pass

        # 2) fallback: nếu self.slot_text dict tồn tại
        try:
            d = getattr(self, "slot_text", None)
            if isinstance(d, dict):
                v = d.get(int(slot_id))
                if v and str(v).strip():
                    return str(v).strip()
        except Exception:
            pass

        # 3) cuối cùng: mặc định
        return f"SLOT{slot_id}"

    def _on_guide_confirm(self, step_idx: int, step):
        # Check self.com_status is exists and listening
        if not hasattr(self, "com_status") or self.com_status != "listening":
            self._update_logs_panel("[guide] COM port not ready", "red")
            return
        
        gp = self._get_active_guide_panel()
        if gp is None:
            self._update_logs_panel("[guide] Missing guide panel instance", "yellow")
            return

        # chặn spam click khi đang chạy command
        if getattr(self, "_guide_busy", False):
            return

        # nếu chưa có plan (vd: vừa mở app) -> reset preview
        if not getattr(self, "_guide_plan", None):
            try:
                self._guide_reset()
            except Exception:
                pass

        # --- STEP 0: BẮT ĐẦU ---
        if step_idx == 0:
            self._guide_start_run()
            return

        done_idx = len(self._guide_plan) + 1
        if step_idx == done_idx:
            # QUYẾT ĐỊNH BẰNG STATE, KHÔNG DỰA VÀO step.confirm_text
            if getattr(self, "_guide_done_mode", "restart") == "exit":
                self._guide_done()   # gửi complete + đóng app
                return

            # restart
            self._guide_reset()
            return

        # nếu user click lệch step (multi-window), kéo về step hiện tại
        if self._guide_running and step_idx != self._guide_current_step:
            # self._guide_goto_all(self._guide_current_step)
            return

        # --- slot step ---
        if not (1 <= step_idx <= len(self._guide_plan)):
            # out of range => an toàn: reset
            self._guide_reset()
            return

        case = self._guide_plan[step_idx - 1]
        slot_id = case.slot_id

        self._guide_busy = True
        self._guide_set_busy_all(True, text="ĐANG KIỂM TRA...")

        dispatch = lambda fn: self.root.after(0, fn)

        def _do():
            ok, lines = self.listenport.send_and_collect(
                cmd=case.cmd,
                append_crlf=True,
                expect=case.expect,
                reject=case.reject,
                on_line=lambda s: dispatch(lambda: self._update_logs_panel(f"RX: {s}", "yellow")),
            )
            return ok, lines

        def _ok(result, _meta):
            ok, lines = result
            self._guide_busy = False
            self._guide_set_busy_all(False, text="XÁC NHẬN")

            if ok:
                PASS_GREEN = "#00FF80"  # #E1163F
                # PASS slot hiện tại
                self.update_slot_status(slot_id, "pass")
                # self.reset_slot_status()
                self._guide_attempts[slot_id] = 0

                # nếu hết slot => done
                if step_idx >= len(self._guide_plan):
                    self._guide_done_mode = "exit"
                    self._guide_running = False
                    self._guide_current_step = done_idx
                    self._guide_goto_all(done_idx)
                    self._guide_patch_step_all(
                        done_idx,
                        title="PASS toàn bộ slot. Fixture OK.",
                        image_key="fixture_pass_guide_240x240",
                        confirm_text="Thoát",
                        title_fill=PASS_GREEN,         # <-- NEW
                    )
                    self._guide_set_content_all(
                        title="PASS toàn bộ slot. Fixture OK.",
                        image_key="fixture_pass_guide_240x240",
                        confirm_text="Thoát",
                        title_fill=PASS_GREEN,         # <-- NEW
                    )
                    self._set_fixture_dummy_key_all("fixture_pass_guide_240x240")
                    self._guide_goto_all(done_idx)
                    return

                # move next slot
                next_step = step_idx + 1
                next_case = self._guide_plan[next_step - 1]
                self._guide_current_step = next_step
                self._guide_goto_all(next_step)
                self._set_fixture_dummy_key_all(self._fixture_dummy_key_for_case(next_case))
                # set TESTING cho slot tiếp theo
                self.update_slot_status(next_case.slot_id, "testing")
                # self.reset_slot_status()
                return
            FAIL_RED = "#FF3B30"  # #E1163F
            att = int(self._guide_attempts.get(slot_id, 0)) + 1
            self._guide_attempts[slot_id] = att
    
            if att >= self._guide_max_attempts:
                self._guide_done_mode = "restart"
                self.update_slot_status(slot_id, "fail")
                self._guide_running = False
                self._guide_current_step = done_idx

                title = (
                    f"FAIL FINAL tại Slot{slot_id} ({att}/{self._guide_max_attempts}). Dừng kiểm tra.\n"
                    f"Lý do thất bại: Tại ô thứ {slot_id} - {self._slot_display_name(slot_id)}"
                )

                self._guide_goto_all(done_idx)  # <-- goto trước

                self._guide_patch_step_all(
                    done_idx,
                    title=title,
                    image_key="fixture_fail_to_check_240x240",
                    confirm_text="BẮT ĐẦU LẠI",
                    title_fill=FAIL_RED,         # <-- NEW
                )
                self._guide_set_content_all(
                    title=title,
                    image_key="fixture_fail_to_check_240x240",
                    confirm_text="BẮT ĐẦU LẠI",
                    title_fill=FAIL_RED,         # <-- NEW
                )
                self._set_fixture_dummy_key_all("fixture_fail_to_check_240x240")
                return

            # fail nhưng cho retry => slot vẫn TESTING, chờ user confirm lần nữa
            self.update_slot_status(slot_id, "testing")

            self._guide_patch_step_all(
                step_idx,
                title=f"FAIL ({att}/{self._guide_max_attempts}).\n{case.title}\nHãy thực hiện lại thao tác rồi bấm THỬ LẠI.",
                image_key=case.image_key,
                title_fill=FAIL_RED,
                confirm_text="Vui lòng thử lại",
            )
            self._guide_set_content_all(
                title=f"FAIL ({att}/{self._guide_max_attempts}).\n{case.title}\nHãy thực hiện lại thao tác rồi bấm THỬ LẠI.",
                title_fill=FAIL_RED,
                confirm_text="Vui lòng thử lại",
            )
            # stay on the same step
            self._guide_goto_all(step_idx)

        def _err(e, _meta):
            self._guide_busy = False
            self._guide_set_busy_all(False, text="THỬ LẠI")
            try:
                self.update_slot_status(slot_id, "fail")
                # self.reset_slot_status()
            except Exception:
                pass
            self._task_error_cb(e, _meta)

        def _finally(_meta):
            self._task_finally_cb(_meta)

        self.send_to_com(case.cmd, on_start=self._task_start_cb, on_success=_ok, on_error=_err, on_finally=_finally, expect=case.expect, reject=case.reject, take_no_response_as_expect=True)

    def _startup_label(self) -> str:
        return "STARTUP: ON" if self.startup_enabled else "STARTUP: OFF"

    def _broadcast_startup_state(self) -> None:
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            btn = ws.get("startup_toggle")
            if not btn:
                continue
            try:
                btn.configure(
                    text=self._startup_label(),
                    fill=("#7CFF7C" if self.startup_enabled else "white"),
                    command=(lambda win=w: self.toggle_startup(win=win)) if self.is_admin else None,
                )
            except Exception:
                pass

    def toggle_startup(self, *, win: tk.Misc | None = None) -> None:
        if not self.is_admin:
            try:
                self._update_logs_panel("[startup] Need ADMIN to change startup", "yellow")
            except Exception:
                pass
            return

        def _log(msg: str):
            try:
                self._update_logs_panel(msg, "yellow")
            except Exception:
                pass

        if self.startup_enabled:
            ok = disable_startup(log_callback=_log)
        else:
            ok = enable_startup(log_callback=_log)

        # refresh state theo OS thật
        self.startup_enabled = is_startup_enabled()
        self._broadcast_startup_state()

        try:
            self._update_logs_panel(
                f"[startup] {'ENABLED' if self.startup_enabled else 'DISABLED'}",
                "green" if self.startup_enabled else "red",
            )
        except Exception:
            pass
    
    def _wd_log(self, msg: str):
        # nếu chưa có logs panel thì print; nếu có thì push vào log panel
        try:
            self._update_logs_panel(f"[watchdog] {msg}", "yellow")
        except Exception:
            print("[watchdog]", msg)
    
    def _ensure_watchdog_running(self):
        # Run ensure watchdog in io_taskq
        self.io_taskq.submit(
            func=ensure_watchdog_running_auto,
            kwargs={
                "log_dir": app_dir() / "logs" / "watchdog",
                "log_callback": self._wd_log,
            },
            name="Ensure Watchdog Running",
            on_start=self._task_start_cb,
            on_success=lambda result, meta: self._task_success_cb(result, meta),
            on_error=self._task_error_cb,
            on_finally=self._task_finally_cb,
            on_progress=self._task_progress_cb,
        )


# --- 1) helper normalize trạng thái ---
def _norm_state(s: Any) -> str:
    if s is None:
        return ""
    # enum -> name/value
    for attr in ("name", "value"):
        if hasattr(s, attr):
            try:
                s = getattr(s, attr)
                break
            except Exception:
                pass
    return str(s).strip().lower()

_PASS = {"pass", "passed", "ok", "success"}
_FAIL = {"fail", "failed", "ng", "error"}
_TESTING = {"testing", "running", "busy", "inprogress", "in_progress"}
_IDLE = {"idle", "item", "stand_by", "standby"}  # giữ nếu bạn cần dùng sau

def _is_pass(s: Any) -> bool:
    return _norm_state(s) in _PASS

def _is_idle(s: Any) -> bool:
    return _norm_state(s) in _IDLE


def _is_fail(s: Any) -> bool:
    return _norm_state(s) in _FAIL

def _is_testing(s: Any) -> bool:
    return _norm_state(s) in _TESTING


