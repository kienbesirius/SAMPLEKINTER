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
from src.gui.widgets.rect_panel import bind_center_rect_panel, CenterRectStyle
from src.gui.fixture.fill_multiple_monitor import fullscreen_on_monitor, get_monitors, monitor_from_point
from src.gui.fixture.get_fixture_port import get_fixture_port, parse_fixture_port_text
from src.gui.fixture.get_serial_list import get_serial_ports
from src.gui.fixture.listen_port import ListenPort
from src.utils.config_go import load_fixture_cfg, choose_slot_font, reset_slot_status_section_to_idle, update_ini_slot_status, load_slot_status_from_ini, SlotStatus, _ALLOWED_STATUS,update_ini_fixture_section, update_ini_manual_slot_info
from src.gui.widgets.dialog import ModalOverlay
import tkinter.font as tkfont


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
                _, _, sw, sh = monitor_rect(monitor)
                
                canvas = tk.Canvas(win, bg=self.background_color, highlightthickness=0)
                canvas.pack(fill=tk.BOTH, expand=True)

                # sw, sh = win.winfo_width(), win.winfo_height()
                win._widgets = self._build_gui(win=win, canvas=canvas, sw=sw, sh=sh)
                win.protocol("WM_DELETE_WINDOW", lambda w=win: self._guarded_close(w))

                # Nuốt Alt+F4 cho đúng target là cửa sổ này
                win.bind("<Alt-KeyPress-F4>", lambda e, w=win: (self._guarded_close(w), "break"))
                win.bind("<Alt-F4>",          lambda e, w=win: (self._guarded_close(w), "break"))

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

        self.listenport = None
        self.current_com_response = ""

        # Task management (no use)
        self._task_handler = None
        self._running = False

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

        # TODO: Create UI for testing fixture

        self.widgets_main = self._build_gui(win=self.root,
            canvas=self._canvas,
            sw=self.screen_width,
            sh=self.screen_height,)

        # Apply fullscreen on current monitor
        fullscreen_on_monitor(self.root, self.current_window)

        self.create_extra_windows()

        self._resolve_COM()

        self._refresh_gui()

        self.install_close_lock(10)
        # self.root.after(3000, self.send_to_com("?"))
        ### Example usage of slot status update
        # self.update_slot_status(slot_id=1, status="testing")
        # self.update_slot_status(slot_id=6, status="testing")
        # self.update_slot_status(slot_id=7, status="pass")
        # self.update_slot_status(slot_id=12, status="fail")
        # # reset slot status after 5s
        # self.root.after(5000, self.reset_slot_status)
    
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
                command=lambda idx=i, w=win: self.show_manual_config_command(win=w, slot_idx=idx),
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

        # # Bind button
        # send_test_cmd_btn = bind_canvas_button(
        #     root=win,
        #     canvas=canvas,
        #     assets=self.assets,
        #     normal_status="fixture_button_confirm_normal",
        #     hover_status="fixture_button_confirm_hover",
        #     active_status="fixture_button_confirm_pressed",
        #     disabled_status="fixture_button_confirm_disabled",
        #     tag="send_test_cmd_button",
        #     x=x+400, y=y,
        #     text="",
        #     command=lambda w=win: self.show_reset_confirm(w),
        # )
        # widgets["send_test_cmd_button"] = send_test_cmd_btn
        #### BUTTON CHECK OKAY!!!
        


        avoid = ["com_status", "logs_panel"] + [f"slot{i}_status" for i in range(1, 13)]

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

        # Dialog must be always last to create 
        modal = ModalOverlay(win)
        widgets["modal"] = modal



        return widgets
    

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
            self.reset_slot_status()   # gọi task reset của bạn

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

        # 3) nếu không có COM thì update status rồi return
        if result == "COMX":
            for w in self._iter_windows():
                ws = self._get_widgets(w)
                com1 = ws.get("com1")
                if com1:
                    com1.set_status("not_found")
                    com1.set_disabled(True)
            return

        # 4) start ListenPort 1 lần
        try:
            dispatch = lambda fn: self.root.after(0, fn)
            self.listenport = ListenPort(
                port=result,                 # dùng result, đừng dùng self.port mơ hồ
                baudrate=self.baudrate,
                log=self.emit_msg,
                on_rx=lambda s: self._update_logs_panel(f"RX: {s}", "white"),
                dispatch=dispatch,
            )
            self.listenport.start()
            status = "listening"
        except Exception as e:
            self._update_logs_panel(f"Error starting ListenPort: {e}", "red")
            status = "error"

        # 5) apply status cho tất cả window
        for w in self._iter_windows():
            ws = self._get_widgets(w)
            com1 = ws.get("com1")
            if com1:
                com1.set_status(status)
                com1.set_disabled(True)

    def send_to_com(self, cmd: str):
        def _do():
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
            self._update_logs_panel(f"TX: {cmd} | RX lines: {len(lines)}", "blue")
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


    def reset_slot_status(self):
        def _do():
            reset_slot_status_section_to_idle(self.cfg_path)
            return True

        def _ok(_result, _meta):
            # sau reset thì reload UI (enqueue tiếp cũng OK, vì taskq serial)
            self.reload_slot_status()

        self.taskq.submit(
            func=_do,
            kwargs={},
            name="Reset Slots",
            on_start=self._task_start_cb,
            on_success=_ok,
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

        self.taskq.submit(
            func=_do,
            kwargs={},
            name="Reload Slots",
            on_start=self._task_start_cb,
            on_success=_ok,
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

        self.taskq.submit(
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

    # Close all windows
    def _close_all_windows(self, source_win: tk.Misc | None = None):
        if self._is_close_locked():
            self._emit_guard(f"[guard] Close bị chặn. Còn ~{self._remaining_lock():.1f}s")
            return
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

    def _emit_guard(self, msg: str):
        try:
            self._update_logs_panel(msg, "yellow")
        except Exception:
            print(msg)

    def install_close_lock(self, seconds: float = 10.0):
        self._close_lock_until = time.monotonic() + float(seconds)

        # lock cả root
        self.root.protocol("WM_DELETE_WINDOW", lambda: self._guarded_close(self.root))
        self.root.bind_all("<Alt-KeyPress-F4>", lambda e: (self._guarded_close(self._focused_window()), "break"), add="+")
        self.root.bind_all("<Alt-F4>",         lambda e: (self._guarded_close(self._focused_window()), "break"), add="+")

        # mở khóa sau 10s
        self.root.after(int(seconds * 1000), self._unlock_close_lock)

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
