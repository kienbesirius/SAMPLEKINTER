import os
import re
import sys
import time
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional, Tuple
from src.platform import dpi
from src.gui.asset import load_assets # TẢI ASSETS vào GDI (fonts) | 
from src.utils import sub_thread # SubProcessThread: XỬ LÝ SUB THREAD (TASKS) | Tách biệt main tkinter GUI thread với các tác vụ nền
from src.utils.resource_path import RESOURCE_PATH, FONT_PATH, ICONS_PATH, app_dir
from src.utils.buffer_logger import build_log_buffer
from src.gui.widgets.button import bind_canvas_button
from src.gui.widgets.entry import bind_canvas_entry
from src.gui.widgets.text_area import bind_canvas_text_area
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
    icon_path = load_assets.ICON_ASSET.get("app_icon", ICONS_PATH / "treasure-svgrepo-com.ico")
    if not icon_path.exists():
        icon_path = app_dir() / "treasure-svgrepo-com.ico"
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

W, H = 640, 480

class AppGUI:
    dpi.set_dpi_awareness()

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

        # Init Runner 
        self.runner = sub_thread.SubProcessRunner(self.root)

        # Setting root
        self.root.title("GUI ByPASS: Warning Usage")
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        self.tektur_font = tkfont.Font(family="Tektur", size=11)
        set_default_font(self.tektur_font)
        set_app_icon(self.root)
        topmost_window(self.root)

        # Main Canvas
        self._canvas = tk.Canvas(self.root, width=W, height=H, bg="white", highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._btn_pressed = {}
        self._btn_disabled = {}

        self.assets = load_assets.tk_load_image_resources()
