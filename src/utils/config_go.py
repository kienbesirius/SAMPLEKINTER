from __future__ import annotations

import configparser
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Union, Literal, Optional, Set
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
_NEUTRAL_STATUS_GATE = {"idle", "item", "stand_by", "unknown"}  # nhóm “trung tính”


def _find_section_bounds(lines: list[str], section_name: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Return (start_idx, end_idx) of section content (not including [SECTION] line)
    If section not found -> (None, None)
    """
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
    return start, end


def reset_slot_status_section_to_idle(
    ini_path: Union[str, Path],
    *,
    slot_test_section: str = "SLOT_TEST",
    slot_status_section: str = "SLOT_STATUS",
    slots: int = 12,
    idle_value: str = "idle",
    item_value: str = "item",
    encoding: str = "utf-8",
) -> None:
    """
    Text-based (giữ format/comment):
    - Đọc [SLOT_TEST] để biết slot nào "có bài" (value != "")
    - Ghi [SLOT_STATUS]:
        + slot rỗng -> idle_value
        + slot có bài -> item_value
    - Nếu thiếu slot -> append
    - Nếu trùng slot -> update tất cả dòng trùng
    - Atomic write
    """
    path = Path(ini_path)

    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"

    text = raw.decode(encoding, errors="replace")
    lines = text.splitlines()

    # --------- 1) parse SLOT_TEST -> set các slot "active" ----------
    st_start, st_end = _find_section_bounds(lines, slot_test_section)
    if st_start is None:
        active_slots: Set[int] = set()
    else:
        if st_end is None:
            st_end = len(lines)

        active_slots = set()
        for ln in lines[st_start:st_end]:
            m = _SLOT_RE.match(ln)
            if not m:
                continue
            indent, key, num_s, eq, val, trail = m.groups()
            try:
                num = int(num_s)
            except ValueError:
                continue
            if 1 <= num <= slots:
                if str(val).strip() != "":
                    # nếu slot bị lặp, chỉ cần 1 dòng có value là coi như active
                    active_slots.add(num)

    def _desired(num: int) -> str:
        return item_value if num in active_slots else idle_value

    # --------- 2) locate/create SLOT_STATUS ----------
    ss_start, ss_end = _find_section_bounds(lines, slot_status_section)

    if ss_start is None:
        # append section cuối file
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"[{slot_status_section}]")
        ss_start = len(lines)
        ss_end = len(lines)
    else:
        if ss_end is None:
            ss_end = len(lines)

    # --------- 3) rewrite SLOT_STATUS content ----------
    seen = set()
    new_section_lines: list[str] = []

    for ln in lines[ss_start:ss_end]:
        m = _SLOT_RE.match(ln)
        if m:
            indent, key, num_s, eq, _old, trail = m.groups()
            try:
                num = int(num_s)
            except ValueError:
                new_section_lines.append(ln)
                continue

            if 1 <= num <= slots:
                new_val = _desired(num)
                new_section_lines.append(f"{indent}{key}{num}{eq}{new_val}{trail}")
                seen.add(num)
                continue

        new_section_lines.append(ln)

    # append missing slots
    missing = [i for i in range(1, slots + 1) if i not in seen]
    if missing:
        if new_section_lines and new_section_lines[-1].strip() != "":
            new_section_lines.append("")
        for i in missing:
            new_section_lines.append(f"slot{i}={_desired(i)}")

    # --------- 4) rebuild + atomic write ----------
    out_lines = lines[:ss_start] + new_section_lines + lines[ss_end:]
    out_text = newline.join(out_lines) + newline

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


def _slot_test_has_value(
    lines: list[str],
    slot_idx: int,
    *,
    section_name: str = "SLOT_TEST",
    slots: int = 12,
) -> bool:
    """
    Text-based đọc SLOT_TEST để chịu được key trùng:
    - Nếu trong [SLOT_TEST] có bất kỳ dòng slot{idx}=<non-empty> -> True
    - Nếu section không có -> False
    """
    if not (1 <= slot_idx <= slots):
        return False

    start, end = _find_section_bounds(lines, section_name)
    if start is None:
        return False
    if end is None:
        end = len(lines)

    for ln in lines[start:end]:
        m = _SLOT_RE.match(ln)
        if not m:
            continue
        _indent, _key, num_s, _eq, val, _trail = m.groups()
        try:
            num = int(num_s)
        except ValueError:
            continue
        if num == slot_idx and str(val).strip() != "":
            return True
    return False


def update_ini_slot_status(
    ini_path: Union[str, Path],
    slot_idx: int,
    status: str,
    *,
    section_name: str = "SLOT_STATUS",
    slot_test_section: str = "SLOT_TEST",
    slots: int = 12,
    encoding: str = "utf-8",
) -> None:
    """
    Text-based update với “gate” theo SLOT_TEST:
    - Nếu status in {idle,item,stand_by,unknown}:
        + SLOT_TEST slot{idx} có value -> ghi 'item'
        + SLOT_TEST slot{idx} rỗng     -> ghi 'idle'
    - Nếu status in {pass,fail,testing,...}: ghi trực tiếp (như cũ)
    - Update tất cả dòng slot{idx}=... trong [SLOT_STATUS]
    - Nếu thiếu thì append vào cuối section
    - Giữ format/comment/các section khác
    """
    if not (1 <= slot_idx <= slots):
        raise ValueError(f"slot_idx out of range: {slot_idx}")

    st_in = str(status).strip().lower()
    if st_in not in _ALLOWED_STATUS:
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

    # --- Gate logic ---
    if st_in in _NEUTRAL_STATUS_GATE:
        has_job = _slot_test_has_value(lines, slot_idx, section_name=slot_test_section, slots=slots)
        st = "item" if has_job else "idle"
    else:
        # pass/fail/testing/... -> giữ nguyên
        st = st_in

    # locate SLOT_STATUS section bounds
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
    new_section: list[str] = []

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

def _parse_active_slots_from_slot_test(
    lines: list[str],
    *,
    section_name: str = "SLOT_TEST",
    slots: int = 12,
) -> Set[int]:
    """
    Active slot = có ít nhất 1 dòng slot{idx}=<non-empty> trong [SLOT_TEST]
    (key trùng vẫn ok: chỉ cần có 1 dòng non-empty là active)
    """
    start, end = _find_section_bounds(lines, section_name)
    if start is None:
        return set()
    if end is None:
        end = len(lines)

    active: Set[int] = set()
    for ln in lines[start:end]:
        m = _SLOT_RE.match(ln)
        if not m:
            continue
        _indent, _key, num_s, _eq, val, _trail = m.groups()
        try:
            idx = int(num_s)
        except ValueError:
            continue
        if 1 <= idx <= slots and str(val).strip() != "":
            active.add(idx)
    return active


def load_slot_status_from_ini(
    ini_path: Union[str, Path],
    *,
    section_name: str = "SLOT_STATUS",
    slot_test_section: str = "SLOT_TEST",
    slots: int = 12,
    encoding: str = "utf-8",
) -> Dict[int, str]:
    """
    Read-only, text-based parse.
    - Nếu key trùng (slot8 lặp) => dòng xuất hiện SAU cùng sẽ thắng.
    - Sau khi parse SLOT_STATUS xong:
        + nếu SLOT_TEST slotX có value và status hiện tại == 'idle' -> set 'item'
        + nếu status != 'idle' -> giữ nguyên
    """
    path = Path(ini_path)
    out: Dict[int, str] = {i: "idle" for i in range(1, slots + 1)}
    if not path.exists():
        return out

    lines = path.read_text(encoding=encoding, errors="replace").splitlines()

    # 1) parse SLOT_TEST -> active slots
    active_slots = _parse_active_slots_from_slot_test(lines, section_name=slot_test_section, slots=slots)

    # 2) parse SLOT_STATUS như cũ (last wins)
    in_section = False
    for ln in lines:
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

    # 3) apply rule: active slot + current idle -> item
    for idx in active_slots:
        if out.get(idx, "idle") == "idle":
            out[idx] = "item"

    return out