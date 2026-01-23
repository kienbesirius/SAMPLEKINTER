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
        self.root.title("GUI Tkinter")
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

        # Build GUI - Bind Events - Pump Logs
        self._init_ui()
        self._binding_events()
        self._pump_log_buffer()
    
    def _init_ui(self):
        # TODO: Initialize UI components here
        x_axis = W//2
        y_axis = H//2
        y_item_offset = 60
        try:
            
            # self.button_sample = self._bind_button(
            #     tag="btn_example",
            #     x_axis=x_axis + + self.assets["button_normal"].width()//2,
            #     y_axis=y_item_offset,
            #     text="Enable Entry",
            #     command=lambda: self.entry_1.configure(state="normal"),
            # )

            self.button_sample = bind_canvas_button(
                root=self.root,
                canvas=self._canvas,
                assets=self.assets,
                tag="btn_example",
                x=x_axis + self.assets["button_normal"].width()//2,
                y=y_item_offset,
                normal_status="button_normal",
                hover_status="button_hover",
                active_status="button_active",
                disabled_status="button_disabled",  # nếu có; không có thì dùng chung button_disabled
                text="START",
                text_font=self.tektur_font,
                command=lambda: self.entry_1.configure(state="normal"),
                cooldown_ms=500,
            )

            self.button_sample2 = bind_canvas_button(
                root=self.root,
                canvas=self._canvas,
                assets=self.assets,
                tag="btn_example2",
                x=x_axis - self.assets["button_normal"].width()//2,
                y=y_item_offset,
                normal_status="button_normal",
                hover_status="button_hover",
                active_status="button_active",
                disabled_status="button_disabled",  # nếu có; không có thì dùng chung button_disabled
                text="CANCEL",
                text_font=self.tektur_font,
                command=lambda: self.entry_1.configure(state="disabled"),
                cooldown_ms=500,
            )

            self.emit_msg("Init UI...")

            # # self.button_sample.configure(state="normal")

            # self.entry_1 = self._bind_entry(
            #     x=x_axis,
            #     y=y_item_offset + 90,
            #     normal="entry_wide_1_normal",
            #     focus="entry_wide_1_focused",
            #     disabled_status="entry_wide_1_disabled",
            #     on_submit=lambda v: self.emit_msg(f"{v} was entered: Entry submitted! {self.entry_1.get()}"),
            #     placeholder="Nhập N…",
            #     field_label="Nhập...",
            # )

            self.entry_1 = bind_canvas_entry(
                root=self.root,
                canvas=self._canvas,
                assets=self.assets,
                x=x_axis,
                y=y_item_offset + 90,
                name="username",
                field_label="Username",
                placeholder="Nhập username...",
                font=self.tektur_font,
                on_submit=lambda s: self.emit_msg(f"submit username: {s}"),
                state="normal",
            )

            self.entry_1.configure(state="disabled")

            # self.result_var, self.result_text, self.result_bg, self.result_win = self._bind_text_area(
            #     x=x_axis,
            #     y=y_item_offset +130,
            #     bg_key="279_result_field",
            #     name="result",
            #     readonly=True,
            #     use_var_sync=False,   # pump logs => dùng append cho mượt
            #     max_lines=500,
            # )

            self.result_var = bind_canvas_text_area(
                root=self.root,
                canvas=self._canvas,
                assets=self.assets,
                x=x_axis,
                y=y_item_offset +130,
                bg_key="279_result_field",
                name="logs",
                anchor="n",
                readonly=True,
                auto_scroll=True,
                max_lines=500,
            )

            # append log:
            self.result_var.append("~/ hello")   # nhanh

            # hoặc set toàn bộ (nếu bạn muốn):
            # self.result_var.set(big_text)  (chỉ có tác dụng nếu use_var_sync=True)

        except Exception as e:
            self.emit_msg(f"Error initializing UI: {e}")
            raise

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
            self.root.after(100, self._pump_log_buffer)

    def _binding_events(self):
        # TODO: Bind events here
        try:
            self.emit_msg("Binding events...")
        except Exception as e:
            pass

    # def _bind_button(
    #     self,
    #     tag: str,
    #     x_axis: int,
    #     y_axis: int,
    #     *,
    #     anchor="center",
    #     normal_status="button_normal",
    #     hover_status="button_hover",
    #     active_status="button_active",
    #     disabled_status="button_disabled",
    #     text: str = "",
    #     text_font=None,
    #     text_fill="black",
    #     cooldown_ms: int = 500,
    #     command=None,
    # ):
    #     # init states nếu chưa có
    #     self._btn_pressed.setdefault(tag, False)
    #     self._btn_disabled.setdefault(tag, False)

    #     if not hasattr(self, "_btn_last_click_ms"):
    #         self._btn_last_click_ms = {}
    #     self._btn_last_click_ms.setdefault(tag, 0)

    #     def now_ms() -> int:
    #         return int(time.time() * 1000)

    #     def is_disabled():
    #         return bool(self._btn_disabled.get(tag, False))

    #     def set_img(key: str):
    #         self._canvas.itemconfig(img_id, image=self.assets[key])

    #     def set_cursor(cursor: str):
    #         try:
    #             self.root.configure(cursor=cursor)
    #         except Exception:
    #             pass

    #     def update_visual_idle():
    #         if is_disabled():
    #             set_img(disabled_status)
    #             set_cursor("")
    #             self._canvas.itemconfig(text_id, fill="white")
    #         else:
    #             set_img(normal_status)
    #             set_cursor("")
    #             self._canvas.itemconfig(text_id, fill="black")

    #     def on_enter(_event):
    #         if is_disabled():
    #             update_visual_idle()
    #             return "break"
    #         set_cursor("hand2")
    #         if not self._btn_pressed[tag]:
    #             set_img(hover_status)
    #             self._canvas.itemconfig(text_id, fill="black")

    #     def on_leave(_event):
    #         # ra khỏi vùng nút -> reset
    #         self._btn_pressed[tag] = False
    #         update_visual_idle()

    #     def on_press(_event):
    #         if is_disabled():
    #             update_visual_idle()
    #             return "break"
    #         self._btn_pressed[tag] = True
    #         set_img(active_status)
    #         self._canvas.itemconfig(text_id, fill="white")


    #     def on_release(_event):
    #         if is_disabled():
    #             self._btn_pressed[tag] = False
    #             update_visual_idle()
    #             return "break"

    #         was_pressed = self._btn_pressed.get(tag, False)
    #         self._btn_pressed[tag] = False

    #         current = self._canvas.find_withtag("current")
    #         inside = bool(current and (img_id in current or text_id in current))

    #         if was_pressed and inside:
    #             t = now_ms()
    #             last = self._btn_last_click_ms.get(tag, 0)
    #             if t - last < cooldown_ms:
    #                 # vẫn giữ hover/normal tuỳ bạn, nhưng không gọi command
    #                 set_img(hover_status)
    #                 self._canvas.itemconfig(text_id, fill="black")
    #                 return "break"
                
    #             self._btn_last_click_ms[tag] = t
    #             set_img(hover_status)
    #             self._canvas.itemconfig(text_id, fill="black")
    #             if callable(command):
    #                 command()
    #         else:
    #             set_img(normal_status)

    #     # 1) background image
    #     img_id = self._canvas.create_image(
    #         x_axis, y_axis,
    #         image=self.assets[normal_status],
    #         anchor=anchor,
    #         tags=(tag, f"{tag}__img"),
    #     )

    #     # 2) centered label (text)
    #     text_id = self._canvas.create_text(
    #         x_axis, y_axis,
    #         text=text,
    #         font=(text_font or self.tektur_font),
    #         fill=text_fill,
    #         anchor="center",
    #         tags=(tag, f"{tag}__text"),
    #     )

    #     # Bind theo tag chung => cả image + text đều clickable/hover
    #     self._canvas.tag_bind(tag, "<Enter>", on_enter)
    #     self._canvas.tag_bind(tag, "<Leave>", on_leave)
    #     self._canvas.tag_bind(tag, "<ButtonPress-1>", on_press)
    #     self._canvas.tag_bind(tag, "<ButtonRelease-1>", on_release)

    #     # đảm bảo trạng thái ban đầu đúng
    #     update_visual_idle()

    #     gui = self
    #     class CanvasButton:
    #         def configure(self, **kw):
    #             nonlocal command
    #             if "state" in kw:
    #                 st = kw["state"]
    #                 gui._btn_disabled[tag] = (st in ("disabled", tk.DISABLED, False) and st != "normal")
    #                 gui._btn_pressed[tag] = False
    #                 update_visual_idle()
    #             if "text" in kw:
    #                 gui._canvas.itemconfig(text_id, text=kw["text"])
    #             if "command" in kw:
    #                 command = kw["command"]

    #         def set_disabled(self, disabled: bool = True):
    #             gui._btn_disabled[tag] = disabled
    #             gui._btn_pressed[tag] = False
    #             update_visual_idle()

    #         @property
    #         def ids(self):
    #             return img_id, text_id

    #     return CanvasButton()

    # def _bind_entry(
    #     self,
    #     *,
    #     x: int,
    #     y: int,
    #     normal: str = "entry_normal",
    #     focus: str = "entry_focused",
    #     name: str = "",
    #     width_pad: int = 20,
    #     height_pad: int = 44,
    #     font=None,
    #     entry_kwargs=None,

    #     # placeholder + field label
    #     placeholder: str = "",
    #     placeholder_fill: str = "#9aa0a6",
    #     placeholder_font=None,
    #     field_label: str = "",
    #     field_label_fill: str = "black",
    #     field_label_font=None,

    #     # offsets
    #     ph_dx: int = 3,
    #     ph_dy: int = 0,
    #     lbl_dx: int = 27,
    #     lbl_dy: int = 12,

    #     # NEW: disabled image key (nếu không có thì fallback normal)
    #     disabled_status: Optional[str] = "entry_disabled",

    #     # submit callback
    #     on_submit: Optional[Callable[[str], None]] = None,

    #     # initial state
    #     state: str = "normal",  # "normal" | "disabled"
    # ):
    #     if len(field_label) <= 7:
    #         normal = "entry_normal"
    #         focus = "entry_focused"
    #         disabled_status = "entry_disabled"
    #     elif len(field_label) <= 12:
    #         normal = "entry_wide_1_normal"
    #         focus = "entry_wide_1_focused"
    #         disabled_status = "entry_wide_1_disabled"
        
    #     # elif len(field_label) <=:
    #     if entry_kwargs is None:
    #         entry_kwargs = {}

    #     img_w = self.assets[normal].width()
    #     img_h = self.assets[normal].height()
    #     entry_w = img_w - width_pad
    #     entry_h = img_h - height_pad

    #     entry_var = tk.StringVar()
    #     entry = tk.Entry(
    #         self.root,
    #         textvariable=entry_var,
    #         font=(font or self.tektur_font),
    #         bd=0,
    #         relief="flat",
    #         highlightthickness=0,
    #         background="white",
    #         **entry_kwargs,
    #     )

    #     # BG image
    #     bg_id = self._canvas.create_image(
    #         x, y,
    #         anchor="center",
    #         image=self.assets[normal],
    #         tags=(f"entry_bg_{name}",) if name else ("entry_bg",),
    #     )

    #     # Entry window
    #     entry_win_id = self._canvas.create_window(
    #         x, y,
    #         width=entry_w,
    #         height=entry_h,
    #         window=entry,
    #         anchor="center",
    #         tags=(f"entry_win_{name}",) if name else ("entry_win",),
    #     )

    #     # Field label in notch
    #     label_id = 0
    #     if field_label:
    #         label_x = x - (img_w // 2) + lbl_dx
    #         label_y = y - (img_h // 2) + lbl_dy
    #         label_id = self._canvas.create_text(
    #             label_x, label_y,
    #             text=field_label,
    #             anchor="w",
    #             fill=field_label_fill,
    #             font=(field_label_font or ("Tektur", 9)),
    #             tags=(f"entry_lbl_{name}",) if name else ("entry_lbl",),
    #         )

    #     # Placeholder overlay (Label)
    #     placeholder_win_id = 0
    #     ph_label = None
    #     if placeholder:
    #         ph_label = tk.Label(
    #             self.root,
    #             text=placeholder,
    #             fg=placeholder_fill,
    #             bg="white",
    #             font=(placeholder_font or (font or self.tektur_font)),
    #             bd=0, padx=0, pady=0,
    #         )
    #         ph_label.configure(takefocus=0)

    #         ph_x = x - (entry_w // 2) + ph_dx
    #         ph_y = y + ph_dy
    #         placeholder_win_id = self._canvas.create_window(
    #             ph_x, ph_y,
    #             window=ph_label,
    #             anchor="w",
    #             tags=(f"entry_ph_{name}",) if name else ("entry_ph",),
    #         )

    #         self._canvas.tag_raise(placeholder_win_id, entry_win_id)

    #     # Local state
    #     _focused = False
    #     _disabled = False
    #     _on_submit = on_submit

    #     def is_disabled() -> bool:
    #         return _disabled

    #     def _set_bg_image():
    #         if _disabled:
    #             if disabled_status and disabled_status in self.assets:
    #                 self._canvas.itemconfig(bg_id, image=self.assets[disabled_status])
    #                 ph_label.configure(background="#D9D9D9")
    #             else:
    #                 self._canvas.itemconfig(bg_id, image=self.assets[normal])
    #                 ph_label.configure(background="white")
    #         else:
    #             self._canvas.itemconfig(bg_id, image=self.assets[focus if _focused else normal])
    #             ph_label.configure(background="white")

    #     def _update_placeholder():
    #         if not placeholder_win_id:
    #             return
    #         show = (entry_var.get() == "")
    #         self._canvas.itemconfigure(placeholder_win_id, state=("normal" if show else "hidden"))

    #     def _set_state(st: str):
    #         nonlocal _disabled
    #         _disabled = (st in ("disabled", tk.DISABLED, False) and st != "normal")
    #         entry.configure(state=("disabled" if _disabled else "normal"))
    #         _set_bg_image()
    #         _update_placeholder()

    #     # --- events ---
    #     def on_focus_in(_event):
    #         nonlocal _focused
    #         if _disabled:
    #             return "break"
    #         _focused = True
    #         _set_bg_image()

    #     def on_focus_out(_event):
    #         nonlocal _focused
    #         _focused = False
    #         _set_bg_image()

    #     def on_key_enter(_event):
    #         if _disabled:
    #             return "break"
    #         value = entry_var.get()
    #         if _on_submit is not None:
    #             _on_submit(value)
    #         else:
    #             self.emit_msg(f"Entry submitted ({name}): {value}")

    #     entry.bind("<FocusIn>", on_focus_in)
    #     entry.bind("<FocusOut>", on_focus_out)
    #     entry.bind("<Return>", on_key_enter)

    #     if ph_label is not None:
    #         def _ph_click(_e):
    #             if _disabled:
    #                 return "break"
    #             entry.focus_set()
    #             return "break"
    #         ph_label.bind("<Button-1>", _ph_click)

    #     # keep placeholder in sync with text
    #     entry_var.trace_add("write", lambda *_: _update_placeholder())
    #     _update_placeholder()

    #     # init state
    #     _set_state(state)

    #     gui = self
    #     class CanvasEntry:
    #         def configure(self, **kw):
    #             nonlocal _on_submit
    #             if "state" in kw:
    #                 _set_state(kw["state"])
    #             if "text" in kw:
    #                 entry_var.set(kw["text"])
    #             if "on_submit" in kw:
    #                 _on_submit = kw["on_submit"]
    #             if "placeholder" in kw and ph_label is not None:
    #                 ph_label.config(text=kw["placeholder"])
    #                 _update_placeholder()
    #             if "field_label" in kw and label_id:
    #                 gui._canvas.itemconfig(label_id, text=kw["field_label"])

    #         def get(self) -> str:
    #             return entry_var.get()

    #         def set(self, value: str):
    #             entry_var.set(value)

    #         def clear(self):
    #             entry_var.set("")

    #         def focus_set(self):
    #             if not _disabled:
    #                 entry.focus_set()

    #         def set_disabled(self, disabled: bool = True):
    #             _set_state("disabled" if disabled else "normal")

    #         @property
    #         def var(self):
    #             return entry_var

    #         @property
    #         def widget(self):
    #             return entry

    #         @property
    #         def ids(self):
    #             return (bg_id, entry_win_id, placeholder_win_id, label_id)

    #     return CanvasEntry()

    # def _bind_text_area(
    #     self,
    #     *,
    #     x: int,
    #     y: int,
    #     bg_key: str,
    #     name: str = "logs",
    #     anchor: str = "n",

    #     # padding so với bg image để ra vùng text thật
    #     pad_w: int = 43,
    #     pad_h: int = 43,

    #     # text style
    #     font=("Tektur", 9, "normal"),
    #     wrap: str = "word",
    #     bg: str = "white",

    #     # behavior
    #     readonly: bool = True,
    #     auto_scroll: bool = True,
    #     use_var_sync: bool = False,  # True = bạn muốn var.set() là sync toàn bộ Text

    #     # mousewheel
    #     wheel_units: int = 2,

    #     # optional: max lines để giới hạn log trong text widget (đỡ nặng)
    #     max_lines: int = 500,
    # ) -> Tuple[tk.StringVar, tk.Text, int, int]:
    #     """
    #     Trả về: (text_var, text_widget, bg_item_id, window_item_id)

    #     - Nếu use_var_sync=True: mỗi khi text_var thay đổi sẽ replace toàn bộ text widget.
    #     - Nếu pump logs: khuyên dùng handle.append(...) thay vì var.set() toàn bộ.
    #     """

    #     text_var = tk.StringVar()

    #     # Frame chứa Text (và scrollbar nếu muốn)
    #     frame = tk.Frame(self.root, bg=bg)

    #     text = tk.Text(
    #         frame,
    #         bg=bg,
    #         highlightthickness=0,
    #         wrap=wrap,
    #         bd=0,
    #         font=font,
    #     )
    #     text.pack(expand=True, fill="both")

    #     # (tuỳ bạn) scrollbar ẩn: tạo nhưng không pack
    #     scroll = tk.Scrollbar(frame, orient="vertical", command=text.yview)
    #     text.configure(yscrollcommand=scroll.set)

    #     def _set_text_full(s: str):
    #         text.configure(state="normal")
    #         text.delete("1.0", "end")
    #         text.insert("end", s or "")
    #         if auto_scroll:
    #             text.see("end")
    #         if readonly:
    #             text.configure(state="disabled")

    #     def _trim_to_max_lines():
    #         if max_lines <= 0:
    #             return
    #         # count lines: "end-1c" là char cuối (không tính newline implicit)
    #         line_count = int(text.index("end-1c").split(".")[0])
    #         if line_count > max_lines:
    #             # xóa phần đầu dư: từ dòng 1 đến dòng (line_count - max_lines)
    #             cut_to = line_count - max_lines
    #             text.delete("1.0", f"{cut_to}.0")

    #     def append(s: str):
    #         """Append log nhanh, không phải replace toàn bộ."""
    #         if not s:
    #             return
    #         text.configure(state="normal")
    #         # nếu text có nội dung rồi, đảm bảo xuống dòng
    #         if text.index("end-1c") != "1.0":
    #             if not text.get("end-2c", "end-1c").endswith("\n"):
    #                 text.insert("end", "\n")
    #         text.insert("end", s)
    #         _trim_to_max_lines()
    #         if auto_scroll:
    #             text.see("end")
    #         if readonly:
    #             text.configure(state="disabled")

    #     def clear():
    #         text.configure(state="normal")
    #         text.delete("1.0", "end")
    #         if readonly:
    #             text.configure(state="disabled")

    #     # optional: sync var -> text
    #     if use_var_sync:
    #         def _sync_var_to_text(*_):
    #             _set_text_full(text_var.get())
    #         text_var.trace_add("write", _sync_var_to_text)

    #     # mousewheel
    #     def _on_mousewheel(event):
    #         if getattr(event, "num", None) == 4:
    #             text.yview_scroll(-wheel_units, "units")
    #         elif getattr(event, "num", None) == 5:
    #             text.yview_scroll(wheel_units, "units")
    #         else:
    #             delta = int(-1 * (event.delta / 120))
    #             text.yview_scroll(delta, "units")
    #         return "break"

    #     text.bind("<MouseWheel>", _on_mousewheel, add="+")  # Win/mac
    #     text.bind("<Button-4>", _on_mousewheel, add="+")    # Linux up
    #     text.bind("<Button-5>", _on_mousewheel, add="+")    # Linux down

    #     # set readonly init
    #     if readonly:
    #         text.configure(state="disabled")

    #     # bg image on canvas
    #     bg_id = self._canvas.create_image(
    #         x, y,
    #         image=self.assets[bg_key],
    #         anchor=anchor,
    #         tags=(f"text_area_bg_{name}",),
    #     )

    #     # tính kích thước vùng đặt frame
    #     w = self.assets[bg_key].width() - pad_w
    #     h = self.assets[bg_key].height() - pad_h
    #     center_offset = self.assets[bg_key].height() // 2

    #     win_id = self._canvas.create_window(
    #         x,
    #         y + center_offset,
    #         width=w,
    #         height=h,
    #         window=frame,
    #         tags=(f"text_area_win_{name}",),
    #     )

    #     # (tùy chọn) trả thêm handle-like nếu bạn thích, nhưng user yêu cầu var => trả var
    #     # mình attach helper lên object để dùng tiện:
    #     text_var.append = append   # type: ignore[attr-defined]
    #     text_var.clear = clear     # type: ignore[attr-defined]
    #     text_var.widget = text     # type: ignore[attr-defined]

    #     return text_var, text, bg_id, win_id

        

