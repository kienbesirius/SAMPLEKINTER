# src/gui/widgets/fixture_check_slot_test.py
from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Tuple, Literal, List
import math
from src.utils.config_go import choose_slot_font
Command = Optional[Callable[[], None]]
SlotStatus = Literal["idle", "testing", "pass", "fail", "stand_by", "item", "unknown"]


# --- ADD (đặt trước class FixtureCheckSlotTest) ---
class _OrbitDotsTrailHoverFX:
    """
    Hover FX:
      - 2 chấm cam to đối diện nhau chạy vòng theo viền rectangle (clockwise)
      - mỗi chấm kéo theo 4 chấm nhỏ dần + nhạt dần phía sau
      - không pulse, không dùng asset, chỉ canvas shapes
    """
    def __init__(
        self,
        *,
        root: tk.Misc,
        canvas: tk.Canvas,
        tag: str,
        base_id: int,          # img_id của slot
        text_id: int,          # text_id để đưa lên top
        fps_ms: int = 33,      # ~30fps mượt, ít tốn CPU hơn 60ms
        extra_pad: int = 3,    # pad cho path chạy quanh viền (ra ngoài/ăn vào)
        speed_px_s: float = 260.0,  # tốc độ chạy theo pixel/giây (ổn định theo thời gian)
        dot_r: int = 7,        # bán kính chấm to
        tail_count: int = 4,   # số chấm đuôi
        tail_step: float = 14.0,  # khoảng cách dọc theo path giữa các chấm đuôi
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.tag = tag
        self.fx_tag = f"{tag}__hoverfx_orbit"
        self.base_id = base_id
        self.text_id = text_id

        self.fps_ms = int(fps_ms)
        self.extra_pad = int(extra_pad)
        self.speed_px_s = float(speed_px_s)

        self.dot_r = int(dot_r)
        self.tail_count = int(tail_count)
        self.tail_step = float(tail_step)

        self._after: Optional[str] = None
        self._running = False

        # tiến độ chạy trên chu vi (đơn vị px trên path)
        self._s = 0.0
        self._t_last: Optional[float] = None

        # ids: mỗi “đầu” có (1 leader + tail_count dots)
        self._dotsA: List[int] = []
        self._dotsB: List[int] = []

        # màu: leader + tail (nhạt dần). Tk không alpha, nên dùng màu sáng dần.
        self._colors = [
            "#1869FF",  # leader (cam đậm)
            "#4A89FF",
            "#76ADFF",
            "#A3CEFF",
            "#D0E4FF",
        ]

    # -------------------------
    # Public
    # -------------------------
    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._s = 0.0
        self._t_last = None

        # tạo dot shapes (leader + tails) cho 2 đầu
        self._create_dots()

        # đảm bảo: fx nằm trên ảnh, text nằm trên fx
        try:
            self.canvas.tag_raise(self.fx_tag, self.base_id)
            # self.canvas.tag_raise(self.text_id, self.fx_tag)
        except Exception:
            pass

        self._tick()

    def stop(self) -> None:
        self._running = False
        if self._after:
            try:
                self.root.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

        try:
            self.canvas.delete(self.fx_tag)
        except Exception:
            pass

        self._dotsA.clear()
        self._dotsB.clear()
        self._t_last = None

    # -------------------------
    # Internals
    # -------------------------
    def _create_dots(self) -> None:
        # clear cũ nếu còn
        try:
            self.canvas.delete(self.fx_tag)
        except Exception:
            pass
        self._dotsA.clear()
        self._dotsB.clear()

        # tạo leader + tail
        total = 1 + max(0, self.tail_count)

        def _mk_one_group() -> List[int]:
            ids: List[int] = []
            for i in range(total):
                col = self._colors[i] if i < len(self._colors) else self._colors[-1]
                r = self._radius_for_index(i)
                _id = self.canvas.create_oval(
                    0, 0, 0, 0,
                    fill=col,
                    outline="",          # cho “đèn” mềm, không viền
                    tags=(self.fx_tag,),
                    state="disabled",    # không ăn click
                )
                ids.append(_id)
            return ids

        self._dotsA = _mk_one_group()
        self._dotsB = _mk_one_group()

        # đặt vị trí lần đầu
        self._reposition_all()

    def _radius_for_index(self, i: int) -> int:
        # i=0: leader, i>0: tail nhỏ dần
        if i <= 0:
            return self.dot_r
        # scale nhanh để thấy “đuôi” rõ (có thể tweak)
        scale = 0.72 ** i
        r = max(2, int(round(self.dot_r * scale)))
        return r

    def _refined_bbox(self) -> Tuple[float, float, float, float]:
        bbox = self.canvas.bbox(self.base_id)
        if bbox:
            x1, y1, x2, y2 = bbox
        else:
            cx, cy = self.canvas.coords(self.base_id) or (0, 0)
            x1, y1, x2, y2 = cx - 20, cy - 20, cx + 20, cy + 20

        # refine theo logic bạn đang dùng (transparent padding của asset)
        x1 += 8
        y1 += 8
        x2 -= 10
        y2 -= 10

        # pad path: >0 chạy hơi “ra ngoài”, <0 chạy ăn vào trong
        pad = float(self.extra_pad)
        x1 -= pad
        y1 -= pad
        x2 += pad
        y2 += pad
        return float(x1), float(y1), float(x2), float(y2)

    def _perimeter_len(self, x1: float, y1: float, x2: float, y2: float) -> float:
        w = max(1.0, x2 - x1)
        h = max(1.0, y2 - y1)
        return 2.0 * (w + h)

    def _pos_on_rect_perimeter(self, s: float, x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
        """
        s chạy trong [0, L). Quy ước:
          s=0 tại (x1,y1) góc trên-trái, đi clockwise:
            top:    (x1->x2)
            right:  (y1->y2)
            bottom: (x2->x1)
            left:   (y2->y1)
        """
        w = max(1.0, x2 - x1)
        h = max(1.0, y2 - y1)
        L = 2.0 * (w + h)
        if L <= 0:
            return x1, y1

        s = s % L

        # top edge
        if s <= w:
            return (x1 + s, y1)

        s -= w
        # right edge
        if s <= h:
            return (x2, y1 + s)

        s -= h
        # bottom edge
        if s <= w:
            return (x2 - s, y2)

        s -= w
        # left edge
        return (x1, y2 - min(s, h))

    def _reposition_group(self, ids: List[int], s_base: float, L: float, x1: float, y1: float, x2: float, y2: float) -> None:
        """
        ids[0] leader tại s_base,
        ids[1..] trailing phía sau: s_base - k*tail_step
        """
        if not ids:
            return

        for i, _id in enumerate(ids):
            s = s_base - (i * self.tail_step)
            x, y = self._pos_on_rect_perimeter(s, x1, y1, x2, y2)
            r = self._radius_for_index(i)
            try:
                self.canvas.coords(_id, x - r, y - r, x + r, y + r)
            except Exception:
                pass

    def _reposition_all(self) -> None:
        x1, y1, x2, y2 = self._refined_bbox()
        L = self._perimeter_len(x1, y1, x2, y2)
        if L <= 1:
            return

        # 2 chấm đối diện nhau: lệch nhau nửa chu vi
        sA = self._s % L
        sB = (self._s + (L * 0.5)) % L

        self._reposition_group(self._dotsA, sA, L, x1, y1, x2, y2)
        self._reposition_group(self._dotsB, sB, L, x1, y1, x2, y2)

        # giữ layer đúng: fx trên base, text trên fx
        try:
            self.canvas.tag_raise(self.fx_tag, self.base_id)
            # self.canvas.tag_raise(self.text_id, self.fx_tag)
        except Exception:
            pass

    def _tick(self) -> None:
        if not self._running:
            return

        import time

        now = time.monotonic()
        if self._t_last is None:
            dt = self.fps_ms / 1000.0
        else:
            dt = max(0.0, now - self._t_last)
        self._t_last = now

        # cập nhật progress theo “px/giây” để tốc độ ổn định kể cả bị drop frame
        x1, y1, x2, y2 = self._refined_bbox()
        L = self._perimeter_len(x1, y1, x2, y2)
        if L > 1:
            self._s = (self._s + self.speed_px_s * dt) % L

        self._reposition_all()
        self._after = self.root.after(self.fps_ms, self._tick)

# --- ADD (đặt trước class FixtureCheckSlotTest) ---
class _RectPulse:
    """
    Hiệu ứng hover kiểu "upgrade": 2 vòng sáng + 6 sparkle.
    Không cần asset, chạy bằng canvas shapes.
    """
    def __init__(
        self,
        *,
        root: tk.Misc,
        canvas: tk.Canvas,
        tag: str,
        base_id: int,          # img_id của slot
        text_id: int,          # text_id để đưa lên top
        fps_ms: int = 30,
        extra_pad: int = 3,
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.tag = tag
        self.fx_tag = f"{tag}__hoverfx"
        self.base_id = base_id
        self.text_id = text_id
        self.fps_ms = int(fps_ms)
        self.extra_pad = int(extra_pad)

        self._after: Optional[str] = None
        self._running = False
        self._phase = 0

        self._ring1: Optional[int] = None
        self._ring2: Optional[int] = None
        self._sparkles: List[int] = []

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._phase = 0

        # bbox đúng theo kích thước ảnh slot (asset)
        bbox = self.canvas.bbox(self.base_id)
        if bbox:
            x1, y1, x2, y2 = bbox
        else:
            cx, cy = self.canvas.coords(self.base_id) or (0, 0)
            x1, y1, x2, y2 = cx - 20, cy - 20, cx + 20, cy + 20

        # refine bbox: actually the image may have transparent padding 8 pixels
        x1 += 8
        y1 += 8
        x2 -= 10
        y2 -= 10

        # pad để viền nằm “đúng viền” hoặc nhô ra/thu vào
        # pad > 0: viền ra ngoài asset; pad < 0: viền ăn vào trong asset
        pad_inner = self.extra_pad - 3  # vòng trong
        if pad_inner < 1:
            pad_inner = 0
        # INNER RECT
        self._ring2 = self.canvas.create_rectangle(
            x1 - pad_inner, y1 - pad_inner, x2 + pad_inner, y2 + pad_inner,
            outline="#FFF2B0", width=1,
            tags=(self.fx_tag,),
            state="disabled",
        )

        # đảm bảo: fx nằm trên ảnh, text nằm trên fx
        try:
            self.canvas.tag_raise(self.fx_tag, self.base_id)
            self.canvas.tag_raise(self.text_id, self.fx_tag)
        except Exception:
            pass

        self._tick()

    def stop(self) -> None:
        self._running = False
        if self._after:
            try:
                self.root.after_cancel(self._after)
            except Exception:
                pass
            self._after = None

        try:
            self.canvas.delete(self.fx_tag)  # xoá toàn bộ item hoverfx
        except Exception:
            pass

        self._ring1 = None
        self._ring2 = None
        self._sparkles.clear()
    
    def _tick(self) -> None:
        if not self._running:
            return

        self._phase += 1

        bbox = self.canvas.bbox(self.base_id)
        if bbox:
            x1, y1, x2, y2 = bbox
        else:
            cx, cy = self.canvas.coords(self.base_id) or (0, 0)
            x1, y1, x2, y2 = cx - 20, cy - 20, cx + 20, cy + 20

        # refine bbox: actually the image may have transparent padding 8 pixels
        x1 += 8
        y1 += 8
        x2 -= 10
        y2 -= 10

        # pulse nhẹ
        pulse = 3 * math.sin(self._phase * 0.35)
        pad_inner = max(1.0, (self.extra_pad - 3) + pulse * 0.6)

        # màu nhấp nháy
        if (self._phase // 4) % 2 == 0:
            c1, c2, c3 = "#FFD24A", "#FFF2B0", "#FFFFFF"
        else:
            c1, c2, c3 = "#FFF2B0", "#FFD24A", "#FFE37A"
        if self._ring2:
            self.canvas.coords(self._ring2, x1 - pad_inner, y1 - pad_inner, x2 + pad_inner, y2 + pad_inner)
            self.canvas.itemconfig(self._ring2, outline=c2)

        self._after = self.root.after(self.fps_ms, self._tick)



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
        is_admin: bool = True,
    ) -> None:

        self.is_admin = bool(is_admin)     # <-- ADD
        self._hovering = False             # <-- ADD
        self._leave_job: Optional[str] = None  # <-- ADD (debounce leave)

        self.root = root
        self.canvas = canvas
        self.assets = assets
        self.tag = tag
        self.hit_tag = f"{self.tag}__hit"
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
            tags=(self.tag, self.hit_tag, f"{self.tag}__img"),
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
            tags=(self.tag, self.hit_tag, f"{self.tag}__text"),
        )
        self._apply_auto_font(text)

        self._hover_fx_enabled = True
        self._hover_fx = _RectPulse(
            root=self.root,
            canvas=self.canvas,
            tag=self.tag,
            base_id=self.img_id,
            text_id=self.text_id,
            fps_ms=15,      # 25 fps-ish
            extra_pad=6,
        )

        self._testing_fx = _OrbitDotsTrailHoverFX(
            root=root,
            canvas=canvas,
            tag=tag,
            base_id=self.img_id,      # hoặc base image id của slot
            text_id=self.text_id,
            fps_ms=20,
            speed_px_s=240,

        )

        # Bind events
        self.canvas.tag_bind(f"{self.tag}", "<Enter>", self._on_enter)
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
        if "font" in kw:
            self.canvas.itemconfig(self.text_id, font=kw["font"])
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

        if "is_admin" in kw:
            self.is_admin = bool(kw["is_admin"])
            self._sync_fx()


    def set_disabled(self, disabled: bool = True):
        self._set_state("disabled" if disabled else "normal")

    def set_status(self, status: SlotStatus):
        # tolerant: nếu status lạ thì fallback idle
        if status not in ("idle", "testing", "pass", "fail", "stand_by", "item", "unknown"):
            status = "idle"  # type: ignore[assignment]
        self._status = status

        key = self._status_to_key(status, self.canvas.itemcget(self.text_id, "text"))
        
        self.canvas.itemconfig(self.img_id, image=self.assets[key])

        # text color depends on disabled
        if self._disabled:
            self.canvas.itemconfig(self.text_id, fill=self.text_fill_disabled)
        else:
            self.canvas.itemconfig(self.text_id, fill=self.text_fill)

        self._sync_fx()

    def set_text(self, text: str):
        self.canvas.itemconfig(self.text_id, text=text)

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

        # --- ADD ---
        try:
            self._hover_fx.stop()
        except Exception:
            pass

        try:
            self._testing_fx.stop()
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

            # --- ADD ---
            try:
                self._hover_fx.stop()
            except Exception:
                pass

            try:
                self._testing_fx.stop()
            except Exception:
                pass

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

    def _status_to_key(self, status: SlotStatus, text= None) -> str:
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

        return _pick_scaled_key(self.canvas, self.assets, base)


    # 2) thêm helper auto-font (dựa theo bề ngang tile, không dùng canvas.winfo_width())
    def _auto_pick_font(self, label: str) -> tuple:
        s = (label or "").strip().replace("\n", " ")
        words = [w for w in s.split(" ") if w]
        max_len = max((len(w) for w in words), default=0)

        # tile width: lưu từ init (xem phần dưới)
        w = int(getattr(self, "_tile_w", 120))

        # bucket theo tile size
        if w <= 70:
            base = 9
            # chữ dài -> giảm
            if max_len >= 8: base = 4
            elif max_len == 7: base = 5
            elif max_len == 6: base = 6
            elif max_len == 5: base = 7
            elif max_len == 4: base = 8
        elif w <= 110:
            base = 11
            if max_len >= 8: base = 5
            elif max_len == 7: base = 6
            elif max_len == 6: base = 7
            elif max_len == 5: base = 9
            elif max_len == 4: base = 10
        else:
            base = 13
            if max_len >= 8: base = 7
            elif max_len == 7: base = 8
            elif max_len == 6: base = 9
            elif max_len == 5: base = 10
            elif max_len == 4: base = 12

        return ("Tektur", base, "bold")


    def _apply_auto_font(self, label: str) -> None:
        if not hasattr(self, "text_id"):
            return
        try:
            self.canvas.itemconfig(self.text_id, font=self._auto_pick_font(label))
        except Exception:
            pass
    # ---------------------------
    # Event handlers
    # ---------------------------
    def _on_enter(self, _event):
        if self._disabled:
            self._set_cursor("")
            return "break"

        # cancel leave debounce
        if self._leave_job:
            try: self.root.after_cancel(self._leave_job)
            except Exception: pass
            self._leave_job = None

        self._hovering = True

        # Hover FX chỉ khi allowed (admin + not testing)
        if self._hover_fx_allowed():
            try:
                self._hover_fx.start()
            except Exception:
                pass

        # cursor logic giữ nguyên...
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

        # debounce: nếu chỉ chuyển giữa image <-> text (cùng tag) thì không stop
        if self._leave_job:
            try: self.root.after_cancel(self._leave_job)
            except Exception: pass
            self._leave_job = None

        def _check_leave():
            self._leave_job = None
            if not self._pointer_in_slot():
                self._hovering = False
                # chỉ tắt hover_fx; testing_fx KHÔNG liên quan hover
                try:
                    self._hover_fx.stop()
                except Exception:
                    pass

        self._leave_job = self.root.after(60, _check_leave)
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
        # If not status testing the start command()
        if self._status != "testing":
            if self.is_admin:
                self.command()
        return "break"

    def _pointer_in_slot(self) -> bool:
        # kiểm tra con trỏ có đang nằm trên bất kỳ item nào mang self.tag không
        try:
            px = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
            py = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
            x = self.canvas.canvasx(px)
            y = self.canvas.canvasy(py)
            items = self.canvas.find_overlapping(x, y, x, y)
            for it in items:
                if self.tag in self.canvas.gettags(it):
                    return True
        except Exception:
            pass
        return False

    def _hover_fx_allowed(self) -> bool:
        # Hover FX chỉ khi: admin + enabled + không disabled + KHÔNG phải testing
        return (not self._disabled) and self._hover_fx_enabled and self.is_admin and (self._status != "testing")

    def _sync_fx(self) -> None:
        """
        Rule:
        - status == testing: bật testing_fx, tắt hover_fx
        - status != testing: tắt testing_fx, hover_fx chỉ bật nếu đang hover và allowed
        """
        if self._disabled:
            try: self._hover_fx.stop()
            except Exception: pass
            try: self._testing_fx.stop()
            except Exception: pass
            return

        if self._status == "testing":
            # testing ưu tiên: luôn bật, không phụ thuộc hover/admin
            try: self._hover_fx.stop()
            except Exception: pass
            try: self._testing_fx.start()
            except Exception: pass
        else:
            # không testing: tắt testing_fx
            try: self._testing_fx.stop()
            except Exception: pass

            # hover_fx theo hover + allowed
            if self._hovering and self._hover_fx_allowed():
                try: self._hover_fx.start()
                except Exception: pass
            else:
                try: self._hover_fx.stop()
                except Exception: pass


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
    is_admin=False,
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
        # canvas_width = canvas.winfo_width()
        # if canvas_width <= 800:
            idle_status += "_0.5"
            testing_status += "_0.5"
            pass_status += "_0.5"
            fail_status += "_0.5" 
            stand_by_status += "_0.5" # "item"
            item_status += "_0.5" # "item"
            unknown_status += "_0.5" # "idle"

        # elif canvas_width <= 1200:
        #     idle_status += "_0.75"
        #     testing_status += "_0.75"
        #     pass_status += "_0.75"
        #     fail_status += "_0.75"
        #     stand_by_status += "_0.75" # "item"
        #     item_status += "_0.75" # "item"
        #     unknown_status += "_0.75" # "idle"

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
        is_admin=is_admin,
    )
