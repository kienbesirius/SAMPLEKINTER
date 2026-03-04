import argparse, json, os, socket, threading, time, sys, platform, subprocess
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
# --- add imports ---
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import os, subprocess
import os, sys
from pathlib import Path

def no_popup_kwargs() -> dict:
    """
    Windows: chặn popup console.
    Linux/macOS: subprocess bình thường không popup terminal => {}.
    """
    if os.name != "nt":
        return {}

    startupinfo = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]
    # ẩn cửa sổ nếu có
    try:
        startupinfo.wShowWindow = subprocess.SW_HIDE  # type: ignore[attr-defined]
    except Exception:
        pass

    return {
        "startupinfo": startupinfo,
        "creationflags": subprocess.CREATE_NO_WINDOW,  # type: ignore[attr-defined]
    }

def _is_executable_file(p: str) -> bool:
    try:
        return os.path.isfile(p) and os.access(p, os.X_OK)
    except Exception:
        return False

def build_launch_cmd(app_argv: list[str], *, env: dict | None = None) -> tuple[list[str], dict | None]:
    """
    Trả về (full_cmd, env) đã được guard:
      - .py => prepend python interpreter
      - .bat/.cmd => cmd.exe /c ...
      - .sh => bash ...
      - file không executable => prepend python (nếu .py) hoặc cố gắng chạy qua shell phù hợp
    """
    if not app_argv:
        return [], env

    argv = list(app_argv)
    exe0 = argv[0]
    p0 = Path(exe0)

    # normalize path nếu là file tương đối
    if not p0.is_absolute():
        exe0_abs = str(p0.resolve())
    else:
        exe0_abs = exe0

    lower = exe0_abs.lower()

    # Windows: .bat/.cmd phải đi qua cmd.exe
    if os.name == "nt" and (lower.endswith(".bat") or lower.endswith(".cmd")):
        return (["cmd.exe", "/c", exe0_abs, *argv[1:]], env)

    # Linux: .sh có thể chạy qua bash (khi chưa chmod +x)
    if os.name != "nt" and lower.endswith(".sh") and not _is_executable_file(exe0_abs):
        return (["/bin/bash", exe0_abs, *argv[1:]], env)

    # .py: luôn chạy qua python để tránh permission denied
    if lower.endswith(".py"):
        # ưu tiên python “nhúng” nếu bạn set env["SLOTHCSV_PYTHON"]
        py = None
        if env:
            py = env.get("SLOTHCSV_PYTHON") or env.get("PYTHON")
        py = py or sys.executable
        return ([py, exe0_abs, *argv[1:]], env)

    # file thường: nếu là file mà không executable trên Linux => vẫn sẽ fail permission
    # => để nguyên (vì có thể là .exe/.bin đã executable) hoặc bạn muốn fallback bash/sh tùy use-case
    return ([exe0_abs, *argv[1:]], env)


# @dataclass
# class ScheduleCfg:
#     # 06:00 và 18:00 (sáng/tối) = 12h một lần
#     times: list[tuple[int, int]] = None
#     heartbeat_timeout_s: float = 10.0
#     restart_cooldown_s: float = 2.0

#     def __post_init__(self):
#         if self.times is None:
#             self.times = [(6, 0), (12, 0), (18, 0), (0, 0)]

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Optional
import configparser
import re
import sys
# Liệt kê nhiều mốc thời gian để debug
# [WATCHDOG]
# times = 00:00,00:05,00:10,00:15,00:20,00:25,00:30,00:35,00:40,00:45,00:50,00:55, \
#         01:00,01:05,01:10,01:15,01:20,01:25,01:30,01:35,01:40,01:45,01:50,01:55, \
#         02:00,02:05,02:10,02:15, ... , 23:55
# heartbeat_timeout_s = 10
# restart_cooldown_s = 2
@dataclass
class ScheduleCfg:
    times: list[tuple[int, int]] | None = None
    heartbeat_timeout_s: float = 10.0
    restart_cooldown_s: float = 2.0

    # ---- internal ----
    _cfg_path: Path = field(init=False, repr=False)

    CFG_FILENAME: ClassVar[str] = "config_watchdog.ini"
    SECTION: ClassVar[str] = "WATCHDOG"
    DEFAULT_TIMES: ClassVar[list[tuple[int, int]]] = [(10, 0), (22, 0)]

    def __post_init__(self):
        # set default trước
        if self.times is None:
            self.times = list(self.DEFAULT_TIMES)

        self._cfg_path = self._resolve_cfg_path()

        # load -> nếu fail thì override default + write file
        if not self._try_load_from_ini(self._cfg_path):
            self.times = list(self.DEFAULT_TIMES)
            self.heartbeat_timeout_s = 10.0
            self.restart_cooldown_s = 2.0
            self._write_ini(self._cfg_path)

    # =========================
    # Resolve config path
    # =========================
    @classmethod
    def _resolve_cfg_path(cls) -> Path:
        base_dir = cls._resolve_exec_dir()
        return base_dir / cls.CFG_FILENAME

    @staticmethod
    def _resolve_exec_dir() -> Path:
        """
        "Cùng thư mục execute của watchdog":
        - nếu watchdog là exe: sys.argv[0] thường là path exe
        - nếu watchdog là script: sys.argv[0] là path script
        Fallback: __file__ / cwd
        """
        candidates: list[Path] = []

        # argv[0] (exe hoặc script path)
        try:
            if sys.argv and sys.argv[0] and sys.argv[0] not in ("-c", "-m"):
                candidates.append(Path(sys.argv[0]).expanduser())
        except Exception:
            pass

        # frozen exe (đôi khi chắc ăn hơn)
        try:
            if bool(getattr(sys, "frozen", False)):
                candidates.append(Path(sys.executable).expanduser())
        except Exception:
            pass

        # module file
        try:
            candidates.append(Path(__file__).expanduser())
        except Exception:
            pass

        # chọn cái tồn tại
        for p in candidates:
            try:
                rp = p.resolve()
                if rp.exists():
                    return rp.parent
            except Exception:
                continue

        # cuối cùng: cwd
        return Path.cwd()

    # =========================
    # Load / Validate
    # =========================
    @classmethod
    def _parse_times(cls, raw: str) -> Optional[list[tuple[int, int]]]:
        """
        Accept:
          times = 06:00,12:00,18:00,00:00
          times = 06:00 12:00 18:00 00:00
          times =
              06:00
              12:00
        """
        if not raw:
            return None

        pairs = re.findall(r"(\d{1,2})\s*:\s*(\d{1,2})", raw)
        if not pairs:
            return None

        out: list[tuple[int, int]] = []
        seen = set()
        for h_s, m_s in pairs:
            hh = int(h_s)
            mm = int(m_s)
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                return None
            t = (hh, mm)
            if t not in seen:
                seen.add(t)
                out.append(t)

        return out or None

    def _try_load_from_ini(self, path: Path) -> bool:
        if not path.exists():
            # không có file -> tạo mặc định luôn
            self._write_ini(path)
            return True

        cp = configparser.ConfigParser()
        try:
            cp.read(path, encoding="utf-8")
        except Exception:
            return False

        if not cp.has_section(self.SECTION):
            return False

        sec = cp[self.SECTION]

        # times (bắt buộc hợp lệ, không hợp lệ -> fail để override)
        times_raw = sec.get("times", fallback="").strip()
        parsed = self._parse_times(times_raw)
        if not parsed:
            return False
        self.times = parsed

        # heartbeat_timeout_s (optional, invalid -> giữ mặc định)
        try:
            v = float(sec.get("heartbeat_timeout_s", fallback=str(self.heartbeat_timeout_s)))
            if v > 0:
                self.heartbeat_timeout_s = v
        except Exception:
            pass

        # restart_cooldown_s (optional, invalid -> giữ mặc định)
        try:
            v = float(sec.get("restart_cooldown_s", fallback=str(self.restart_cooldown_s)))
            if v >= 0:
                self.restart_cooldown_s = v
        except Exception:
            pass

        return True

    # =========================
    # Write
    # =========================
    def _write_ini(self, path: Path) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            times_str = ",".join(f"{hh:02d}:{mm:02d}" for hh, mm in (self.times or self.DEFAULT_TIMES))
            content = (
                f"[{self.SECTION}]\n"
                f"times = {times_str}\n"
                f"heartbeat_timeout_s = {self.heartbeat_timeout_s}\n"
                f"restart_cooldown_s = {self.restart_cooldown_s}\n"
            )
            path.write_text(content, encoding="utf-8")
        except Exception:
            # nếu không ghi được (permission), vẫn chạy bằng config đang có trong RAM
            pass

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


def spawn_detached(
    app_argv: list[str],
    *,
    cwd: str | None = None,
    env: dict | None = None,
    log_path: str | None = None,
) -> subprocess.Popen | None:
    full_cmd, env = build_launch_cmd(app_argv, env=env)
    if not full_cmd:
        return None

    pop = no_popup_kwargs()

    # watchdog nên redirect log -> file (tránh PIPE)
    stdout = stderr = None
    log_fh = None
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        log_fh = open(log_path, "a", encoding="utf-8", buffering=1)
        stdout = log_fh
        stderr = subprocess.STDOUT

    try:
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        
        p = subprocess.Popen(
            full_cmd,
            cwd=cwd or None,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stdout if stdout is not None else subprocess.DEVNULL,
            stderr=stderr if stderr is not None else subprocess.DEVNULL,
            text=True,
            start_new_session=True,   # Linux detach khỏi watchdog
            shell=False,
            **pop,
        )
        return p
    finally:
        # KHÔNG close log_fh ở đây nếu bạn muốn child tiếp tục ghi.
        # Nhưng nếu bạn dùng DEVNULL thì thôi.
        # Với file handle: thường vẫn ok để giữ mở trong watchdog process.
        pass

def spawn_app(app_argv: list[str], cwd: str | None, *, log_dir: Path, embedded_python: str | None = None):
    env = os.environ.copy()
    if embedded_python:
        env["SLOTHCSV_PYTHON"] = str(embedded_python)

    full_cmd, env = build_launch_cmd(app_argv, env=env)

    # log spawn
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app_spawn.log"
    # out = open(log_path, "a", encoding="utf-8", buffering=1)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    with open(log_path, "a", encoding="utf-8", buffering=1) as out:
        kwargs = {
            "cwd": cwd or None,
            "env": env,
            "stdin": subprocess.DEVNULL,
            "stdout": out,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
            "shell": False,
            "start_new_session": True,
        }
        kwargs.update(no_popup_kwargs())
        subprocess.Popen(full_cmd, **kwargs)
    # kwargs = {
    #     "cwd": cwd or None,
    #     "env": env,
    #     "stdin": subprocess.DEVNULL,
    #     "stdout": out,
    #     "stderr": subprocess.STDOUT,
    #     "text": True,
    #     "bufsize": 1,
    #     "shell": False,
    #     "start_new_session": True,
    # }
    # kwargs.update(no_popup_kwargs())

    # subprocess.Popen(full_cmd, **kwargs)


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

        self.cfg = ScheduleCfg()
        self.mode = "GUARD"     # "GUARD" | "SCHEDULE"
        self.completed = False

        self.target_run_id = ""
        self.last_heartbeat_ts = 0.0
        self.last_restart_ts = 0.0
        self.next_run_ts = 0.0
        self.target_python: str | None = None

        self._recalc_next_run()


    def _recalc_next_run(self) -> None:
        """Next schedule time based on local time."""
        now = datetime.now()
        cands = []
        for hh, mm in self.cfg.times:
            dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if dt <= now:
                dt += timedelta(days=1)
            cands.append(dt)
        self.next_run_ts = min(cands).timestamp() if cands else (time.time() + 12*3600)

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
            # giữ tương thích (không dùng để monitor)
            return "OK"

        if cmd == "heartbeat":
            pid = int(payload.get("pid") or 0)
            run_id = str(payload.get("run_id") or "")
            with self._lock:
                # chỉ nhận heartbeat đúng phiên
                if self.target_run_id and run_id and run_id != self.target_run_id:
                    return "OK"
                if pid > 0 and self.target_pid == 0:
                    self.target_pid = pid
                self.last_heartbeat_ts = time.time()
            return "OK"

        if cmd == "complete":
            pid = int(payload.get("pid") or 0)
            run_id = str(payload.get("run_id") or "")
            self.logger.info(f"received COMPLETE pid={pid} run_id={run_id}")

            with self._lock:
                self.completed = True
                self.mode = "SCHEDULE"
                # clear current target so watchdog won't restart immediately
                self.target_pid = 0
                self.target_run_id = ""
                self.last_heartbeat_ts = 0.0
                self._recalc_next_run()

            return "OK"

        if cmd == "register":
            pid = int(payload.get("pid") or 0)
            argv = payload.get("app_argv") or []
            cwd = payload.get("cwd") or None
            run_id = str(payload.get("run_id") or "")

            py = payload.get("python") or payload.get("embedded_python") or None

            with self._lock:
                self.target_pid = pid
                self.target_argv = list(argv) if isinstance(argv, list) else []
                self.target_cwd = str(cwd) if cwd else None
                self.target_run_id = run_id
                self.target_python = str(py) if py else None
                self.last_heartbeat_ts = time.time()

                # đăng ký là bắt đầu 1 phiên => quay lại GUARD, reset completed
                self.completed = False
                self.mode = "GUARD"

            self.logger.info(f"register pid={pid} run_id={run_id} argv={self.target_argv[:2]}...")
            return "OK"

        if cmd == "shutdown":
            self.logger.info("received shutdown")
            self._stop = True
            return "BYE"

        return "OK"

    def _monitor_loop(self):
        while not self._stop:
            time.sleep(0.5)

            with self._lock:
                mode = self.mode
                pid = self.target_pid
                argv = list(self.target_argv)
                cwd = self.target_cwd
                last_hb = self.last_heartbeat_ts
                next_run = self.next_run_ts

            now = time.time()

            # -------- SCHEDULE MODE --------
            if mode == "SCHEDULE":
                if now >= next_run:
                    self.logger.warning("schedule time reached -> spawn app")
                    if argv:
                        try:
                            spawn_app(argv, cwd, log_dir=self.log_dir, embedded_python=getattr(self, "target_python", None))

                        except Exception as e:
                            self.logger.error(f"spawn scheduled app failed: {e}")

                    # chuyển qua GUARD để bắt đầu đợi register/heartbeat
                    with self._lock:
                        self.mode = "GUARD"
                        self.completed = False
                        self.target_pid = 0
                        self.target_run_id = ""
                        self.last_heartbeat_ts = now  # grace 10s
                        self.last_restart_ts = now
                    continue

                continue

            # -------- GUARD MODE --------
            # Cooldown chống spam restart
            with self._lock:
                if now - self.last_restart_ts < self.cfg.restart_cooldown_s:
                    continue

            # 1) heartbeat timeout => restart
            if last_hb > 0 and (now - last_hb) > self.cfg.heartbeat_timeout_s:
                self.logger.warning(f"heartbeat timeout ({now-last_hb:.1f}s) -> restart")
                if argv:
                    try:
                        spawn_app(argv, cwd, log_dir=self.log_dir, embedded_python=getattr(self, "target_python", None))

                    except Exception as e:
                        self.logger.error(f"restart failed: {e}")

                with self._lock:
                    self.last_restart_ts = now
                    self.target_pid = 0
                    self.target_run_id = ""
                    self.last_heartbeat_ts = now  # grace window
                continue

            # 2) pid dead => restart
            if pid > 0 and (not pid_exists(pid)):
                self.logger.warning(f"app pid={pid} is dead -> restart")
                if argv:
                    try:
                        spawn_app(argv, cwd, log_dir=self.log_dir, embedded_python=getattr(self, "target_python", None))
                    except Exception as e:
                        self.logger.error(f"restart failed: {e}")

                with self._lock:
                    self.last_restart_ts = now
                    self.target_pid = 0
                    self.target_run_id = ""
                    self.last_heartbeat_ts = now
                continue

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=43999)
    ap.add_argument("--log-dir", type=str, default="logs/watchdog")
    args = ap.parse_args()

    wd = Watchdog(args.port, Path(args.log_dir))
    wd.serve()

if __name__ == "__main__":
    main()
