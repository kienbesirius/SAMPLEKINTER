import os
import re
import sys
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
def countZ_primes(n: int) -> int:
    if n <= 2: 
        return 0
    sieve = bytearray(b"\x01")*n
    sieve[0:2] = b"\x00\x00"
    p = 2
    while p * p < n:
        if sieve[p]:
            step = p
            start = p*p
            sieve[start:n:step] = b"\x00" * ((n- start - 1) // step + 1)
        p += 1
    return int(sum(sieve))

# GUI Phase
W, H = 640, 480
class LeetCode204_Gui:
    dpi.set_dpi_awareness()
    def __init__(self, root: tk.Tk):
        self.logger, self.log_buffer = build_log_buffer(name="LeetCode204_Gui", level=20, max_buffer=500)
        self.emit_msg = self.logger.info

        self.root = root
        root.title("LeetCode204 Count Primes")
        root.geometry(f"{W}x{H}")
        root.resizable(False, False)

        self.tektur_font = tkfont.Font(family="Tektur", size=13)

        set_app_icon(root, emit=self.emit_msg)
        topmost_window(root)
        set_default_font(self.tektur_font)
        
        # In ra các font có chữ "Tektur"
        tektur = sorted([f for f in tkfont.families(root) if "Tektur" in f])
        self.emit_msg("Tektur families: " + ", ".join(tektur))
        self.emit_msg(f"Có 'Tektur' không? " + str(bool("Tektur" in tkfont.families(root))))

        # Make a canvas full-screen as background
        self.canvas_full = tk.Canvas(root, width=W, height=H, highlightthickness=0)
        self.canvas_full.pack(fill="both", expand=True)

        self.assets = load_assets.tk_load_image_resources()
        
        self.build_gui()
        self.build_events()

    def build_gui(self):
        x_axis = W // 2
        y_axis = H // 2

        # 1) background_gui204_640x480 - stretch to full canvas
        self.canvas_full.create_image(0, 0, image=self.assets["background_gui204_640x480"], anchor="nw")

        # 2) notice_title - center the title at the top
        y_item_offset = 10
        self.canvas_full.create_image(x_axis, y_item_offset, image=self.assets["notice_title"], anchor="n")

        # Calculate next item offset
        y_item_offset += self.assets["notice_title"].height()*2

        entry_w = self.assets["entry_field_normal"].width() - 23
        entry_h = self.assets["entry_field_normal"].height() - 23

        self.build_entry_block(
            x=x_axis, y=y_item_offset,
            img_normal_key="entry_field_normal",
            img_focus_key="entry_field_focused",
            img_disabled_key="entry_field_disabled",
            width=entry_w, height=entry_h
        )

        # Calculate next item offset
        y_item_offset += self.assets["entry_field_normal"].height()

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
        self.result_field_id = self.canvas_full.create_image(
            x_axis, y_item_offset,
            image=self.assets["result_field"], anchor="n"
        )

        self.result_var = tk.StringVar()
        self.result_label = tk.Label(
            self.root, 
            textvariable=self.result_var,
            font=("Tektur", 13),
            bg="#FFFFFF",
        )

        result_w = self.assets["result_field"].width() - 40
        result_h = self.assets["result_field"].height() - 40
        center_result_bg_offset = (self.assets["result_field"].height()//2)
        self.result_window_id = self.canvas_full.create_window(
            x_axis, 
            y_item_offset + center_result_bg_offset,
            width=result_w,
            height=result_h,
            window=self.result_label,
        )

    def build_events(self):

        self._bind_button(
            "start_button",
            self.start_button_id,
            normal="button_start_normal",
            hover="button_start_hover",
            active="button_start_active",
            command=None
        )

        self._bind_button(
            "cancel_button",
            self.cancel_button_id,
            normal="button_cancel_normal",
            hover="button_cancel_hover",
            active="button_cancel_active",
            command=None
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


    # Build tạm thời một block entry cố định (không tái sử dụng được thành nhiều entry)
    def build_entry_block(self, x: int, y: int,
                      img_normal_key: str,
                      img_focus_key: str,
                      img_disabled_key: str,
                      width: int = 420,
                      height: int = 26):
        # lưu keys để đổi ảnh
        self._entry_img = {
            "normal": img_normal_key,
            "focus": img_focus_key,
            "disabled": img_disabled_key,
        }
        self._entry_disabled = False

        # 1) vẽ ảnh nền entry trên canvas
        self.entry_bg_id = self.canvas_full.create_image(
            x, y, anchor="center", image=self.assets[img_normal_key], tags=("entry_bg",)
        )

        # 2) tạo Entry thật
        self.var_n = tk.StringVar()
        self.ent_n = tk.Entry(
            self.root,
            textvariable=self.var_n,
            bd=0,
            relief="flat",
            highlightthickness=0,
        )

        # 3) đặt Entry lên canvas (window item)
        self.ent_win_id = self.canvas_full.create_window(
            x, y, anchor="center", width=width, height=height, window=self.ent_n, tags=("entry_win",)
        )

        # 4) bind focus in/out
        self.ent_n.bind("<FocusIn>", self._entry_on_focus_in)
        self.ent_n.bind("<FocusOut>", self._entry_on_focus_out)

        # (tuỳ chọn) click vào ảnh nền cũng focus entry
        self.canvas_full.tag_bind("entry_bg", "<Button-1>", lambda e: self.focus_entry())

    def _set_entry_bg(self, state: str):
        # nếu disabled thì luôn ưu tiên disabled
        if self._entry_disabled:
            self.canvas_full.itemconfig(self.entry_bg_id, image=self.assets[self._entry_img["disabled"]])
            return

        if state == "focus":
            self.canvas_full.itemconfig(self.entry_bg_id, image=self.assets[self._entry_img["focus"]])
        else:
            self.canvas_full.itemconfig(self.entry_bg_id, image=self.assets[self._entry_img["normal"]])

    def _entry_on_focus_in(self, _e):
        self._set_entry_bg("focus")

    def _entry_on_focus_out(self, _e):
        self._set_entry_bg("normal")

    def focus_entry(self):
        if not self._entry_disabled:
            self.ent_n.focus_set()

    def disable_entry(self):
        self._entry_disabled = True
        self.ent_n.config(state="disabled")
        self._set_entry_bg("disabled")

    def enable_entry(self):
        self._entry_disabled = False
        self.ent_n.config(state="normal")
        # nếu đang focus thì hiện focus, không thì normal
        if self.ent_n == self.root.focus_get():
            self._set_entry_bg("focus")
        else:
            self._set_entry_bg("normal")

