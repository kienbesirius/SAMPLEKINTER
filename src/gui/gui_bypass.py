# import os
# import re
# import sys
# import time
# import threading
# import tkinter as tk
# from pathlib import Path
# from typing import Callable, Optional, Tuple
# from src.platform import dpi
# from src.gui.asset import load_assets # TẢI ASSETS vào GDI (fonts) | 
# from src.utils import sub_thread # SubProcessThread: XỬ LÝ SUB THREAD (TASKS) | Tách biệt main tkinter GUI thread với các tác vụ nền
# from src.utils.resource_path import RESOURCE_PATH, FONT_PATH, ICONS_PATH, app_dir
# from src.utils.buffer_logger import build_log_buffer
# from src.gui.widgets.button import bind_canvas_button
# from src.gui.widgets.entry import bind_canvas_entry
# from src.gui.widgets.text_area import bind_canvas_text_area
# import tkinter.font as tkfont

# # Keep the window always on top (works on Windows and many Tk backends)
# def topmost_window(root):
#     try:
#         root.attributes("-topmost", True)
#     except Exception:
#         try:
#             root.wm_attributes("-topmost", 1)
#         except Exception:
#             pass

# # Set application icon
# def set_app_icon(root):
#     icon_path = load_assets.ICON_ASSET.get("app_icon", ICONS_PATH / "treasure-svgrepo-com.ico")
#     if not icon_path.exists():
#         icon_path = app_dir() / "treasure-svgrepo-com.ico"
#     try:
#         # Some Tk builds (especially on X11) don't accept the 'default=' kwarg
#         # and .ico may not be supported. Prefer iconphoto with a PhotoImage
#         # for PNG/GIF when available, otherwise call iconbitmap with a
#         # positional argument. Keep a reference to the PhotoImage to avoid
#         # it being garbage-collected.
#         if icon_path.exists() and str(icon_path).lower().endswith((".png", ".gif")):
#             img = tk.PhotoImage(file=str(icon_path))
#             root.iconphoto(True, img)
#             root._icon_img = img
#         else:
#             # use positional arg instead of named 'default' to avoid
#             # "wrong # args" errors on some platforms
#             root.iconbitmap(str(icon_path))
#     except Exception as e:
#         print(f"Không thể đặt icon ứng dụng: {e}")

# # Set default font for the application
# def set_default_font(font: tkfont.Font):
#     tkfont.nametofont("TkDefaultFont").configure(
#         family=font.actual("family"),
#         size=font.actual("size"),
#         weight=font.actual("weight"),
#         slant=font.actual("slant"),
#     )

# W, H = 480, 240
# FAIL_COLOR = "#E1163F"
# PASS_COLOR = "#00FF80"

# class AppGUI:
#     dpi.set_dpi_awareness()

#     def __init__(self, root: tk.Tk):
#         # Build log buffer
#         self.log_buffer_max_lines = 500
#         self.logger, self.log_buffer = build_log_buffer(max_buffer=self.log_buffer_max_lines)
#         self.emit_msg = self.logger.info
#         self._log_lock = getattr(self.logger, "_log_lock", threading.Lock())

#         # Task management
#         self._task_handler = None
#         self._is_task_running = False

#         self.root = root

#         # Init Runner 
#         self.runner = sub_thread.SubProcessRunner(self.root)

#         # Setting root
#         self.root.title("GUI ByPASS: Warning Usage")
#         self.root.geometry(f"{W}x{H}")
#         self.root.resizable(False, False)
#         self.tektur_font = tkfont.Font(family="Tektur", size=11)
#         set_default_font(self.tektur_font)
#         set_app_icon(self.root)
#         topmost_window(self.root)

#         # Main Canvas
#         self._canvas = tk.Canvas(self.root, width=W, height=H, bg="white", highlightthickness=0)
#         self._canvas.pack(fill=tk.BOTH, expand=True)
#         self._btn_pressed = {}
#         self._btn_disabled = {}

#         self.assets = load_assets.tk_load_image_resources()

#         from src.gui.widgets.entry import bind_canvas_entry

#         x_axis = W // 2
#         y_axis = H // 2

#         y_item_offset = 10
#         # 2 draw title
#         self._canvas.create_image(x_axis, y_item_offset, anchor="n", image=self.assets["bypass_notice_title"])

#         y_item_offset += self.assets["bypass_notice_title"].height()*1.5


#         self.user_entry = bind_canvas_entry(
#             root=self.root,
#             canvas=self._canvas,
#             assets=self.assets,
#             x=x_axis,
#             y=y_item_offset,
#             name="username",
#             field_label="Scan DSN:",
#             placeholder="Sảo mã DSN...",
#             font=self.tektur_font,
#             on_submit=lambda s: self.emit_msg(f"submit username: {s}"),
#             state="normal",
#         )

#         y_item_offset += 24
#         self.status_label = self._canvas.create_image(x_axis, y_item_offset, anchor="n", image=self.assets["standby_title"])


#         # self._canvas.configure(bg=FAIL_COLOR)

#         # # Canvas.create_image returns an int item id, not a widget. Use
#         # # itemconfigure to update the displayed image.
#         # self._canvas.itemconfigure(self.status_label, image=self.assets["fail_title"])


#         self._canvas.configure(bg=PASS_COLOR)

#         # Canvas.create_image returns an int item id, not a widget. Use
#         # itemconfigure to update the displayed image.
#         self._canvas.itemconfigure(self.status_label, image=self.assets["pass_title"])

import re
import time
import threading
import tkinter as tk
from typing import Any, Dict, Optional

import tkinter.font as tkfont

from src.platform import dpi
from src.gui.asset import load_assets  # TẢI ASSETS vào GDI (fonts)
from src.utils import sub_thread       # SubProcessRunner: chạy task nền
from src.utils.buffer_logger import build_log_buffer
from src.utils.resource_path import ICONS_PATH, app_dir

from src.gui.widgets.entry import bind_canvas_entry


# ----------------------------
# Window helpers
# ----------------------------

def topmost_window(root: tk.Misc) -> None:
    try:
        root.attributes("-topmost", True)
    except Exception:
        try:
            root.wm_attributes("-topmost", 1)
        except Exception:
            pass


def set_app_icon(root: tk.Misc) -> None:
    icon_path = load_assets.ICON_ASSET.get("app_icon", ICONS_PATH / "treasure-svgrepo-com.ico")
    if not icon_path.exists():
        icon_path = app_dir() / "treasure-svgrepo-com.ico"
    try:
        if icon_path.exists() and str(icon_path).lower().endswith((".png", ".gif")):
            img = tk.PhotoImage(file=str(icon_path))
            root.iconphoto(True, img)
            root._icon_img = img  # keep ref
        else:
            root.iconbitmap(str(icon_path))
    except Exception as e:
        print(f"Không thể đặt icon ứng dụng: {e}")


def set_default_font(font: tkfont.Font) -> None:
    tkfont.nametofont("TkDefaultFont").configure(
        family=font.actual("family"),
        size=font.actual("size"),
        weight=font.actual("weight"),
        slant=font.actual("slant"),
    )


# ----------------------------
# GUI config
# ----------------------------
W, H = 480, 240

FAIL_COLOR = "#E1163F"
PASS_COLOR = "#00FF80"
RUN_COLOR = "#FFD24A"
STANDBY_COLOR = "#FFFFFF"

# Adjust to your DSN format if needed
_DSN_RE = re.compile(r"^[A-Za-z0-9._-]{6,64}$")

# ----------------------------
# Worker (MUST be top-level for SubProcessRunner on Windows spawn)
# ----------------------------
from src.utils.SFC import do_bypass_simple

def bypass_worker(dsn: str, *, cancel_event=None, progress_cb=None) -> Dict[str, Any]:
    """
    Worker chạy ở process phụ (SubProcessRunner).
    Trả về dict để UI quyết định PASS/FAIL và message.

    TODO: thay phần mô phỏng dưới đây bằng logic bypass thật của bạn.
    """
    dsn = (dsn or "").strip()
    result = do_bypass_simple(SN=dsn)
    # Check Start result out = f"Result=PASS|{data}"
    if not result:
        return {"ok": False, "msg": "Bypass returned no result"}
    
    try:
        if result.startswith("Result=PASS"):
            data = result.split("|", 1)[1] if "|" in result else ""
            # out = f"Result=PASS|Return={data}"
            return {"ok": True, "msg": data}
        # out = f"Result=FAIL|Return={data}"
        return {"ok": False, "msg": result}
    except Exception as e:
        return {"ok": False, "msg": f"Bypass exception: {e}"}


class AppGUI:
    dpi.set_dpi_awareness()

    def __init__(self, root: tk.Tk):
        # Build log buffer (optional)
        self.log_buffer_max_lines = 500
        self.logger, self.log_buffer = build_log_buffer(max_buffer=self.log_buffer_max_lines)
        self.emit_msg = self.logger.info
        self._log_lock = getattr(self.logger, "_log_lock", threading.Lock())

        # Task management
        self._task_handler = None
        self._is_task_running = False

        # Focus guard job id
        self._focus_guard_job: Optional[str] = None

        self.root = root
        self.runner = sub_thread.SubProcessRunner(self.root)

        # Window setup
        self.root.title("GUI ByPASS: Warning Usage")
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)

        self.tektur_font = tkfont.Font(family="Tektur", size=11)
        set_default_font(self.tektur_font)

        set_app_icon(self.root)
        topmost_window(self.root)

        # Main Canvas
        self._canvas = tk.Canvas(self.root, width=W, height=H, bg=STANDBY_COLOR, highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Load assets
        self.assets = load_assets.tk_load_image_resources()

        x_axis = W // 2
        y_item_offset = 10

        # Title
        self._canvas.create_image(x_axis, y_item_offset, anchor="n", image=self.assets["bypass_notice_title"])
        y_item_offset += int(self.assets["bypass_notice_title"].height() * 1.5)

        # Entry (barcode scan)
        self.user_entry = bind_canvas_entry(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            x=x_axis,
            y=y_item_offset,
            name="dsn",
            field_label="Scan DSN:",
            placeholder="Sảo mã DSN...",
            font=self.tektur_font,
            on_submit=self._on_scan_submit,
            state="normal",
        )

        y_item_offset += 24
        self.status_label = self._canvas.create_image(
            x_axis, y_item_offset, anchor="n", image=self._pick_asset("standby_title")
        )

        # Initial UI state
        self._set_status_ui("standby")

        # Auto-focus and keep focus for scanner
        self._setup_focus_guard()

    # ----------------------------
    # Focus handling
    # ----------------------------
    def _setup_focus_guard(self) -> None:
        # after window appears
        self.root.after(120, self._ensure_entry_focus)

        # if user clicks somewhere else, snap focus back to entry
        # (use add='+' so we don't clobber other bindings)
        self.root.bind_all("<Button-1>", self._on_any_click, add="+")

        # periodic guard (some WMs steal focus sometimes)
        self._schedule_focus_guard()

    def _on_any_click(self, _evt) -> None:
        # wait a tick to allow Tk to process click, then refocus
        self.root.after(1, self._ensure_entry_focus)

    def _schedule_focus_guard(self) -> None:
        if not self.root.winfo_exists():
            return
        self._ensure_entry_focus()
        self._focus_guard_job = self.root.after(250, self._schedule_focus_guard)

    def _ensure_entry_focus(self) -> None:
        if self._is_task_running:
            return
        try:
            if self.root.focus_get() is not self.user_entry.widget:
                self.user_entry.focus_set()
        except Exception:
            pass

    # ----------------------------
    # UI helpers
    # ----------------------------
    def _pick_asset(self, key: str):
        # fallback: nếu key không tồn tại -> standby_title
        if key in self.assets:
            return self.assets[key]
        return self.assets.get("standby_title")

    def _set_status_ui(self, status: str, msg: str = "") -> None:
        """
        status: 'standby' | 'running' | 'pass' | 'fail'
        """
        if status == "pass":
            self._canvas.configure(bg=PASS_COLOR)
            img_key = "pass_title"
        elif status == "fail":
            self._canvas.configure(bg=FAIL_COLOR)
            img_key = "fail_title"
        elif status == "running":
            self._canvas.configure(bg=RUN_COLOR)
            img_key = "standby_title"  # nếu có running_title thì đổi ở đây
        else:
            self._canvas.configure(bg=STANDBY_COLOR)
            img_key = "standby_title"

        try:
            self._canvas.itemconfigure(self.status_label, image=self._pick_asset(img_key))
        except Exception:
            pass

        if msg:
            self.emit_msg(msg)

    # ----------------------------
    # Scan -> start task
    # ----------------------------
    def _on_scan_submit(self, raw: str) -> None:
        dsn = (raw or "").strip()

        if not dsn:
            self._ensure_entry_focus()
            return

        # Prevent double-run
        if self._is_task_running:
            try:
                self.root.bell()
            except Exception:
                pass
            return

        self._start_bypass_task(dsn)

    def _start_bypass_task(self, dsn: str) -> None:
        # UI: disable entry while running
        self._is_task_running = True
        self.user_entry.set_disabled(True)
        self._set_status_ui("running", msg=f"[bypass] Start: {dsn}")

        # Start worker process
        self._task_handler = self.runner.submit(
            bypass_worker,
            args=(dsn,),
            name="bypass_worker",
            on_success=self._task_on_success,
            on_error=self._task_on_error,
            on_finally=self._task_on_finally,
            # on_start is optional; we already set UI above
        )

    # ----------------------------
    # Runner callbacks (Tk thread)
    # ----------------------------
    def _task_on_success(self, result: Any, meta: Dict[str, Any]) -> None:
        # result is dict from bypass_worker
        try:
            ok = bool(result.get("ok"))
            msg = str(result.get("msg") or "")
        except Exception:
            ok = False
            msg = "Bad result from worker"

        self._set_status_ui("pass" if ok else "fail", msg=msg)

    def _task_on_error(self, traceback_str: str, meta: Dict[str, Any]) -> None:
        self.emit_msg("[bypass] ERROR:\n" + (traceback_str or ""))
        self._set_status_ui("fail", msg="Bypass exception")

    def _task_on_finally(self, status: str, meta: Dict[str, Any]) -> None:
        # Re-enable entry, clear, refocus
        self._is_task_running = False
        self.user_entry.set_disabled(False)
        self.user_entry.clear()
        self._ensure_entry_focus()
