from __future__ import annotations

import queue
import time
import tkinter as tk
from dataclasses import dataclass
from collections import deque
from typing import Any, Dict, Deque, Optional, Tuple, List


@dataclass
class LogPanelSkins:
    bg: str = "fixture_info_frame_bg"   # base key; widget sẽ tự pick _0.5/_0.75 nếu có


def _pick_scaled_key(canvas: tk.Canvas, assets: Dict[str, Any], base_key: str) -> str:
    """Chọn key _0.5/_0.75 nếu tồn tại trong assets, giống các widget trước."""
    if base_key.endswith("_0.5") or base_key.endswith("_0.75"):
        return base_key

    try:
        w = int(canvas.winfo_width())
    except Exception:
        w = 0

    # nếu canvas chưa ready -> ưu tiên 0.75 (đỡ bé quá)
    if w <= 1:
        k = f"{base_key}_0.75"
        return k if k in assets else base_key

    if w <= 800:
        k = f"{base_key}_0.5"
        if k in assets:
            return k
    if w <= 1200:
        k = f"{base_key}_0.75"
        if k in assets:
            return k

    return base_key


def _norm_color(c: str) -> str:
    """Chuẩn hoá màu theo 4 màu bạn yêu cầu."""
    t = (c or "").strip().lower()
    if t in ("red", "r", "đỏ", "do"):
        return "red"
    if t in ("yellow", "y", "vàng", "vang"):
        return "yellow"
    if t in ("blue", "b", "xanh", "xanh dương", "xanhduong"):
        return "blue"
    if t in ("green", "g", "xanh lá", "xanhla", "xanh lá cây", "xanhlacay"):
        return "green"
    return "white"


class CanvasLogWidget:
    """
    Canvas Log Widget:
      - background asset (auto scale)
      - Text widget đặt vào canvas bằng create_window
      - lưu buffer + hiển thị last N lines
      - scroll ẩn scrollbar
      - pump log an toàn bằng after loop (batch + trim)
    
    Usage:

    from src.gui.widgets.canvas_log_widget import bind_canvas_log_widget

    self.logs = bind_canvas_log_widget(
        root=self.root,
        canvas=self._canvas,
        assets=self.assets,
        tag="logs_panel",
        x=600, y=260,
        bg_key="info_frame_bg",
        ui_max_lines=100,
        buf_max_lines=500,
    )

    # bơm log (có thể gọi spam, hoặc từ thread khác)
    self.logs.emit("Device connected", "white")
    self.logs.emit("ERROR: timeout", "red")
    self.logs.emit("Warning: low signal", "yellow")
    self.logs.emit("RX OK", "blue")

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
        skins: LogPanelSkins = LogPanelSkins(),
        # layout
        pad: Tuple[int, int, int, int] = (14, 14, 14, 14),   # left, top, right, bottom
        # text options
        font: Any = ("Tektur", 10),
        text_bg: str = "#652200",
        wrap: str = "word",
        # buffer limits
        ui_max_lines: int = 100,
        buf_max_lines: int = 500,
        # pump safety
        pump_ms: int = 60,
        max_batch_per_pump: int = 200,
        auto_refresh_on_resize: bool = True,
        refresh_debounce_ms: int = 150,
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.assets = assets
        self.tag = tag
        self.anchor = anchor

        self.skins = skins
        self.pad_l, self.pad_t, self.pad_r, self.pad_b = map(int, pad)

        self.ui_max_lines = int(ui_max_lines)
        self.buf_max_lines = int(buf_max_lines)

        self.pump_ms = int(pump_ms)
        self.max_batch_per_pump = int(max_batch_per_pump)

        self._destroyed = False

        # thread-safe input queue (emit từ bất kỳ thread nào cũng OK)
        self._q: "queue.Queue[Tuple[str, str]]" = queue.Queue()

        # lưu buffer logs (text, color)
        self.log_buffer: Deque[Tuple[str, str]] = deque(maxlen=self.buf_max_lines)

        # background
        self._bg_base = self.skins.bg
        self._bg_key = _pick_scaled_key(self.canvas, self.assets, self._bg_base)

        self.bg_id = self.canvas.create_image(
            x, y,
            image=self.assets[self._bg_key],
            anchor=self.anchor,
            tags=(self.tag, f"{self.tag}__bg"),
        )

        # Text frame inside canvas
        self.frame = tk.Frame(self.root, bg=text_bg, highlightthickness=0, bd=0)
        self.text = tk.Text(
            self.frame,
            bg=text_bg,
            fg="white",
            highlightthickness=0,
            bd=0,
            wrap=wrap,
            font=font,
            insertwidth=0,
        )
        self.text.pack(expand=True, fill="both")

        # text tags for colors
        self.text.tag_configure("white", foreground="white")
        self.text.tag_configure("red", foreground="#ff4a4a")
        self.text.tag_configure("yellow", foreground="#ffd24a")
        self.text.tag_configure("blue", foreground="#5aa7ff")
        self.text.tag_configure("green", foreground="#68ff5a")

        # make it read-only (insert will temporarily enable)
        self.text.configure(state="disabled")

        # create_window for clipping scroll area inside asset
        self.window_id = self.canvas.create_window(
            0, 0,
            window=self.frame,
            anchor="nw",
            width=10,
            height=10,
            tags=(self.tag, f"{self.tag}__win"),
        )
        self._layout_from_bg()

        # scroll bindings (hidden scrollbar)
        self._bind_scroll()

        # pump loop (safe even if emit called spam)
        self._after_id: Optional[str] = None
        self._schedule_pump()

        # auto refresh skin on resize (debounced)
        self._auto_refresh = bool(auto_refresh_on_resize)
        self._refresh_debounce_ms = int(refresh_debounce_ms)
        self._resize_after_id: Optional[str] = None
        if self._auto_refresh:
            self._bind_canvas_resize()

    # -------------------------
    # Public API
    # -------------------------
    def emit(self, line: str, color: str = "white") -> None:
        """Nhận 1 dòng log (có thể gọi từ thread khác)."""
        if self._destroyed:
            return
        txt = str(line).rstrip("\n")
        c = _norm_color(color)
        # Queue không giới hạn; nhưng ta pump + trim -> không crash.
        # (Nếu bạn muốn chặn queue quá lớn, có thể thêm guard ở đây.)
        self._q.put((txt, c))

    def emit_many(self, lines: List[str], color: str = "white") -> None:
        c = _norm_color(color)
        for s in lines:
            self.emit(s, c)

    def clear(self) -> None:
        """Xoá UI và buffer."""
        self.log_buffer.clear()
        try:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.configure(state="disabled")
        except Exception:
            pass

    def refresh_skin(self) -> None:
        """Re-pick bg key theo canvas width và relayout (an toàn)."""
        if self._destroyed:
            return
        try:
            new_key = _pick_scaled_key(self.canvas, self.assets, self._bg_base)
            if new_key != self._bg_key and new_key in self.assets:
                self._bg_key = new_key
                self.canvas.itemconfig(self.bg_id, image=self.assets[self._bg_key])
            self._layout_from_bg()
        except Exception:
            pass

    def destroy(self) -> None:
        self._destroyed = True
        try:
            if self._after_id:
                self.root.after_cancel(self._after_id)
        except Exception:
            pass
        try:
            if self._resize_after_id:
                self.root.after_cancel(self._resize_after_id)
        except Exception:
            pass
        try:
            self.canvas.delete(self.bg_id)
        except Exception:
            pass
        try:
            self.canvas.delete(self.window_id)
        except Exception:
            pass
        try:
            self.frame.destroy()
        except Exception:
            pass

    @property
    def ids(self) -> Tuple[int, int]:
        return (self.bg_id, self.window_id)

    # -------------------------
    # Internals: layout & scroll
    # -------------------------
    def _layout_from_bg(self) -> None:
        bbox = self.canvas.bbox(self.bg_id)
        if not bbox:
            return
        x1, y1, x2, y2 = bbox

        inner_x = x1 + self.pad_l
        inner_y = y1 + self.pad_t
        inner_w = max(10, (x2 - x1) - (self.pad_l + self.pad_r))
        inner_h = max(10, (y2 - y1) - (self.pad_t + self.pad_b))

        self.canvas.coords(self.window_id, inner_x, inner_y)
        self.canvas.itemconfig(self.window_id, width=inner_w, height=inner_h)

    def _bind_scroll(self) -> None:
        # Windows / Mac
        self.text.bind("<MouseWheel>", self._on_mousewheel, add="+")
        # Linux
        self.text.bind("<Button-4>", self._on_mousewheel_linux, add="+")
        self.text.bind("<Button-5>", self._on_mousewheel_linux, add="+")

        # also bind frame so user can scroll when pointer is on empty area
        self.frame.bind("<MouseWheel>", self._on_mousewheel, add="+")
        self.frame.bind("<Button-4>", self._on_mousewheel_linux, add="+")
        self.frame.bind("<Button-5>", self._on_mousewheel_linux, add="+")

    def _on_mousewheel(self, e):
        try:
            # Windows: e.delta is multiple of 120
            delta = int(e.delta)
            if delta == 0:
                return "break"
            steps = -1 if delta > 0 else 1
            self.text.yview_scroll(steps, "units")
        except Exception:
            pass
        return "break"

    def _on_mousewheel_linux(self, e):
        try:
            if e.num == 4:
                self.text.yview_scroll(-1, "units")
            elif e.num == 5:
                self.text.yview_scroll(1, "units")
        except Exception:
            pass
        return "break"

    def _bind_canvas_resize(self) -> None:
        def handler(_evt=None):
            if self._destroyed:
                return
            # debounce để tránh gọi refresh quá nhiều
            try:
                if self._resize_after_id:
                    self.root.after_cancel(self._resize_after_id)
            except Exception:
                pass
            self._resize_after_id = self.root.after(self._refresh_debounce_ms, self.refresh_skin)

        try:
            self.canvas.bind("<Configure>", handler, add="+")
        except TypeError:
            # fallback nếu Tk không hỗ trợ add kw
            self.canvas.bind("<Configure>", handler)

    # -------------------------
    # Pump loop (SAFE)
    # -------------------------
    def _schedule_pump(self) -> None:
        if self._destroyed:
            return
        self._after_id = self.root.after(self.pump_ms, self._pump_once)

    def _pump_once(self) -> None:
        if self._destroyed:
            return

        try:
            drained = 0
            batch: List[Tuple[str, str]] = []

            while drained < self.max_batch_per_pump:
                try:
                    item = self._q.get_nowait()
                except queue.Empty:
                    break
                batch.append(item)
                drained += 1

            if batch:
                # update buffer
                for txt, c in batch:
                    self.log_buffer.append((txt, c))

                # append to UI (read-only safe)
                self._append_to_text(batch)

                # trim UI to last ui_max_lines
                self._trim_text_to_last_n(self.ui_max_lines)

        except Exception:
            # Không để crash dù pump bị gọi dồn / widget đang destroy giữa chừng
            pass
        finally:
            self._schedule_pump()

    def _append_to_text(self, batch: List[Tuple[str, str]]) -> None:
        try:
            self.text.configure(state="normal")
            for txt, c in batch:
                self.text.insert("end", txt + "\n", (c,))
            self.text.configure(state="disabled")
            # auto scroll to end (nhưng vẫn cho user scroll lên: nếu bạn muốn giữ vị trí,
            # có thể thêm logic "only autoscroll when at bottom")
            self.text.see("end")
        except Exception:
            try:
                self.text.configure(state="disabled")
            except Exception:
                pass

    def _trim_text_to_last_n(self, n: int) -> None:
        if n <= 0:
            return
        try:
            # số dòng hiện tại
            end_index = self.text.index("end-1c")         # e.g. "123.0"
            total_lines = int(end_index.split(".")[0])

            extra = total_lines - n
            if extra > 0:
                self.text.configure(state="normal")
                # delete first 'extra' lines
                self.text.delete("1.0", f"{extra + 1}.0")
                self.text.configure(state="disabled")
        except Exception:
            try:
                self.text.configure(state="disabled")
            except Exception:
                pass


def bind_canvas_log_widget(
    *,
    root: tk.Misc,
    canvas: tk.Canvas,
    assets: Dict[str, Any],
    tag: str,
    x: int,
    y: int,
    anchor: str = "center",
    bg_key: str = "fixture_info_frame_bg",
    pad: Tuple[int, int, int, int] = (14, 14, 14, 14),
    font: Any = ("Tektur", 10),
    text_bg: str = "#652200",
    ui_max_lines: int = 100,
    buf_max_lines: int = 500,
    pump_ms: int = 60,
) -> CanvasLogWidget:
    """
    Canvas Log Widget:
      - background asset (auto scale)
      - Text widget đặt vào canvas bằng create_window
      - lưu buffer + hiển thị last N lines
      - scroll ẩn scrollbar
      - pump log an toàn bằng after loop (batch + trim)
    
    Usage:

    from src.gui.widgets.canvas_log_widget import bind_canvas_log_widget

    self.logs = bind_canvas_log_widget(
        root=self.root,
        canvas=self._canvas,
        assets=self.assets,
        tag="logs_panel",
        x=600, y=260,
        bg_key="info_frame_bg",
        ui_max_lines=100,
        buf_max_lines=500,
    )

    # bơm log (có thể gọi spam, hoặc từ thread khác)
    self.logs.emit("Device connected", "white")
    self.logs.emit("ERROR: timeout", "red")
    self.logs.emit("Warning: low signal", "yellow")
    self.logs.emit("RX OK", "blue")

    """
    skins = LogPanelSkins(bg=bg_key)
    return CanvasLogWidget(
        root=root,
        canvas=canvas,
        assets=assets,
        tag=tag,
        x=x,
        y=y,
        anchor=anchor,
        skins=skins,
        pad=pad,
        font=font,
        text_bg=text_bg,
        ui_max_lines=ui_max_lines,
        buf_max_lines=buf_max_lines,
        pump_ms=pump_ms,
    )
