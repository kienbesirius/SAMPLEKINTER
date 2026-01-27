from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import tkinter as tk

@dataclass(frozen=True)
class Monitor:
    x: int
    y: int
    width: int
    height: int
    is_primary: bool = False
    name: str = ""

def get_monitors() -> List[Monitor]:
    """
    Ưu tiên dùng screeninfo để lấy đúng geometry từng màn hình.
    pip install screeninfo
    """
    try:
        from screeninfo import get_monitors as _get
        mons = []
        for m in _get():
            mons.append(Monitor(
                x=int(getattr(m, "x", 0)),
                y=int(getattr(m, "y", 0)),
                width=int(getattr(m, "width", 0)),
                height=int(getattr(m, "height", 0)),
                is_primary=bool(getattr(m, "is_primary", False)),
                name=str(getattr(m, "name", "")),
            ))
        # sort để ổn định (theo x,y)
        mons.sort(key=lambda a: (a.x, a.y))
        return mons
    except Exception:
        # Fallback: Tk chỉ biết virtual root (tổng 2 màn), không tách từng monitor được
        # => trả về 1 "monitor" bao trùm.
        # Nếu bạn cần tách monitor mà không dùng screeninfo, ta sẽ dùng xrandr/ctypes riêng.
        return [Monitor(0, 0, 0, 0, True, "virtual")]

def monitor_from_point(monitors: List[Monitor], px: int, py: int) -> Optional[Monitor]:
    for m in monitors:
        if m.width <= 0 or m.height <= 0:
            continue
        if m.x <= px < m.x + m.width and m.y <= py < m.y + m.height:
            return m
    return None

def fullscreen_on_monitor(win: tk.Tk | tk.Toplevel, mon: Monitor) -> None:
    """
    Đưa window vào đúng monitor + fullscreen.
    """
    # Move window vào monitor (đặt tạm size nhỏ để WM chắc chắn “đưa” qua màn)
    win.attributes("-fullscreen", False)
    win.geometry(f"200x200+{mon.x + 20}+{mon.y + 20}")
    win.update_idletasks()
    win.update()

    # Bật fullscreen
    try:
        win.attributes("-fullscreen", True)
    except Exception:
        # fallback: borderless + geometry full monitor
        win.overrideredirect(True)
        win.geometry(f"{mon.width}x{mon.height}+{mon.x}+{mon.y}")
    win.update_idletasks()
    win.update()
