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
from src.gui.fixture.get_fixture_port import get_fixture_port, parse_fixture_port_text
from src.gui.fixture.get_serial_list import get_serial_ports
from src.gui.fixture.listen_port import ListenPort
from src.utils.config_go import load_fixture_cfg, choose_slot_font, reset_slot_status_section_to_idle, update_ini_slot_status, load_slot_status_from_ini, SlotStatus, _ALLOWED_STATUS, update_ini_fixture_section, update_ini_manual_slot_info
from src.gui.widgets.dialog import ModalOverlay
import tkinter.font as tkfont
from src.watchdog.watchdog_gui import wd_register, wd_heartbeat, wd_complete
from src.watchdog.watchdog_gui import ensure_watchdog_running_auto
from collections import deque

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


# CORE-1: Getting fixture port
def obtaining_fixture_com(emit=print, cancel_event: threading.Event=None, progress_cb=None):
    """
    Lấy cổng COM của thiết bị fixture.
    Trả về chuỗi tên cổng (vd: "COM3") hoặc None nếu không tìm thấy.
    progress_cb: Callable[[str], None] - callback để báo tiến trình (nếu cần)
    cancel_event: threading.Event - sự kiện để hủy bỏ quá trình tìm kiếm
    """
    cfg_path = Path(app_dir()) / "config.ini"
    fx = load_fixture_cfg(cfg_path)

    try:
        def _progress(msg: str, *, port: str = "", baudrate: int = 0, ending_line: str = ""):
            if progress_cb:
                progress_cb({
                    "message": msg,
                    "port": port,
                    "baudrate": baudrate,
                    "ending_line": ending_line,
                })
        
        # 1) ưu tiên cache trong config
        if fx.port and fx.port.upper() != "COMX":
            _progress(f"Checking cached fixture port: {fx.port} ...",
                      port=fx.port, baudrate=fx.baudrate, ending_line=fx.ending_line)

            try:
                r = get_fixture_port(
                    fx.port,
                    baudrates=[fx.baudrate],
                )
                r = parse_fixture_port_text(r)
                if r:
                    emit("Found fixture from config:", fx.port)
                    # (optional) refresh cache theo kết quả thực tế nếu bạn đã mở rộng ProbeResult
                    try:
                        update_ini_fixture_section(
                            cfg_path,
                            port=r.port,
                            baudrate=getattr(r.baudrate, "baudrate", fx.baudrate),
                            ending_line=getattr(r.line_ending, "ending_line", fx.ending_line),
                            timeout=fx.timeout,
                        )
                    except Exception:
                        pass

                    _progress("Found fixture (cached).",
                            port=r.port,
                            baudrate=getattr(r, "baudrate", fx.baudrate),
                            ending_line=getattr(r, "ending_line", fx.ending_line))
                    return r.port
            except Exception as e:
                emit(f"Error checking cached port {fx.port}: {e}")
                r = None
                
                _progress(f"Cached port not fixture, fallback scanning...", port=fx.port,
                        baudrate=fx.baudrate, ending_line=fx.ending_line)
                

        ports = get_serial_ports()
        for port in ports:
            if cancel_event and cancel_event.is_set():
                emit("Obtaining COM cancelled.")
                return "COMX"
            if progress_cb:
                progress_cb({"message": f"Checking {port}..."})
            found = get_fixture_port(port)
            parsed = parse_fixture_port_text(found)
            if found:
                emit("Found fixture on COM:", port)
                if progress_cb:
                    progress_cb({
                        "message": f"Found: {found}...",
                        "port": parsed.port,
                        "baudrate": parsed.baudrate,
                        "ending_line": parsed.line_ending    
                    })

                # 3) ghi cache vào config để lần sau nhanh
                update_ini_fixture_section(
                    cfg_path,
                    port=port,
                    baudrate=getattr(r, "baudrate", parsed.baudrate),
                    ending_line=getattr(r, "ending_line", parsed.line_ending),
                    timeout=fx.timeout,
                )

                _progress("Found fixture (scanned).",
                          port=port,
                          baudrate=getattr(r, "baudrate", parsed.baudrate),
                          ending_line=getattr(r, "ending_line", parsed.line_ending))
                return port
            time.sleep(0.1)  # giả lập delay kiểm tra

        emit("No fixture COM found.")
        return "COMX"
    except Exception as e:
        emit(f"Found exception on obtaining COM ---")
        emit(str(e))
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

        self.assets = load_assets.tk_load_image_resources()
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

    def _wd_do_register(self) -> None:
        pid = os.getpid()
        if getattr(sys, "frozen", False):
            argv = [sys.executable, *sys.argv[1:]]
        else:
            argv = [sys.executable, os.path.abspath(sys.argv[0]), *sys.argv[1:]]
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
        guide.set_steps(self._build_guide_preview_steps())
        guide.start()

        widgets["guide"] = guide
        # Dialog must be always last to create 
        modal = ModalOverlay(win)
        widgets["modal"] = modal

        return widgets
    

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

        def _ok():
            modal.hide()
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

        def _confirm():
            new_test = (txt_entry.get() or "").strip()
            new_cmd = (cmd_entry.get() or "").strip()
            modal.hide()

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

            modal.hide()

        def _cancel():
            modal.hide()

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

        modal.show(dim_level=0.45)



    def _get_modal(self, win: tk.Misc) -> "ModalOverlay | None":
        ws = self._get_widgets(win)
        return ws.get("modal")

    def _refresh_gui(self):
        # nếu queue bận, bỏ qua lần này (3s sau thử lại)
        if not self.taskq.is_busy():
            self.reload_slot_status()

        self.root.after(3000, self._refresh_gui)

    # Resolve COM port
    def _resolve_COM(self):
        # Get COM port and update UI through runner
        self.io_taskq.submit(
            func=obtaining_fixture_com,
            kwargs={},
            name="Obtain fixture COM",
            on_start=self._task_start_cb,
            on_success=lambda result, meta: self._resolve_COM_task_finished(result, meta),
            on_error=self._task_error_cb,
            on_finally=self._task_finally_cb,
            on_progress=self._task_progress_cb,
        )

    def _resolve_COM_task_finished(self, result: str, _meta):
        # 1) update label cho tất cả window trước
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            com1 = ws.get("com1")
            if com1:
                com1.set_label(result)

        # 2) stop instance cũ (nếu có)
        if getattr(self, "listenport", None):
            try:
                self.listenport.stop()
            except Exception:
                pass
            self.listenport = None

        for w in self._iter_windows():
            ws = self._get_widgets(w)
            pl = ws.get("probe_logs")
            if pl:
                try: pl.clear()
                except Exception: pass

        # 3) nếu không có COM thì update status rồi return
        if result == "COMX":
            for w in self._iter_windows():
                ws = self._get_widgets(w)
                com1 = ws.get("com1")
                if com1:
                    com1.set_status("not_found")
                    com1.set_disabled(True)
                    self.com_status = "not_found"
            return

        # 4) start ListenPort 1 lần
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
            status = self.com_status = "listening"

            self.send_to_com(cmd="help", on_start=self._task_start_cb, on_success=None, on_error=None, on_finally=None, expect=None, reject=None)
            self.send_to_com(cmd="?", on_start=self._task_start_cb, on_success=None, on_error=None, on_finally=None, expect=None, reject=None)
            self._update_logs_panel(f"ListenPort started on {result}", "green")
        except Exception as e:
            self._update_logs_panel(f"Error starting ListenPort: {e}", "red")
            status = self.com_status = "error"

        # 5) apply status cho tất cả window
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            com1 = ws.get("com1")
            if com1:
                com1.set_status(status)
                com1.set_disabled(True)

    def send_to_com(self, cmd: str, on_start, on_success, on_error, on_finally, expect=None, reject=None):
        def _do():
            if not self.listenport:
                raise RuntimeError("ListenPort not initialized")
            dispatch = lambda fn: self.root.after(0, fn)
            ok, lines = self.listenport.send_and_collect(
                cmd=cmd,
                append_crlf=True, 
                expect=expect,
                reject=reject,
                on_line=lambda s: dispatch(lambda: self._update_logs_panel(f"RX: {s}", "yellow"))
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

    def _guide_make_case(self, slot_id: int, slot_label: str, slot_cmd0: str) -> GuideCase:
        label = (slot_label or "").strip().upper()
        cmd0 = (slot_cmd0 or "").strip()
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

        print(f"Making guide case for Slot{slot_id}: label={label!r}, cmd0={cmd0!r}")


        # --- choose expect + image + title ---
        img = "fixture_240x240"
        title = f"[Slot{slot_id}] {label or 'CHECK'}"
        expect: Optional[Pattern[str]] = None


        ## TODO: CATCH patterns
        # OK_WORDS = ["ok", "pass", "passed", "success", "done"]
        # expect = re.compile(r"\b(?:%s)\b" % "|".join(map(re.escape, OK_WORDS)), re.I)
        # reject = re.compile(r"\b(?:OK|ok|True|true|closed|CLOSED|Closed)\b", re.I)
        up_cmd = cmd.strip().upper()

        if "SENSOR TOP LEFT" in label:
            img = "guide_sensor_top_left"
            title = f"[Slot{slot_id}] Hãy dùng công cụ che Cảm Biến góc trên trái ở cửa vào Fixture.\nBấm xác nhận để kiểm tra!"
            # expect = re.compile(r"ok", re.I)
            ## TODO: CATCH patterns
            expect = re.compile(r"\b(?:PRODUCT_NG|FIX_SAFE_NG|CLOSE_NG|error|sensor\s+error|NG)\b", re.I)
            reject = re.compile(r"\b(?:OK|ok|True|true|closed|CLOSED|Closed)\b", re.I)
        elif "SENSOR TOP RIGHT" in label:
            img = "guide_sensor_top_right"
            title = f"[Slot{slot_id}] Hãy dùng công cụ che Cảm Biến góc trên phải ở cửa vào Fixture.\nBấm xác nhận để kiểm tra!"
            ## TODO: CATCH patterns
            expect = re.compile(r"\b(?:PRODUCT_NG|FIX_SAFE_NG|CLOSE_NG|error|sensor\s+error|NG)\b", re.I)
            reject = re.compile(r"\b(?:OK|ok)\b", re.I)
        elif "SENSOR BOT LEFT" in label:
            img = "guide_sensor_bottom_left"
            title = f"[Slot{slot_id}] Hãy dùng công cụ che Cảm Biến góc dưới trái ở cửa vào Fixture.\nBấm xác nhận để kiểm tra!"
            # theo dummy fixture bạn đã mô tả: có thể trả STOPPED/NG/timeout/EMC
            expect = re.compile(r"\b(?:PRODUCT_NG|FIX_SAFE_NG|CLOSE_NG|error|sensor\s+error|NG)\b", re.I)
            reject = re.compile(r"\b(?:OK|ok)\b", re.I)
        elif "SENSOR BOT RIGHT" in label:
            img = "guide_sensor_bottom_right"
            title = f"[Slot{slot_id}] Hãy dùng công cụ che Cảm Biến góc dưới phải ở cửa vào Fixture.\nBấm xác nhận để kiểm tra!"
            expect = re.compile(r"\b(?:PRODUCT_NG|FIX_SAFE_NG|CLOSE_NG|error|sensor\s+error|NG)\b", re.I)
            reject = re.compile(r"\b(?:OK|ok)\b", re.I)
        elif "SENSOR" in up_cmd:
            img = "guide_close_fixture"
            title = f"[Slot{slot_id}] Hãy dùng công cụ che SENSOR ở cửa vào Fixture.\nBấm xác nhận để kiểm tra!"
            expect = re.compile(r"\b(?:PRODUCT_NG|FIX_SAFE_NG|CLOSE_NG|error|sensor\s+error|NG)\b", re.I)
            reject = re.compile(r"\b(?:OK|ok)\b", re.I)

        elif "STOP" in label or "FORCE STOP" in label:
            img = "fixture_stop_guide_240x240"
            title = f"[Slot{slot_id}] Hãy nhấn nút FORCE STOP - DỪNG KHẨN CẤP.\nBấm xác nhận để kiểm tra!"
            expect = re.compile(r"\b(?:not\s+ok|fail(?:ed)?|ng|error|timeout|EMC|emc|STOPPED|STOP_ON|STOP!|HOLD_ON)\b", re.I)
            # expect = re.compile(r"OK", re.I)
            reject = re.compile(r"\b(?:OK|ok)\b", re.I)

        return GuideCase(
            slot_id=slot_id,
            slot_label=label,
            title=title,
            image_key=img,
            cmd=cmd,
            expect=expect,
            reject=reject,
        )

    def _guide_build_plan(self) -> list[GuideCase]:
        """Đọc config.ini và build plan các slot có nội dung test."""
        try:
            self.fx_cfg = load_fixture_cfg(app_dir() / "config.ini")
        except Exception:
            pass

        plan: list[GuideCase] = []
        fx = getattr(self, "fx_cfg", None)
        if fx is not None:
            for slot_id in range(1, 13):
                lbl = (fx.slot_text.get(slot_id, "") or "").strip()
                if not lbl:
                    continue
                cmd0 = (fx.slot_command.get(slot_id, "") or "").strip()
                plan.append(self._guide_make_case(slot_id, lbl, cmd0))

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

        self.send_to_com(case.cmd, on_start=self._task_start_cb, on_success=_ok, on_error=_err, on_finally=_finally, expect=case.expect, reject=case.reject)

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


