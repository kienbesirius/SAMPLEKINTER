import os
import re
import sys
import time
import threading
import tkinter as tk
from pathlib import Path
from src.platform import dpi
from src.gui.asset import load_assets # TẢI ASSETS vào GDI (fonts) | 
from src.utils import sub_thread # XỬ LÝ SUB THREAD (TASKS) | Tách biệt main tkinter GUI thread với các tác vụ nền
from src.utils.resource_path import RESOURCE_PATH, FONT_PATH, ICONS_PATH, app_dir
from src.utils.buffer_logger import build_log_buffer
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
def set_app_icon(root, emit=print):
    icon_path = load_assets.ICON_ASSET.get("app_icon", ICONS_PATH / "treasure-svgrepo-com.ico")
    if not icon_path.exists():
        icon_path = app_dir() / "treasure-svgrepo-com.ico"
    try:
        root.iconbitmap(default=str(icon_path))
    except Exception as e:
        emit(f"Không thể đặt icon ứng dụng: {e}")

def set_default_font(font: tkfont.Font):
    tkfont.nametofont("TkDefaultFont").configure(
        family=font.actual("family"),
        size=font.actual("size"),
        weight=font.actual("weight"),
        slant=font.actual("slant"),
        underline=font.actual("underline"),
        overstrike=font.actual("overstrike"),
    )

# Core-Example function to count primes in a range
def countZ_primes(n: int, cancel_event: threading.Event, progress_cb=None) -> int:
    if n <= 2: 
        return 0
    sieve = bytearray(b"\x01")*n
    sieve[0:2] = b"\x00\x00"
    p = 2
    while p * p < n:
        if cancel_event and cancel_event.is_set():
            return -1
        if sieve[p]:
            step = p
            start = p*p
            sieve[start:n:step] = b"\x00" * ((n- start - 1) // step + 1)
        p += 1
        if callable(progress_cb):
            pct = int((p * p) / n * 100)
            progress_cb({"pct": pct,})
    return int(sum(sieve))

# GUI Phase
W, H = 640, 480
class LeetCode204_Gui:
    dpi.set_dpi_awareness()
    def __init__(self, root: tk.Tk):
        self.logger, self.log_buffer = build_log_buffer(name="LeetCode204_Gui", max_buffer=500)
        self.emit_msg = self.logger.info

        self._task_handler = None # Task handler dùng làm gì? Tại sao bằng None
        self._running = False # Kiểm tra có đang chạy tác vụ nào đó không

        # Pmp log buffer -> optional for text widget
        self._log_lock = getattr(self.logger, "_samplekinter_lock", threading.RLock())

        self.root = root
        self.runner = sub_thread.SubProcessRunner(self.root, poll_ms=80)
        root.title("LeetCode204 Count Primes")
        root.geometry(f"{W}x{H}")
        root.resizable(False, False)

        self.tektur_font = tkfont.Font(family="Tektur", size=13)

        set_app_icon(root, emit=self.emit_msg)
        topmost_window(root)
        set_default_font(self.tektur_font)
        
        # Make a canvas full-screen as background
        self.canvas_full = tk.Canvas(root, width=W, height=H, highlightthickness=0)
        self.canvas_full.pack(fill="both", expand=True)

        self.assets = load_assets.tk_load_image_resources()
        
        self.build_gui()
        self.build_events()

        self._pump_logs()

    def build_gui(self):
        x_axis = W // 2
        y_axis = H // 2

        # 1) background_gui204_640x480 - stretch to full canvas
        self.canvas_full.create_image(0, 0, image=self.assets["background_gui204_640x480"], anchor="nw")

        # 2) notice_title - center the title at the top
        y_item_offset = 10
        self.canvas_full.create_image(x_axis, y_item_offset, image=self.assets["notice_title"], anchor="n")

        # Calculate next item offset
        y_item_offset += self.assets["notice_title"].height()*1.7

        entry_w = self.assets["279_entry_field_normal"].width() - 20
        entry_h = self.assets["279_entry_field_normal"].height() - 44

        self.entry_nvar = tk.StringVar()
        self.n_entry = tk.Entry(
            self.root,
            textvariable=self.entry_nvar,
            font=self.tektur_font,
            bd=0, 
            relief="flat",
            highlightthickness=0,
            background="white"
        )

        self.entry_background = self.canvas_full.create_image(
            x_axis,
            y_item_offset,
            anchor=tk.CENTER,
            image=self.assets["279_entry_field_normal"],
            tags="entry_background"
        )

        self.entry_id = self.canvas_full.create_window(
            x_axis,
            y_item_offset,
            anchor=tk.CENTER,
            window=self.n_entry,
            width=entry_w,
            height=entry_h,
            tags="entry_id"
        )


        # Calculate next item offset
        y_item_offset += self.assets["entry_field_normal"].height()//2

        # 4) start_button - center the start button
        self.start_button_id = self.canvas_full.create_image(
            x_axis + self.assets["button_start_normal"].width() // 2, y_item_offset, 
            image=self.assets["button_start_normal"], anchor="n", tag="start_button"
        )

        # 5) cancel_button - center the cancel button
        self.cancel_button_id = self.canvas_full.create_image(
            x_axis - self.assets["button_cancel_normal"].width() // 2, y_item_offset,
            image=self.assets["button_cancel_normal"], anchor="n", tag="cancel_button"
        )

        y_item_offset += self.assets["button_cancel_normal"].height() + 15

        # 6) result_field - center the result field
        self.result_var = tk.StringVar()

        self.result_frame = tk.Frame(self.root, bg="white")

        self.result_label = tk.Text(self.result_frame,bg="white",highlightthickness=0,wrap="word",bd=0,font=("Tektur", 9, "normal"))

        self._result_scroll = tk.Scrollbar(self.result_frame, orient="vertical", command=self.result_label.yview)

        # Setting the scroll event for the label
        self.result_label.configure(yscrollcommand=self._result_scroll.set, state=tk.DISABLED)
        self.result_label.pack(expand=True,fill=tk.BOTH)
        self.result_var.trace_add("write", self._sync_result_var_to_text)
        self._bind_mousewheel(self.result_label)

        result_w = self.assets["279_result_field"].width() - 40
        result_h = self.assets["279_result_field"].height() - 40
        center_result_bg_offset = (self.assets["279_result_field"].height()//2)

        self.result_background = self.canvas_full.create_image(x_axis, y_item_offset,image=self.assets["279_result_field"],anchor="n")

        self.result_window_id = self.canvas_full.create_window(
            x_axis, 
            y_item_offset + center_result_bg_offset,
            width=result_w,
            height=result_h,
            window=self.result_frame,
        )
    
    def _sync_result_var_to_text(self,  *_):
        self.set_result(self.result_var.get())

    def set_result(self, txt):
        self.result_label.config(state=tk.NORMAL)
        self.result_label.delete("1.0", "end")
        self.result_label.insert("end",txt or "")
        self.result_label.see("end")
        self.result_label.configure(state=tk.DISABLED)

    def _bind_mousewheel(self, widget):
        # Windows / macOS
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        # Linux (X11)
        widget.bind("<Button-4>", self._on_mousewheel, add="+")
        widget.bind("<Button-5>", self._on_mousewheel, add="+")

    def _on_mousewheel(self, event):
        if event.num == 4:          # Linux scroll up
            self.result_field_label.yview_scroll(-2, "units")
        elif event.num == 5:        # Linux scroll down
            self.result_field_label.yview_scroll(2, "units")
        else:                       # Windows/macOS
            delta = int(-1 * (event.delta / 120))
            self.result_field_label.yview_scroll(delta, "units")
        return "break"
    
    # Entry field event
    def _bind_entry_field(self, tk_entry: tk.Entry, entry_bg_tag, normal:str, focus:str):
        def on_focus_in(event):
            self.canvas_full.itemconfig(entry_bg_tag, image=self.assets[focus])

        def on_focus_out(event):
            self.canvas_full.itemconfig(entry_bg_tag, image=self.assets[normal])

        tk_entry.bind("<FocusIn>", on_focus_in)
        tk_entry.bind("<FocusOut>", on_focus_out)

        # On Key Enter
        def on_key_enter(event):
            # self.canvas_full.focus_set()  # Remove focus from entry field
            # Emit the entered value
            value = tk_entry.get()
            self.emit_msg(f"Entry field submitted with value: {value}")

        tk_entry.bind("<Return>", on_key_enter)

    def build_events(self):
        self._bind_entry_field(
            self.n_entry,
            "entry_background",
            "279_entry_field_normal",
            "279_entry_field_focused"
        )
        self._bind_button(
            "start_button",
            self.start_button_id,
            normal="button_start_normal",
            hover="button_start_hover",
            active="button_start_active",
            command=self.on_start_clicked
        )

        self._bind_button(
            "cancel_button",
            self.cancel_button_id,
            normal="button_cancel_normal",
            hover="button_cancel_hover",
            active="button_cancel_active",
            command=self.on_cancel_clicked
        )

    def _bind_button(self, tag:str, item_id: int, normal:str, hover:str,active:str,command=None):
        """
        Bind events cho 1 button dạng Canvas image.
        normal/hover/active là KEY trong self.assets (ảnh đã load).
        """
        self._btn_pressed = getattr(self, "_btn_pressed", {})
        self._btn_pressed[tag] = False

        def _set_img(key:str):
            self.canvas_full.itemconfig(item_id, image=self.assets[key])

        def on_enter(_e):
            self.root.configure(cursor="hand2")
            # chỉ đổi hover nếu không đang nhấn
            if not self._btn_pressed[tag]:
                _set_img(hover)

        def on_leave(_e):
            self.root.configure(cursor="")
            # nếu đang nhấn mà rời nút thì vẫn có thể giữ active hoặc về normal tuỳ bạn
            if self._btn_pressed[tag]:
                _set_img(normal)  # lựa chọn 1: rời là về normal
            else:
                _set_img(normal)
        
        def on_press(_e):
            self._btn_pressed[tag] = True
            _set_img(active)

        def on_release(_e):
            was_pressed = self._btn_pressed[tag]
            self._btn_pressed[tag] = False

            # Kiểm tra thả chuột có nằm trên chính item không
            x, y = self.canvas_full.winfo_pointerxy()
            x -= self.canvas_full.winfo_rootx()
            y -= self.canvas_full.winfo_rooty()
            current = self.canvas_full.find_withtag("current")  # item dưới chuột

            if was_pressed and current and item_id in current:
                _set_img(hover)
                if callable(command):
                    command()
            else:
                _set_img(normal)

        self.canvas_full.tag_bind(tag, "<Enter>", on_enter)
        self.canvas_full.tag_bind(tag, "<Leave>", on_leave)
        self.canvas_full.tag_bind(tag, "<ButtonPress-1>", on_press)
        self.canvas_full.tag_bind(tag, "<ButtonRelease-1>", on_release)

    def on_start_clicked(self):
        if self._running:
            return
        
        self._running = True

        try:
            n = int(self.n_entry.get().strip())
            if n < 0:
                return
            if n > 50_000_000:
                return
        except:
            return

        self._task_handler = self.runner.submit(
            func=countZ_primes,
            kwargs={"n":n},
            on_start=self._on_task_start,
            on_success=self._on_task_success,
            on_error=self._on_task_error,
            on_finally=self._on_task_finally,
            on_progress=self._on_task_progress,
        )
    def on_cancel_clicked(self):
         # self.emit_msg("Cancel button clicked.")
        if self._task_handler and self._running:
            self.emit_msg("Cancelling the running task...")
            self.runner.cancel(self._task_handler)  # set handle.cancel_event
        else:
            self.emit_msg("Không có tác vụ nào đang chạy để hủy.")


    def _on_task_start(self, meta):
        pass

    def _on_task_success(self, payload, meta):
        self.emit_msg(f"payload: {payload} meta: {meta}")
        pass

    def _on_task_error(self, payload, meta):
        pass

    def _on_task_finally(self, status, meta):
        self._running = False
        # self.emit_msg(f"Task {status}: {meta}")
        self._task_handler = None

    def _on_task_progress(self, payload):
        percentage = payload.get("pct", 0)
        self.emit_msg(percentage)

    def _pump_logs(self):
        # Safely grab any new log entries since last index and append them
        # to the result_var. The shared buffer is a List[str], so slice from
        # _log_last_idx to the end and advance by the number of entries.
        with self._log_lock:
            buf_len = len(self.log_buffer)

            new_logs = self.log_buffer[buf_len-1:]
            if new_logs:
                self.result_var.set("\n".join(new_logs))

        # Schedule next pump
        try:
            self.root.after(200, self._pump_logs)
        except Exception:
            # If root has been destroyed, ignore scheduling errors silently
            pass
