# src/gui/widgets/entry.py
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple


OnSubmit = Optional[Callable[[str], None]]


@dataclass
class EntrySkins:
    normal: str = "entry_normal"
    focus: str = "entry_focused"
    disabled: Optional[str] = "entry_disabled"


class CanvasEntry:
    """
    Canvas-based Entry:
      - background image on canvas
      - embedded tk.Entry via create_window
      - optional field label (canvas text)
      - optional placeholder (tk.Label via create_window)

    Usage:
        from src.gui.widgets.entry import bind_canvas_entry

        self.user_entry = bind_canvas_entry(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            x=320,
            y=220,
            name="username",
            field_label="Username",
            placeholder="Nhập username...",
            font=self.tektur_font,
            on_submit=lambda s: self.emit_msg(f"submit username: {s}"),
            state="normal",
        )

        self.user_entry.configure(state="disabled")
        self.user_entry.configure(text="abc")
        val = self.user_entry.get()

    """


    def __init__(
        self,
        *,
        root: tk.Misc,
        canvas: tk.Canvas,
        assets: Dict[str, Any],
        x: int,
        y: int,
        name: str = "",
        skins: EntrySkins = EntrySkins(),
        width_pad: int = 20,
        height_pad: int = 44,
        font: Optional[Any] = None,
        entry_kwargs: Optional[dict] = None,
        placeholder: str = "",
        placeholder_fill: str = "#9aa0a6",
        placeholder_font: Optional[Any] = None,
        field_label: str = "",
        field_label_fill: str = "black",
        field_label_font: Optional[Any] = None,
        ph_dx: int = 3,
        ph_dy: int = 0,
        lbl_dx: int = 27,
        lbl_dy: int = 12,
        on_submit: OnSubmit = None,
        state: str = "normal",  # "normal" | "disabled"
        background_normal: str = "white",
        background_disabled: str = "#D9D9D9",
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.assets = assets
        self.x = x
        self.y = y
        self.name = name

        self.skins = skins
        self.width_pad = int(width_pad)
        self.height_pad = int(height_pad)
        self.on_submit = on_submit

        self.background_normal = background_normal
        self.background_disabled = background_disabled

        if entry_kwargs is None:
            entry_kwargs = {}

        # ---- size from normal skin ----
        img_w = self.assets[self.skins.normal].width()
        img_h = self.assets[self.skins.normal].height()
        self.entry_w = img_w - self.width_pad
        self.entry_h = img_h - self.height_pad

        # ---- tk.Entry ----
        self.var = tk.StringVar()
        self.entry = tk.Entry(
            self.root,
            textvariable=self.var,
            font=font,
            bd=0,
            relief="flat",
            highlightthickness=0,
            background=self.background_normal,
            **entry_kwargs,
        )

        # ---- background image on canvas ----
        self.bg_id = self.canvas.create_image(
            x, y,
            anchor="center",
            image=self.assets[self.skins.normal],
            tags=(f"entry_bg_{name}",) if name else ("entry_bg",),
        )

        # ---- entry window on canvas ----
        self.entry_win_id = self.canvas.create_window(
            x, y,
            width=self.entry_w,
            height=self.entry_h,
            window=self.entry,
            anchor="center",
            tags=(f"entry_win_{name}",) if name else ("entry_win",),
        )

        # ---- field label ----
        self.label_id = 0
        if field_label:
            label_x = x - (img_w // 2) + int(lbl_dx)
            label_y = y - (img_h // 2) + int(lbl_dy)
            self.label_id = self.canvas.create_text(
                label_x, label_y,
                text=field_label,
                anchor="w",
                fill=field_label_fill,
                font=field_label_font,
                tags=(f"entry_lbl_{name}",) if name else ("entry_lbl",),
            )

        # ---- placeholder label overlay ----
        self.placeholder = placeholder
        self.placeholder_win_id = 0
        self.ph_label: Optional[tk.Label] = None
        if placeholder:
            self.ph_label = tk.Label(
                self.root,
                text=placeholder,
                fg=placeholder_fill,
                bg=self.background_normal,
                font=placeholder_font or font,
                bd=0,
                padx=0,
                pady=0,
            )
            # don't allow tab focus to land on placeholder
            try:
                self.ph_label.configure(takefocus=0)
            except Exception:
                pass

            ph_x = x - (self.entry_w // 2) + int(ph_dx)
            ph_y = y + int(ph_dy)
            self.placeholder_win_id = self.canvas.create_window(
                ph_x, ph_y,
                window=self.ph_label,
                anchor="w",
                tags=(f"entry_ph_{name}",) if name else ("entry_ph",),
            )
            # ensure placeholder above entry window
            self.canvas.tag_raise(self.placeholder_win_id, self.entry_win_id)

        # ---- local state ----
        self._focused = False
        self._disabled = False

        # ---- bind events ----
        self.entry.bind("<FocusIn>", self._on_focus_in)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self.entry.bind("<Return>", self._on_key_enter)

        if self.ph_label is not None:
            self.ph_label.bind("<Button-1>", self._on_placeholder_click)

        self.var.trace_add("write", lambda *_: self._update_placeholder())

        # init state + placeholder
        self._set_state(state)
        self._update_placeholder()

    # ---------------------------
    # Public API (tk-like)
    # ---------------------------
    def configure(self, **kw):
        if "state" in kw:
            self._set_state(kw["state"])
        if "text" in kw:
            self.var.set(kw["text"])
        if "on_submit" in kw:
            self.on_submit = kw["on_submit"]

        if "placeholder" in kw and self.ph_label is not None:
            self.placeholder = str(kw["placeholder"])
            self.ph_label.config(text=self.placeholder)
            self._update_placeholder()

        if "field_label" in kw and self.label_id:
            self.canvas.itemconfig(self.label_id, text=kw["field_label"])

        if "font" in kw:
            self.entry.config(font=kw["font"])
            if self.ph_label is not None:
                self.ph_label.config(font=kw["font"])

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str):
        self.var.set(value)

    def clear(self):
        self.var.set("")

    def focus_set(self):
        if not self._disabled:
            self.entry.focus_set()

    def set_disabled(self, disabled: bool = True):
        self._set_state("disabled" if disabled else "normal")

    @property
    def widget(self) -> tk.Entry:
        return self.entry

    @property
    def ids(self) -> Tuple[int, int, int, int]:
        return (self.bg_id, self.entry_win_id, self.placeholder_win_id, self.label_id)

    def destroy(self):
        try:
            self.canvas.delete(self.bg_id)
        except Exception:
            pass
        try:
            self.canvas.delete(self.entry_win_id)
        except Exception:
            pass
        if self.placeholder_win_id:
            try:
                self.canvas.delete(self.placeholder_win_id)
            except Exception:
                pass
        if self.label_id:
            try:
                self.canvas.delete(self.label_id)
            except Exception:
                pass
        try:
            self.entry.destroy()
        except Exception:
            pass
        if self.ph_label is not None:
            try:
                self.ph_label.destroy()
            except Exception:
                pass

    # ---------------------------
    # Internals
    # ---------------------------
    def _set_bg_image(self):
        if self._disabled:
            if self.skins.disabled and self.skins.disabled in self.assets:
                self.canvas.itemconfig(self.bg_id, image=self.assets[self.skins.disabled])
                if self.ph_label is not None:
                    self.ph_label.configure(bg=self.background_disabled)
            else:
                self.canvas.itemconfig(self.bg_id, image=self.assets[self.skins.normal])
                if self.ph_label is not None:
                    self.ph_label.configure(bg=self.background_normal)
        else:
            key = self.skins.focus if self._focused else self.skins.normal
            self.canvas.itemconfig(self.bg_id, image=self.assets[key])
            if self.ph_label is not None:
                self.ph_label.configure(bg=self.background_normal)

    def _update_placeholder(self):
        if not self.placeholder_win_id:
            return
        show = (self.var.get() == "")
        self.canvas.itemconfigure(self.placeholder_win_id, state=("normal" if show else "hidden"))

    def _set_state(self, st: str):
        self._disabled = (st in ("disabled", tk.DISABLED, False) and st != "normal")
        self.entry.configure(state=("disabled" if self._disabled else "normal"))
        self._set_bg_image()
        self._update_placeholder()

    # ---------------------------
    # Event handlers
    # ---------------------------
    def _on_focus_in(self, _event):
        if self._disabled:
            return "break"
        self._focused = True
        self._set_bg_image()

    def _on_focus_out(self, _event):
        self._focused = False
        self._set_bg_image()

    def _on_key_enter(self, _event):
        if self._disabled:
            return "break"
        value = self.var.get()
        if self.on_submit is not None:
            self.on_submit(value)
        return "break"

    def _on_placeholder_click(self, _event):
        if self._disabled:
            return "break"
        self.entry.focus_set()
        return "break"


# Helper: auto choose skins by label length (giữ y chang logic của bạn)
def choose_entry_skins_by_label(field_label: str) -> EntrySkins:
    if len(field_label) <= 7:
        return EntrySkins(
            normal="entry_normal",
            focus="entry_focused",
            disabled="entry_disabled",
        )
    if len(field_label) <= 12:
        return EntrySkins(
            normal="entry_wide_1_normal",
            focus="entry_wide_1_focused",
            disabled="entry_wide_1_disabled",
        )
    if len(field_label) <= 17:
        return EntrySkins(
            normal="entry_wide_2_normal",
            focus="entry_wide_2_focused",
            disabled="entry_wide_2_disabled",
        )
    
    if len(field_label) <= 22:
        return EntrySkins(
            normal="entry_wide_3_normal",
            focus="entry_wide_3_focused",
            disabled="entry_wide_3_disabled",
        )
    
    # fallback default (bạn có thể mở rộng wide_2, wide_3...)
    return EntrySkins(
        normal="entry_wide_3_normal",
        focus="entry_wide_3_focused",
        disabled="entry_wide_3_disabled",
    )


def bind_canvas_entry(
    *,
    root: tk.Misc,
    canvas: tk.Canvas,
    assets: Dict[str, Any],
    x: int,
    y: int,
    name: str = "",
    normal: str = "entry_normal",
    focus: str = "entry_focused",
    disabled_status: Optional[str] = "entry_disabled",
    auto_skin_by_label: bool = True,
    width_pad: int = 20,
    height_pad: int = 44,
    font: Optional[Any] = None,
    entry_kwargs: Optional[dict] = None,
    placeholder: str = "",
    placeholder_fill: str = "#9aa0a6",
    placeholder_font: Optional[Any] = None,
    field_label: str = "",
    field_label_fill: str = "black",
    field_label_font: Optional[Any] = None,
    ph_dx: int = 3,
    ph_dy: int = 0,
    lbl_dx: int = 27,
    lbl_dy: int = 12,
    on_submit: OnSubmit = None,
    state: str = "normal",
) -> CanvasEntry:
    """
    Canvas-based Entry:
      - background image on canvas
      - embedded tk.Entry via create_window
      - optional field label (canvas text)
      - optional placeholder (tk.Label via create_window)

    Usage:
        from src.gui.widgets.entry import bind_canvas_entry

        self.user_entry = bind_canvas_entry(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            x=320,
            y=220,
            name="username",
            field_label="Username",
            placeholder="Nhập username...",
            font=self.tektur_font,
            on_submit=lambda s: self.emit_msg(f"submit username: {s}"),
            state="normal",
        )

        self.user_entry.configure(state="disabled")
        self.user_entry.configure(text="abc")
        val = self.user_entry.get()

    """

    if auto_skin_by_label and field_label:
        skins = choose_entry_skins_by_label(field_label)
    else:
        skins = EntrySkins(normal=normal, focus=focus, disabled=disabled_status)

    return CanvasEntry(
        root=root,
        canvas=canvas,
        assets=assets,
        x=x,
        y=y,
        name=name,
        skins=skins,
        width_pad=width_pad,
        height_pad=height_pad,
        font=font,
        entry_kwargs=entry_kwargs,
        placeholder=placeholder,
        placeholder_fill=placeholder_fill,
        placeholder_font=placeholder_font,
        field_label=field_label,
        field_label_fill=field_label_fill,
        field_label_font=field_label_font,
        ph_dx=ph_dx,
        ph_dy=ph_dy,
        lbl_dx=lbl_dx,
        lbl_dy=lbl_dy,
        on_submit=on_submit,
        state=state,
    )
