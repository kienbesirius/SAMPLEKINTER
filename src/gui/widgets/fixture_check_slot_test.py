# src/gui/widgets/fixture_check_slot_test.py
from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple, Literal


Command = Optional[Callable[[], None]]
SlotStatus = Literal["idle", "testing", "pass", "fail", "stand_by", "item", "unknown"]


@dataclass
class SlotTestSkins:
    """
    4 trạng thái cho slot-test indicator.
    Các giá trị là KEY trong assets dict (PhotoImage đã load sẵn).
    """
    idle: str = "fixture_slot_test_idle"
    testing: str = "fixture_slot_test_testing"
    passed: str = "fixture_slot_test_pass"
    failed: str = "fixture_slot_test_fail"
    stand_by: str = "fixture_slot_test_item"
    item: str = "fixture_slot_test_item"
    unknown: str = "fixture_slot_test_idle"


def _pick_scaled_key(canvas: tk.Canvas, assets: Dict[str, Any], base_key: str) -> str:
    """
    Tự chọn variant _0.5 / _0.75 nếu tồn tại trong assets,
    dựa trên canvas width (giống style bên button.py, nhưng an toàn hơn).
    """
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


class FixtureCheckSlotTest:
    """
    Canvas 'status indicator' gồm:
      - Canvas image item (the status tile)
      - Canvas text item (optional label: slot name / number)

    Public API gần giống CanvasButton:
      - configure(...)
      - set_status(...)
      - set_disabled(...)
      - destroy()
      - ids property

    Click (optional):
      - Nếu có command -> click-release-inside sẽ gọi command (có cooldown).
    
    Usage:

    from src.gui.widgets.fixture_check_slot_test import bind_fixture_check_slot_test

    self.slot1 = bind_fixture_check_slot_test(
        root=self.root,
        canvas=self._canvas,
        assets=self.assets,
        tag="slot1_status",
        x=200, y=120,
        status="idle",
        text="S1",
        text_font=self.tektur_font,
    )

    # update trạng thái:
    self.slot1.set_status("testing")
    self.slot1.set_status("pass")
    self.slot1.set_status("fail")

    # disable click (nếu có command):
    self.slot1.set_disabled(True)

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
        skins: SlotTestSkins = SlotTestSkins(),
        status: SlotStatus = "idle",
        text: str = "",
        text_font: Optional[Any] = None,
        text_fill: str = "white",
        text_fill_disabled: str = "white",
        cooldown_ms: int = 300,
        command: Command = None,
        cursor: str = "hand2",
        text_wrap_width: Optional[int] = None,
        text_wrap_pad: int = 8,
        text_justify: str = "center",
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.assets = assets
        self.tag = tag
        self.anchor = anchor

        self.skins = skins
        self._status: SlotStatus = "idle"

        self.text_fill = text_fill
        self.text_fill_disabled = text_fill_disabled
        self.cooldown_ms = int(cooldown_ms)
        self.command = command
        self.cursor = cursor

        self._disabled = False
        self._pressed = False
        self._last_click_ms = 0
        self._prev_cursor: Optional[str] = None

        # Build items
        img_key = self._status_to_key(status)
        self.img_id = self.canvas.create_image(
            x,
            y,
            image=self.assets[img_key],
            anchor=self.anchor,
            tags=(self.tag, f"{self.tag}__img"),
        )

        # sau khi lấy img_key, lấy kích thước ảnh để tính wrap_width
        img = self.assets[img_key]                 # PhotoImage
        img_w = int(img.width()) if hasattr(img, "width") else 0

        wrap_w = text_wrap_width
        if wrap_w is None:
            # wrap theo bề ngang ảnh (trừ padding)
            wrap_w = max(1, img_w - 2 * text_wrap_pad) if img_w > 0 else 1

        self.text_id = self.canvas.create_text(
            x,
            y,
            text=text,
            font=text_font,
            fill=self.text_fill,
            anchor="center",
            width=wrap_w,              # <-- wrap word
            justify=text_justify,      # <-- align center multi-line
            tags=(self.tag, f"{self.tag}__text"),
        )

        # Bind events
        self.canvas.tag_bind(self.tag, "<Enter>", self._on_enter)
        self.canvas.tag_bind(self.tag, "<Leave>", self._on_leave)
        self.canvas.tag_bind(self.tag, "<ButtonPress-1>", self._on_press)
        self.canvas.tag_bind(self.tag, "<ButtonRelease-1>", self._on_release)

        self.set_status(status)

    # ---------------------------
    # Public API
    # ---------------------------
    def configure(self, **kw):
        if "state" in kw:
            self._set_state(kw["state"])
        if "status" in kw:
            self.set_status(kw["status"])
        if "text" in kw:
            self.canvas.itemconfig(self.text_id, text=kw["text"])
        if "command" in kw:
            self.command = kw["command"]
        if "cooldown_ms" in kw:
            self.cooldown_ms = int(kw["cooldown_ms"])
        if "cursor" in kw:
            self.cursor = kw["cursor"]
        if "skins" in kw and isinstance(kw["skins"], SlotTestSkins):
            self.skins = kw["skins"]
            # refresh current status with new skins
            self.set_status(self._status)

    def set_disabled(self, disabled: bool = True):
        self._set_state("disabled" if disabled else "normal")

    def set_status(self, status: SlotStatus):
        # tolerant: nếu status lạ thì fallback idle
        if status not in ("idle", "testing", "pass", "fail", "stand_by", "item", "unknown"):
            status = "idle"  # type: ignore[assignment]
        self._status = status

        key = self._status_to_key(status)
        self.canvas.itemconfig(self.img_id, image=self.assets[key])

        # text color depends on disabled
        if self._disabled:
            self.canvas.itemconfig(self.text_id, fill=self.text_fill_disabled)
        else:
            self.canvas.itemconfig(self.text_id, fill=self.text_fill)

    def destroy(self):
        try:
            self.canvas.tag_unbind(self.tag, "<Enter>")
            self.canvas.tag_unbind(self.tag, "<Leave>")
            self.canvas.tag_unbind(self.tag, "<ButtonPress-1>")
            self.canvas.tag_unbind(self.tag, "<ButtonRelease-1>")
        except Exception:
            pass

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

    @property
    def status(self) -> SlotStatus:
        return self._status

    # ---------------------------
    # Internals
    # ---------------------------
    def _now_ms(self) -> int:
        return int(time.monotonic() * 1000)

    def _set_state(self, st):
        disabled = (st in ("disabled", tk.DISABLED, False) and st != "normal")
        self._disabled = bool(disabled)
        self._pressed = False

        # cursor + text color
        if self._disabled:
            self._set_cursor("")
            self.canvas.itemconfig(self.text_id, fill=self.text_fill_disabled)
        else:
            self._set_cursor("")
            self.canvas.itemconfig(self.text_id, fill=self.text_fill)

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

    def _status_to_key(self, status: SlotStatus) -> str:
        # map status -> base skin key
        if status == "testing":
            base = self.skins.testing
        elif status == "pass":
            base = self.skins.passed
        elif status == "fail":
            base = self.skins.failed
        elif status == "stand_by":
            base = self.skins.stand_by
        elif status == "item":
            base = self.skins.item
        elif status == "unknown":
            base = self.skins.unknown
        else:
            base = self.skins.idle

        # auto scale if *_0.5 / *_0.75 exists
        return _pick_scaled_key(self.canvas, self.assets, base)

    # ---------------------------
    # Event handlers
    # ---------------------------
    def _on_enter(self, _event):
        if self._disabled:
            self._set_cursor("")
            return "break"

        # only show hand cursor if clickable
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


def bind_fixture_check_slot_test(
    *,
    root: tk.Misc,
    canvas: tk.Canvas,
    assets: Dict[str, Any],
    tag: str,
    x: int,
    y: int,
    anchor: str = "center",
    idle_status: str = "fixture_slot_test_idle",
    testing_status: str = "fixture_slot_test_testing",
    pass_status: str = "fixture_slot_test_pass",
    fail_status: str = "fixture_slot_test_fail",
    stand_by_status: str = "fixture_slot_test_item",
    item_status: str = "fixture_slot_test_item",
    unknown_status: str = "fixture_slot_test_idle",
    status: SlotStatus = "idle",
    text: str = "",
    text_font: Optional[Any] = None,
    text_fill: str = "white",
    text_fill_disabled: str = "white",
    cooldown_ms: int = 300,
    command: Command = None,
) -> FixtureCheckSlotTest:
    
    """
    Canvas 'status indicator' gồm:
      - Canvas image item (the status tile)
      - Canvas text item (optional label: slot name / number)

    Public API gần giống CanvasButton:
      - configure(...)
      - set_status(...)
      - set_disabled(...)
      - destroy()
      - ids property

    Click (optional):
      - Nếu có command -> click-release-inside sẽ gọi command (có cooldown).
    
    Usage:

    from src.gui.widgets.fixture_check_slot_test import bind_fixture_check_slot_test

    self.slot1 = bind_fixture_check_slot_test(
        root=self.root,
        canvas=self._canvas,
        assets=self.assets,
        tag="slot1_status",
        x=200, y=120,
        status="idle",
        text="S1",
        text_font=self.tektur_font,
    )

    # update trạng thái:
    self.slot1.set_status("testing")
    self.slot1.set_status("pass")
    self.slot1.set_status("fail")

    # disable click (nếu có command):
    self.slot1.set_disabled(True)

    """

    # Get canvas width to pick scaled assets
    if "fixture" in idle_status:
        # Get canvas height width to define button skins
        canvas_width = canvas.winfo_width()
        if canvas_width <= 800:
            idle_status += "_0.5"
            testing_status += "_0.5"
            pass_status += "_0.5"
            fail_status += "_0.5" 
            stand_by_status += "_0.5" # "item"
            item_status += "_0.5" # "item"
            unknown_status += "_0.5" # "idle"

        elif canvas_width <= 1200:
            idle_status += "_0.75"
            testing_status += "_0.75"
            pass_status += "_0.75"
            fail_status += "_0.75"
            stand_by_status += "_0.75" # "item"
            item_status += "_0.75" # "item"
            unknown_status += "_0.75" # "idle"

    # Build skins
    skins = SlotTestSkins(
        idle=idle_status,
        testing=testing_status,
        passed=pass_status,
        failed=fail_status,
        stand_by=stand_by_status,
        item=item_status,
        unknown=unknown_status,
    )
    return FixtureCheckSlotTest(
        root=root,
        canvas=canvas,
        assets=assets,
        tag=tag,
        x=x,
        y=y,
        anchor=anchor,
        skins=skins,
        status=status,
        text=text,
        text_font=text_font,
        text_fill=text_fill,
        text_fill_disabled=text_fill_disabled,
        cooldown_ms=cooldown_ms,
        command=command,
    )
