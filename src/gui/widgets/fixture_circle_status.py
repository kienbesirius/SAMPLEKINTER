# src/gui/widgets/fixture_com_status.py
from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple, Literal
import re


Command = Optional[Callable[[], None]]
ComStatus = Literal["not_found", "listening", "stand_by"]


@dataclass
class ComStatusSkins:
    """
    3 trạng thái cho COM status background.
    Các giá trị là KEY trong assets dict (PhotoImage đã load sẵn).
    """
    not_found: str = "fixture_circle_dock_status_not_found"
    listening: str = "fixture_circle_dock_status_listening"
    stand_by: str = "fixture_circle_dock_status_stand_by"


def _pick_scaled_key(canvas: tk.Canvas, assets: Dict[str, Any], base_key: str) -> str:
    """Tự chọn variant _0.5 / _0.75 nếu tồn tại trong assets."""
    try:
        w = int(canvas.winfo_width())
    except Exception:
        w = 0

    if w and w <= 800:
        k = f"{base_key}_0.5"
        if k in assets:
            return k
    if w and w <= 1200:
        k = f"{base_key}_0.75"
        if k in assets:
            return k
    return base_key


def _norm_status(s: str) -> ComStatus:
    """Tolerant input: standy/standby/stand by/stand_by."""
    t = (s or "").strip().lower().replace("-", "_")
    t = "_".join(t.split())  # collapse spaces -> _
    if t in ("notfound", "not_found", "nf"):
        return "not_found"
    if t in ("listening", "listen"):
        return "listening"
    if t in ("standby", "stand_by", "stand", "standy", "stand__by"):
        return "stand_by"
    return "not_found"

def _scale_suffix_from_canvas(canvas: tk.Canvas) -> Optional[str]:
    """
    Match logic của button.py / fixture_check_slot_test.py:
      <= 800  -> _0.5
      <= 1200 -> _0.75
      else    -> None
    """
    try:
        w = int(canvas.winfo_width())
    except Exception:
        w = 0

    # nếu winfo_width chưa “ready” (hay gặp lúc init), fallback về 0.75
    if w <= 1:
        return "_0.75"

    if w <= 800:
        return "_0.5"
    if w <= 1200:
        return "_0.75"
    return None


def _maybe_append_scale(assets: Dict[str, Any], canvas: tk.Canvas, base_key: str) -> str:
    """
    Append _0.5 / _0.75 cho fixture assets nếu có tồn tại.
    Nếu base_key đã có _0.5/_0.75 rồi thì giữ nguyên.
    """
    if base_key.endswith("_0.5") or base_key.endswith("_0.75"):
        return base_key

    suf = _scale_suffix_from_canvas(canvas)
    if suf:
        k = f"{base_key}{suf}"
        if k in assets:
            return k
    return base_key

_COM_NUM_RE = re.compile(r"(?i)\bcom\s*(\d+)\b")


def _find_fixture_text_com_key(assets: Dict[str, Any], canvas: tk.Canvas, label: str) -> Optional[str]:
    """
    label: "COM1" / "com 2" / ...
    assets keys:
      - fixture_text_com{N}_0.5
      - fixture_text_com{N}_0.75
    """
    raw = (label or "").strip()
    if not raw:
        return None

    m = _COM_NUM_RE.search(raw)
    if not m:
        return None

    num = m.group(1)  # "1".."17"...
    scale = _scale_suffix_from_canvas(canvas)  # "_0.5" / "_0.75" / None

    # ưu tiên scale hiện tại trước
    candidates = []
    if scale in ("_0.5", "_0.75"):
        candidates.append(f"fixture_text_com{num}{scale}")

    # fallback sang scale khác (nếu có)
    candidates.extend([
        f"fixture_text_com{num}_0.75",
        f"fixture_text_com{num}_0.5",
        f"fixture_text_com{num}",  # phòng khi sau này bạn có key base
    ])

    for k in candidates:
        if k in assets:
            return k
    return None

class FixtureComStatus:
    """
    Canvas widget cho COM status:
      - background image theo status
      - label ở CENTER: ưu tiên image label nếu assets có, fallback text label.

    Public API:
      - configure(...)
      - set_status(...)
      - set_label(...)
      - set_disabled(...)
      - destroy()
      - ids property

    Usage:

    from src.gui.widgets.fixture_com_status import bind_fixture_com_status

    self.com1 = bind_fixture_com_status(
        root=self.root,
        canvas=self._canvas,
        assets=self.assets,
        tag="com1_status",
        x=300, y=220,
        label="COM1",          # nếu assets có 'com1' (hoặc 'COM1', 'TEXT_COM1', ...)
        status="listening",
    )

    # đổi trạng thái
    self.com1.set_status("not_found")
    self.com1.set_status("stand_by")

    # đổi label
    self.com1.set_label("COM2")

    # disable click
    self.com1.set_disabled(True)

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
        skins: ComStatusSkins = ComStatusSkins(),
        status: ComStatus = "not_found",
        label: str = "COM1",
        label_font: Optional[Any] = ("Tektur", 18, "bold"),
        label_fill: str = "white",
        label_fill_disabled: str = "white",
        label_wrap_width: Optional[int] = None,
        label_wrap_pad: int = 10,
        label_justify: str = "center",
        cooldown_ms: int = 300,
        command: Command = None,
        cursor: str = "hand2",
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.assets = assets
        self.tag = tag
        self.anchor = anchor

        self.skins = skins
        self._status: ComStatus = "not_found"

        self.label_fill = label_fill
        self.label_fill_disabled = label_fill_disabled
        self.label_font = label_font
        self.label_wrap_width = label_wrap_width
        self.label_wrap_pad = int(label_wrap_pad)
        self.label_justify = label_justify

        self.cooldown_ms = int(cooldown_ms)
        self.command = command
        self.cursor = cursor

        self._disabled = False
        self._pressed = False
        self._last_click_ms = 0
        self._prev_cursor: Optional[str] = None

        # --- background ---
        bg_key = self._status_to_bg_key(status)
        self.bg_id = self.canvas.create_image(
            x,
            y,
            image=self.assets[bg_key],
            anchor=self.anchor,
            tags=(self.tag, f"{self.tag}__bg"),
        )

        # --- label (both image + text; toggle) ---
        self._label: str = ""
        self._label_img_key: Optional[str] = None

        # wrap width default from bg image width
        bg_img = self.assets[bg_key]
        bg_w = int(bg_img.width()) if hasattr(bg_img, "width") else 0
        if self.label_wrap_width is None:
            self.label_wrap_width = max(1, bg_w - 2 * self.label_wrap_pad) if bg_w > 0 else 1

        # --- label: create BOTH image and text, then toggle ---
        self.label_img_id = self.canvas.create_image(
            x, y,
            image="",           # set later
            anchor="center",
            state="hidden",
            tags=(self.tag, f"{self.tag}__label_img"),
        )
        self.label_text_id = self.canvas.create_text(
            x, y,
            text="",
            font=self.label_font,
            fill=self.label_fill,
            anchor="center",
            width=int(self.label_wrap_width),
            justify=self.label_justify,
            tags=(self.tag, f"{self.tag}__label_text"),
        )

        # Bind events
        self.canvas.tag_bind(self.tag, "<Enter>", self._on_enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self._on_leave)
        self.canvas.tag_bind(self.tag, "<ButtonPress-1>", self._on_press)
        self.canvas.tag_bind(self.tag, "<ButtonRelease-1>", self._on_release)

        self.set_status(status)
        self.set_label(label)

    # ---------------------------
    # Public API
    # ---------------------------
    def configure(self, **kw):
        if "state" in kw:
            self._set_state(kw["state"])
        if "status" in kw:
            self.set_status(kw["status"])
        if "label" in kw:
            self.set_label(kw["label"])
        if "command" in kw:
            self.command = kw["command"]
        if "cooldown_ms" in kw:
            self.cooldown_ms = int(kw["cooldown_ms"])
        if "cursor" in kw:
            self.cursor = kw["cursor"]
        if "skins" in kw and isinstance(kw["skins"], ComStatusSkins):
            self.skins = kw["skins"]
            self.set_status(self._status)

    def set_disabled(self, disabled: bool = True):
        self._set_state("disabled" if disabled else "normal")

    def set_status(self, status: str | ComStatus):
        self._status = _norm_status(str(status))
        bg_key = self._status_to_bg_key(self._status)
        self.canvas.itemconfig(self.bg_id, image=self.assets[bg_key])

        # nếu wrap_width chưa set thủ công thì cập nhật theo bg mới
        if self.label_wrap_width is None:
            bg_img = self.assets[bg_key]
            bg_w = int(bg_img.width()) if hasattr(bg_img, "width") else 0
            wrap_w = max(1, bg_w - 2 * self.label_wrap_pad) if bg_w > 0 else 1
            self.canvas.itemconfig(self.label_text_id, width=wrap_w)

        # refresh label fill depending on state
        if self._disabled:
            self.canvas.itemconfig(self.label_text_id, fill=self.label_fill_disabled)
        else:
            self.canvas.itemconfig(self.label_text_id, fill=self.label_fill)

    def set_label(self, label: str):
        self._label = (label or "").strip()

        # Try image label first
        k = _find_fixture_text_com_key(self.assets, self.canvas, self._label)
        self._label_img_key = k

        if k is not None:
            self.canvas.itemconfig(self.label_img_id, image=self.assets[k], state="normal")
            self.canvas.itemconfig(self.label_text_id, state="hidden", text="")
        else:
            self.canvas.itemconfig(self.label_img_id, state="hidden")
            self.canvas.itemconfig(self.label_text_id, state="normal", text=self._label)

    def destroy(self):
        try:
            self.canvas.tag_unbind(self.tag, "<Enter>")
            self.canvas.tag_unbind(self.tag, "<Leave>")
            self.canvas.tag_unbind(self.tag, "<ButtonPress-1>")
            self.canvas.tag_unbind(self.tag, "<ButtonRelease-1>")
        except Exception:
            pass

        for _id in (self.bg_id, self.label_img_id, self.label_text_id):
            try:
                self.canvas.delete(_id)
            except Exception:
                pass

    @property
    def ids(self) -> Tuple[int, int, int]:
        return (self.bg_id, self.label_img_id, self.label_text_id)

    @property
    def status(self) -> ComStatus:
        return self._status

    @property
    def label(self) -> str:
        return self._label

    # ---------------------------
    # Internals
    # ---------------------------
    def _now_ms(self) -> int:
        return int(time.monotonic() * 1000)

    def _set_state(self, st):
        disabled = (st in ("disabled", tk.DISABLED, False) and st != "normal")
        self._disabled = bool(disabled)
        self._pressed = False

        if self._disabled:
            self._set_cursor("")
            self.canvas.itemconfig(self.label_text_id, fill=self.label_fill_disabled)
        else:
            self._set_cursor("")
            self.canvas.itemconfig(self.label_text_id, fill=self.label_fill)

    def _set_cursor(self, cur: str):
        try:
            self.root.configure(cursor=cur)
        except Exception:
            pass

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

    def _status_to_bg_key(self, status: ComStatus) -> str:
        if status == "listening":
            base = self.skins.listening
        elif status == "stand_by":
            base = self.skins.stand_by
        else:
            base = self.skins.not_found
        return _pick_scaled_key(self.canvas, self.assets, base)

    # ---------------------------
    # Event handlers
    # ---------------------------
    def _on_enter(self, _event):
        if self._disabled:
            self._set_cursor("")
            return "break"

        try:
            self._prev_cursor = str(self.root.cget("cursor"))
        except Exception:
            self._prev_cursor = None

        if callable(self.command):
            self._set_cursor(self.cursor)
        else:
            self._set_cursor("")

    def _on_leave(self, _event):
        self._pressed = False
        if self._prev_cursor is not None:
            self._set_cursor(self._prev_cursor)
        else:
            self._set_cursor("")
        return "break"

    def _on_press(self, _event):
        if self._disabled:
            return "break"
        self._pressed = True
        return "break"

    def _on_release(self, _event):
        if self._disabled:
            self._pressed = False
            return "break"

        was_pressed = bool(self._pressed)
        self._pressed = False

        if not (was_pressed and self._hit_test_inside()):
            return "break"

        if not callable(self.command):
            return "break"

        t = self._now_ms()
        if t - self._last_click_ms < self.cooldown_ms:
            return "break"

        self._last_click_ms = t
        self.command()
        return "break"


def bind_fixture_circle_com_status(
    *,
    root: tk.Misc,
    canvas: tk.Canvas,
    assets: Dict[str, Any],
    tag: str,
    x: int,
    y: int,
    anchor: str = "center",
    not_found_bg: str = "fixture_circle_dock_status_not_found",
    listening_bg: str = "fixture_circle_dock_status_listening",
    stand_by_bg: str = "fixture_circle_dock_status_stand_by",
    status: str | ComStatus = "not_found",
    label: str = "COM1",
    label_font: Optional[Any] = None,
    label_fill: str = "white",
    label_fill_disabled: str = "white",
    label_wrap_width: Optional[int] = None,
    label_wrap_pad: int = 10,
    label_justify: str = "center",
    cooldown_ms: int = 300,
    command: Command = None,
    cursor: str = "hand2",
) -> FixtureComStatus:
    """
    Canvas widget cho COM status:
      - background image theo status
      - label ở CENTER: ưu tiên image label nếu assets có, fallback text label.

    Public API:
      - configure(...)
      - set_status(...)
      - set_label(...)
      - set_disabled(...)
      - destroy()
      - ids property

    Usage:

    from src.gui.widgets.fixture_com_status import bind_fixture_com_status

    self.com1 = bind_fixture_com_status(
        root=self.root,
        canvas=self._canvas,
        assets=self.assets,
        tag="com1_status",
        x=300, y=220,
        label="COM1",          # nếu assets có 'com1' (hoặc 'COM1', 'TEXT_COM1', ...)
        status="listening",
    )

    # đổi trạng thái
    self.com1.set_status("not_found")
    self.com1.set_status("stand_by")

    # đổi label
    self.com1.set_label("COM2")

    # disable click
    self.com1.set_disabled(True)

    """

    # Get canvas width to pick scaled assets
    if "fixture" in not_found_bg:
        # Get canvas height width to define button skins
        canvas_width = canvas.winfo_width()
        if canvas_width <= 800:
            not_found_bg += "_0.5"
            listening_bg += "_0.5"
            stand_by_bg += "_0.5"
        elif canvas_width <= 1200:
            not_found_bg += "_0.75"
            listening_bg += "_0.75"
            stand_by_bg += "_0.75"


    skins = ComStatusSkins(
        not_found=not_found_bg,
        listening=listening_bg,
        stand_by=stand_by_bg,
    )
    return FixtureComStatus(
        root=root,
        canvas=canvas,
        assets=assets,
        tag=tag,
        x=x,
        y=y,
        anchor=anchor,
        skins=skins,
        status=_norm_status(str(status)),
        label=label,
        label_font=label_font,
        label_fill=label_fill,
        label_fill_disabled=label_fill_disabled,
        label_wrap_width=label_wrap_width,
        label_wrap_pad=label_wrap_pad,
        label_justify=label_justify,
        cooldown_ms=cooldown_ms,
        command=command,
        cursor=cursor,
    )
