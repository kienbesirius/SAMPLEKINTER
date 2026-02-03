# src/gui/widgets/center_rect_panel.py
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence, Tuple, Union

AvoidRef = Union[str, int]  # canvas tag hoặc item id


@dataclass
class CenterRectStyle:
    outline: str = "#FFB14A"
    width: int = 3
    fill: str = ""               # "" = transparent (no fill)
    stipple: str = ""            # ví dụ: "gray25" để giả lập trong suốt
    radius: int = 0              # (chưa dùng - Tk canvas không bo góc native)
    inner_pad: int = 14          # padding cho content frame bên trong


class CenterRectPanel:
    """
    Vẽ 1 khung chữ nhật "center panel" trên Canvas, tự co giãn để tránh đè lên
    các widget khác (dựa vào bbox của tags/item_ids trong avoid).

    - Có sẵn `body` (Frame) đặt ở giữa panel để bạn pack/grid widget Tk bình thường.
    - Tự redraw khi root resize (<Configure>).

    Usage:

    from src.gui.widgets.center_rect_panel import bind_center_rect_panel, CenterRectStyle

    # ... sau khi đã tạo slots + logs ...

    avoid = ["com_status", "logs_panel"] + [f"slot{i}_status" for i in range(1, 13)]

    center_panel = bind_center_rect_panel(
        root=win,
        canvas=canvas,
        tag="center_panel",
        avoid=avoid,
        style=CenterRectStyle(
            outline="#FFB14A",
            width=3,
            fill="",          # hoặc "#000000" + stipple="gray25" nếu muốn kiểu mờ
            stipple="",
            inner_pad=16,
        ),
        pad_screen=18,
        pad_avoid=16,
        min_size=(520, 320),
        keep_ratio=None,     # hoặc 16/9 nếu muốn khung “đẹp” theo tỉ lệ
    )

    center_panel.set_title("CENTER AREA")
    widgets["center_panel"] = center_panel

    """
    def __init__(
        self,
        *,
        root: tk.Misc,
        canvas: tk.Canvas,
        tag: str,
        avoid: Optional[Sequence[AvoidRef]] = None,
        style: CenterRectStyle = CenterRectStyle(),
        pad_screen: int = 18,         # padding biên màn hình
        pad_avoid: int = 14,          # padding nới bbox các widget cần tránh
        min_size: Tuple[int, int] = (520, 320),
        max_size: Optional[Tuple[int, int]] = None,  # None = không giới hạn
        keep_ratio: Optional[float] = None,          # None = full available, hoặc 16/9, 4/3...
        state: str = "normal",
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.tag = tag

        try:
            self.canvas.delete(tag)
        except Exception:
            pass
        self.avoid: List[AvoidRef] = list(avoid or [])
        self.style = style

        self.pad_screen = int(pad_screen)
        self.pad_avoid = int(pad_avoid)
        self.min_w, self.min_h = int(min_size[0]), int(min_size[1])
        self.max_size = max_size
        self.keep_ratio = keep_ratio

        self._shown = True

        # rect + title (optional)
        self.rect_id = self.canvas.create_rectangle(
            0, 0, 10, 10,
            outline=self.style.outline,
            width=self.style.width,
            fill=self.style.fill,
            stipple=self.style.stipple if self.style.stipple else "",
            tags=(self.tag, f"{self.tag}__rect"),
        )

        self.title_id = self.canvas.create_text(
            0, 0,
            text="",
            fill="#FFE37A",
            font=("Tektur", 14, "bold"),
            anchor="n",
            tags=(self.tag, f"{self.tag}__title"),
        )

        # content frame (để nhét widget Tk bình thường)
        self._after_redraw: str | None = None
        self._last_layout: tuple | None = None
        self._suspended = False
        
        # self.body = tk.Frame(self.root, bg="", bd=0, highlightthickness=0)
        self.body = tk.Frame(self.canvas, bg=self.style.fill or self.canvas.cget("bg"),
                     bd=0, highlightthickness=0)

        self.win_id = self.canvas.create_window(
            0, 0,
            window=self.body,
            anchor="center",
            width=10,
            height=10,
            tags=(self.tag, f"{self.tag}__win"),
        )

        self.set_state(state)

        # redraw on resize
        self.root.bind("<Configure>", self._on_resize, add="+")

        # initial draw (sau khi các widget khác đã tạo)
        # ✅ defer initial redraw
        self._request_redraw()
    

    def suspend(self, on: bool = True) -> None:
        self._suspended = bool(on)

    def _on_resize(self, _e=None) -> None:
        if self._suspended or (not self._shown):
            return
        self._request_redraw()

    def _request_redraw(self) -> None:
        if self._after_redraw:
            return
        try:
            self._after_redraw = self.root.after_idle(self._redraw_now)
        except Exception:
            self._after_redraw = None

    def _redraw_now(self) -> None:
        self._after_redraw = None

        if not self._shown:
            return

        W = int(self.canvas.winfo_width() or 0)
        H = int(self.canvas.winfo_height() or 0)
        if W <= 2 or H <= 2:
            # geometry chưa sẵn sàng -> thử lại
            try:
                self.root.after(16, self._request_redraw)
            except Exception:
                pass
            return

        # ---- tính layout như redraw() hiện tại ----
        # (bạn có thể copy nội dung redraw() vào đây,
        #  rồi ở cuối build ra key layout để skip nếu không đổi)

        # ví dụ layout key tối thiểu:
        layout_key = (W, H, tuple(self.avoid), self.style.outline, self.style.width,
                      self.style.fill, self.style.stipple, self.style.inner_pad,
                      self.canvas.itemcget(self.title_id, "text"))

        if layout_key == self._last_layout:
            return
        self._last_layout = layout_key

        self.redraw()  # hoặc inline toàn bộ logic redraw vào đây để khỏi tính 2 lần

    # -------------------------
    # Public API (giống style các widget khác)
    # -------------------------
    def configure(self, **kw: Any) -> None:
        if "avoid" in kw:
            self.avoid = list(kw["avoid"] or [])
        if "style" in kw and isinstance(kw["style"], CenterRectStyle):
            self.style = kw["style"]
        if "title" in kw:
            self.set_title(str(kw["title"]))
        if "state" in kw:
            self.set_state(kw["state"])
        if "keep_ratio" in kw:
            self.keep_ratio = kw["keep_ratio"]
        if "min_size" in kw:
            ms = kw["min_size"]
            self.min_w, self.min_h = int(ms[0]), int(ms[1])
        if "pad_screen" in kw:
            self.pad_screen = int(kw["pad_screen"])
        if "pad_avoid" in kw:
            self.pad_avoid = int(kw["pad_avoid"])
        self.redraw()

    def set_title(self, text: str) -> None:
        self.canvas.itemconfig(self.title_id, text=text or "")
        self.redraw()

    def set_state(self, state: str) -> None:
        # "disabled" để panel không bắt event nếu bạn muốn
        self.canvas.itemconfig(self.rect_id, state=state)
        self.canvas.itemconfig(self.title_id, state=state)
        self.canvas.itemconfig(self.win_id, state=state)

    def show(self) -> None:
        if self._shown:
            return
        self._shown = True
        self.set_state("normal")
        self.redraw()

    def hide(self) -> None:
        if not self._shown:
            return
        self._shown = False
        self.set_state("hidden")

    def destroy(self) -> None:
        try:
            self.canvas.delete(self.tag)
        except Exception:
            pass
        try:
            self.body.destroy()
        except Exception:
            pass

    def redraw(self) -> None:
        if not self._shown:
            return

        W = max(2, int(self.canvas.winfo_width() or self.root.winfo_width() or 2))
        H = max(2, int(self.canvas.winfo_height() or self.root.winfo_height() or 2))
        cx, cy = W / 2.0, H / 2.0

        inner = int(self.style.inner_pad)
        border = int(self.style.width)

        title = str(self.canvas.itemcget(self.title_id, "text") or "")
        title_on = bool(title.strip())
        title_space = 34 if title_on else 0  # bạn có thể tune 28~40

        # ------------------------------------------------------------
        # 1) Build danh sách avoid rectangles (đã expand pad_avoid)
        # ------------------------------------------------------------
        avoid_rects = []
        for ref in self.avoid:
            if ref == self.tag:
                continue
            bb = self.canvas.bbox(ref)
            if not bb:
                continue
            avoid_rects.append(_expand(bb, self.pad_avoid))

        # ------------------------------------------------------------
        # 2) Tính initial BODY rect (CONTENT) lớn nhất trong màn hình
        #    BODY = vùng window(self.body) -> cái này là "nội dung"
        # ------------------------------------------------------------
        # trừ pad_screen + inner/border để outer rect không vượt màn hình
        max_half_w = (W / 2.0) - self.pad_screen - inner - border
        max_half_h = (H / 2.0) - self.pad_screen - inner - border - (title_space / 2.0)

        half_w = max(10.0, max_half_w)
        half_h = max(10.0, max_half_h)

        # apply max_size nếu có (tính theo outer -> đổi về body)
        if self.max_size is not None:
            max_outer_w, max_outer_h = int(self.max_size[0]), int(self.max_size[1])
            max_body_w = max(10, max_outer_w - 2 * (inner + border))
            max_body_h = max(10, max_outer_h - 2 * (inner + border) - title_space)
            half_w = min(half_w, max_body_w / 2.0)
            half_h = min(half_h, max_body_h / 2.0)

        # ------------------------------------------------------------
        # 3) Soft-avoid solver:
        #    nếu BODY giao với avoid -> chỉ shrink 1 trục (x hoặc y)
        #    chọn shrink trục nào "mất ít diện tích hơn"
        # ------------------------------------------------------------
        def body_rect(hw, hh):
            return (cx - hw, cy - hh, cx + hw, cy + hh)

        def allowed_half_w_to_avoid(avoid):
            ax1, ay1, ax2, ay2 = avoid
            # muốn không overlap theo X => panel_right <= ax1 OR panel_left >= ax2
            # với center cố định => chỉ khả thi nếu avoid nằm hẳn 1 bên center
            if ax2 <= cx:
                return max(0.0, cx - ax2)
            if ax1 >= cx:
                return max(0.0, ax1 - cx)
            return 0.0  # avoid cắt qua center -> shrink X không giải quyết

        def allowed_half_h_to_avoid(avoid):
            ax1, ay1, ax2, ay2 = avoid
            if ay2 <= cy:
                return max(0.0, cy - ay2)
            if ay1 >= cy:
                return max(0.0, ay1 - cy)
            return 0.0

        # loop vài vòng là đủ vì shrink đơn điệu
        for _ in range(24):
            b = body_rect(half_w, half_h)

            hit = None
            for av in avoid_rects:
                if _intersect(b, av):
                    hit = av
                    break

            if hit is None:
                break

            # candidate shrink theo X / Y
            allow_w = allowed_half_w_to_avoid(hit)
            allow_h = allowed_half_h_to_avoid(hit)

            # nếu cả 2 đều 0 => không thể tránh bằng shrink (avoid nằm giữa)
            if allow_w <= 0.0 and allow_h <= 0.0:
                break

            # shrink theo trục nào giữ được "diện tích" lớn hơn
            area_if_shrink_w = allow_w * half_h if allow_w > 0 else -1
            area_if_shrink_h = half_w * allow_h if allow_h > 0 else -1

            if area_if_shrink_w >= area_if_shrink_h:
                half_w = min(half_w, allow_w)
            else:
                half_h = min(half_h, allow_h)

            # tránh shrink về 0
            half_w = max(20.0, half_w)
            half_h = max(20.0, half_h)

        # NOTE: min_size là "mong muốn", nhưng nếu ép min sẽ đè widget.
        # => chỉ dùng min_size như default, không ép ngược lại sau solver.
        # (Nếu bạn muốn: có thể thử tăng dần tới min và check collide.)

        body_w = int(max(10, 2 * half_w))
        body_h = int(max(10, 2 * half_h))

        # keep_ratio nếu muốn (fit trong body_w/body_h)
        if self.keep_ratio and body_w > 0 and body_h > 0:
            r = float(self.keep_ratio)
            w1 = body_w
            h1 = int(w1 / r)
            h2 = body_h
            w2 = int(h2 * r)
            if h1 <= body_h:
                body_h = max(10, h1)
            else:
                body_w = max(10, w2)

        # ------------------------------------------------------------
        # 4) Từ BODY -> OUTER rect (viền)
        # ------------------------------------------------------------
        panel_w = body_w + 2 * (inner + border)
        panel_h = body_h + 2 * (inner + border) + title_space

        x1 = int(cx - panel_w / 2)
        y1 = int(cy - panel_h / 2)
        x2 = int(cx + panel_w / 2)
        y2 = int(cy + panel_h / 2)

        self.canvas.itemconfig(
            self.rect_id,
            outline=self.style.outline,
            width=self.style.width,
            fill=self.style.fill,
            stipple=self.style.stipple if self.style.stipple else "",
        )
        self.canvas.coords(self.rect_id, x1, y1, x2, y2)

        if title_on:
            self.canvas.coords(self.title_id, int(cx), int(y1 + 10))
            self.canvas.itemconfig(self.title_id, anchor="n", state="normal")
        else:
            self.canvas.itemconfig(self.title_id, state="hidden")

        # body window: luôn là vùng "nội dung" để tránh overlap
        self.canvas.coords(self.win_id, int(cx), int(cy))
        self.canvas.itemconfig(self.win_id, width=body_w, height=body_h)


    # -------------------------
    # events
    # -------------------------
    def _on_resize(self, _e=None) -> None:
        # root resize => redraw
        try:
            if not self.root.winfo_exists():
                return
        except Exception:
            return
        self.redraw()


def bind_center_rect_panel(
    *,
    root: tk.Misc,
    canvas: tk.Canvas,
    tag: str,
    avoid: Optional[Sequence[AvoidRef]] = None,
    style: CenterRectStyle = CenterRectStyle(),
    pad_screen: int = 18,
    pad_avoid: int = 14,
    min_size: Tuple[int, int] = (520, 320),
    max_size: Optional[Tuple[int, int]] = None,
    keep_ratio: Optional[float] = None,
    state: str = "normal",
) -> CenterRectPanel:
    return CenterRectPanel(
        root=root,
        canvas=canvas,
        tag=tag,
        avoid=avoid,
        style=style,
        pad_screen=pad_screen,
        pad_avoid=pad_avoid,
        min_size=min_size,
        max_size=max_size,
        keep_ratio=keep_ratio,
        state=state,
    )


def _intersect(a, b) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    return not (ax2 <= bx1 or ax1 >= bx2 or ay2 <= by1 or ay1 >= by2)

def _expand(bb, pad: int):
    x1, y1, x2, y2 = bb
    return (x1 - pad, y1 - pad, x2 + pad, y2 + pad)

