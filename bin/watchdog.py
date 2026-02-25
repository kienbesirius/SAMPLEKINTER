import argparse, json, os, socket, threading, time, sys, platform, subprocess
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from src.utils.terminal_no_popup_cmd_kwargs import no_popup_kwargs, build_launch_cmd


@dataclass
class ScheduleCfg:

    times: list[tuple[int, int]] = None
    heartbeat_timeout_s: float = 10.0
    restart_cooldown_s: float = 2.0

    def __post_init__(self):
        if self.times is None:
            self.times = [(6, 0), (12, 0), (18, 0), (0, 0)]

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
            start_new_session=True, 
            shell=False,
            **pop,
        )
        return p
    finally:
        pass

def spawn_app(app_argv: list[str], cwd: str | None, *, log_dir: Path, embedded_python: str | None = None):
    env = os.environ.copy()
    if embedded_python:
        env["SLOTHCSV_PYTHON"] = str(embedded_python)

    full_cmd, env = build_launch_cmd(app_argv, env=env)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app_spawn.log"

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
        self.mode = "GUARD"  
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

            return "OK"

        if cmd == "heartbeat":
            pid = int(payload.get("pid") or 0)
            run_id = str(payload.get("run_id") or "")
            with self._lock:

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


            if mode == "SCHEDULE":
                if now >= next_run:
                    self.logger.warning("schedule time reached -> spawn app")
                    if argv:
                        try:
                            spawn_app(argv, cwd, log_dir=self.log_dir, embedded_python=getattr(self, "target_python", None))

                        except Exception as e:
                            self.logger.error(f"spawn scheduled app failed: {e}")

                    with self._lock:
                        self.mode = "GUARD"
                        self.completed = False
                        self.target_pid = 0
                        self.target_run_id = ""
                        self.last_heartbeat_ts = now  # grace 10s
                        self.last_restart_ts = now
                    continue

                continue

            with self._lock:
                if now - self.last_restart_ts < self.cfg.restart_cooldown_s:
                    continue


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
                    self.last_heartbeat_ts = now  
                continue

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
