from __future__ import annotations

import configparser
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Union, Literal, Optional, Set, List
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

_ALLOWED_ENDING = {"CRLF", "LF", "CR", "NONE"}
_FIX_KV_RE = re.compile(r"^(\s*)(port|baudrate|ending_line|timeout)(\s*=\s*)(.*?)(\s*)$", re.IGNORECASE)


def _norm_ending(v: str, default: str = "CRLF") -> str:
    v = (v or "").strip().upper()
    return v if v in _ALLOWED_ENDING else default

@dataclass(frozen=True)
class FixtureConfig:
    port: str
    baudrate: int
    ending_line: str      # actual chars: "\r\n" | "\n" | "\r" | ""
    timeout: float
    slot_text: Dict[int, str]
    slot_command: Dict[int, str]
    slot_status: Dict[int, str] 

def load_fixture_cfg(path: str) -> FixtureConfig:
    # strict=False để không crash nếu config có key trùng (slot8 bị lặp)
    cfg = configparser.ConfigParser(strict=False)
    cfg.read(path, encoding="utf-8")


    port = cfg.get("FIXTURE", "port", fallback="").strip()
    baudrate = cfg.getint("FIXTURE", "baudrate", fallback=9600)
    ending_mode = cfg.get("FIXTURE", "ending_line", fallback="CRLF").strip().upper()
    ending_line = ENDING_MAP.get(ending_mode, "\r\n")
    timeout = cfg.getfloat("FIXTURE", "timeout", fallback=2.0)

    slot_text: Dict[int, str] = {}
    slot_command: Dict[int, str] = {}
    slot_status: Dict[int, str] = {}
    for i in range(1, 13):
        slot_text[i] = cfg.get("SLOT_TEST", f"slot{i}", fallback="").strip()
        slot_command[i] = cfg.get("SLOT_COMMAND", f"slot{i}", fallback="").strip()
        slot_status[i] = cfg.get("SLOT_STATUS", f"slot{i}", fallback="idle").strip()

    return FixtureConfig(
        port=port,
        baudrate=baudrate,
        ending_line=ending_line,
        timeout=timeout,
        slot_text=slot_text,
        slot_command=slot_command,
        slot_status=slot_status,
    )

def update_ini_fixture_section(
    ini_path: Union[str, Path],
    *,
    port: Optional[str] = None,
    baudrate: Optional[int] = None,
    ending_line: Optional[str] = None,   # "CRLF"|"LF"|"CR"|"NONE"
    timeout: Optional[float] = None,
    section_name: str = "FIXTURE",
    encoding: str = "utf-8",
) -> None:
    path = Path(ini_path)
    raw = path.read_bytes() if path.exists() else b""
    newline = "\r\n" if b"\r\n" in raw else "\n"
    lines = (raw.decode(encoding, errors="replace").splitlines() if raw else [])

    start, end = _find_section_bounds(lines, section_name)
    if start is None:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"[{section_name}]")
        start = len(lines)
        end = len(lines)
    if end is None:
        end = len(lines)

    want = {}
    if port is not None: want["port"] = (port or "").strip()
    if baudrate is not None: want["baudrate"] = str(int(baudrate))
    if ending_line is not None: want["ending_line"] = _norm_ending(ending_line)
    if timeout is not None: want["timeout"] = str(float(timeout))

    seen = {k: False for k in want.keys()}
    new_sec: list[str] = []
    for ln in lines[start:end]:
        m = _FIX_KV_RE.match(ln)
        if m:
            indent, key, eq, _old, trail = m.groups()
            k = key.lower()
            if k in want:
                new_sec.append(f"{indent}{key}{eq}{want[k]}{trail}")
                seen[k] = True
                continue
        new_sec.append(ln)

    # append missing keys
    missing = [k for k, ok in seen.items() if not ok]
    if missing:
        if new_sec and new_sec[-1].strip() != "":
            new_sec.append("")
        for k in missing:
            new_sec.append(f"{k}={want[k]}")

    out_lines = lines[:start] + new_sec + lines[end:]
    out_text = newline.join(out_lines) + newline
    _atomic_write_text(path, out_text, encoding=encoding)

def choose_slot_font(label: str) -> Tuple[str, int, str]:
    label = (label or "").strip()
    # Check if contain SPACE
    # If there is a word with len 6 or more, use smaller font
    words = label.split(" ")
    # find max len in words
    max_len = max(len(w) for w in words)
    if max_len == 4:
        return ("Tektur", 10, "bold")
    if max_len == 5:
        return ("Tektur", 9, "bold")
    if max_len == 6:
        return ("Tektur", 7, "bold")
    if max_len == 7:
        return ("Tektur", 6, "bold")
    if max_len == 8:
        return ("Tektur", 5, "bold")
    if max_len <= 3:
        return ("Tektur", 12, "bold")
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

def update_ini_manual_slot_info(
    ini_path: Union[str, Path],
    *,
    slot_idx: int,
    slot_test: Optional[str] = None,
    slot_cmd: Optional[str] = None,
    slot_test_section: str = "SLOT_TEST",
    slot_cmd_section: str = "SLOT_COMMAND",
    slots: int = 12,
    encoding: str = "utf-8",
) -> None:
    """
    Cập nhật thủ công thông tin slot:
      - [SLOT_TEST]  slot{idx}=<slot_test>
      - [SLOT_COMMAND] slot{idx}=<slot_cmd>   (section có thể đổi bằng slot_cmd_section)

    - Text-based: giữ comment/format
    - Nếu section chưa có -> tự tạo
    - Nếu slot bị lặp nhiều dòng -> update TẤT CẢ dòng trùng
    - Nếu chưa có key slot{idx} -> append vào cuối section
    - Atomic write
    """
    if not (1 <= int(slot_idx) <= int(slots)):
        raise ValueError(f"slot_idx out of range: {slot_idx}")

    path = Path(ini_path)

    if path.exists():
        raw = path.read_bytes()
        newline = _detect_newline(raw)
        lines = raw.decode(encoding, errors="replace").splitlines()
    else:
        newline = "\n"
        lines = []

    def _upsert_slot_value_in_section(
        lines_in: list[str],
        section_name: str,
        idx: int,
        value: str,
    ) -> list[str]:
        """
        Upsert slot{idx}=value trong section_name.
        Update tất cả dòng trùng. Nếu chưa có -> append.
        """
        start, end = _find_section_bounds(lines_in, section_name)

        # create section if missing
        if start is None:
            if lines_in and lines_in[-1].strip() != "":
                lines_in.append("")
            lines_in.append(f"[{section_name}]")
            start = len(lines_in)
            end = len(lines_in)
        if end is None:
            end = len(lines_in)

        target = int(idx)
        found_any = False
        new_sec: list[str] = []

        for ln in lines_in[start:end]:
            m = _SLOT_RE.match(ln)
            if m:
                indent, key, num_s, eq, _old, trail = m.groups()
                try:
                    num = int(num_s)
                except ValueError:
                    new_sec.append(ln)
                    continue

                if num == target:
                    # preserve indent/eq/trailing spaces
                    new_sec.append(f"{indent}{key}{num}{eq}{value}{trail}")
                    found_any = True
                    continue

            new_sec.append(ln)

        if not found_any:
            if new_sec and new_sec[-1].strip() != "":
                new_sec.append("")
            new_sec.append(f"slot{target}={value}")

        return lines_in[:start] + new_sec + lines_in[end:]

    # normalize values (allow empty string)
    if slot_test is not None:
        v = (slot_test or "").strip()
        lines = _upsert_slot_value_in_section(lines, slot_test_section, slot_idx, v)

    if slot_cmd is not None:
        v = (slot_cmd or "").strip()
        lines = _upsert_slot_value_in_section(lines, slot_cmd_section, slot_idx, v)

    out_text = newline.join(lines) + newline
    _atomic_write_text(path, out_text, encoding=encoding)

# ===================== STATION CONFIG =====================

_STATION_CMD_KEYS: Tuple[str, ...] = (
    # commands
    "open_cmd",
    "close_cmd",
    "status_cmd",
    "raster_state_cmd",

    # fallback patterns
    "expect",
    "reject",

    # per-case patterns (recommend)
    "sensor_expect",
    "sensor_reject",
    "stop_expect",
    "stop_reject",
    "raster_expect",
    "raster_reject",
)

# ====== config_go.py ======
# (1) update Station dataclass: thêm 2 dict slot_test/slot_command

@dataclass(frozen=True)
class Station:
    name: str
    cmds: Dict[str, str]                 # keys cố định theo _STATION_CMD_KEYS
    slot_test: Dict[int, str]            # slot_idx -> label (trước dấu phẩy)
    slot_command: Dict[int, str]         # slot_idx -> cmd   (sau dấu phẩy)


def _parse_station_slot_pair(raw: str) -> tuple[str, str]:
    """
    Parse: "SENSOR1, raster_state" -> ("SENSOR1", "raster_state")
    - Nếu không có dấu phẩy: coi như chỉ có slot_test, slot_command=""
    - Strip spaces an toàn
    """
    s = (raw or "").strip()
    if not s:
        return "", ""
    if "," not in s:
        return s, ""
    left, right = s.split(",", 1)
    return left.strip(), right.strip()


def load_station_cfg(
    path: Union[str, Path],
    *,
    encoding: str = "utf-8",
    station_root_section: str = "STATION",
    station_prefix: str = "STATION_",
    cmd_keys: Tuple[str, ...] = _STATION_CMD_KEYS,
    slots: int = 12,   # <-- NEW
) -> Tuple[Optional[str], List[Station], Dict[str, Station]]:
    """
    Return: (selected_station_name, stations_list, station_map)

    - Ưu tiên đọc thứ tự từ [STATION].stations (csv)
    - Fallback: scan all sections STATION_<NAME>
    - Mỗi station có:
        + cmds dict (như cũ)
        + slot_test / slot_command dict theo slot1..slot{slots}
          Format trong ini: slot1 = <slot_test>, <slot_command>
    """
    cfg = configparser.ConfigParser(strict=False)
    cfg.read(str(path), encoding=encoding)

    selected = cfg.get(station_root_section, "selected_station", fallback="").strip() or None

    # 1) lấy list station theo order nếu có
    station_names: List[str] = []
    if cfg.has_section(station_root_section):
        station_names = _split_csv(cfg.get(station_root_section, "stations", fallback=""))

    # 2) fallback scan nếu list rỗng
    if not station_names:
        for sec in cfg.sections():
            if sec.upper().startswith(station_prefix.upper()):
                name = sec[len(station_prefix):].strip()
                if name:
                    station_names.append(name)
        station_names.sort(key=lambda x: x.upper())

    stations_list: List[Station] = []
    station_map: Dict[str, Station] = {}

    for name in station_names:
        sec = f"{station_prefix}{name}"

        # defaults (kể cả khi thiếu section)
        cmds = {k: "" for k in cmd_keys}
        slot_test: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
        slot_command: Dict[int, str] = {i: "" for i in range(1, slots + 1)}

        if cfg.has_section(sec):
            # --- cmds (như cũ) ---
            for k in cmd_keys:
                cmds[k] = cfg.get(sec, k, fallback="").strip()

            # --- slots (NEW) ---
            for i in range(1, slots + 1):
                raw = cfg.get(sec, f"slot{i}", fallback="").strip()
                st, sc = _parse_station_slot_pair(raw)
                slot_test[i] = st
                slot_command[i] = sc

        st_obj = Station(
            name=name,
            cmds=cmds,
            slot_test=slot_test,
            slot_command=slot_command,
        )
        stations_list.append(st_obj)
        station_map[name] = st_obj

    # print(stations_list)
    # print(station_map)
    return selected, stations_list, station_map

def _split_csv(s: str) -> List[str]:
    # "AFT, ADL1,ADL2" -> ["AFT","ADL1","ADL2"]
    out: List[str] = []
    for p in (s or "").split(","):
        p = p.strip()
        if p:
            out.append(p)
    return out

def get_selected_station(
    path: Union[str, Path],
    *,
    encoding: str = "utf-8",
) -> Optional[Station]:
    selected, stations_list, station_map, mp = load_station_cfg(path, encoding=encoding)

    if not selected:
        return None
    
    # print(stations_list)
    print(station_map)
    return mp.get(selected)

