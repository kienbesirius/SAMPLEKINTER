import os
import re
import sys
import time
import threading
import tkinter as tk
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal
from typing import Callable, Optional, Tuple
from src.gui.gui279_perfect_squares import count_perfect_squares
from src.platform import dpi
from src.gui.asset import load_assets # TẢI ASSETS vào GDI (fonts) | 
from src.utils import sub_thread # SubProcessThread: XỬ LÝ SUB THREAD (TASKS) | Tách biệt main tkinter GUI thread với các tác vụ nền
from src.utils.resource_path import RESOURCE_PATH, FONT_PATH, ICONS_PATH, app_dir
from src.utils.buffer_logger import build_log_buffer
from src.gui.widgets.button import bind_canvas_button
from src.gui.widgets.entry import bind_canvas_entry
from src.gui.widgets.text_area import bind_canvas_text_area
from src.gui.widgets.fixture_check_slot_test import bind_fixture_check_slot_test
from src.gui.widgets.fixture_circle_status import bind_fixture_circle_com_status
from src.gui.widgets.paint_asset import bind_canvas_asset
from src.gui.widgets.canvas_log_widget import bind_canvas_log_widget
from src.gui.fixture.fill_multiple_monitor import fullscreen_on_monitor, get_monitors, monitor_from_point
from src.gui.fixture.get_fixture_port import get_fixture_port, parse_fixture_port_text
from src.gui.fixture.get_serial_list import get_serial_ports
from src.utils.config_go import load_fixture_cfg, choose_slot_font, reset_slot_status_section_to_idle, update_ini_slot_status, load_slot_status_from_ini, SlotStatus, _ALLOWED_STATUS
import tkinter.font as tkfont

# CORE-1: Getting fixture port
def obtaining_fixture_com(emit=print, cancel_event: threading.Event=None, progress_cb=None):
    """
    Lấy cổng COM của thiết bị fixture.
    Trả về chuỗi tên cổng (vd: "COM3") hoặc None nếu không tìm thấy.
    progress_cb: Callable[[str], None] - callback để báo tiến trình (nếu cần)
    cancel_event: threading.Event - sự kiện để hủy bỏ quá trình tìm kiếm
    """
    try:
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
                _, _, sw, sh = monitor_rect(monitor)
                
                canvas = tk.Canvas(win, bg=self.background_color, highlightthickness=0)
                canvas.pack(fill=tk.BOTH, expand=True)

                # sw, sh = win.winfo_width(), win.winfo_height()
                win._widgets = self._build_gui(win=win, canvas=canvas, sw=sw, sh=sh)
                win.protocol("WM_DELETE_WINDOW", lambda w=win: self._close_all_windows(w))

                self.roots_extra.append(win)
            except Exception:
                pass
            
    def __init__(self, root: tk.Tk):
        # Build log buffer
        self.cfg_path = app_dir() / "config.ini"
        self.status_map = load_slot_status_from_ini(self.cfg_path)

        self.log_buffer_max_lines = 500
        self.logger, self.log_buffer = build_log_buffer(max_buffer=self.log_buffer_max_lines)
        self.emit_msg = self.logger.info
        self._log_lock = getattr(self.logger, "_log_lock", threading.Lock())

        # Task management
        self._task_handler = None
        self._is_task_running = False

        self.root = root
        self.background_color = "#652200"
        
        # Get monitors
        self.monitors = get_monitors()
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

        # Setting root
        self.root.title("GUI Tkinter")
        # Open fullscreen instead of fixed-size window
        # Use the screen dimensions so canvas/UI can adapt to full screen
        # self.screen_width = self.root.winfo_screenwidth()
        # self.screen_height = self.root.winfo_screenheight()

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

        # Build GUI - Bind Events - Pump Logs
        # self._init_ui()

        # self.widgets_main = self._build_ui_on(
        #     win=self.root,
        #     canvas=self._canvas,
        #     sw=self.screen_width,
        #     sh=self.screen_height,
        # )

        # # nếu code khác vẫn cần self.entry_1/self.result_var:
        # self.entry_1 = self.widgets_main["entry"]
        # self.result_var = self.widgets_main["logs"]

        # TODO: Create UI for testing fixture

        self.widgets_main = self._build_gui(win=self.root,
            canvas=self._canvas,
            sw=self.screen_width,
            sh=self.screen_height,)

        # Apply fullscreen on current monitor
        fullscreen_on_monitor(self.root, self.current_window)

        self.create_extra_windows()

        self._resolve_COM()
        self.update_slot_status(1, "pass")
        self.update_slot_status(2, "fail")
    
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
            font = choose_slot_font(text)

            slot = bind_fixture_check_slot_test(
                root=win,
                canvas=canvas,
                assets=self.assets,
                tag=f"slot{i}_status",
                x=x, y=y,
                status=self.status_map.get(i, "idle"),
                text=text,
                text_font=font,
            )

            widgets[f"slot{i}"] = slot

        # Paint arrow
        x += slot_gap*2
        y -= slot_gap
        arrow = bind_canvas_asset(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="arrow_indicator",
            x=x, y=y,
            anchor="center",
            right_key="fixture_arrow_to_right",
            state="normal",
        )

        widgets[f"arrow"] = arrow

        x += slot_gap*1.5 + self.assets["fixture_info_frame_bg"].width() / 2
        logs = bind_canvas_log_widget(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="logs_panel",
            x=x, y=y,
            bg_key="fixture_info_frame_bg",
            anchor="center",
            ui_max_lines=100,
            buf_max_lines=500,
        )

        widgets["logs"] = logs

        return widgets
    
    # Resolve COM port
    def _resolve_COM(self):
        # Get COM port and update UI through runner
        self._task_hander = self.runner.submit(
            func=obtaining_fixture_com,
            kwargs={"emit": self._update_logs_panel},
            name="Obtain fixture COM",
            on_start=self._task_start_cb,
            on_success=lambda result, meta: self._resolve_COM_task_finished(result, meta),
            on_error=self._task_error_cb,
            on_finally=self._task_finally_cb,
            on_progress=self._task_progress_cb,
        )

    # Resolve COM port
    def _resolve_COM_task_finished(self, result: str, meta: dict):
        self._update_logs_panel(f"COM: {result}", "green")
        # Update UI accordingly
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            com1 = ws.get("com1")
            if com1:
                com1.set_label(result)
                if result == "COMX":
                    com1.set_status("not_found")
                else: 
                    com1.set_status("listening")
                    
            com1.set_disabled(True)

    def update_slot_status(self, slot_id: int = 1, status: SlotStatus = "idle") -> None:
        """
        1) Update config file
        2) Load lại status từ file
        3) Set status widget
        """
        def _do():
            # validate runtime (đảm bảo không sai)
            st = str(status).strip().lower()
            if st not in _ALLOWED_STATUS:
                raise ValueError(f"Invalid status: {status!r}. Allowed: {sorted(_ALLOWED_STATUS)}")
            if not (1 <= slot_id <= 12):
                raise ValueError(f"slot_idx out of range: {slot_id}")

            # 1) update file
            update_ini_slot_status(self.cfg_path, slot_id, st)
            # 2) load lại status
            self.status_map = load_slot_status_from_ini(self.cfg_path)
            # 3) set status widget
            new_status = self.status_map.get(slot_id, "idle")
            for w in self._iter_windows():
                ws = self._get_widgets(w)
                slot = ws.get(f"slot{slot_id}")
                if slot:        
                    slot.set_status(new_status)
        # Run in process for safe (if needed)
        self._task_hander = self.runner.submit(
            func=_do,
            kwargs={},
            name=f"Update slot{slot_id}",
            on_start=self._task_start_cb,
            on_success=None,
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

    ### Runner Callback
    def _task_start_cb(self, meta):
        name = meta["name"]
        self._update_logs_panel(f"{name}...", "yellow")

    def _task_progress_cb(self, payload):
        message = payload["message"]
        port = payload["port"]
        baudrate = payload["baudrate"]
        ending_line = payload["ending_line"]
        # message = getattr(payload, "message", str(payload))
        self._update_logs_panel(f"{message}")
        self._update_logs_panel(f"port: {port}")
        self._update_logs_panel(f"baudrate: {baudrate}")
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
        if status.lower() == "ok":
            self._update_logs_panel(f"{name} ~ END", "yellow")

    # Close all windows
    def _close_all_windows(self, source_win: tk.Misc | None = None):
        # chống re-entrant (vì destroy root sẽ destroy các toplevel, callback có thể bị gọi chồng)
        if getattr(self, "_is_closing_all", False):
            return
        self._is_closing_all = True

        # (optional) cleanup runner/process nếu bạn có stop/terminate
        try:
            self.runner.stop_all()
        except Exception:
            pass

        # destroy tất cả cửa sổ con trước (optional)
        for w in list(self.roots_extra):
            try:
                if w.winfo_exists():
                    w.destroy()
            except Exception:
                pass
        self.roots_extra.clear()

        # destroy root (Tk sẽ tự kéo theo mọi Toplevel còn lại)
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except Exception:
            pass

