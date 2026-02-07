import os
import re
import sys
import time
import threading
import tkinter as tk
from pathlib import Path
from typing import Callable, Optional, Tuple, Literal
from src.platform import dpi
from src.gui.asset import load_assets # TẢI ASSETS vào GDI (fonts) | 
from src.utils import sub_thread # SubProcessThread: XỬ LÝ SUB THREAD (TASKS) | Tách biệt main tkinter GUI thread với các tác vụ nền
from src.utils.resource_path import RESOURCE_PATH, FONT_PATH, ICONS_PATH, app_dir
from src.utils.buffer_logger import build_log_buffer
from src.gui.widgets.button import bind_canvas_button
from src.gui.widgets.entry import bind_canvas_entry
from src.gui.widgets.text_area import bind_canvas_text_area
import tkinter.font as tkfont

from src.gui.fixture.listen_port import ListenPort

LogColor = Literal["white", "red", "green", "yellow", "blue"]

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

        self.root = root

        # For sending commands
        self.io_runner = sub_thread.SubThreadRunner(self.root)
        self.io_taskq = sub_thread.SequentialTaskQueue(root=self.root, runner=self.io_runner)

        # Setting root
        self.root.title("GUI Tkinter ByPass Panel")
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        self.tektur_font = tkfont.Font(family="Tektur", size=11)
        set_default_font(self.tektur_font)
        set_app_icon(self.root)
        topmost_window(self.root)

        # Main Canvas
        self.fail_color = "#E1163F"
        self.pass_color = "#00FF80"
        self.stand_by_color = "#F3FFB8"
        self.default_color = "#FFFFFF"
        self._canvas = tk.Canvas(self.root, width=W, height=H, bg=self.default_color, highlightthickness=0)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._btn_pressed = {}
        self._btn_disabled = {}

        self.assets = load_assets.tk_load_image_resources()

        # PanelSN debounce / idle trigger
        self._panel_sn_debounce_ms: int = 250
        self._panel_sn_after_id: Optional[str] = None
        self._panel_sn_last_sent_cmd: str = ""
        self._panel_sn_last_sent_ts: float = 0.0

        # Initialize GUI
        self._gui_()
        self._set_port_listener__()

    def _set_port_listener__(self, com_port: Optional[str] = None):
        # 4) start ListenPort 1 lần
        try:
            if com_port is None:
                com_port = self.txt_entry_com_sfc.get()
            # 2) stop instance cũ (nếu có)
            if getattr(self, "listenport", None):
                try:
                    self.listenport.stop()
                except Exception:
                    pass
                self.listenport = None

            # 3) khởi tạo ListenPort mới
             # Lấy cổng COM từ entry
            # sfc_port = self.txt_entry_com_sfc.get()
            if not com_port:
                self._update_logs_panel("Cổng COM SFC không được để trống", "red")
                raise ValueError("Cổng COM SFC không được để trống")
            
            dispatch = lambda fn: self.root.after(0, fn)
            self.listenport = ListenPort(
                port=com_port,
                baudrate=9600,
                log=self.emit_msg,
                on_rx=lambda s: self._update_logs_panel(f"RX: {s}", "white"),
                dispatch=dispatch,
            )
            self.listenport.start()
            self._update_logs_panel(f"ListenPort started on {com_port}", "green")
        except Exception as e:
            self._update_logs_panel(f"Error starting ListenPort: {e}", "red")

    def _gui_(self):
        x_axis = W//2
        y_axis = H//2
        from src.gui.widgets.canvas_log_widget import bind_canvas_log_widget
        bottom_x = W - (self.assets["bg_480x148"].width() // 2) - 8
        bottom_y = H - (self.assets["bg_480x148"].height() // 2) - 8

        self.ui_logs = bind_canvas_log_widget(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            tag="logs_panel",
            x=bottom_x, y=bottom_y,
            text_bg="#8D8D8D",
            bg_key="bg_480x148",
            font=("Tektur", 8, "normal"),
            anchor="center",
            ui_max_lines=100,
            buf_max_lines=500,
        )
        self._update_logs_panel("Logs panel initialized.", "white")

        # --- SLOT TEST edit entry (nằm dưới, không đụng dòng vàng) ---
        self.txt_entry_panel_dsn = bind_canvas_entry(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            x=x_axis,
            y=y_axis,
            name=f"panel_dsn",          # ✅ đổi name, tránh trùng
            field_label="Panel DSN",
            field_label_fill="#000000",
            placeholder="Nhập/Scan PanelSN...",
            font=getattr(self, "tektur_font", None),
            auto_skin_by_label=False,
            normal="entry_wide_1_normal",
            focus="entry_wide_1_focused",
            disabled_status="entry_wide_1_disabled",
            state="normal",
            on_submit=lambda s: self._on_panel_sn_submit(s),
        )
        self.txt_entry_panel_dsn.set("")
        self._update_logs_panel("Entry panel_dsn initialized.", "white")

        ## Mapping pos
        x = 4
        y = 4

        x_text_entry_com_sfc = x + (self.assets["entry_wide_1_normal"].width() // 2)
        y_text_entry_com_sfc = y + (self.assets["entry_wide_1_normal"].height() // 2)

        x_text_entry_mo = x + (self.assets["entry_wide_1_normal"].width() // 2)
        y_text_entry_mo = y + (self.assets["entry_wide_1_normal"].height() // 2) + y_text_entry_com_sfc + 16
        
        x_text_entry_laser_id = x + (self.assets["entry_wide_1_normal"].width() // 2)
        y_text_entry_laser_id = y + (self.assets["entry_wide_1_normal"].height() // 2) + y_text_entry_mo + 16

        self.txt_entry_com_sfc = bind_canvas_entry(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            x=x_text_entry_com_sfc,
            y=y_text_entry_com_sfc,
            name=f"com",          # ✅ đổi name, tránh trùng
            field_label="COM SFC",
            field_label_fill="#000000",
            placeholder="Nhập cổng COM nối với SFC",
            font=getattr(self, "tektur_font", None),
            auto_skin_by_label=False,
            normal="entry_wide_1_normal",
            focus="entry_wide_1_focused",
            disabled_status="entry_wide_1_disabled",
            state="normal",
            on_submit=lambda val: self._set_port_listener__(val)
        )
        self.txt_entry_com_sfc.set("/dev/ttyUSB3")

        self.txt_entry_mo = bind_canvas_entry(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            x=x_text_entry_mo,
            y=y_text_entry_mo,
            name=f"mo",          # ✅ đổi name, tránh trùng
            field_label="WO/MO",
            field_label_fill="#000000",
            placeholder="Nhập công lệnh WO/MO",
            font=getattr(self, "tektur_font", None),
            auto_skin_by_label=False,
            normal="entry_wide_1_normal",
            focus="entry_wide_1_focused",
            disabled_status="entry_wide_1_disabled",
            state="normal",
        )
        self.txt_entry_mo.set("")

        self.txt_entry_laser_id = bind_canvas_entry(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            x=x_text_entry_mo,
            y=y_text_entry_laser_id,
            name=f"laser_id",          # ✅ đổi name, tránh trùng
            field_label="LASER ID",
            field_label_fill="#000000",
            placeholder="Nhập tên máy laser (VD: fixup_laser_001)",
            font=getattr(self, "tektur_font", None),
            auto_skin_by_label=False,
            normal="entry_wide_1_normal",
            focus="entry_wide_1_focused",
            disabled_status="entry_wide_1_disabled",
            state="normal",
        )
        self.txt_entry_laser_id.set("")
        # Bind auto-focus + debounce send logic
        self._bind_bypass_events()

    ### Pump log buffer to UI through emit_msg to the log.info    
    def _update_logs_panel(self, msg: str, color: LogColor = "white"):
        self.emit_msg(msg)

        with self._log_lock:
            # get last line
            line = self.log_buffer[-1:]
        if line:
            # iter window and update log
            logs = self.ui_logs
            if logs:
                logs.emit(line[0], color)  # màu trắng mặc định


    def send_to_com(self, cmd: str):
        def _do():
            # Disable the entry during sending
            self.txt_entry_com_sfc.configure(state="disabled")
            self.txt_entry_mo.configure(state="disabled")
            self.txt_entry_laser_id.configure(state="disabled")
            self.txt_entry_panel_dsn.configure(state="disabled")

            self._canvas.configure(bg=self.stand_by_color)
            if not self.listenport:
                raise RuntimeError("ListenPort not initialized")
            dispatch = lambda fn: self.root.after(0, fn)
            ok, lines = self.listenport.send_and_collect(
                cmd=cmd,
                append_crlf=True, 
                on_line=lambda s: dispatch(lambda: self._update_logs_panel(f"RX: {s}", "yellow"))
            )
            return ok, lines

        def _ok(result, _meta):
            ok, lines = result
            # Check if any line end with PASSED=1PASS
            if any(line.endswith("PASSED=1PASS") for line in lines):
                ok = True
                self._canvas.configure(bg=self.pass_color)
            else:
                ok = False
                self._canvas.configure(bg=self.fail_color)
            self._update_logs_panel(f"TX: {cmd} | RX lines: {len(lines)}", "blue")

            self.txt_entry_com_sfc.configure(state="normal")
            self.txt_entry_mo.configure(state="normal")
            self.txt_entry_laser_id.configure(state="normal")
            self.txt_entry_panel_dsn.configure(state="normal")
            self.txt_entry_panel_dsn.set("")
            if lines:
                self._update_logs_panel(f"RX last: {lines[-1]}", "green" if ok else "yellow")

        self.io_taskq.submit(
            func=_do,
            name="Send to COM",
            on_start=self._task_start_cb,
            on_success=_ok,
            on_error=self._task_error_cb,
            on_finally=self._task_finally_cb,
        )


    ### Runner Callback
    def _task_start_cb(self, meta):
        name = meta["name"]

        if "RELOAD" in name.upper():
            return None
        self._update_logs_panel(f"{name}...", "yellow")

    def _task_progress_cb(self, payload):
        if not isinstance(payload, dict):
            return
        self.message = payload["message"]
        self.port = payload["port"]
        self.baudrate = payload["baudrate"]
        self.ending_line = payload["ending_line"]
        # message = getattr(payload, "message", str(payload))
        self._update_logs_panel(f"{self.message}")
        self._update_logs_panel(f"port: {self.port}")
        self._update_logs_panel(f"baudrate: {self.baudrate}")
        self._update_logs_panel(f"ending_line: {self.ending_line}")

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

        if getattr(self, "txt_entry_panel_dsn", None):
            self.txt_entry_panel_dsn.set("")

    # -----------------------------
    # Bypass panel logic
    # -----------------------------
    def _bind_bypass_events(self) -> None:
        """Enter on other entries => focus PanelSN.
        PanelSN entry:
          - Enter triggers send immediately
          - No input for 250ms triggers send (idle debounce)
        """

        # Enter on other entries => focus to PanelSN
        def _focus_panel_sn(_evt=None):
            try:
                self.txt_entry_panel_dsn.focus_set()
            except Exception:
                try:
                    self.txt_entry_panel_dsn.widget.focus_set()
                except Exception:
                    pass
            return "break"

        for other in (getattr(self, "txt_entry_com_sfc", None), getattr(self, "txt_entry_mo", None)):
            if not other:
                continue
            try:
                other.widget.bind("<Return>", _focus_panel_sn)
                other.widget.bind("<KP_Enter>", _focus_panel_sn)
            except Exception:
                pass

        # PanelSN: reset idle timer on any change
        def _on_panel_keyrelease(evt):
            # Ignore Enter key (Enter is handled by on_submit)
            ks = getattr(evt, "keysym", "")
            if ks in ("Return", "KP_Enter"):
                return
            self._panel_sn_on_change()

        try:
            self.txt_entry_panel_dsn.widget.bind("<KeyRelease>", _on_panel_keyrelease)
        except Exception:
            pass

        # Also track programmatic changes (StringVar)
        try:
            self.txt_entry_panel_dsn.var.trace_add("write", lambda *_: self._panel_sn_on_change())
        except Exception:
            pass

        # Initial focus
        try:
            self.root.after(120, lambda: self.txt_entry_panel_dsn.focus_set())
        except Exception:
            pass

    def _on_panel_sn_submit(self, s: str) -> None:
        """Called when PanelSN entry receives Enter."""
        self._cancel_panel_idle_timer()
        self._trigger_send_panel_sn(panel_sn=s, reason="enter")

    def _panel_sn_on_change(self) -> None:
        """Called whenever PanelSN text changes.
        We schedule an idle send (250ms after last change).
        """
        try:
            raw = self.txt_entry_panel_dsn.get() or ""
        except Exception:
            raw = ""

        # If somehow pasted text contains newline, normalize and send immediately.
        if "\n" in raw or "\r" in raw:
            cleaned = re.sub(r"[\r\n]+", "", raw).strip()
            try:
                self.txt_entry_panel_dsn.set(cleaned)
            except Exception:
                pass
            self._cancel_panel_idle_timer()
            self._trigger_send_panel_sn(panel_sn=cleaned, reason="newline")
            return

        self._schedule_panel_idle_send()

    def _cancel_panel_idle_timer(self) -> None:
        if self._panel_sn_after_id:
            try:
                self.root.after_cancel(self._panel_sn_after_id)
            except Exception:
                pass
            self._panel_sn_after_id = None

    def _schedule_panel_idle_send(self) -> None:
        self._cancel_panel_idle_timer()
        try:
            snapshot = self.txt_entry_panel_dsn.get() or ""
        except Exception:
            snapshot = ""

        try:
            self._panel_sn_after_id = self.root.after(
                int(self._panel_sn_debounce_ms),
                lambda s=snapshot: self._panel_sn_idle_fire(s),
            )
        except Exception:
            self._panel_sn_after_id = None

    def _panel_sn_idle_fire(self, snapshot: str) -> None:
        self._panel_sn_after_id = None

        try:
            current = self.txt_entry_panel_dsn.get() or ""
        except Exception:
            current = ""

        if current != snapshot:
            return

        self._trigger_send_panel_sn(panel_sn=current, reason="idle")

    def _trigger_send_panel_sn(self, *, panel_sn: str, reason: str) -> None:
        panel_sn = re.sub(r"[\r\n]+", "", panel_sn or "").strip()
        if not panel_sn:
            return

        try:
            mo = (self.txt_entry_mo.get() or "").strip()
        except Exception:
            mo = ""
            self.txt_entry_panel_dsn.set("")
            return self._update_logs_panel("WO/MO trống, không thể gửi lệnh bypass.", "red")
        if not mo:
            self.txt_entry_panel_dsn.set("")
            return self._update_logs_panel("WO/MO trống, không thể gửi lệnh bypass.", "red")

        laser_id = (self.txt_entry_laser_id.get() or "").strip()
        if laser_id:
            cmd = f"{mo},{panel_sn},{laser_id},PASSED=1"
        else:
            cmd = f"{mo},{panel_sn},PASSED=1"

        # Avoid accidental duplicate (e.g., Enter + idle firing close together)
        now = time.time()
        if cmd == self._panel_sn_last_sent_cmd and (now - float(self._panel_sn_last_sent_ts)) < 0.8:
            return
        self._panel_sn_last_sent_cmd = cmd
        self._panel_sn_last_sent_ts = now

        try:
            self._update_logs_panel(f"Trigger send ({reason}): {cmd}", "yellow")
        except Exception:
            pass

        # # Clear PanelSN for next scan and focus back
        # try:
        #     self.txt_entry_panel_dsn.clear()
        # except Exception:
        #     try:
        #         self.txt_entry_panel_dsn.set("")
        #     except Exception:
        #         pass

        try:
            self.root.after(0, lambda: self.txt_entry_panel_dsn.focus_set())
        except Exception:
            pass

        if not self.listenport:
            self._update_logs_panel("ListenPort chưa sẵn sàng (chưa mở COM).", "red")
            return

        self.send_to_com(cmd)
