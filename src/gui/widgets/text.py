# src/gui/widgets/text.py
from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable, Optional, Tuple


Command = Optional[Callable[[], None]]


@dataclass
class TextSkins:
    """Color skins for a text-only clickable canvas widget."""
    normal: str = "white"
    active: str = "#FFD24A"   # pressed feedback
    disabled: str = "#CFCFCF"


class CanvasText:
    """A text-only clickable widget on a Tk canvas.

    - No hover visual effects.
    - On press: change fill to skins.active
    - On release (inside): call command, then restore to skins.normal

    This is ideal for lightweight clickable labels like `mode_oper`.
    """

    def __init__(
        self,
        *,
        root: tk.Misc,
        canvas: tk.Canvas,
        tag: str,
        x: int,
        y: int,
        anchor: str = "center",
        text: str = "",
        text_font: Optional[Any] = None,
        skins: TextSkins = TextSkins(),
        cooldown_ms: int = 250,
        command: Command = None,
        cursor: str = "hand2",
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.tag = tag
        self.anchor = anchor
        self.text_font = text_font

        self.skins = skins
        self.cooldown_ms = int(cooldown_ms)
        self.command = command
        self.cursor = cursor

        self._pressed = False
        self._disabled = False
        self._last_click_ms = 0
        self._prev_cursor: Optional[str] = None

        self.text_id = self.canvas.create_text(
            x,
            y,
            text=text,
            font=text_font,
            fill=self.skins.normal,
            anchor=self.anchor,
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
            self.cursor = str(kw["cursor"])

        # allow direct color updates
        if "fill" in kw:
            self.skins.normal = str(kw["fill"])
            self._update_visual_idle()

        if "active_fill" in kw:
            self.skins.active = str(kw["active_fill"])

        if "disabled_fill" in kw:
            self.skins.disabled = str(kw["disabled_fill"])
            self._update_visual_idle()

        if "skins" in kw and isinstance(kw["skins"], TextSkins):
            self.skins = kw["skins"]
            self._update_visual_idle()

    def set_disabled(self, disabled: bool = True):
        self._set_state("disabled" if disabled else "normal")

    def destroy(self):
        try:
            self.canvas.tag_unbind(self.tag, "<Enter>")
            self.canvas.tag_unbind(self.tag, "<Leave>")
            self.canvas.tag_unbind(self.tag, "<ButtonPress-1>")
            self.canvas.tag_unbind(self.tag, "<ButtonRelease-1>")
        except Exception:
            pass

        try:
            self.canvas.delete(self.text_id)
        except Exception:
            pass

    @property
    def ids(self) -> Tuple[int]:
        return (self.text_id,)

    # ---------------------------
    # Internals
    # ---------------------------
    def _now_ms(self) -> int:
        return int(time.monotonic() * 1000)

    def _is_disabled(self) -> bool:
        return bool(self._disabled)

    def _set_cursor(self, cur: str):
        try:
            self.root.configure(cursor=cur)
        except Exception:
            pass

    def _update_visual_idle(self):
        if self._is_disabled():
            self.canvas.itemconfig(self.text_id, fill=self.skins.disabled)
            self._set_cursor("")
        else:
            self.canvas.itemconfig(self.text_id, fill=self.skins.normal)
            self._set_cursor("")

    def _set_state(self, st):
        disabled = (st in ("disabled", tk.DISABLED, False) and st != "normal")
        self._disabled = bool(disabled)
        self._pressed = False
        self._update_visual_idle()

    def _hit_test_inside(self) -> bool:
        current = self.canvas.find_withtag("current")
        if not current:
            return False
        for item in current:
            try:
                if self.tag in self.canvas.gettags(item):
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

        # Only cursor change (no hover visuals)
        try:
            self._prev_cursor = str(self.root.cget("cursor"))
        except Exception:
            self._prev_cursor = None

        self._set_cursor(self.cursor)

    def _on_leave(self, _event):
        self._pressed = False

        if self._prev_cursor is not None:
            self._set_cursor(self._prev_cursor)
        else:
            self._set_cursor("")

        # restore normal fill (no hover)
        self._update_visual_idle()

    def _on_press(self, _event):
        if self._is_disabled():
            self._update_visual_idle()
            return "break"

        self._pressed = True
        self.canvas.itemconfig(self.text_id, fill=self.skins.active)
        return "break"

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
                # ignore click, restore normal
                self.canvas.itemconfig(self.text_id, fill=self.skins.normal)
                return "break"

            self._last_click_ms = t
            self.canvas.itemconfig(self.text_id, fill=self.skins.normal)
            if callable(self.command):
                self.command()
            return "break"

        # released outside
        self.canvas.itemconfig(self.text_id, fill=self.skins.normal)
        return "break"


def bind_canvas_text(
    *,
    root: tk.Misc,
    canvas: tk.Canvas,
    tag: str,
    x: int,
    y: int,
    anchor: str = "center",
    text: str = "",
    text_font: Optional[Any] = None,
    fill: str = "white",
    active_fill: str = "#FFD24A",
    disabled_fill: str = "#CFCFCF",
    cooldown_ms: int = 250,
    command: Command = None,
    cursor: str = "hand2",
) -> CanvasText:
    skins = TextSkins(normal=fill, active=active_fill, disabled=disabled_fill)
    return CanvasText(
        root=root,
        canvas=canvas,
        tag=tag,
        x=x,
        y=y,
        anchor=anchor,
        text=text,
        text_font=text_font,
        skins=skins,
        cooldown_ms=cooldown_ms,
        command=command,
        cursor=cursor,
    )
