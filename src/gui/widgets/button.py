# src/gui/widgets/button.py
from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple


Command = Optional[Callable[[], None]]


@dataclass
class ButtonSkins:
    normal: str = "button_normal"
    hover: str = "button_hover"
    active: str = "button_active"
    disabled: str = "button_disabled"


class CanvasButton:
    """
    A 'button' composed of:
      - Canvas image item (background)
      - Canvas text item (label)

    Handles:
      - hover / press / release
      - disabled state
      - cooldown click
      - click only if release happens inside

    Usage:
        from src.gui.widgets.button import bind_canvas_button

        # ...
        self.btn_start = bind_canvas_button(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            tag="start_button",
            x=x_axis,
            y=y_item_offset,
            normal_status="button_start_normal",
            hover_status="button_start_hover",
            active_status="button_start_active",
            disabled_status="button_start_disabled",  # nếu có; không có thì dùng chung button_disabled
            text="START",
            text_font=self.tektur_font,
            command=self.on_start_clicked,
            cooldown_ms=500,
        )

        self.btn_start.configure(state="disabled")     # hoặc:
        self.btn_start.set_disabled(True)

        # đổi text/command lúc runtime:
        self.btn_start.configure(text="RUN", command=self.on_start_clicked)
    """

    def __init__(
        self,
        *,
        root: tk.Misc,
        canvas: tk.Canvas,
        assets: Dict[str, Any],
        tag: str,
        x: int,
        y: int,
        anchor: str = "center",
        skins: ButtonSkins = ButtonSkins(),
        text: str = "",
        text_font: Optional[Any] = None,
        text_fill: str = "black",
        text_fill_disabled: str = "white",
        cooldown_ms: int = 500,
        command: Command = None,
        cursor: str = "hand2",
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.assets = assets
        self.tag = tag
        self.anchor = anchor

        self.skins = skins
        self.text_fill = text_fill
        self.text_fill_disabled = text_fill_disabled
        self.cooldown_ms = int(cooldown_ms)
        self.command = command
        self.cursor = cursor

        self._pressed = False
        self._disabled = False
        self._last_click_ms = 0
        self._prev_cursor: Optional[str] = None

        # Build items
        self.img_id = self.canvas.create_image(
            x, y,
            image=self.assets[self.skins.normal],
            anchor=self.anchor,
            tags=(self.tag, f"{self.tag}__img"),
        )
        self.text_id = self.canvas.create_text(
            x, y,
            text=text,
            font=text_font,
            fill=text_fill,
            anchor="center",
            tags=(self.tag, f"{self.tag}__text"),
        )

        # Bind events on common tag
        self.canvas.tag_bind(self.tag, "<Enter>", self._on_enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self._on_leave)
        self.canvas.tag_bind(self.tag, "<ButtonPress-1>", self._on_press)
        self.canvas.tag_bind(self.tag, "<ButtonRelease-1>", self._on_release)

        self._update_visual_idle()

    # ---------------------------
    # Public API (similar to tk widgets)
    # ---------------------------
    def configure(self, **kw):
        if "state" in kw:
            self._set_state(kw["state"])
        if "text" in kw:
            self.canvas.itemconfig(self.text_id, text=kw["text"])
        if "command" in kw:
            self.command = kw["command"]
        if "cooldown_ms" in kw:
            self.cooldown_ms = int(kw["cooldown_ms"])
        if "cursor" in kw:
            self.cursor = kw["cursor"]

        # allow update skins dynamically if needed
        if "skins" in kw and isinstance(kw["skins"], ButtonSkins):
            self.skins = kw["skins"]
            self._update_visual_idle()

    def set_disabled(self, disabled: bool = True):
        self._set_state("disabled" if disabled else "normal")

    def destroy(self):
        # unbind tag events
        try:
            self.canvas.tag_unbind(self.tag, "<Enter>")
            self.canvas.tag_unbind(self.tag, "<Leave>")
            self.canvas.tag_unbind(self.tag, "<ButtonPress-1>")
            self.canvas.tag_unbind(self.tag, "<ButtonRelease-1>")
        except Exception:
            pass

        # delete items
        try:
            self.canvas.delete(self.img_id)
        except Exception:
            pass
        try:
            self.canvas.delete(self.text_id)
        except Exception:
            pass

    @property
    def ids(self) -> Tuple[int, int]:
        return (self.img_id, self.text_id)

    # ---------------------------
    # Internals
    # ---------------------------
    def _now_ms(self) -> int:
        # monotonic -> safe against system clock changes
        return int(time.monotonic() * 1000)

    def _is_disabled(self) -> bool:
        return bool(self._disabled)

    def _set_img(self, key: str):
        self.canvas.itemconfig(self.img_id, image=self.assets[key])

    def _set_cursor(self, cur: str):
        try:
            self.root.configure(cursor=cur)
        except Exception:
            pass

    def _update_visual_idle(self):
        if self._is_disabled():
            self._set_img(self.skins.disabled)
            self._set_cursor("")
            self.canvas.itemconfig(self.text_id, fill=self.text_fill_disabled)
        else:
            self._set_img(self.skins.normal)
            self._set_cursor("")
            self.canvas.itemconfig(self.text_id, fill=self.text_fill)

    def _set_state(self, st):
        disabled = (st in ("disabled", tk.DISABLED, False) and st != "normal")
        self._disabled = bool(disabled)
        self._pressed = False
        self._update_visual_idle()

    def _hit_test_inside(self) -> bool:
        """
        Return True if pointer is currently over ANY item that has this button tag.
        Safer than checking only ids, because canvas 'current' can be multiple items.
        """
        current = self.canvas.find_withtag("current")
        if not current:
            return False
        for item in current:
            try:
                tags = self.canvas.gettags(item)
                if self.tag in tags:
                    return True
            except Exception:
                continue
        return False

    # ---------------------------
    # Event handlers
    # ---------------------------
    def _on_enter(self, _event):
        if self._is_disabled():
            self._update_visual_idle()
            return "break"

        # store current cursor to restore later
        try:
            self._prev_cursor = str(self.root.cget("cursor"))
        except Exception:
            self._prev_cursor = None

        self._set_cursor(self.cursor)

        if not self._pressed:
            self._set_img(self.skins.hover)
            self.canvas.itemconfig(self.text_id, fill=self.text_fill)

    def _on_leave(self, _event):
        self._pressed = False

        # restore previous cursor if possible
        if self._prev_cursor is not None:
            self._set_cursor(self._prev_cursor)
        else:
            self._set_cursor("")

        self._update_visual_idle()

    def _on_press(self, _event):
        if self._is_disabled():
            self._update_visual_idle()
            return "break"

        self._pressed = True
        self._set_img(self.skins.active)
        self.canvas.itemconfig(self.text_id, fill=self.text_fill_disabled)

    def _on_release(self, _event):
        if self._is_disabled():
            self._pressed = False
            self._update_visual_idle()
            return "break"

        was_pressed = bool(self._pressed)
        self._pressed = False

        inside = self._hit_test_inside()
        if was_pressed and inside:
            t = self._now_ms()
            if t - self._last_click_ms < self.cooldown_ms:
                # ignore click but keep hover visual
                self._set_img(self.skins.hover)
                self.canvas.itemconfig(self.text_id, fill=self.text_fill)
                return "break"

            self._last_click_ms = t
            self._set_img(self.skins.hover)
            self.canvas.itemconfig(self.text_id, fill=self.text_fill)
            if callable(self.command):
                self.command()
            return "break"

        # released outside
        self._set_img(self.skins.normal)
        self.canvas.itemconfig(self.text_id, fill=self.text_fill)
        return "break"


def bind_canvas_button(
    *,
    root: tk.Misc,
    canvas: tk.Canvas,
    assets: Dict[str, Any],
    tag: str,
    x: int,
    y: int,
    anchor: str = "center",
    normal_status: str = "button_normal",
    hover_status: str = "button_hover",
    active_status: str = "button_active",
    disabled_status: str = "button_disabled",
    text: str = "",
    text_font: Optional[Any] = None,
    text_fill: str = "black",
    text_fill_disabled: str = "white",
    cooldown_ms: int = 500,
    command: Command = None,
) -> CanvasButton:
    """
    A 'button' composed of:
      - Canvas image item (background)
      - Canvas text item (label)

    Handles:
      - hover / press / release
      - disabled state
      - cooldown click
      - click only if release happens inside

    Usage:
        from src.gui.widgets.button import bind_canvas_button

        # ...
        self.btn_start = bind_canvas_button(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            tag="start_button",
            x=x_axis,
            y=y_item_offset,
            normal_status="button_start_normal",
            hover_status="button_start_hover",
            active_status="button_start_active",
            disabled_status="button_start_disabled",  # nếu có; không có thì dùng chung button_disabled
            text="START",
            text_font=self.tektur_font,
            command=self.on_start_clicked,
            cooldown_ms=500,
        )

        self.btn_start.configure(state="disabled")     # hoặc:
        self.btn_start.set_disabled(True)

        # đổi text/command lúc runtime:
        self.btn_start.configure(text="RUN", command=self.on_start_clicked)
    """
    skins = ButtonSkins(
        normal=normal_status,
        hover=hover_status,
        active=active_status,
        disabled=disabled_status,
    )
    return CanvasButton(
        root=root,
        canvas=canvas,
        assets=assets,
        tag=tag,
        x=x,
        y=y,
        anchor=anchor,
        skins=skins,
        text=text,
        text_font=text_font,
        text_fill=text_fill,
        text_fill_disabled=text_fill_disabled,
        cooldown_ms=cooldown_ms,
        command=command,
    )
