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
from src.gui.widgets.fixture_check_slot_test import bind_fixture_check_slot_test
from src.gui.widgets.fixture_circle_status import bind_fixture_circle_com_status
from src.gui.widgets.paint_asset import bind_canvas_asset
from src.gui.widgets.canvas_log_widget import bind_canvas_log_widget
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

        self._binding_events()
        self._pump_log_buffer()

        # Apply fullscreen on current monitor
        fullscreen_on_monitor(self.root, self.current_window)

        self.create_extra_windows()
    
    # TODO: Create UI for testing fixture
    def _build_gui(self, *, win: tk.Misc, canvas: tk.Canvas, sw: int, sh: int):
        # layout
        x_axis = sw // 2
        y_axis = sh // 2

        # --- button start ---
        # btn_start = bind_canvas_button(
        #     root=win,
        #     canvas=canvas,
        #     assets=self.assets,
        #     tag="btn_start",
        #     x=x_axis,
        #     y=y_top,
        #     normal_status="fixture_button_confirm_normal",
        #     hover_status="fixture_button_confirm_hover",
        #     active_status="fixture_button_confirm_pressed",
        #     disabled_status="fixture_button_confirm_disabled",
        #     text="",
        #     text_font=self.tektur_font,
        #     command=None,           # hoặc: lambda w=win: self.on_start(w)
        #     cooldown_ms=500,
        # )

        # --- COM status (dock origin) ---
        com1 = bind_fixture_circle_com_status(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="com_status",
            x=-2, y=0,          # (x,y) là gốc DOCK theo logic bạn mới muốn
            label="COM999",
            status="stand_by",
        )
        com1.set_disabled(True)
        
        # --- slots: row 1 ---
        y_slot_offset = y_axis // 2 * 0.8
        x_slot_origin = x_axis * 0.1
        left_x = x_slot_origin
        slot_gap = self.assets["fixture_slot_test"].width() * 0.5
        slot1 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot1_status",
            x=left_x, y=y_slot_offset,
            status="idle",
            text="IN",
            text_font=("Tektur", 17, "bold"),
        )

        # Calculate positions for slot2 and slot3 based on slot1 and asset width 
        slot2_x = left_x + slot_gap
        slot3_x = slot2_x + slot_gap
        slot4_x = slot3_x + slot_gap

        slot2 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot2_status",
            x=slot2_x, y=y_slot_offset,
            status="idle",
            text="OUT",
            text_font=("Tektur", 17, "bold"),
        )

        slot3 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot3_status",
            x=slot3_x, y=y_slot_offset,
            status="idle",
            text="FORCE\nSTOP",
            text_font=("Tektur", 11, "bold"),
        )

        slot4 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot4_status",
            x=slot4_x, y=y_slot_offset,
            status="idle",
            text="RESET",
            text_font=("Tektur", 11, "bold"),
        )

        # --- slots: row 2 ---
        y_slot_offset += slot_gap
        left_x = x_slot_origin

        # (You can add more slots or other widgets here as needed)
        slot5 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot5_status",
            x=left_x, y=y_slot_offset,
            status="idle",
            text="",
            text_font=("Tektur", 13, "bold"),
        )

        left_x += slot_gap
        slot6 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot6_status",
            x=left_x, y=y_slot_offset,
            status="idle",
            text="",
            text_font=("Tektur", 13, "bold"),
        )

        left_x += slot_gap
        slot7 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot7_status",
            x=left_x, y=y_slot_offset,
            status="idle",
            text="",
            text_font=("Tektur", 13, "bold"),
        )

        left_x += slot_gap
        slot8 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot8_status",
            x=left_x, y=y_slot_offset,
            status="idle",
            text="",
            text_font=("Tektur", 13, "bold"),
        )

        # --- slots: row 3 ---
        y_slot_offset += slot_gap
        left_x = x_slot_origin

        # (You can add more slots or other widgets here as needed)
        slot9 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot9_status",
            x=left_x, y=y_slot_offset,
            status="idle",
            text="",
            text_font=("Tektur", 13, "bold"),
        )

        left_x += slot_gap
        slot10 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot10_status",
            x=left_x, y=y_slot_offset,
            status="idle",
            text="",
            text_font=("Tektur", 13, "bold"),
        )

        left_x += slot_gap
        slot11 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot11_status",
            x=left_x, y=y_slot_offset,
            status="idle",
            text="",
            text_font=("Tektur", 13, "bold"),
        )

        left_x += slot_gap
        slot12 = bind_fixture_check_slot_test(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="slot12_status",
            x=left_x, y=y_slot_offset,
            status="idle",
            text="",
            text_font=("Tektur", 13, "bold"),
        )

        # Paint arrow
        left_x += slot_gap*2
        y_slot_offset -= slot_gap
        arrow = bind_canvas_asset(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="arrow_indicator",
            x=left_x, y=y_slot_offset,
            anchor="center",
            right_key="fixture_arrow_to_right",
            state="normal",
        )


        left_x += slot_gap*1.5 + self.assets["fixture_info_frame_bg"].width() / 2
        self.logs = logs = bind_canvas_log_widget(
            root=win,
            canvas=canvas,
            assets=self.assets,
            tag="logs_panel",
            x=left_x, y=y_slot_offset,
            bg_key="fixture_info_frame_bg",
            anchor="center",
            ui_max_lines=100,
            buf_max_lines=500,
        )

        # bơm log (có thể gọi spam, hoặc từ thread khác)
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        self.logs.emit("Device connected", "white")
        self.logs.emit("ERROR: timeout", "red")
        self.logs.emit("Warning: low signal", "yellow")
        self.logs.emit("RX OK", "blue")
        self.logs.emit("Bế Chí Kiên", "green")
        return {
            # "btn_start": btn_start,
            "slot1": slot1,
            "slot2": slot2,
            "slot3": slot3,
            "slot4": slot4,
            "slot5": slot5,
            "slot6": slot6,
            "slot7": slot7,
            "slot8": slot8,
            "slot9": slot9,
            "slot10": slot10,
            "slot11": slot11,
            "slot12": slot12,
            "arrow": arrow,
            "logs": logs,
            "com1": com1,
        }

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
