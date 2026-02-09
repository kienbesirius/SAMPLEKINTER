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
