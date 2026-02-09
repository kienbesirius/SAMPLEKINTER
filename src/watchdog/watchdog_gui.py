import os, sys, json, socket, subprocess, platform
from pathlib import Path

WD_PORT = 43999  # chọn 1 port cố định localhost
WD_HOST = "127.0.0.1"

def _is_windows() -> bool:
    return platform.system().lower().startswith("win")

def _spawn_detached(exe: Path, args: list[str]) -> None:
    # không tạo terminal, không inherit stdio
    kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }

    if _is_windows():
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

    subprocess.Popen([str(exe), *args], **kwargs)

def _wd_send(payload: dict, timeout=0.25) -> bool:
    try:
        with socket.create_connection((WD_HOST, WD_PORT), timeout=timeout) as s:
            s.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            # optional: read ack
            s.settimeout(timeout)
            _ = s.recv(64)
        return True
    except Exception:
        return False

def ensure_watchdog_running(wd_exe: Path, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)

    # 1) ping watchdog nếu đang chạy
    if not _wd_send({"cmd": "ping"}):
        # 2) chưa chạy -> spawn watchdog
        _spawn_detached(wd_exe, ["--port", str(WD_PORT), "--log-dir", str(log_dir)])

        # 3) thử connect nhanh vài lần (rất ngắn)
        for _ in range(10):
            if _wd_send({"cmd": "ping"}):
                break

    # 4) register PID hiện tại cho watchdog theo dõi
    _wd_send({
        "cmd": "register",
        "pid": os.getpid(),
        "app_argv": sys.argv,          # để watchdog có thể restart app nếu muốn
        "cwd": os.getcwd(),
    })

# --- dùng ở AppGUI.__init__ hoặc main() ---
# wd_exe = app_dir() / "bin" / ("watchdog.exe" nếu win else "watchdog")
# ensure_watchdog_running(wd_exe, app_dir()/ "logs" / "watchdog")
