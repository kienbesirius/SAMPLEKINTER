# src/gui/widgets/guide_panel.py
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from src.gui.widgets.button import bind_canvas_button
from src.gui.widgets.paint_asset import bind_canvas_asset
from typing import Optional, Callable
from pathlib import Path


@dataclass
class GuideStep:
    title: str                      # ví dụ: "Xin thực hiện đóng fixture..."
    image_key: str                  # key ảnh trong assets (base key)
    confirm_text: str = "Bắt đầu"  # text trên button (có thể để "" nếu button asset đã có chữ)
    title_fill: Optional[str] = None   # NEW
    # bạn có thể mở rộng thêm: hint_text, auto_delay, v.v...


class GuidePanel:
    """
    A fixed-layout panel inside center_panel.body:
      [Title]
      [Big Image]
      [Confirm Button]

    Only updates content on each step (no rebuild).
    """

    def __init__(
        self,
        *,
        root: tk.Misc,
        center_panel: Any,                 # object returned by bind_center_rect_panel
        assets: Dict[str, Any],
        tag: str = "guide_panel",
        title_font: Any = ("Tektur", 16, "bold"),
        title_fill: str = "#FFE37A",
        bg: Optional[str] = None,
        img_max_ratio: float = 0.55,       # image area <= 55% height of panel body
        img_min_h: int = 120,
        btn_pad_y: int = 10,
        auto_hide_on_done: bool = True,
        on_done: Optional[Callable[[], None]] = None,
        on_confirm: Optional[Callable[[int, GuideStep], None]] = None,  
    ) -> None:
        self.root = root
        self.center_panel = center_panel
        self.assets = assets
        self.tag = tag

        self.img_max_ratio = float(img_max_ratio)
        self.img_min_h = int(img_min_h)
        self.btn_pad_y = int(btn_pad_y)
        self.auto_hide_on_done = bool(auto_hide_on_done)
        self.on_done = on_done

        # panel background color
        if bg is None:
            # try to reuse style.fill if exists
            bg = getattr(getattr(center_panel, "style", None), "fill", None) or "#471800"
        self.bg = bg

        # --- state ---
        self.steps: List[GuideStep] = []
        self.idx: int = 0

        # --- build fixed layout once ---
        self.frame = tk.Frame(self.center_panel.body, bg=self.bg)
        self.frame.pack(fill="both", expand=True)

        # Title
        self.title_var = tk.StringVar(value="")
        self.lb_title = tk.Label(
            self.frame,
            textvariable=self.title_var,
            font=title_font,
            fg=title_fill,
            bg=self.bg,
            justify="center",
            wraplength=10,   # will update on resize
        )
        self._title_fill_default = title_fill

        self.lb_title.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        # Image canvas (use bind_canvas_asset here)
        self.cv_img = tk.Canvas(self.frame, bg=self.bg, highlightthickness=0, bd=0)
        self.cv_img.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 6))

        # Placeholder when missing image
        self._img_placeholder_id = self.cv_img.create_text(
            0, 0,
            text="(no image)",
            fill="#FFFFFF",
            font=("Tektur", 12, "bold"),
            anchor="center",
        )

        self._img_widget = None  # created lazily when we have a valid key

        # Button canvas
        self.cv_btn = tk.Canvas(self.frame, bg=self.bg, highlightthickness=0, bd=0, height=92)
        self.cv_btn.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 10))

        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(1, weight=1)

        # pick button skins safely
        def _pick_btn_key(*keys: str, fallback: str) -> str:
            for k in keys:
                if k and k in self.assets:
                    return k
            return fallback if fallback in self.assets else (keys[0] if keys else fallback)

        self.on_confirm = on_confirm  

        self._btn = bind_canvas_button(
            root=self.frame,
            canvas=self.cv_btn,
            assets=self.assets,
            tag=f"{self.tag}__confirm",
            x=10, y=10,  # will layout later
            normal_status=_pick_btn_key("fixture_button_no_label_normal", "button_normal", fallback="button_normal"),
            hover_status=_pick_btn_key("fixture_button_no_label_hover", "button_hover", fallback="button_hover"),
            active_status=_pick_btn_key(
                "fixture_button_no_label_pressed", "fixture_button_no_label_active", "button_active",
                fallback="button_active",
            ),
            disabled_status=_pick_btn_key("fixture_button_no_label_disabled", "button_disabled", fallback="button_disabled"),
            text="BẮT ĐẦU",  # will set per-step
            text_fill="white",
            text_font=("Tektur", 13, "bold"),
            command=self._on_confirm_click,
            cooldown_ms=500,
        )

        # resize bindings
        self.frame.bind("<Configure>", self._on_resize, add="+")
        self.cv_img.bind("<Configure>", self._on_img_resize, add="+")
        self.cv_btn.bind("<Configure>", self._on_btn_resize, add="+")

        try:
            self.frame.configure(takefocus=1)
            self.lb_title.configure(takefocus=0)   # label không cần focus
            self.cv_img.configure(takefocus=1)
            self.cv_btn.configure(takefocus=1)
        except Exception:
            pass
        # --- enter to confirm ---
        self._visible = True
        self._enter_enabled = True
        # self.root.bind("<Return>", self._on_key_enter, add="+")
        # self.root.bind("<KP_Enter>", self._on_key_enter, add="+")

        # bind vào toplevel thật sự (đúng window đang chứa guide)
        self._top = self.frame.winfo_toplevel()

        # lưu bind id để unbind được (tránh kẹt callback sau khi hide/destroy)
        self._bindid_return = self._top.bind("<Return>", self._on_key_enter, add="+")
        self._bindid_kp = self._top.bind("<KP_Enter>", self._on_key_enter, add="+")

    def _unbind_enter(self):
        try:
            if getattr(self, "_bindid_return", None):
                self._top.unbind("<Return>", self._bindid_return)
                self._bindid_return = None
            if getattr(self, "_bindid_kp", None):
                self._top.unbind("<KP_Enter>", self._bindid_kp)
                self._bindid_kp = None
        except Exception:
            pass
    # def _on_key_enter(self, event=None):
    #     # chỉ xử lý khi guide đang hiện
    #     if not getattr(self, "_visible", True) or not getattr(self, "_enter_enabled", True):
    #         return None
    #     if not self.steps:
    #         return None

    #     # nếu đang focus vào entry/text thì để nó tự xử lý Enter (không hijack)
    #     w = None
    #     try:
    #         w = self.root.focus_get()
    #     except Exception:
    #         w = None

    #     if w is not None:
    #         try:
    #             cls = w.winfo_class()
    #         except Exception:
    #             cls = ""
    #         if cls in ("Entry", "TEntry", "Text", "TCombobox", "Spinbox", "TSpinbox"):
    #             return None

    #     # nếu button đang disabled (busy) thì bỏ qua
    #     if getattr(self._btn, "_disabled", False):
    #         return "break"

    #     # trigger giống click
    #     self._on_confirm_click()
    #     return "break"

    def _is_descendant(self, w: tk.Misc, ancestor: tk.Misc) -> bool:
        """True nếu w nằm bên trong ancestor (đi ngược master chain)."""
        try:
            while w is not None:
                if w == ancestor:
                    return True
                w = w.master
        except Exception:
            pass
        return False

    def _on_key_enter(self, event=None):
        if not getattr(self, "_visible", True) or not getattr(self, "_enter_enabled", True):
            return None
        if not self.steps:
            return None

        # focus widget: dùng event.widget (đúng cửa sổ đang nhận key)
        w = None
        try:
            if event is not None and getattr(event, "widget", None) is not None:
                w = event.widget.focus_get()
            else:
                w = self.frame.focus_get()
        except Exception:
            w = None

        # ✅ chỉ xử lý Enter nếu focus đang nằm trong GuidePanel
        if w is None or not self._is_descendant(w, self.frame):
            return None

        # nếu đang focus vào entry/text trong guide thì không hijack
        try:
            cls = w.winfo_class()
        except Exception:
            cls = ""
        if cls in ("Entry", "TEntry", "Text", "TCombobox", "Spinbox", "TSpinbox"):
            return None

        if getattr(self._btn, "_disabled", False):
            return "break"

        self._on_confirm_click()
        return "break"
    # ----------------------------
    # Public APIs
    # ----------------------------
    def set_steps(self, steps: Sequence[GuideStep], *, start_index: int = 0) -> None:
        self.steps = list(steps)
        self.idx = max(0, min(int(start_index), max(0, len(self.steps) - 1)))
        self._apply_step()

    def start(self) -> None:
        self.show()
        self._apply_step()

    def focus_default(self):
        # focus vào canvas button để Enter luôn thuộc GuidePanel
        try:
            self.cv_btn.focus_set()
            return
        except Exception:
            pass
        try:
            self.frame.focus_set()
        except Exception:
            pass
        
    def _bind_enter(self):
        try:
            self._top = self.frame.winfo_toplevel()
            if not getattr(self, "_bindid_return", None):
                self._bindid_return = self._top.bind("<Return>", self._on_key_enter, add="+")
            if not getattr(self, "_bindid_kp", None):
                self._bindid_kp = self._top.bind("<KP_Enter>", self._on_key_enter, add="+")
        except Exception:
            pass
        
    def show(self) -> None:
        self._visible = True
        self._bind_enter()
        if hasattr(self.center_panel, "show"):
            try:
                self.center_panel.show()
            except Exception:
                pass
        self.frame.lift()
        self.focus_default()

    # def hide(self) -> None:
    #     self._visible = False
    #     if hasattr(self.center_panel, "hide"):
    #         try:
    #             self.center_panel.hide()
    #         except Exception:
    #             pass

    def hide(self) -> None:
        self._visible = False
        self._unbind_enter()
        if hasattr(self.center_panel, "hide"):
            try:
                self.center_panel.hide()
            except Exception:
                pass

    def goto(self, index: int) -> None:
        if not self.steps:
            return
        self.idx = max(0, min(int(index), len(self.steps) - 1))
        self._apply_step()

    def next(self) -> None:
        if not self.steps:
            return
        if self.idx >= len(self.steps) - 1:
            # DONE
            if callable(self.on_done):
                try:
                    self.on_done()
                except Exception:
                    pass
            if self.auto_hide_on_done:
                self.hide()
            return

        self.idx += 1
        self._apply_step()

    def _on_confirm_click(self) -> None:
        """Confirm clicked: delegate to controller if provided, else fallback next()."""
        if callable(self.on_confirm) and self.steps:
            try:
                self.on_confirm(self.idx, self.steps[self.idx])
                return
            except Exception:
                pass
        self.next()

    # --- helper APIs for controller ---
    def set_busy(self, busy: bool, *, text: Optional[str] = None) -> None:
        try:
            self._btn.set_disabled(busy)
        except Exception:
            pass
        if text is not None:
            self._btn_set_text(text)

    def set_content(
        self,
        *,
        title: Optional[str] = None,
        image_key: Optional[str] = None,
        confirm_text: Optional[str] = None,
        title_fill: Optional[str] = None,
    ) -> None:
        if title is not None:
            self.title_var.set(title)
        if confirm_text is not None:
            self._btn_set_text(confirm_text)
        if image_key is not None:
            self._update_image(image_key)
        if title_fill is not None:
            try:
                fill = self._title_fill_default if title_fill in ("", "default") else title_fill
                self.lb_title.configure(fg=fill)
            except Exception:
                pass
    # ----------------------------
    # Internals
    # ----------------------------
    def _pick_existing_asset_key(self, base_key: str, canvas_w: int) -> str:
        """
        assets naming convention:
          base_key, base_key_0.75, base_key_0.5

        IMPORTANT: bind_canvas_asset internally might fallback to base_key,
        so we ensure the chosen key truly exists (prefer scaled key).
        """
        if not base_key:
            return ""

        # prefer by current width (same logic style as your _pick_scaled_key)
        if canvas_w <= 800:
            k = f"{base_key}_0.5"
            if k in self.assets:
                return k
        if canvas_w <= 1200:
            k = f"{base_key}_0.75"
            if k in self.assets:
                return k

        # fallback
        if base_key in self.assets:
            return base_key
        if f"{base_key}_0.75" in self.assets:
            return f"{base_key}_0.75"
        if f"{base_key}_0.5" in self.assets:
            return f"{base_key}_0.5"
        return ""

    def _btn_move_to_center(self) -> None:
        # move button by directly moving its canvas items (safe even if btn has no move_to)
        try:
            w = int(self.cv_btn.winfo_width())
            h = int(self.cv_btn.winfo_height())
        except Exception:
            return
        cx, cy = w // 2, h // 2
        try:
            # most of your widgets expose img_id + text_id
            self.cv_btn.coords(self._btn.img_id, cx, cy)
            self.cv_btn.coords(self._btn.text_id, cx, cy)
        except Exception:
            pass

    def _btn_set_text(self, s: str) -> None:
        # try widget configure first
        try:
            self._btn.configure(text=s)
            return
        except Exception:
            pass
        # fallback: direct canvas
        try:
            self.cv_btn.itemconfig(self._btn.text_id, text=s)
        except Exception:
            pass

    def _apply_step(self) -> None:
        if not self.steps:
            self.title_var.set("")
            self._btn_set_text("")
            self._show_missing_image("(no steps)")
            return

        st = self.steps[self.idx]
        self.title_var.set(st.title or "Xin thực hiện ...")
        self._btn_set_text(st.confirm_text)

        try:
            fill = st.title_fill if st.title_fill is not None else self._title_fill_default
            self.lb_title.configure(fg=fill)
        except Exception:
            pass
        # ensure layout sizes already updated
        self._on_resize()

        # update image
        self._update_image(st.image_key)

        # move button center (after text update too)
        self.root.after(0, self._btn_move_to_center)

    def _show_missing_image(self, msg: str) -> None:
        try:
            w = int(self.cv_img.winfo_width())
            h = int(self.cv_img.winfo_height())
        except Exception:
            w, h = 0, 0

        self.cv_img.coords(self._img_placeholder_id, max(1, w // 2), max(1, h // 2))
        self.cv_img.itemconfig(self._img_placeholder_id, text=msg, state="normal")

        if self._img_widget is not None:
            try:
                self._img_widget.set_visible(False)
            except Exception:
                pass

    def get_img_widget_wh(self, *, fallback=(480, 270), fill_if_missing=True) -> tuple[int, int]:
        """
        Return (w, h) size thật của vùng hiển thị ảnh.
        - Ưu tiên cv_img (Canvas)
        - Nếu chưa layout xong -> dùng reqwidth/reqheight
        - Nếu cv_img None và fill_if_missing -> fill placeholder màu bg
        """
        wdg = getattr(self, "cv_img", None) or getattr(self, "_img_widget", None)

        w = h = 0
        if wdg is not None:
            try:
                wdg.update_idletasks()
            except Exception:
                pass

            # size thật sau layout
            try:
                w = int(wdg.winfo_width())
                h = int(wdg.winfo_height())
            except Exception:
                w = h = 0

            # nếu gọi sớm quá -> winfo_* thường = 1, lấy size "request"
            if w <= 1 or h <= 1:
                try:
                    w = int(wdg.winfo_reqwidth())
                    h = int(wdg.winfo_reqheight())
                except Exception:
                    pass

            # fallback cuối: cget
            if w <= 1 or h <= 1:
                try:
                    w = int(wdg.cget("width"))
                    h = int(wdg.cget("height"))
                except Exception:
                    pass

        if w <= 1 or h <= 1:
            w, h = fallback

        # nếu cv_img None -> fill tạm bg
        if getattr(self, "cv_img", None) is None and fill_if_missing:
            bg = getattr(self, "bg", "#471800")
            try:
                # nếu _img_widget là Label
                if isinstance(wdg, tk.Label):
                    self._img_placeholder = tk.PhotoImage(master=wdg, width=w, height=h)
                    self._img_placeholder.put(bg, to=(0, 0, w, h))
                    wdg.configure(image=self._img_placeholder, bg=bg)
                    wdg.image = self._img_placeholder
                # nếu _img_widget là Canvas
                elif isinstance(wdg, tk.Canvas):
                    wdg.configure(bg=bg)
                    wdg.delete("all")
                    wdg.create_rectangle(0, 0, w, h, fill=bg, outline="")
            except Exception:
                pass

        return int(w), int(h)
    
    def _update_image(self, base_key: str) -> None:
        try:
            w = int(self.cv_img.winfo_width())
            h = int(self.cv_img.winfo_height())
        except Exception:
            w, h = 0, 0

        key = self._pick_existing_asset_key(base_key, w)
        if not key:
            self._show_missing_image(f"(missing asset: {base_key})")
            return

        # hide placeholder
        self.cv_img.itemconfig(self._img_placeholder_id, state="hidden")

        cx, cy = max(1, w // 2), max(1, h // 2)

        if self._img_widget is None:
            # create lazily (must pass an existing key!)
            self._img_widget = bind_canvas_asset(
                root=self.frame,
                canvas=self.cv_img,
                assets=self.assets,
                tag=f"{self.tag}__img",
                x=cx, y=cy,
                anchor="center",
                right_key=key,  # can be any image key, not only arrow
                state="normal",
            )
        else:
            try:
                self._img_widget.configure(x=cx, y=cy, key=key, state="normal")
                self._img_widget.set_visible(True)
            except Exception:
                pass

    def _on_resize(self, _ev: Any = None) -> None:
        # wrap title nicely
        try:
            w = int(self.frame.winfo_width())
            h = int(self.frame.winfo_height())
        except Exception:
            return

        self.lb_title.configure(wraplength=max(10, w - 24))

        # limit image area height
        # compute desired img height cap by ratio
        img_h = max(self.img_min_h, int(h * self.img_max_ratio))
        # keep button area visible
        # (button canvas already has its own height)
        try:
            self.cv_img.configure(height=img_h)
        except Exception:
            pass

        # also center placeholder text
        self._on_img_resize()
        self._on_btn_resize()

    def _on_img_resize(self, _ev: Any = None) -> None:
        # keep placeholder centered, and image centered
        try:
            w = int(self.cv_img.winfo_width())
            h = int(self.cv_img.winfo_height())
        except Exception:
            return

        cx, cy = max(1, w // 2), max(1, h // 2)
        try:
            self.cv_img.coords(self._img_placeholder_id, cx, cy)
        except Exception:
            pass

        if self._img_widget is not None and self.steps:
            # re-pick scaled key when canvas width changes
            base = self.steps[self.idx].image_key
            key = self._pick_existing_asset_key(base, w)
            if key:
                try:
                    self._img_widget.configure(x=cx, y=cy, key=key)
                except Exception:
                    pass

    def _on_btn_resize(self, _ev: Any = None) -> None:
        self._btn_move_to_center()
