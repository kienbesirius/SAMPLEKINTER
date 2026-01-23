import os
import re
import sys
import time
import threading
import tkinter as tk
from pathlib import Path
from src.platform import dpi
from src.gui.asset import load_assets
from src.utils import sub_thread
from src.utils.resource_path import RESOURCE_PATH, FONT_PATH, ICONS_PATH, app_dir
from src.utils.buffer_logger import build_log_buffer
import tkinter.font as tkfont
import math
from collections import deque

def topmost_window(root):
    try:
        root.attributes("-topmost", True)
    except Exception:
        try: 
            root.wm_attributes("-topmost", 1)
        except Exception:
            pass

def set_app_icon(root, emit=print):
    try:
        icon_path = load_assets.ICON_ASSET.get("app_icon", ICONS_PATH / "treasure-svgrepo-com.ico")
        if not icon_path.exists():
            icon_path = ICONS_PATH / "treasure-svgrepo-com.ico"
        root.iconbitmap(default=str(icon_path))
        emit(f"Set application icon: {icon_path}")
    except Exception as e:
        emit(f"Failed to set application icon: {e}")

def set_default_font(font:tkfont.Font):
    tkfont.nametofont("TkDefaultFont").configure(
        family=font.actual("family"),
        size=font.actual("size"),
        weight=font.actual("weight"),
        slant=font.actual("slant"),
    )

# Core-example: LeetCode279_Gui Perfect Squares
def count_perfect_squares(n: int, cancel_event: threading.Event = None, progress_cb=None) -> int:
    if n <= 0:
        return 0

    squares = [i*i for i in range(1, int(math.isqrt(n)) + 1)]
    dp = [0] + [10**9] * n

    for i in range(1, n + 1):
        if cancel_event is not None and getattr(cancel_event, "is_set", False) and cancel_event.is_set():
            return -1  # bạn có thể chọn raise Exception("cancelled") cũng được

        best = 10**9
        for s in squares:
            if s > i:
                break
            cand = dp[i - s] + 1
            if cand < best:
                best = cand
        dp[i] = best

        if progress_cb and (i % 200 == 0 or i == n):
            pct = int((i / n) * 100)
            progress_cb({"percentage": pct, "index": i})

    return dp[n]

W, H = 640, 480
class LeetCode279_Gui:
    dpi.set_dpi_awareness()

    def __init__(self, root: tk.Tk):
        self.UI_MAX_LINES = 200
        self.LOG_MAX = 500
        self.logger, self.log_buffer = build_log_buffer(name= "LeetCode279",max_buffer=self.LOG_MAX)
        self.emit_msg = self.logger.info 

        self._task_handler = None
        self._running = False

        # build_log_buffer attaches a lock as `_laserlink_lock` on the logger
        # use that lock to safely read the shared list buffer.
        # cursor theo index trong list buffer
        self._log_last_idx = 0
        # UI chỉ giữ 200 dòng gần nhất
        self._ui_lines = deque(maxlen=self.UI_MAX_LINES)

        self._log_lock = getattr(self.logger, "_laserlink_lock", threading.RLock())

        self.root = root

        self.runner = sub_thread.SubProcessRunner(self.root)

        self.root.title("LeetCode 279 - Perfect Squares")
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)
        self.tektur_font = tkfont.Font(family="Tektur", size=11)
        set_default_font(self.tektur_font)
        set_app_icon(self.root, emit=self.emit_msg)
        topmost_window(self.root)

        self.screen_canvas = tk.Canvas(self.root, width=W, height=H, highlightthickness=0, bg="white")
        self.screen_canvas.pack(fill="both", expand=True)
        self.assets = load_assets.tk_load_image_resources()

        self.build_gui()
        self.build_event()
        self._pump_logs()


    def build_gui(self):
        x_axis = W//2
        y_axis = H//2

        # 1 draw canvass
        self.screen_canvas.create_image(0, 0, anchor="nw", image=self.assets["background_gui279_640x480"])  

        y_item_offset = 10
        # 2 draw title
        self.screen_canvas.create_image(x_axis, y_item_offset, anchor="n", image=self.assets["279_notice_title"])

        y_item_offset += self.assets["279_notice_title"].height()*1.7
        # 3 calculate entry field size base on resource image
        entry_w = self.assets["279_entry_field_normal"].width() - 20
        entry_h = self.assets["279_entry_field_normal"].height() - 44 

        # 4 draw entry field
        self.entry_n_var = tk.StringVar()
        self.entry_n = tk.Entry(
            self.root,
            textvariable=self.entry_n_var,
            font=self.tektur_font,
            bd=0,
            relief="flat",
            highlightthickness=0,
            background="white",
        )

        self.entry_bg = self.screen_canvas.create_image(
            x_axis,
            y_item_offset,
            anchor="center",
            image=self.assets["279_entry_field_normal"],
            tags="entry_bg",
        )   

        # set entry tk centered on the entry_bg

        self.entry_id = self.screen_canvas.create_window(
            x_axis,
            y_item_offset,
            width=entry_w,
            height=entry_h,
            window=self.entry_n,
            anchor="center",
            tags="entry_id",
            
        )

        # 5 draw start button
        y_item_offset += self.assets["279_entry_field_normal"].height()//2

        self.start_button = self.screen_canvas.create_image(
            x_axis + self.assets["button_start_normal"].width()//2, y_item_offset,
            image=self.assets["button_start_normal"], tags="start_button", anchor="n"
        )

        self.cancel_button = self.screen_canvas.create_image(
            x_axis - self.assets["button_cancel_normal"].width()//2, y_item_offset,
            image=self.assets["button_cancel_normal"], tags="cancel_button", anchor="n"
        )

        # Build Scroll Text Result area
        self.result_field_var = tk.StringVar()
        self.result_field_frame = tk.Frame(
            self.root,
            bg="white",
        )
        self.result_field_label = tk.Text(
            self.result_field_frame,
            bg="white",
            highlightthickness=0,
            wrap="word",
            bd=0,
            font=("Tektur",9,"normal"),
        )
        # self.result_field_label.pack(padx=5, pady=5)

        self._result_field_scroll = tk.Scrollbar(
            self.result_field_frame,
            orient="vertical",
            command=self.result_field_label.yview)
        
        self.result_field_label.configure(yscrollcommand=self._result_field_scroll.set)
        self.result_field_label.pack(expand=True, fill="both")
        self.result_field_label.configure(state="disabled")
        self.result_field_var.trace_add("write", self._sync_result_var_to_text)
        self._bind_mousewheel(self.result_field_label)

        # Calculate the result field position
        y_item_offset += self.assets["button_start_normal"].height() + 20
        result_field_w = self.assets["279_result_field"].width() - 43
        result_field_h = self.assets["279_result_field"].height() - 43
        center_result_field_offset = self.assets["279_result_field"].height()//2

        self.result_field_bg = self.screen_canvas.create_image(
            x_axis, y_item_offset,
            image=self.assets["279_result_field"], anchor="n"
        )

        # Place the result field frame on the canvas
        self.result_field_window = self.screen_canvas.create_window(
            x_axis,
            y_item_offset + center_result_field_offset,
            width=result_field_w,
            height=result_field_h,
            window=self.result_field_frame
        )

    def _sync_result_var_to_text(self, *_):
        self.set_result(self.result_field_var.get())

    def set_result(self, text: str):
        self.result_field_label.configure(state="normal")
        self.result_field_label.delete("1.0", "end")
        self.result_field_label.insert("end", text or "")
        self.result_field_label.see("end")
        self.result_field_label.configure(state="disabled")

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
            self.screen_canvas.itemconfig(entry_bg_tag, image=self.assets[focus])

        def on_focus_out(event):
            self.screen_canvas.itemconfig(entry_bg_tag, image=self.assets[normal])

        tk_entry.bind("<FocusIn>", on_focus_in)
        tk_entry.bind("<FocusOut>", on_focus_out)

        # On Key Enter
        def on_key_enter(event):
            # self.screen_canvas.focus_set()  # Remove focus from entry field
            # Emit the entered value
            value = tk_entry.get()
            self.emit_msg(f"Entry field submitted with value: {value}")

        tk_entry.bind("<Return>", on_key_enter)

    # Buttons event
    def _bind_button(self, tag:str, item_id: int, normal:str, hover:str, active:str, command=None):

        self._btn_pressed = getattr(self, "_btn_pressed", {})
        self._btn_pressed[tag] = False

        def _set_img(key:str):
            self.screen_canvas.itemconfig(item_id, image=self.assets[key])

        def on_enter(event):
            self.root.configure(cursor="hand2")
            _set_img(hover)

        def on_leave(event):
            self.root.configure(cursor="")
            if self._btn_pressed[tag]:
                _set_img(normal)  # lựa chọn 1: rời là về normal
            else:
                _set_img(normal)  # lựa chọn 2: rời là về normal

        def on_press(event):
            self._btn_pressed[tag] = True
            _set_img(active)

        def on_release(event):
            was_pressed = self._btn_pressed.get(tag, False)
            self._btn_pressed[tag] = False

            # # Kiểm tra thả chuột có nằm trên chính item không
            # x, y = self.screen_canvas.winfo_pointerxy()
            # x -= self.screen_canvas.winfo_rootx()
            # y -= self.screen_canvas.winfo_rooty()

            current = self.screen_canvas.find_withtag("current")

            if was_pressed and current and item_id in current:
                _set_img(hover)
                if callable(command):
                    command()
            else:
                _set_img(normal)

            # Unfocused entry field when clicking button
            # self.root.focus_set()

        self.screen_canvas.tag_bind(tag, "<Enter>", on_enter)
        self.screen_canvas.tag_bind(tag, "<Leave>", on_leave)
        self.screen_canvas.tag_bind(tag, "<ButtonPress-1>", on_press)
        self.screen_canvas.tag_bind(tag, "<ButtonRelease-1>", on_release)


    def build_event(self):
        self._bind_entry_field(
            self.entry_n,
            "entry_bg",
            "279_entry_field_normal",
            "279_entry_field_focused"
        )
        self._bind_button(
            "start_button",
            self.start_button,
            "button_start_normal",
            "button_start_hover",
            "button_start_active",
            command=self.on_start_clicked
        )
        self._bind_button(
            "cancel_button",
            self.cancel_button,
            "button_cancel_normal",
            "button_cancel_hover",
            "button_cancel_active",
            command=self.on_cancel_clicked
        )

    def on_start_clicked(self):
        # self.emit_msg("Start button clicked.")
        if self._running:
            self.emit_msg("A task is already running. Please wait or cancel it first.")
            return
        
        try:
            n = int(self.entry_n_var.get().strip())
            if n < 1:
                self.emit_msg("Please enter a positive integer greater than 0.")
                return  
            
            if n > 990000:
                self.emit_msg("Please enter a smaller integer (<= 20000) to avoid long computation time.")
                return
        except:
            self.emit_msg("Invalid input. Please enter a valid positive integer.")
            return

        self._running = True
        # self.disable_entry()
        self.emit_msg(f"Starting computation for n={n}...")

        # Explain how task_handler works heres.
        self._task_handler = self.runner.submit(
            func=count_perfect_squares,
            kwargs={"n": n},
            name="PerfectSquaresTask",
            on_start=self._task_start_cb,
            on_success=lambda result, meta: self._task_success_cb(n, result, meta),
            on_error=self._task_error_cb,
            on_finally=self._task_finally_cb,
            on_progress=self._task_progress_cb,
        )

    def _task_start_cb(self, meta):
        # self.emit_msg(f"Task started: {meta}")
        pass

    def _task_success_cb(self, n, result, meta):
        # self.emit_msg(f"Task succeededed: {meta}")
        self.emit_msg(f"Number of perfect squares <= {n}: {result}")

    def _task_error_cb(self, exception, meta):
        # self.emit_msg(f"Task failed: {meta}")
        self.emit_msg(f"Error details exception: {exception}")

    # Căn cứ theo runner hiện tại được định nghĩa trong utils/sub_thread.py
    def _task_finally_cb(self, status:str, meta:dict):
        self._running = False
        # self.emit_msg(f"Task {status}: {meta}")
        self._task_handler = None
        if status == "cancelled":
            self.emit_msg("Computation was cancelled by the user.")
        # elif status == "ok":
        #     self.emit_msg("Computation completed successfully.")
        # else:
        #     # self.emit_msg("Computation ended with errors.")
        #     self.emit_msg(f"Error details meta: {meta}")

    # task progress callback: called in the main thread
    def _task_progress_cb(self, payload):
        pct = payload.get("percentage", 0)
        index = payload.get("index", 0)
        self.emit_msg(f"Progress: {pct}%")

    def on_cancel_clicked(self):
        # self.emit_msg("Cancel button clicked.")
        if self._task_handler and self._running:
            self.emit_msg("Cancelling the running task...")
            self.runner.cancel(self._task_handler)  # set handle.cancel_event
        else:
            self.emit_msg("Không có tác vụ nào đang chạy để hủy.")

    def _pump_logs(self):
        updated = False

        with self._log_lock:
            buf_len = len(self.log_buffer)

            new_logs = self.log_buffer[buf_len-1:]
            if new_logs:
                self.result_field_var.set("\n".join(new_logs))
        try:
            self.root.after(200, self._pump_logs)
        except Exception:
            pass
