import argparse, json, os, socket, threading, time, sys, platform, subprocess
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

def is_windows() -> bool:
    return platform.system().lower().startswith("win")

def pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if is_windows():
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
        if handle == 0:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    else:
        try:
            os.kill(pid, 0)
            return True
        except PermissionError:
            return True
        except ProcessLookupError:
            return False
        except Exception:
            return False

def spawn_app(app_argv: list[str], cwd: str | None):
    if not app_argv:
        return
    kwargs = {
        "cwd": cwd or None,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if is_windows():
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        DETACHED_PROCESS = 0x00000008
        CREATE_NO_WINDOW = 0x08000000
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    subprocess.Popen(app_argv, **kwargs)

class Watchdog:
    def __init__(self, port: int, log_dir: Path):
        self.port = port
        self.log_dir = log_dir
        self._lock = threading.Lock()
        self.target_pid: int = 0
        self.target_argv: list[str] = []
        self.target_cwd: str | None = None
        self._stop = False

        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._setup_log()

    def _setup_log(self):
        self.logger = logging.getLogger("watchdog")
        self.logger.setLevel(logging.INFO)
        fh = RotatingFileHandler(
            self.log_dir / "watchdog.log",
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s")
        fh.setFormatter(fmt)
        self.logger.addHandler(fh)

    def serve(self):
        self.logger.info(f"watchdog start on 127.0.0.1:{self.port}")

        t = threading.Thread(target=self._monitor_loop, daemon=True)
        t.start()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", self.port))
            srv.listen(5)
            srv.settimeout(0.5)

            while not self._stop:
                try:
                    conn, _addr = srv.accept()
                except socket.timeout:
                    continue
                except Exception as e:
                    self.logger.error(f"accept error: {e}")
                    continue

                with conn:
                    try:
                        data = conn.recv(4096).decode("utf-8", errors="ignore").strip()
                        payload = json.loads(data.splitlines()[0]) if data else {}
                        resp = self._handle(payload)
                        conn.sendall((resp + "\n").encode("utf-8"))
                    except Exception as e:
                        self.logger.error(f"handle error: {e}")
                        try:
                            conn.sendall(b"ERR\n")
                        except Exception:
                            pass

        self.logger.info("watchdog stopped")

    def _handle(self, payload: dict) -> str:
        cmd = (payload.get("cmd") or "").lower()

        if cmd == "ping":
            return "OK"

        if cmd == "shutdown":
            self.logger.info("received shutdown")
            self._stop = True
            return "BYE"

        if cmd == "register":
            pid = int(payload.get("pid") or 0)
            argv = payload.get("app_argv") or []
            cwd = payload.get("cwd") or None
            with self._lock:
                self.target_pid = pid
                self.target_argv = list(argv) if isinstance(argv, list) else []
                self.target_cwd = str(cwd) if cwd else None
            self.logger.info(f"register pid={pid} argv={self.target_argv[:2]}...")
            return "OK"

        return "OK"

    def _monitor_loop(self):
        last_dead = 0.0
        while not self._stop:
            time.sleep(0.5)
            with self._lock:
                pid = self.target_pid
                argv = list(self.target_argv)
                cwd = self.target_cwd

            if pid <= 0:
                continue

            alive = pid_exists(pid)
            if alive:
                continue

            now = time.time()
            # chống spam restart nếu app vừa chết và vừa bật lại nhanh
            if now - last_dead < 2.0:
                continue
            last_dead = now

            self.logger.warning(f"app pid={pid} is dead -> action")
            # Action 1: restart app (nếu bạn muốn)
            if argv:
                try:
                    self.logger.warning("restart app...")
                    spawn_app(argv, cwd)
                except Exception as e:
                    self.logger.error(f"restart failed: {e}")

            # Nếu bạn chỉ muốn chạy script khác:
            # subprocess.Popen(["path/to/cleanup.exe"], ...)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=43999)
    ap.add_argument("--log-dir", type=str, default="logs/watchdog")
    args = ap.parse_args()

    wd = Watchdog(args.port, Path(args.log_dir))
    wd.serve()

if __name__ == "__main__":
    main()
