from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import os
import re
import subprocess
import sys
import tkinter as tk

@dataclass(frozen=True)
class Monitor:
    x: int
    y: int
    width: int
    height: int
    is_primary: bool = False
    name: str = ""

def _tk_geom(w: int, h: int, x: int, y: int) -> str:
    # Dùng +{x}+{y} để negative thành "+-1920" (hay dùng để đặt monitor bên trái)
    return f"{int(w)}x{int(h)}+{int(x)}+{int(y)}"

def _get_monitors_screeninfo() -> List[Monitor]:
    from screeninfo import get_monitors as _get  # type: ignore
    mons: List[Monitor] = []
    for m in _get():
        mons.append(Monitor(
            x=int(getattr(m, "x", 0)),
            y=int(getattr(m, "y", 0)),
            width=int(getattr(m, "width", 0)),
            height=int(getattr(m, "height", 0)),
            is_primary=bool(getattr(m, "is_primary", False)),
            name=str(getattr(m, "name", "")),
        ))
    mons.sort(key=lambda a: (a.x, a.y))
    return mons

def _get_monitors_windows_ctypes() -> List[Monitor]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
            ("szDevice", wintypes.WCHAR * 32),
        ]

    MONITORINFOF_PRIMARY = 1

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(RECT),
        wintypes.LPARAM,
    )

    out: List[Monitor] = []

    def _cb(hMon, hdc, lprc, lparam):
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if user32.GetMonitorInfoW(hMon, ctypes.byref(info)):
            x = int(info.rcMonitor.left)
            y = int(info.rcMonitor.top)
            w = int(info.rcMonitor.right - info.rcMonitor.left)
            h = int(info.rcMonitor.bottom - info.rcMonitor.top)
            primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
            name = str(info.szDevice)
            if w > 0 and h > 0:
                out.append(Monitor(x, y, w, h, primary, name))
        return True

    user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_cb), 0)

    if out:
        out.sort(key=lambda a: (a.x, a.y))
    return out

def _get_monitors_linux_xrandr() -> List[Monitor]:
    # X11: xrandr --query
    # Dòng thường gặp: "HDMI-1 connected primary 1920x1080+0+0 ..."
    try:
        txt = subprocess.check_output(["xrandr", "--query"], text=True, stderr=subprocess.STDOUT)
    except Exception:
        return []

    out: List[Monitor] = []
    for line in txt.splitlines():
        if " connected" not in line:
            continue
        name = line.split()[0].strip()
        primary = (" primary " in f" {line} ")
        m = re.search(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", line)
        if not m:
            continue
        w, h, x, y = map(int, m.groups())
        if w > 0 and h > 0:
            out.append(Monitor(x, y, w, h, primary, name))

    out.sort(key=lambda a: (a.x, a.y))
    return out

def get_monitors(root: Optional[tk.Misc] = None) -> List[Monitor]:
    """
    Trả về list monitor có geometry chuẩn.
    Ưu tiên screeninfo; fallback Windows ctypes / Linux xrandr; cuối cùng fallback Tk (1 monitor).
    """
    # 1) screeninfo (khuyến nghị)
    try:
        mons = _get_monitors_screeninfo()
        if mons:
            return mons
    except Exception:
        pass

    # 2) OS fallback
    if os.name == "nt":
        mons = _get_monitors_windows_ctypes()
        if mons:
            return mons
    elif sys.platform.startswith("linux"):
        mons = _get_monitors_linux_xrandr()
        if mons:
            return mons

    # 3) Tk fallback: chỉ 1 monitor (không tách được)
    if root is not None:
        try:
            w = int(root.winfo_screenwidth())
            h = int(root.winfo_screenheight())
            return [Monitor(0, 0, w, h, True, "tk-primary")]
        except Exception:
            pass

    return [Monitor(0, 0, 1920, 1080, True, "fallback")]

def monitor_from_point(monitors: List[Monitor], px: int, py: int) -> Optional[Monitor]:
    for m in monitors:
        if m.width <= 0 or m.height <= 0:
            continue
        if m.x <= px < m.x + m.width and m.y <= py < m.y + m.height:
            return m
    return None

def fullscreen_on_monitor(win: tk.Tk | tk.Toplevel, mon: Monitor) -> None:
    """
    Đưa window vào đúng monitor + fullscreen. Ưu tiên -fullscreen, fallback overrideredirect.
    """
    # Đặt vị trí trước (nhiều WM cần move trước rồi fullscreen mới đúng monitor)
    try:
        win.attributes("-fullscreen", False)
    except Exception:
        pass

    try:
        win.withdraw()
    except Exception:
        pass

    win.geometry(_tk_geom(300, 200, mon.x + 30, mon.y + 30))
    win.update_idletasks()
    win.update()

    try:
        win.deiconify()
    except Exception:
        pass

    # Fullscreen
    try:
        win.overrideredirect(False)
        win.attributes("-fullscreen", True)
    except Exception:
        # Borderless full-rect monitor
        win.attributes("-fullscreen", False)
        win.overrideredirect(True)
        win.geometry(_tk_geom(mon.width, mon.height, mon.x, mon.y))

    win.update_idletasks()
    win.update()
