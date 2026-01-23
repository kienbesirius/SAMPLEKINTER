import os
import subprocess
from pathlib import Path
from typing import Mapping, Sequence, Union, Optional


PathLike = Union[str, os.PathLike]


def popen_nopopup(
    full_cmd: Sequence[str],
    *,
    embedded_python: PathLike,
    cwd: Optional[PathLike] = None,
    env_extra: Optional[Mapping[str, str]] = None,
    text: bool = True,
    bufsize: int = 1,
) -> subprocess.Popen:
    """
    Start a child process with stdout piped, stderr merged into stdout.
    On Windows: hide console window (no terminal popup).
    Also inject env var: SLOTHCSV_PYTHON=<embedded_python>.
    """
    creationflags = 0
    startupinfo = None

    if os.name == "nt":
        # Hide child console window completely
        creationflags |= getattr(subprocess, "CREATE_NO_WINDOW", 0)

        # Optional STARTUPINFO (extra safety)
        si = subprocess.STARTUPINFO()  # type: ignore[attr-defined]
        si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)  # type: ignore[attr-defined]
        startupinfo = si

    env = os.environ.copy()
    env["SLOTHCSV_PYTHON"] = str(embedded_python)
    if env_extra:
        env.update(env_extra)

    proc = subprocess.Popen(
        list(full_cmd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=text,
        bufsize=bufsize,
        cwd=str(cwd) if cwd is not None else None,
        shell=False,
        startupinfo=startupinfo,
        creationflags=creationflags,
    )
    return proc
