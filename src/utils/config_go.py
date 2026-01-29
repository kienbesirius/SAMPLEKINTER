from __future__ import annotations

import configparser
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Union, Literal
import os
import re
import tempfile
from pathlib import Path

ENDING_MAP = {
    "CRLF": "\r\n",
    "LF": "\n",
    "CR": "\r",
    "NONE": "",
}

@dataclass(frozen=True)
class FixtureConfig:
    baudrate: int
    ending_line: str      # actual chars: "\r\n" | "\n" | "\r" | ""
    timeout: float
    slot_text: Dict[int, str]
    slot_status: Dict[int, str]

def load_fixture_cfg(path: str) -> FixtureConfig:
    # strict=False để không crash nếu config có key trùng (slot8 bị lặp)
    cfg = configparser.ConfigParser(strict=False)
    cfg.read(path, encoding="utf-8")

    baudrate = cfg.getint("FIXTURE", "baudrate", fallback=9600)
    ending_mode = cfg.get("FIXTURE", "ending_line", fallback="CRLF").strip().upper()
    ending_line = ENDING_MAP.get(ending_mode, "\r\n")
    timeout = cfg.getfloat("FIXTURE", "timeout", fallback=2.0)

    slot_text: Dict[int, str] = {}
    slot_status: Dict[int, str] = {}
    for i in range(1, 13):
        slot_text[i] = cfg.get("SLOT_TEST", f"slot{i}", fallback="").strip()
        slot_status[i] = cfg.get("SLOT_STATUS", f"slot{i}", fallback="idle").strip()

    return FixtureConfig(
        baudrate=baudrate,
        ending_line=ending_line,
        timeout=timeout,
        slot_text=slot_text,
        slot_status=slot_status,
    )

def choose_slot_font(label: str) -> Tuple[str, int, str]:
    label = (label or "").strip()
    if not label:
        return ("Tektur", 13, "bold")
    if len(label) <= 4:
        return ("Tektur", 17, "bold")     # IN/OUT
    if len(label) <= 5:
        return ("Tektur", 11, "bold")     # RESET
    if len(label) <= 8 and " " not in label:
        return ("Tektur", 9, "bold")
    if len(label) <= 8 and " " in label:
        return ("Tektur", 13, "bold")
    return ("Tektur", 11, "bold")         # FORCE STOP



_SLOT_RE = re.compile(r"^(\s*)(slot)(\d+)(\s*=\s*)(.*?)(\s*)$", re.IGNORECASE)
_SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")


def reset_slot_status_section_to_idle(
    ini_path: Union[str, Path],
    *,
    section_name: str = "SLOT_STATUS",
    slots: int = 12,
    idle_value: str = "idle",
    encoding: str = "utf-8",
) -> None:
    """
    Chỉ làm việc với FILE (text-based):
    - set slot1..slot{slots} = idle trong [SLOT_STATUS]
    - giữ nguyên format/comment/các section khác
    - nếu thiếu slot -> append
    - nếu trùng slot (slot8 lặp) -> update tất cả dòng trùng
    - ghi file atomic
    """
    path = Path(ini_path)

    raw = path.read_bytes()
    # detect newline style
    if b"\r\n" in raw:
        newline = "\r\n"
    else:
        newline = "\n"

    text = raw.decode(encoding, errors="replace")
    lines = text.splitlines()

    # locate section
    start = None
    end = None
    for i, ln in enumerate(lines):
        m = _SECTION_RE.match(ln)
        if not m:
            continue
        name = m.group(1).strip()
        if start is None and name.upper() == section_name.upper():
            start = i + 1
            continue
        if start is not None:
            # next section starts -> end of SLOT_STATUS
            end = i
            break

    if start is None:
        # nếu chưa có section, append ở cuối file
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"[{section_name}]")
        start = len(lines)
        end = len(lines)

    if end is None:
        end = len(lines)

    # process section lines
    seen = set()
    new_section_lines = []
    for ln in lines[start:end]:
        m = _SLOT_RE.match(ln)
        if m:
            indent, key, num_s, eq, _old, trail = m.groups()
            try:
                num = int(num_s)
            except ValueError:
                new_section_lines.append(ln)
                continue

            if 1 <= num <= slots:
                # rewrite to idle, preserve indent + spacing around '=' + trailing spaces
                new_section_lines.append(f"{indent}{key}{num}{eq}{idle_value}{trail}")
                seen.add(num)
                continue

        new_section_lines.append(ln)

    # append missing slots
    missing = [i for i in range(1, slots + 1) if i not in seen]
    if missing:
        # nếu section không rỗng và dòng cuối không trống, thêm 1 dòng trống cho đẹp
        if new_section_lines and new_section_lines[-1].strip() != "":
            new_section_lines.append("")
        for i in missing:
            new_section_lines.append(f"slot{i}={idle_value}")

    # rebuild file
    out_lines = lines[:start] + new_section_lines + lines[end:]
    out_text = newline.join(out_lines) + newline  # ensure trailing newline

    # atomic write
    tmp_dir = str(path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=tmp_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(out_text)
        os.replace(tmp_name, path)
    finally:
        try:
            os.remove(tmp_name)
        except FileNotFoundError:
            pass


SlotStatus = Literal["pass", "fail", "testing", "idle"]
_ALLOWED_STATUS = {"pass", "fail", "testing", "idle"}

def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    tmp_dir = str(path.parent)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=tmp_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(text)
        os.replace(tmp_name, path)
    finally:
        try:
            os.remove(tmp_name)
        except FileNotFoundError:
            pass


def _detect_newline(raw: bytes) -> str:
    return "\r\n" if b"\r\n" in raw else "\n"


def update_ini_slot_status(
    ini_path: Union[str, Path],
    slot_idx: int,
    status: str,
    *,
    section_name: str = "SLOT_STATUS",
    encoding: str = "utf-8",
) -> None:
    """
    Text-based update:
    - Update tất cả dòng slot{idx}=... trong [SLOT_STATUS] => slot{idx}=status
    - Nếu thiếu thì append vào cuối section
    - Giữ format/comment/các section khác
    """
    if not (1 <= slot_idx <= 12):
        raise ValueError(f"slot_idx out of range: {slot_idx}")

    st = status.strip().lower()
    if st not in _ALLOWED_STATUS:
        raise ValueError(f"Invalid status: {status!r}. Allowed: {sorted(_ALLOWED_STATUS)}")

    path = Path(ini_path)

    if path.exists():
        raw = path.read_bytes()
        newline = _detect_newline(raw)
        text = raw.decode(encoding, errors="replace")
        lines = text.splitlines()
    else:
        newline = "\n"
        lines = []

    # locate section bounds
    start = None
    end = None
    for i, ln in enumerate(lines):
        m = _SECTION_RE.match(ln)
        if not m:
            continue
        name = m.group(1).strip()
        if start is None and name.upper() == section_name.upper():
            start = i + 1
            continue
        if start is not None:
            end = i
            break

    if start is None:
        # append section at EOF
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"[{section_name}]")
        start = len(lines)
        end = len(lines)
    if end is None:
        end = len(lines)

    target = slot_idx
    found_any = False
    new_section = []

    for ln in lines[start:end]:
        m = _SLOT_RE.match(ln)
        if m:
            indent, key, num_s, eq, _old, trail = m.groups()
            try:
                num = int(num_s)
            except ValueError:
                new_section.append(ln)
                continue

            if num == target:
                # update line, preserve indent/spaces around "=" and trailing spaces
                new_section.append(f"{indent}{key}{num}{eq}{st}{trail}")
                found_any = True
                continue

        new_section.append(ln)

    if not found_any:
        # append new slot line
        if new_section and new_section[-1].strip() != "":
            new_section.append("")
        new_section.append(f"slot{target}={st}")

    out_lines = lines[:start] + new_section + lines[end:]
    out_text = newline.join(out_lines) + newline
    _atomic_write_text(path, out_text, encoding=encoding)


def load_slot_status_from_ini(
    ini_path: Union[str, Path],
    *,
    section_name: str = "SLOT_STATUS",
    slots: int = 12,
    encoding: str = "utf-8",
) -> Dict[int, str]:
    """
    Read-only, text-based parse.
    Nếu key trùng (slot8 lặp) => dòng xuất hiện SAU cùng sẽ thắng.
    """
    path = Path(ini_path)
    out = {i: "idle" for i in range(1, slots + 1)}
    if not path.exists():
        return out

    raw = path.read_text(encoding=encoding, errors="replace").splitlines()

    in_section = False
    for ln in raw:
        msec = _SECTION_RE.match(ln)
        if msec:
            in_section = (msec.group(1).strip().upper() == section_name.upper())
            continue
        if not in_section:
            continue

        m = _SLOT_RE.match(ln)
        if not m:
            continue
        _indent, _key, num_s, _eq, val, _trail = m.groups()
        try:
            idx = int(num_s)
        except ValueError:
            continue
        if 1 <= idx <= slots:
            out[idx] = val.strip().lower() or "idle"

    return out
