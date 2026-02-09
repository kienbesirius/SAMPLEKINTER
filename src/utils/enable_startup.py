# src/utils/enable_startup.py
from __future__ import annotations

import os
import sys
import stat
import re
import tempfile
import shlex
import platform
from pathlib import Path

from src.utils.resource_path import external_path

APP_NAME = "FixtureHealthCare"
DISPLAY_NAME = "Fixture Health Care"
APP_ID = "Fixturehealthcare"
# -------------------------- helpers --------------------------
def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def _is_linux() -> bool:
    return platform.system().lower() == "linux"


def _slugify(name: str) -> str:
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "app"


def _atomic_write_text(path: str, text: str) -> None:
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".autostart_", dir=d, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except Exception:
            pass


# -------------------------- UBUNTU (.desktop autostart) --------------------------
def _read_desktop(path: str) -> dict:
    data = {}
    if not os.path.exists(path):
        return data
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line == "[Desktop Entry]":
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    return data


def _linux_autostart_dir() -> str:
    return os.path.expanduser("~/.config/autostart")


def _linux_autostart_paths() -> tuple[str, str]:
    d = _linux_autostart_dir()
    return (
        os.path.join(d, f"{APP_NAME}.desktop"),
        os.path.join(d, f"{_slugify(APP_NAME)}.desktop"),
    )


def _linux_pick_desktop_file() -> str:
    p_old, p_slug = _linux_autostart_paths()
    if os.path.exists(p_old):
        return p_old
    if os.path.exists(p_slug):
        return p_slug
    return p_old


def _linux_exec_cmd() -> tuple[str, str]:
    """
    Returns (Exec, TryExec)
    - frozen: Exec = "/abs/app.exe"
    - dev:    Exec = "/abs/python3" "/abs/gui_check_fixture.py"
    """
    if getattr(sys, "frozen", False):
        exe = os.path.abspath(sys.executable)
        return (shlex.quote(exe), shlex.quote(exe))

    py = os.path.abspath(sys.executable)
    script = os.path.abspath(sys.argv[0])
    exec_cmd = f"{shlex.quote(py)} {shlex.quote(script)}"
    return (exec_cmd, shlex.quote(py))


def enable_autostart(log_callback=print) -> bool:
    """
    Ubuntu per-user autostart via ~/.config/autostart/*.desktop
    """
    if not _is_linux():
        return False

    os.makedirs(_linux_autostart_dir(), exist_ok=True)

    desktop_file = _linux_pick_desktop_file()
    current = _read_desktop(desktop_file)

    exec_cmd, try_exec = _linux_exec_cmd()
    icon_path = external_path("app-icon.svg")
    if not icon_path or not os.path.exists(icon_path):
        icon_path = None

    new_data = dict(current)
    new_data.update(
        {
            "Name": DISPLAY_NAME,
            "Exec": exec_cmd,
            "TryExec": try_exec,
            "Type": "Application",
            "Terminal": "false",
            "X-GNOME-Autostart-enabled": "true",
            "StartupWMClass": APP_NAME,
            "X-GNOME-Application-ID": APP_ID,
        }
    )
    if icon_path:
        new_data["Icon"] = icon_path

    ordered_keys = [
        "Name",
        "Comment",
        "Exec",
        "TryExec",
        "Icon",
        "Type",
        "Terminal",
        "X-GNOME-Autostart-enabled",
        "OnlyShowIn",
        "StartupWMClass",
        "X-GNOME-Application-ID",
    ]

    lines = ["[Desktop Entry]"]
    seen = set()
    for k in ordered_keys:
        if k in new_data:
            lines.append(f"{k}={new_data[k]}")
            seen.add(k)
    for k, v in new_data.items():
        if k not in seen:
            lines.append(f"{k}={v}")

    _atomic_write_text(desktop_file, "\n".join(lines) + "\n")

    # 0644 là đủ, nhưng bạn đang set execute bit -> giữ nguyên
    st = os.stat(desktop_file).st_mode
    os.chmod(desktop_file, (st | stat.S_IXUSR))

    created = "created" if not current else "updated"
    log_callback(f"✅ Autostart {created}: {desktop_file}")
    return True


def disable_autostart(log_callback=print) -> bool:
    if not _is_linux():
        return False
    p_old, p_slug = _linux_autostart_paths()
    removed = False
    for p in (p_old, p_slug):
        try:
            if os.path.exists(p):
                os.unlink(p)
                removed = True
        except Exception:
            pass
    if removed:
        log_callback("🧹 Autostart removed.")
    return removed


def is_autostart_enabled() -> bool:
    if _is_linux():
        p_old, p_slug = _linux_autostart_paths()
        return os.path.exists(p_old) or os.path.exists(p_slug)
    return False


# -------------------------- WINDOWS (HKCU Run key, no admin) --------------------------
def _windows_run_value_name() -> str:
    # value name hiển thị trong Run key
    return APP_ID or APP_NAME


def _windows_cmdline() -> str:
    """
    Returns the string stored in HKCU Run:
    - frozen:  "C:\\...\\app.exe"
    - dev:     "C:\\...\\pythonw.exe" "C:\\...\\gui_check_fixture.py"
    """
    if getattr(sys, "frozen", False):
        exe = str(Path(sys.executable).resolve())
        return f"\"{exe}\""

    script = str(Path(os.path.abspath(sys.argv[0])).resolve())
    py = Path(sys.executable).resolve()

    # prefer pythonw.exe để khỏi bật console
    if py.name.lower() == "python.exe":
        pyw = py.with_name("pythonw.exe")
        if pyw.exists():
            py = pyw

    return f"\"{str(py)}\" \"{script}\""


def enable_startup_windows(log_callback=print) -> bool:
    if not _is_windows():
        return False
    try:
        import winreg  # only on Windows

        run_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        name = _windows_run_value_name()
        cmd = _windows_cmdline()

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_path, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, cmd)

        log_callback(f"✅ Startup enabled (HKCU Run): {name} -> {cmd}")
        return True
    except Exception as e:
        log_callback(f"❌ enable_startup_windows failed: {e}")
        return False


def disable_startup_windows(log_callback=print) -> bool:
    if not _is_windows():
        return False
    try:
        import winreg

        run_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        name = _windows_run_value_name()

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_path, 0, winreg.KEY_SET_VALUE) as k:
            try:
                winreg.DeleteValue(k, name)
            except FileNotFoundError:
                return False

        log_callback(f"🧹 Startup removed (HKCU Run): {name}")
        return True
    except Exception as e:
        log_callback(f"❌ disable_startup_windows failed: {e}")
        return False


def is_startup_windows_enabled() -> bool:
    if not _is_windows():
        return False
    try:
        import winreg

        run_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        name = _windows_run_value_name()

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_path, 0, winreg.KEY_READ) as k:
            _v, _t = winreg.QueryValueEx(k, name)
        return True
    except Exception:
        return False


# -------------------------- unified API --------------------------
def enable_startup(log_callback=print) -> bool:
    if _is_windows():
        return enable_startup_windows(log_callback=log_callback)
    if _is_linux():
        return enable_autostart(log_callback=log_callback)
    log_callback("Startup not supported on this OS.")
    return False


def disable_startup(log_callback=print) -> bool:
    if _is_windows():
        return disable_startup_windows(log_callback=log_callback)
    if _is_linux():
        return disable_autostart(log_callback=log_callback)
    log_callback("Startup not supported on this OS.")
    return False


def is_startup_enabled() -> bool:
    if _is_windows():
        return is_startup_windows_enabled()
    if _is_linux():
        return is_autostart_enabled()
    return False
