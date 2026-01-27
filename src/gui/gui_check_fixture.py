import os
import re
import sys
import time
import threading
import tkinter as tk
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List
from typing import Callable, Optional, Tuple
from src.platform import dpi
from src.gui.asset import load_assets # TẢI ASSETS vào GDI (fonts) | 
from src.utils import sub_thread # SubProcessThread: XỬ LÝ SUB THREAD (TASKS) | Tách biệt main tkinter GUI thread với các tác vụ nền
from src.utils.resource_path import RESOURCE_PATH, FONT_PATH, ICONS_PATH, app_dir
from src.utils.buffer_logger import build_log_buffer
from src.gui.widgets.button import bind_canvas_button
from src.gui.widgets.entry import bind_canvas_entry
from src.gui.widgets.text_area import bind_canvas_text_area
from src.gui.fixture.fill_multiple_monitor import fullscreen_on_monitor, get_monitors, monitor_from_point

import tkinter.font as tkfont

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
                
                canvas = tk.Canvas(win, bg="white", highlightthickness=0)
                canvas.pack(fill=tk.BOTH, expand=True)

                # sw, sh = win.winfo_width(), win.winfo_height()
                win._widgets = self._build_ui_on(win=win, canvas=canvas, sw=sw, sh=sh)
                win.protocol("WM_DELETE_WINDOW", lambda w=win: self._close_all_windows(w))

                self.roots_extra.append(win)
            except Exception:
                pass
            
    def __init__(self, root: tk.Tk):
        # Build log buffer
        self.log_buffer_max_lines = 500
        self.logger, self.log_buffer = build_log_buffer(max_buffer=self.log_buffer_max_lines)
        self.emit_msg = self.logger.info
        self._log_lock = getattr(self.logger, "_log_lock", threading.Lock())

        # Task management
        self._task_handler = None
        self._is_task_running = False

        self.root = root
        
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
        self._canvas = tk.Canvas(self.root, bg="white", highlightthickness=0)
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

        # Phase Statuses
        self.COMX_status = False  # or "Connected", "Error", etc.
        self.PHASE_1_IN_STATUS = False
        self.PHASE_1_OUT_STATUS = False
        self.PHASE_2_FORCE_STOP_STATUS = False
        self.PHASE_3_RESET_STATUS = False
        self.APP_TITLE = "KIỂM TRA FIXTURE"
        self.GUIDE_TEXT = "Vui lòng thực hiện theo hướng dẫn dưới đây!"



        self._binding_events()
        self._pump_log_buffer()

        # Apply fullscreen on current monitor
        fullscreen_on_monitor(self.root, self.current_window)

        self.create_extra_windows()
    
    # TODO: Create UI for testing fixture
    def _init_phase_test(self):
        pass

    # def _init_ui(self):
    #     # : Initialize UI components here
    #     # center and layout based on current screen size (fullscreen)
    #     x_axis = self.screen_width // 2
    #     y_axis = self.screen_height // 2
    #     y_item_offset = 60
    #     try:
            
    #         self.button_sample = bind_canvas_button(
    #             root=self.root,
    #             canvas=self._canvas,
    #             assets=self.assets,
    #             tag="btn_example",
    #             x=x_axis + self.assets["button_normal"].width()//2,
    #             y=y_item_offset,
    #             normal_status="button_normal",
    #             hover_status="button_hover",
    #             active_status="button_active",
    #             disabled_status="button_disabled",  # nếu có; không có thì dùng chung button_disabled
    #             text="START",
    #             text_font=self.tektur_font,
    #             command=lambda: self.entry_1.configure(state="normal"),
    #             cooldown_ms=500,
    #         )

    #         self.button_sample2 = bind_canvas_button(
    #             root=self.root,
    #             canvas=self._canvas,
    #             assets=self.assets,
    #             tag="btn_example2",
    #             x=x_axis - self.assets["button_normal"].width()//2,
    #             y=y_item_offset,
    #             normal_status="button_normal",
    #             hover_status="button_hover",
    #             active_status="button_active",
    #             disabled_status="button_disabled",  # nếu có; không có thì dùng chung button_disabled
    #             text="CANCEL",
    #             text_font=self.tektur_font,
    #             command=lambda: self.entry_1.configure(state="disabled"),
    #             cooldown_ms=500,
    #         )

    #         self.emit_msg("Init UI...")

    #         self.entry_1 = bind_canvas_entry(
    #             root=self.root,
    #             canvas=self._canvas,
    #             assets=self.assets,
    #             x=x_axis,
    #             y=y_item_offset + 90,
    #             name="username",
    #             field_label="Username",
    #             placeholder="Nhập username...",
    #             font=self.tektur_font,
    #             on_submit=lambda s: self.emit_msg(f"submit username: {s}"),
    #             state="normal",
    #         )

    #         self.result_var = bind_canvas_text_area(
    #             root=self.root,
    #             canvas=self._canvas,
    #             assets=self.assets,
    #             x=x_axis,
    #             y=y_item_offset +130,
    #             bg_key="279_result_field",
    #             name="logs",
    #             anchor="n",
    #             readonly=True,
    #             auto_scroll=True,
    #             max_lines=500,
    #         )

    #         # append log:
    #         self.result_var.append("~/ hello")   # nhanh

    #         self._is_closing_all = False
    #         self.root.protocol("WM_DELETE_WINDOW", lambda: self._close_all_windows(self.root))

    #     except Exception as e:
    #         self.emit_msg(f"Error initializing UI: {e}")
    #         raise


    # def _build_ui_on(self, *, win: tk.Misc, canvas: tk.Canvas, sw: int, sh: int):
    #     x_axis = sw // 2
    #     y_item_offset = 60

    #     # Entry (mỗi window có entry riêng)
    #     entry = bind_canvas_entry(
    #         root=win,
    #         canvas=canvas,
    #         assets=self.assets,
    #         x=x_axis,
    #         y=y_item_offset + 90,
    #         name="username",
    #         field_label="Username",
    #         placeholder="Nhập username...",
    #         font=self.tektur_font,
    #         on_submit=lambda s: self.emit_msg(f"[{win.winfo_name()}] submit username: {s}"),
    #         state="normal",
    #     )

    #     # Buttons (command phải thao tác entry của CHÍNH window đó, không dùng self.entry_1)
    #     btn_start = bind_canvas_button(
    #         root=win,
    #         canvas=canvas,
    #         assets=self.assets,
    #         tag="btn_example",
    #         x=x_axis + self.assets["button_normal"].width() // 2,
    #         y=y_item_offset,
    #         normal_status="button_normal",
    #         hover_status="button_hover",
    #         active_status="button_active",
    #         disabled_status="button_disabled",
    #         text="START",
    #         text_font=self.tektur_font,
    #         command=lambda w=win: self.on_start(w),
    #         cooldown_ms=500,
    #     )

    #     btn_cancel = bind_canvas_button(
    #         root=win,
    #         canvas=canvas,
    #         assets=self.assets,
    #         tag="btn_example2",
    #         x=x_axis - self.assets["button_normal"].width() // 2,
    #         y=y_item_offset,
    #         normal_status="button_normal",
    #         hover_status="button_hover",
    #         active_status="button_active",
    #         disabled_status="button_disabled",
    #         text="CANCEL",
    #         text_font=self.tektur_font,
    #         command=lambda w=win: self.on_cancel(w),
    #         cooldown_ms=500,
    #     )

    #     # Logs area
    #     logs = bind_canvas_text_area(
    #         root=win,
    #         canvas=canvas,
    #         assets=self.assets,
    #         x=x_axis,
    #         y=y_item_offset + 130,
    #         bg_key="279_result_field",
    #         name="logs",
    #         anchor="n",
    #         readonly=True,
    #         auto_scroll=True,
    #         max_lines=500,
    #     )

    #     return {"entry": entry, "btn_start": btn_start, "btn_cancel": btn_cancel, "logs": logs}

    def _pump_log_buffer(self):
        try:
            with self._log_lock:
                if self.log_buffer:
                    for msg in self.log_buffer:
                        getattr(self.emit_msg, "print", print)(msg)
                    self.log_buffer.clear()
        except Exception as e:
            pass
        finally:
            try:
                if self.root.winfo_exists() and not getattr(self, "_is_closing_all", False):
                    self.root.after(100, self._pump_log_buffer)
            except tk.TclError:
                pass

    def _binding_events(self):
        # TODO: Bind events here
        try:
            self.emit_msg("Binding events...")
        except Exception as e:
            pass
    
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

    def _apply_start(self, win: tk.Misc):
        # TODO: Need to modify
        ws = self._get_widgets(win)
        entry = ws.get("entry")
        if entry:
            entry.configure(state="normal")

    def _apply_cancel(self, win: tk.Misc):
        # TODO: Need to modify
        ws = self._get_widgets(win)
        entry = ws.get("entry")
        if entry:
            entry.configure(state="disabled")

    def on_start(self, source_win: tk.Misc):
        # TODO: Need to modify
        # 1) xử lý window hiện tại
        self._apply_start(source_win)
        # 2) broadcast sang các window khác
        for w in self._iter_windows():
            if w is source_win:
                continue
            self._apply_start(w)

    def on_cancel(self, source_win: tk.Misc):
        # TODO: Need to modify
        self._apply_cancel(source_win)
        for w in self._iter_windows():
            if w is source_win:
                continue
            self._apply_cancel(w)

    def _close_all_windows(self, source_win: tk.Misc | None = None):
        # chống re-entrant (vì destroy root sẽ destroy các toplevel, callback có thể bị gọi chồng)
        if getattr(self, "_is_closing_all", False):
            return
        self._is_closing_all = True

        # (optional) cleanup runner/process nếu bạn có stop/terminate
        # try:
        #     self.runner.stop_all()
        # except Exception:
        #     pass

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
