import os, sys, json, socket, subprocess, platform, shutil, tempfile
from pathlib import Path
from typing import Sequence, Union, Optional

from src.utils.resource_path import app_dir, bundled_dir  # :contentReference[oaicite:1]{index=1}

WD_PORT = 43999
WD_HOST = "127.0.0.1"

def _is_windows() -> bool:
    return platform.system().lower().startswith("win")

def _is_linux() -> bool:
    return platform.system().lower() == "linux"

def _pick_python_exe() -> Path:
    """
    Dev mode on Windows: prefer pythonw.exe (no console).
    """
    py = Path(sys.executable).resolve()
    if _is_windows() and py.name.lower() == "python.exe":
        pyw = py.with_name("pythonw.exe")
        if pyw.exists():
            return pyw
    return py

def _spawn_detached(cmd: list[str]) -> None:
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

    subprocess.Popen(cmd, **kwargs)

def _wd_send(payload: dict, timeout=0.25) -> bool:
    try:
        with socket.create_connection((WD_HOST, WD_PORT), timeout=timeout) as s:
            s.sendall((json.dumps(payload) + "\n").encode("utf-8"))
            s.settimeout(timeout)
            _ = s.recv(64)
        return True
    except Exception:
        return False


def wd_register(pid: int, run_id: str, app_argv: list[str], cwd: str | None) -> bool:
    return _wd_send({
        "cmd": "register",
        "pid": int(pid),
        "run_id": str(run_id),
        "app_argv": list(app_argv or []),
        "cwd": cwd or "",
    })

def wd_heartbeat(pid: int, run_id: str) -> bool:
    return _wd_send({
        "cmd": "heartbeat",
        "pid": int(pid),
        "run_id": str(run_id),
    })

def wd_complete(pid: int, run_id: str) -> bool:
    return _wd_send({
        "cmd": "complete",
        "pid": int(pid),
        "run_id": str(run_id),
    })

def _is_writable_dir(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".wtest_", dir=str(p))
        os.close(fd)
        os.unlink(tmp)
        return True
    except Exception:
        return False

def _user_bin_dir() -> Path:
    """
    Per-user writable bin folder (no admin):
    - Windows: %LOCALAPPDATA%/SampleKinter/bin (fallback)
    - Linux:   ~/.local/share/SampleKinter/bin (fallback)
    """
    if _is_windows():
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
        return base / "SampleKinter" / "bin"
    return Path.home() / ".local" / "share" / "SampleKinter" / "bin"

def _pick_bin_dir() -> Path:
    """
    Prefer app_dir()/bin; if not writable -> fallback per-user bin.
    """
    p = app_dir() / "bin"
    if _is_writable_dir(p):
        return p
    return _user_bin_dir()

def _chmod_exec_if_needed(p: Path) -> None:
    if _is_linux():
        try:
            mode = p.stat().st_mode
            p.chmod(mode | 0o111)  # add +x
        except Exception:
            pass

def _copy_if_needed(src: Path, dst: Path) -> bool:
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            # copy only if size differs (cheap)
            if dst.stat().st_size == src.stat().st_size:
                return True
        shutil.copy2(str(src), str(dst))
        _chmod_exec_if_needed(dst)
        return True
    except Exception:
        return False

def _find_first_existing(candidates: Sequence[Path]) -> Optional[Path]:
    for p in candidates:
        print(p)
        try:
            if p and p.exists() and p.is_file():
                
                return p
        except Exception:
            pass
    return None

def resolve_watchdog_cmd(log_callback=print) -> list[str]:
    """
    Resolve watchdog command with priority:
    1) app_dir()/bin/<watchdog[.exe]>
    2) app_dir()/src/watchdog/<watchdog_service.py|watchdog.py> (dev fallback)
    3) frozen: bundled_dir()/src/watchdog/<watchdog.exe|watchdog> -> copy to bin_dir and use
       (also try bundled_dir() root / bin/)
    """
    is_frozen = bool(getattr(sys, "frozen", False))

    # ----- 1) prefer installed bin -----
    exe_name = "watchdog.exe" if _is_windows() else "watchdog"
    bin_dir = _pick_bin_dir()
    bin_exe = bin_dir / exe_name
    if bin_exe.exists():
        _chmod_exec_if_needed(bin_exe)
        return [str(bin_exe)]

    # ----- 2) dev fallback to python script in app_dir/src/watchdog -----
    # (only reliable when NOT frozen)
    if not is_frozen:
        py = _pick_python_exe()
        script_candidates = [
            app_dir() / "src" / "watchdog" / "watchdog_service.py",
            app_dir() / "src" / "watchdog" / "watchdog.py",
            # also allow resolving from current module folder
            Path(__file__).resolve().parent / "watchdog_service.py",
            Path(__file__).resolve().parent / "watchdog.py",
        ]
        wd_py = _find_first_existing(script_candidates)
        if wd_py:
            return [str(py), str(wd_py)]

        # dev but still may have a built watchdog in repo
        repo_exe_candidates = [
            app_dir() / "src" / "watchdog" / exe_name,
            Path(__file__).resolve().parent / exe_name,
        ]
        repo_exe = _find_first_existing(repo_exe_candidates)
        if repo_exe:
            if _copy_if_needed(repo_exe, bin_exe):
                log_callback(f"[watchdog] copied -> {bin_exe}")
                return [str(bin_exe)]
            return [str(repo_exe)]

    # ----- 3) frozen: search in _MEIPASS then copy to writable bin -----
    bdir = bundled_dir()
    bundle_candidates = [
        bdir / "src" / "watchdog" / "watchdog.exe",
        bdir / "src" / "watchdog" / "watchdog",
        bdir / "watchdog.exe",
        bdir / "watchdog",
        bdir / "bin" / "watchdog.exe",
        bdir / "bin" / "watchdog",
        # sometimes people add-data "src/watchdog/" folder directly:
        bdir / "watchdog" / "watchdog.exe",
        bdir / "watchdog" / "watchdog",
    ]
    bundle_exe = _find_first_existing(bundle_candidates)
    if bundle_exe:
        if _copy_if_needed(bundle_exe, bin_exe):
            log_callback(f"[watchdog] installed from bundle -> {bin_exe}")
            return [str(bin_exe)]
        # if cannot copy (rare), run directly from bundle (still ok)
        _chmod_exec_if_needed(bundle_exe)
        log_callback(f"[watchdog] run from bundle -> {bundle_exe}")
        return [str(bundle_exe)]

    # last resort: try app_dir/src/watchdog exe in frozen install (if shipped)
    maybe_src_exe = _find_first_existing([
        app_dir() / "src" / "watchdog" / exe_name,
        app_dir() / "src" / "watchdog" / "watchdog.exe",
        app_dir() / "src" / "watchdog" / "watchdog",
    ])
    if maybe_src_exe:
        if _copy_if_needed(maybe_src_exe, bin_exe):
            log_callback(f"[watchdog] copied src exe -> {bin_exe}")
            return [str(bin_exe)]
        return [str(maybe_src_exe)]

    raise FileNotFoundError(
        "Cannot resolve watchdog launcher. Missing watchdog exe (bundle/bin) and watchdog python script."
    )

def ensure_watchdog_running(
    wd_cmd: Union[Path, str, Sequence[str]],
    log_dir: Path,
    *,
    port: int = WD_PORT,
    log_callback=print,
) -> None:
    """
    wd_cmd:
      - Path/"string": executable path
      - Sequence[str]: base command, e.g. ["python", "watchdog_service.py"] or ["watchdog.exe"]
    """
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(wd_cmd, (Path, str)):
        base = [str(wd_cmd)]
    else:
        base = list(wd_cmd)

    log_callback(f"[watchdog] ensuring running at port {port}...")
    # 1) ping watchdog if running
    if not _wd_send({"cmd": "ping"}):
        # 2) spawn watchdog with args
        cmd = [*base, "--port", str(port), "--log-dir", str(log_dir)]
        _spawn_detached(cmd)

        # 3) quick retry connect
        for _ in range(10):
            if _wd_send({"cmd": "ping"}):
                break

    # 4) register current PID for monitoring
    # log_callback("[watchdog] registering current process...")
    # log_callback(f"[watchdog] PID={os.getpid()}, ARGV={sys.argv}, CWD={os.getcwd()}")
    # _wd_send({
    #     "cmd": "register",
    #     "pid": os.getpid(),
    #     "app_argv": sys.argv,
    #     "cwd": os.getcwd(),
    # })

def ensure_watchdog_running_auto(
    log_dir: Optional[Path] = None,
    *,
    port: int = WD_PORT,
    log_callback=print,
) -> None:
    """
    One-liner: auto resolve + ensure watchdog running.
    """
    if log_dir is None:
        log_dir = app_dir() / "logs" / "watchdog"
    cmd = resolve_watchdog_cmd(log_callback=log_callback)
    ensure_watchdog_running(cmd, log_dir, port=port, log_callback=log_callback)
