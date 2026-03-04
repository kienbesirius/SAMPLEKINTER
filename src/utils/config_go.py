# from __future__ import annotations

# import configparser
# from dataclasses import dataclass
# from typing import Dict, Any, Tuple, Union, Literal, Optional, Set, List
# import os
# import re
# import csv
# from io import StringIO
# import tempfile
# from pathlib import Path

# _UTF8_BOM = b"\xef\xbb\xbf"

# def strip_utf8_bom_inplace(path: str | Path) -> bool:
#     """
#     Xóa UTF-8 BOM ở đầu file (nếu có) và ghi lại file.
#     Return True nếu đã xóa BOM, False nếu không có BOM hoặc file không tồn tại.
#     """
#     p = Path(path)
#     if not p.is_file():
#         return False

#     data = p.read_bytes()
#     if not data.startswith(_UTF8_BOM):
#         return False

#     new_data = data[len(_UTF8_BOM):]

#     # atomic write: ghi ra temp trong cùng thư mục rồi replace
#     with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(p.parent), prefix=p.name + ".", suffix=".tmp") as f:
#         tmp_path = Path(f.name)
#         f.write(new_data)
#         f.flush()
#         os.fsync(f.fileno())

#     os.replace(str(tmp_path), str(p))
#     return True


# def try_strip_utf8_bom(path: str | Path) -> None:
#     """Không throw: có lỗi thì bỏ qua."""
#     try:
#         strip_utf8_bom_inplace(path)
#     except Exception:
#         pass

# ENDING_MAP = {
#     "CRLF": "\r\n",
#     "LF": "\n",
#     "CR": "\r",
#     "NONE": "",
# }

# _ALLOWED_ENDING = {"CRLF", "LF", "CR", "NONE"}
# _FIX_KV_RE = re.compile(r"^(\s*)(port|baudrate|ending_line|timeout)(\s*=\s*)(.*?)(\s*)$", re.IGNORECASE)


# def _norm_ending(v: str, default: str = "CRLF") -> str:
#     v = (v or "").strip().upper()
#     return v if v in _ALLOWED_ENDING else default

# @dataclass(frozen=True)
# class FixtureConfig:
#     port: str
#     baudrate: int
#     ending_line: str      # actual chars: "\r\n" | "\n" | "\r" | ""
#     timeout: float
#     slot_text: Dict[int, str]
#     slot_command: Dict[int, str]
#     slot_status: Dict[int, str] 
#     slot_guide: Dict[int, str]
#     slot_image: Dict[int, str]

# def load_fixture_cfg(path: str) -> FixtureConfig:
#     # strict=False để không crash nếu config có key trùng (slot8 bị lặp)
#     cfg = configparser.ConfigParser(strict=False)
#     # cfg.read(path, encoding="utf-8-sig")
#     try_strip_utf8_bom(path)
#     cfg.read(path, encoding=_ini_encoding("utf-8-sig"))


#     port = cfg.get("FIXTURE", "port", fallback="").strip()
#     baudrate = cfg.getint("FIXTURE", "baudrate", fallback=9600)
#     ending_mode = cfg.get("FIXTURE", "ending_line", fallback="CRLF").strip().upper()
#     ending_line = ENDING_MAP.get(ending_mode, "\r\n")
#     timeout = cfg.getfloat("FIXTURE", "timeout", fallback=2.0)

#     slot_text: Dict[int, str] = {}
#     slot_command: Dict[int, str] = {}
#     slot_status: Dict[int, str] = {}
#     slot_guide: Dict[int, str] = {}
#     slot_image: Dict[int, str] = {}
#     for i in range(1, 13):
#         slot_text[i] = cfg.get("SLOT_TEST", f"slot{i}", fallback="").strip()
#         slot_command[i] = cfg.get("SLOT_COMMAND", f"slot{i}", fallback="").strip()
#         slot_status[i] = cfg.get("SLOT_STATUS", f"slot{i}", fallback="idle").strip()

#         g = cfg.get("SLOT_GUIDE", f"slot{i}", fallback="").strip()
#         slot_guide[i] = g.replace(r"\n", "\n")
#         slot_image[i] = cfg.get("SLOT_IMAGE", f"slot{i}", fallback="").strip()
#     # for i in range(1, 13):
#     #     slot_text[i] = cfg.get("SLOT_TEST", f"slot{i}", fallback="").strip()
#     #     slot_command[i] = cfg.get("SLOT_COMMAND", f"slot{i}", fallback="").strip()
#     #     slot_status[i] = cfg.get("SLOT_STATUS", f"slot{i}", fallback="idle").strip()

#     return FixtureConfig(
#         port=port,
#         baudrate=baudrate,
#         ending_line=ending_line,
#         timeout=timeout,
#         slot_text=slot_text,
#         slot_command=slot_command,
#         slot_status=slot_status,
#         slot_guide=slot_guide,
#         slot_image=slot_image,
#     )

# def update_ini_fixture_section(
#     ini_path: Union[str, Path],
#     *,
#     port: Optional[str] = None,
#     baudrate: Optional[int] = None,
#     ending_line: Optional[str] = None,   # "CRLF"|"LF"|"CR"|"NONE"
#     timeout: Optional[float] = None,
#     section_name: str = "FIXTURE",
#     encoding: str = "utf-8-sig",
# ) -> None:
#     path = Path(ini_path)
#     raw = path.read_bytes() if path.exists() else b""
#     newline = "\r\n" if b"\r\n" in raw else "\n"
#     lines = (raw.decode(_ini_encoding(encoding), errors="replace").splitlines() if raw else [])

#     start, end = _find_section_bounds(lines, section_name)
#     if start is None:
#         if lines and lines[-1].strip() != "":
#             lines.append("")
#         lines.append(f"[{section_name}]")
#         start = len(lines)
#         end = len(lines)
#     if end is None:
#         end = len(lines)

#     want = {}
#     if port is not None: want["port"] = (port or "").strip()
#     if baudrate is not None: want["baudrate"] = str(int(baudrate))
#     if ending_line is not None: want["ending_line"] = _norm_ending(ending_line)
#     if timeout is not None: want["timeout"] = str(float(timeout))

#     seen = {k: False for k in want.keys()}
#     new_sec: list[str] = []
#     for ln in lines[start:end]:
#         m = _FIX_KV_RE.match(ln)
#         if m:
#             indent, key, eq, _old, trail = m.groups()
#             k = key.lower()
#             if k in want:
#                 new_sec.append(f"{indent}{key}{eq}{want[k]}{trail}")
#                 seen[k] = True
#                 continue
#         new_sec.append(ln)

#     # append missing keys
#     missing = [k for k, ok in seen.items() if not ok]
#     if missing:
#         if new_sec and new_sec[-1].strip() != "":
#             new_sec.append("")
#         for k in missing:
#             new_sec.append(f"{k}={want[k]}")

#     out_lines = lines[:start] + new_sec + lines[end:]
#     out_text = newline.join(out_lines) + newline
#     _atomic_write_text(path, out_text, encoding=encoding)

# def update_ini_slot_guide(
#     ini_path: Union[str, Path],
#     *,
#     slot_idx: int,
#     guide_text: str,
#     section_name: str = "SLOT_GUIDE",
#     slots: int = 12,
#     encoding: str = "utf-8-sig",
# ) -> None:
#     if not (1 <= int(slot_idx) <= int(slots)):
#         raise ValueError(f"slot_idx out of range: {slot_idx}")

#     path = Path(ini_path)
#     if path.exists():
#         raw = path.read_bytes()
#         newline = _detect_newline(raw)
#         lines = raw.decode(_ini_encoding(encoding), errors="replace").splitlines()
#     else:
#         newline = "\n"
#         lines = []

#     # encode \n to literal to keep single-line ini
#     v = (guide_text or "").replace("\n", r"\n")

#     # reuse your internal helper pattern from update_ini_manual_slot_info
#     def _upsert(lines_in: list[str]) -> list[str]:
#         start, end = _find_section_bounds(lines_in, section_name)
#         if start is None:
#             if lines_in and lines_in[-1].strip() != "":
#                 lines_in.append("")
#             lines_in.append(f"[{section_name}]")
#             start = len(lines_in)
#             end = len(lines_in)
#         if end is None:
#             end = len(lines_in)

#         found = False
#         new_sec: list[str] = []
#         for ln in lines_in[start:end]:
#             m = _SLOT_RE.match(ln)
#             if m:
#                 indent, key, num_s, eq, _old, trail = m.groups()
#                 try:
#                     num = int(num_s)
#                 except ValueError:
#                     new_sec.append(ln)
#                     continue
#                 if num == int(slot_idx):
#                     new_sec.append(f"{indent}{key}{num}{eq}{v}{trail}")
#                     found = True
#                     continue
#             new_sec.append(ln)

#         if not found:
#             if new_sec and new_sec[-1].strip() != "":
#                 new_sec.append("")
#             new_sec.append(f"slot{int(slot_idx)}={v}")

#         return lines_in[:start] + new_sec + lines_in[end:]

#     lines = _upsert(lines)
#     out_text = newline.join(lines) + newline
#     _atomic_write_text(path, out_text, encoding=encoding)

# def update_ini_slot_image(
#     ini_path: Union[str, Path],
#     *,
#     slot_idx: int,
#     image_key: str,
#     section_name: str = "SLOT_IMAGE",
#     slots: int = 12,
#     encoding: str = "utf-8-sig",
# ) -> None:
#     path = Path(ini_path)
#     if path.exists():
#         raw = path.read_bytes()
#         newline = _detect_newline(raw)
#         lines = raw.decode(_ini_encoding(encoding), errors="replace").splitlines()
#     else:
#         newline = "\n"
#         lines = []

#     v = (image_key or "").strip()

#     start, end = _find_section_bounds(lines, section_name)
#     if start is None:
#         if lines and lines[-1].strip() != "":
#             lines.append("")
#         lines.append(f"[{section_name}]")
#         start = len(lines)
#         end = len(lines)
#     if end is None:
#         end = len(lines)

#     found = False
#     new_sec: list[str] = []
#     for ln in lines[start:end]:
#         m = _SLOT_RE.match(ln)
#         if m:
#             indent, key, num_s, eq, _old, trail = m.groups()
#             try:
#                 num = int(num_s)
#             except ValueError:
#                 new_sec.append(ln); continue
#             if num == int(slot_idx):
#                 new_sec.append(f"{indent}{key}{num}{eq}{v}{trail}")
#                 found = True
#                 continue
#         new_sec.append(ln)

#     if not found:
#         if new_sec and new_sec[-1].strip() != "":
#             new_sec.append("")
#         new_sec.append(f"slot{int(slot_idx)}={v}")

#     out_text = newline.join(lines[:start] + new_sec + lines[end:]) + newline
#     _atomic_write_text(path, out_text, encoding=encoding)

# def choose_slot_font(label: str) -> Tuple[str, int, str]:
#     label = (label or "").strip()
#     # Check if contain SPACE
#     # If there is a word with len 6 or more, use smaller font
#     words = label.split(" ")
#     # find max len in words
#     max_len = max(len(w) for w in words)
#     if max_len == 4:
#         return ("Tektur", 10, "bold")
#     if max_len == 5:
#         return ("Tektur", 9, "bold")
#     if max_len == 6:
#         return ("Tektur", 7, "bold")
#     if max_len == 7:
#         return ("Tektur", 6, "bold")
#     if max_len == 8:
#         return ("Tektur", 5, "bold")
#     if max_len <= 3:
#         return ("Tektur", 12, "bold")
#     return ("Tektur", 11, "bold")         # FORCE STOP

# _SLOT_RE = re.compile(r"^(\s*)(slot)(\d+)(\s*=\s*)(.*?)(\s*)$", re.IGNORECASE)
# _SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
# _NEUTRAL_STATUS_GATE = {"idle", "item", "stand_by", "unknown"}  # nhóm “trung tính”


# def _find_section_bounds(lines: list[str], section_name: str) -> Tuple[Optional[int], Optional[int]]:
#     """
#     Return (start_idx, end_idx) of section content (not including [SECTION] line)
#     If section not found -> (None, None)
#     """
#     start = None
#     end = None
#     for i, ln in enumerate(lines):
#         m = _SECTION_RE.match(ln)
#         if not m:
#             continue
#         name = m.group(1).strip()
#         if start is None and name.upper() == section_name.upper():
#             start = i + 1
#             continue
#         if start is not None:
#             end = i
#             break
#     return start, end


# def reset_slot_status_section_to_idle(
#     ini_path: Union[str, Path],
#     *,
#     slot_test_section: str = "SLOT_TEST",
#     slot_status_section: str = "SLOT_STATUS",
#     slots: int = 12,
#     idle_value: str = "idle",
#     item_value: str = "item",
#     encoding: str = "utf-8-sig",
# ) -> None:
#     """
#     Text-based (giữ format/comment):
#     - Đọc [SLOT_TEST] để biết slot nào "có bài" (value != "")
#     - Ghi [SLOT_STATUS]:
#         + slot rỗng -> idle_value
#         + slot có bài -> item_value
#     - Nếu thiếu slot -> append
#     - Nếu trùng slot -> update tất cả dòng trùng
#     - Atomic write
#     """
#     path = Path(ini_path)

#     raw = path.read_bytes()
#     newline = "\r\n" if b"\r\n" in raw else "\n"

#     text = raw.decode(_ini_encoding(encoding), errors="replace")
#     lines = text.splitlines()

#     # --------- 1) parse SLOT_TEST -> set các slot "active" ----------
#     st_start, st_end = _find_section_bounds(lines, slot_test_section)
#     if st_start is None:
#         active_slots: Set[int] = set()
#     else:
#         if st_end is None:
#             st_end = len(lines)

#         active_slots = set()
#         for ln in lines[st_start:st_end]:
#             m = _SLOT_RE.match(ln)
#             if not m:
#                 continue
#             indent, key, num_s, eq, val, trail = m.groups()
#             try:
#                 num = int(num_s)
#             except ValueError:
#                 continue
#             if 1 <= num <= slots:
#                 if str(val).strip() != "":
#                     # nếu slot bị lặp, chỉ cần 1 dòng có value là coi như active
#                     active_slots.add(num)

#     def _desired(num: int) -> str:
#         return item_value if num in active_slots else idle_value

#     # --------- 2) locate/create SLOT_STATUS ----------
#     ss_start, ss_end = _find_section_bounds(lines, slot_status_section)

#     if ss_start is None:
#         # append section cuối file
#         if lines and lines[-1].strip() != "":
#             lines.append("")
#         lines.append(f"[{slot_status_section}]")
#         ss_start = len(lines)
#         ss_end = len(lines)
#     else:
#         if ss_end is None:
#             ss_end = len(lines)

#     # --------- 3) rewrite SLOT_STATUS content ----------
#     seen = set()
#     new_section_lines: list[str] = []

#     for ln in lines[ss_start:ss_end]:
#         m = _SLOT_RE.match(ln)
#         if m:
#             indent, key, num_s, eq, _old, trail = m.groups()
#             try:
#                 num = int(num_s)
#             except ValueError:
#                 new_section_lines.append(ln)
#                 continue

#             if 1 <= num <= slots:
#                 new_val = _desired(num)
#                 new_section_lines.append(f"{indent}{key}{num}{eq}{new_val}{trail}")
#                 seen.add(num)
#                 continue

#         new_section_lines.append(ln)

#     # append missing slots
#     missing = [i for i in range(1, slots + 1) if i not in seen]
#     if missing:
#         if new_section_lines and new_section_lines[-1].strip() != "":
#             new_section_lines.append("")
#         for i in missing:
#             new_section_lines.append(f"slot{i}={_desired(i)}")

#     # --------- 4) rebuild + atomic write ----------
#     out_lines = lines[:ss_start] + new_section_lines + lines[ss_end:]
#     out_text = newline.join(out_lines) + newline

#     tmp_dir = str(path.parent)
#     fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=tmp_dir, text=True)
#     try:
#         with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
#             f.write(out_text)
#         os.replace(tmp_name, path)
#     finally:
#         try:
#             os.remove(tmp_name)
#         except FileNotFoundError:
#             pass


# SlotStatus = Literal["pass", "fail", "testing", "idle"]
# _ALLOWED_STATUS = {"pass", "fail", "testing", "idle"}

# def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8-sig") -> None:
#     tmp_dir = str(path.parent)
#     fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=tmp_dir, text=True)
#     try:
#         with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
#             f.write(text)
#         os.replace(tmp_name, path)
#     finally:
#         try:
#             os.remove(tmp_name)
#         except FileNotFoundError:
#             pass


# def _detect_newline(raw: bytes) -> str:
#     return "\r\n" if b"\r\n" in raw else "\n"


# def _slot_test_has_value(
#     lines: list[str],
#     slot_idx: int,
#     *,
#     section_name: str = "SLOT_TEST",
#     slots: int = 12,
# ) -> bool:
#     """
#     Text-based đọc SLOT_TEST để chịu được key trùng:
#     - Nếu trong [SLOT_TEST] có bất kỳ dòng slot{idx}=<non-empty> -> True
#     - Nếu section không có -> False
#     """
#     if not (1 <= slot_idx <= slots):
#         return False

#     start, end = _find_section_bounds(lines, section_name)
#     if start is None:
#         return False
#     if end is None:
#         end = len(lines)

#     for ln in lines[start:end]:
#         m = _SLOT_RE.match(ln)
#         if not m:
#             continue
#         _indent, _key, num_s, _eq, val, _trail = m.groups()
#         try:
#             num = int(num_s)
#         except ValueError:
#             continue
#         if num == slot_idx and str(val).strip() != "":
#             return True
#     return False


# def update_ini_slot_status(
#     ini_path: Union[str, Path],
#     slot_idx: int,
#     status: str,
#     *,
#     section_name: str = "SLOT_STATUS",
#     slot_test_section: str = "SLOT_TEST",
#     slots: int = 12,
#     encoding: str = "utf-8-sig",
# ) -> None:
#     """
#     Text-based update với “gate” theo SLOT_TEST:
#     - Nếu status in {idle,item,stand_by,unknown}:
#         + SLOT_TEST slot{idx} có value -> ghi 'item'
#         + SLOT_TEST slot{idx} rỗng     -> ghi 'idle'
#     - Nếu status in {pass,fail,testing,...}: ghi trực tiếp (như cũ)
#     - Update tất cả dòng slot{idx}=... trong [SLOT_STATUS]
#     - Nếu thiếu thì append vào cuối section
#     - Giữ format/comment/các section khác
#     """
#     if not (1 <= slot_idx <= slots):
#         raise ValueError(f"slot_idx out of range: {slot_idx}")

#     st_in = str(status).strip().lower()
#     if st_in not in _ALLOWED_STATUS:
#         raise ValueError(f"Invalid status: {status!r}. Allowed: {sorted(_ALLOWED_STATUS)}")

#     path = Path(ini_path)

#     if path.exists():
#         raw = path.read_bytes()
#         newline = _detect_newline(raw)
#         text = raw.decode(_ini_encoding(encoding), errors="replace")
#         lines = text.splitlines()
#     else:
#         newline = "\n"
#         lines = []

#     # --- Gate logic ---
#     if st_in in _NEUTRAL_STATUS_GATE:
#         has_job = _slot_test_has_value(lines, slot_idx, section_name=slot_test_section, slots=slots)
#         st = "item" if has_job else "idle"
#     else:
#         # pass/fail/testing/... -> giữ nguyên
#         st = st_in

#     # locate SLOT_STATUS section bounds
#     start = None
#     end = None
#     for i, ln in enumerate(lines):
#         m = _SECTION_RE.match(ln)
#         if not m:
#             continue
#         name = m.group(1).strip()
#         if start is None and name.upper() == section_name.upper():
#             start = i + 1
#             continue
#         if start is not None:
#             end = i
#             break

#     if start is None:
#         # append section at EOF
#         if lines and lines[-1].strip() != "":
#             lines.append("")
#         lines.append(f"[{section_name}]")
#         start = len(lines)
#         end = len(lines)
#     if end is None:
#         end = len(lines)

#     target = slot_idx
#     found_any = False
#     new_section: list[str] = []

#     for ln in lines[start:end]:
#         m = _SLOT_RE.match(ln)
#         if m:
#             indent, key, num_s, eq, _old, trail = m.groups()
#             try:
#                 num = int(num_s)
#             except ValueError:
#                 new_section.append(ln)
#                 continue

#             if num == target:
#                 # update line, preserve indent/spaces around "=" and trailing spaces
#                 new_section.append(f"{indent}{key}{num}{eq}{st}{trail}")
#                 found_any = True
#                 continue

#         new_section.append(ln)

#     if not found_any:
#         # append new slot line
#         if new_section and new_section[-1].strip() != "":
#             new_section.append("")
#         new_section.append(f"slot{target}={st}")

#     out_lines = lines[:start] + new_section + lines[end:]
#     out_text = newline.join(out_lines) + newline
#     _atomic_write_text(path, out_text, encoding=encoding)

# def _parse_active_slots_from_slot_test(
#     lines: list[str],
#     *,
#     section_name: str = "SLOT_TEST",
#     slots: int = 12,
# ) -> Set[int]:
#     """
#     Active slot = có ít nhất 1 dòng slot{idx}=<non-empty> trong [SLOT_TEST]
#     (key trùng vẫn ok: chỉ cần có 1 dòng non-empty là active)
#     """
#     start, end = _find_section_bounds(lines, section_name)
#     if start is None:
#         return set()
#     if end is None:
#         end = len(lines)

#     active: Set[int] = set()
#     for ln in lines[start:end]:
#         m = _SLOT_RE.match(ln)
#         if not m:
#             continue
#         _indent, _key, num_s, _eq, val, _trail = m.groups()
#         try:
#             idx = int(num_s)
#         except ValueError:
#             continue
#         if 1 <= idx <= slots and str(val).strip() != "":
#             active.add(idx)
#     return active


# def load_slot_status_from_ini(
#     ini_path: Union[str, Path],
#     *,
#     section_name: str = "SLOT_STATUS",
#     slot_test_section: str = "SLOT_TEST",
#     slots: int = 12,
#     encoding: str = "utf-8-sig",
# ) -> Dict[int, str]:
#     """
#     Read-only, text-based parse.
#     - Nếu key trùng (slot8 lặp) => dòng xuất hiện SAU cùng sẽ thắng.
#     - Sau khi parse SLOT_STATUS xong:
#         + nếu SLOT_TEST slotX có value và status hiện tại == 'idle' -> set 'item'
#         + nếu status != 'idle' -> giữ nguyên
#     """
#     path = Path(ini_path)
#     out: Dict[int, str] = {i: "idle" for i in range(1, slots + 1)}
#     if not path.exists():
#         return out

#     lines = path.read_text(encoding=encoding, errors="replace").splitlines()

#     # 1) parse SLOT_TEST -> active slots
#     active_slots = _parse_active_slots_from_slot_test(lines, section_name=slot_test_section, slots=slots)

#     # 2) parse SLOT_STATUS như cũ (last wins)
#     in_section = False
#     for ln in lines:
#         msec = _SECTION_RE.match(ln)
#         if msec:
#             in_section = (msec.group(1).strip().upper() == section_name.upper())
#             continue
#         if not in_section:
#             continue

#         m = _SLOT_RE.match(ln)
#         if not m:
#             continue
#         _indent, _key, num_s, _eq, val, _trail = m.groups()
#         try:
#             idx = int(num_s)
#         except ValueError:
#             continue
#         if 1 <= idx <= slots:
#             out[idx] = val.strip().lower() or "idle"

#     # 3) apply rule: active slot + current idle -> item
#     for idx in active_slots:
#         if out.get(idx, "idle") == "idle":
#             out[idx] = "item"

#     return out

# def update_ini_manual_slot_info(
#     ini_path: Union[str, Path],
#     *,
#     slot_idx: int,
#     slot_test: Optional[str] = None,
#     slot_cmd: Optional[str] = None,
#     slot_test_section: str = "SLOT_TEST",
#     slot_cmd_section: str = "SLOT_COMMAND",
#     slots: int = 12,
#     encoding: str = "utf-8-sig",
# ) -> None:
#     """
#     Cập nhật thủ công thông tin slot:
#       - [SLOT_TEST]  slot{idx}=<slot_test>
#       - [SLOT_COMMAND] slot{idx}=<slot_cmd>   (section có thể đổi bằng slot_cmd_section)

#     - Text-based: giữ comment/format
#     - Nếu section chưa có -> tự tạo
#     - Nếu slot bị lặp nhiều dòng -> update TẤT CẢ dòng trùng
#     - Nếu chưa có key slot{idx} -> append vào cuối section
#     - Atomic write
#     """
#     if not (1 <= int(slot_idx) <= int(slots)):
#         raise ValueError(f"slot_idx out of range: {slot_idx}")

#     path = Path(ini_path)

#     if path.exists():
#         raw = path.read_bytes()
#         newline = _detect_newline(raw)
#         lines = raw.decode(_ini_encoding(encoding), errors="replace").splitlines()
#     else:
#         newline = "\n"
#         lines = []

#     def _upsert_slot_value_in_section(
#         lines_in: list[str],
#         section_name: str,
#         idx: int,
#         value: str,
#     ) -> list[str]:
#         """
#         Upsert slot{idx}=value trong section_name.
#         Update tất cả dòng trùng. Nếu chưa có -> append.
#         """
#         start, end = _find_section_bounds(lines_in, section_name)

#         # create section if missing
#         if start is None:
#             if lines_in and lines_in[-1].strip() != "":
#                 lines_in.append("")
#             lines_in.append(f"[{section_name}]")
#             start = len(lines_in)
#             end = len(lines_in)
#         if end is None:
#             end = len(lines_in)

#         target = int(idx)
#         found_any = False
#         new_sec: list[str] = []

#         for ln in lines_in[start:end]:
#             m = _SLOT_RE.match(ln)
#             if m:
#                 indent, key, num_s, eq, _old, trail = m.groups()
#                 try:
#                     num = int(num_s)
#                 except ValueError:
#                     new_sec.append(ln)
#                     continue

#                 if num == target:
#                     # preserve indent/eq/trailing spaces
#                     new_sec.append(f"{indent}{key}{num}{eq}{value}{trail}")
#                     found_any = True
#                     continue

#             new_sec.append(ln)

#         if not found_any:
#             if new_sec and new_sec[-1].strip() != "":
#                 new_sec.append("")
#             new_sec.append(f"slot{target}={value}")

#         return lines_in[:start] + new_sec + lines_in[end:]

#     # normalize values (allow empty string)
#     if slot_test is not None:
#         v = (slot_test or "").strip()
#         lines = _upsert_slot_value_in_section(lines, slot_test_section, slot_idx, v)

#     if slot_cmd is not None:
#         v = (slot_cmd or "").strip()
#         lines = _upsert_slot_value_in_section(lines, slot_cmd_section, slot_idx, v)

#     out_text = newline.join(lines) + newline
#     _atomic_write_text(path, out_text, encoding=encoding)

# # ===================== STATION CONFIG =====================

# _STATION_CMD_KEYS: Tuple[str, ...] = (
#     # commands
#     "open_cmd",
#     "close_cmd",
#     "status_cmd",
#     "raster_state_cmd",

#     # fallback patterns
#     "expect",
#     "reject",

#     # per-case patterns (recommend)
#     "sensor_expect",
#     "sensor_reject",
#     "stop_expect",
#     "stop_reject",
#     "raster_expect",
#     "raster_reject",
# )

# # ====== config_go.py ======
# # (1) update Station dataclass: thêm 2 dict slot_test/slot_command

# @dataclass(frozen=True)
# class Station:
#     name: str
#     cmds: Dict[str, str]                 # keys cố định theo _STATION_CMD_KEYS
#     slot_test: Dict[int, str]            # slot_idx -> label (trước dấu phẩy)
#     slot_command: Dict[int, str]         # slot_idx -> cmd   (sau dấu phẩy)
#     slot_guide: Dict[int, str]
#     slot_image: Dict[int, str]  

# def _parse_station_slot_pair(raw: str) -> tuple[str, str]:
#     """
#     Parse: "SENSOR1, raster_state" -> ("SENSOR1", "raster_state")
#     - Nếu không có dấu phẩy: coi như chỉ có slot_test, slot_command=""
#     - Strip spaces an toàn
#     """
#     s = (raw or "").strip()
#     if not s:
#         return "", ""
#     if "," not in s:
#         return s, ""
#     left, right = s.split(",", 1)
#     return left.strip(), right.strip()

# # def _parse_station_slot_line(v: str) -> tuple[str, str, str]:
# #     v = (v or "").strip()
# #     if not v:
# #         return "", "", ""
# #     row = next(csv.reader(StringIO(v), skipinitialspace=True))
# #     # row: [test, cmd, guide]  (guide có thể thiếu)
# #     test = row[0].strip() if len(row) > 0 else ""
# #     cmd  = row[1].strip() if len(row) > 1 else ""
# #     guide = row[2] if len(row) > 2 else ""
# #     guide = guide.strip()
# #     # bỏ quote ngoài nếu còn
# #     if len(guide) >= 2 and guide[0] == '"' and guide[-1] == '"':
# #         guide = guide[1:-1]
# #     guide = guide.replace(r"\n", "\n")
# #     return test, cmd, guide

# def _parse_station_slot_line(v: str) -> tuple[str, str, str, str]:
#     v = (v or "").strip()
#     if not v:
#         return "", "", "", ""
#     row = next(csv.reader(StringIO(v), skipinitialspace=True))

#     test  = row[0].strip() if len(row) > 0 else ""
#     cmd   = row[1].strip() if len(row) > 1 else ""
#     guide = row[2].strip() if len(row) > 2 else ""
#     img   = row[3].strip() if len(row) > 3 else ""

#     # bỏ quote ngoài nếu còn (csv thường đã xử lý, nhưng giữ để chắc)
#     if len(guide) >= 2 and guide[0] == '"' and guide[-1] == '"':
#         guide = guide[1:-1]
#     guide = guide.replace(r"\n", "\n")
#     return test, cmd, guide, img


# # ===================== TEST PLAN CSV (new) =====================
# # Quy ước:
# # - test_plan/ nằm cùng level với config.ini và file binary
# # - mỗi file: <StationName>.csv
# # - dòng đầu tiên (meta): StationName,bechjkjen,...
# #   + StationName phải TRÙNG tên file (stem)
# #   + cột 2 phải đúng "bechjkjen" (lowercase) -> nếu không thì bỏ qua file
# #
# # CSV format tối thiểu (sau meta + header):
# # slot,slot_text,slot_cmd,expect,reject,sensor_expect/raster_expect,sensor_reject/raster_reject,stop_expect,stop_reject,guide,image_guide,note

# _TESTPLAN_OWNER_TAG = "bechjkjen"

# @dataclass(frozen=True)
# class TestPlan:
#     name: str
#     station: Station
#     slot_expect: Dict[int, str]
#     slot_reject: Dict[int, str]
#     source_csv: Path

# _KEYVAL_RE_TEMPLATE = r"^(\s*)({key})(\s*=\s*)(.*?)(\s*)$"

# def _strip_outer_quotes(s: str) -> str:
#     s = (s or "").strip()
#     # bỏ nhiều lớp quote nếu có (vd: """text""" )
#     while len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
#         s = s[1:-1].strip()
#     return s

# def _decode_guide_text(s: str) -> str:
#     s = _strip_outer_quotes(s)
#     return (s or "").replace(r"\n", "\n").strip()

# def _encode_guide_for_ini(s: str) -> str:
#     # ini giữ 1 dòng, dùng literal \n
#     return (s or "").replace("\n", r"\n")

# def get_test_plan_dir(
#     ini_path: Union[str, Path],
#     *,
#     test_plan_dirname: str = "test_plan",
# ) -> Path:
#     """
#     Trả về path thư mục test_plan/ cùng level với config.ini.
#     """
#     base_dir = Path(ini_path).resolve().parent
#     return base_dir / test_plan_dirname

# def list_test_plans(
#     ini_path: Union[str, Path],
#     *,
#     test_plan_dirname: str = "test_plan",
#     owner_tag: str = _TESTPLAN_OWNER_TAG,
# ) -> Tuple[List[str], Dict[str, Path]]:
#     """
#     Scan test_plan/**.csv và trả về:
#       (list_station_names, map_name_to_csv_path)

#     Layout mới (strict):
#       test_plan/
#         FATP/ | PCBA/ | ...
#           <Project>/
#             <Station>/
#               <Project>_<Station>.csv
#               (optional) *.png  # ảnh guide nằm cùng thư mục CSV

#     Rule CSV hợp lệ (giữ như cũ + strict thêm path):
#       - file stem (VD: Hapuka_MT) phải == meta[0]
#       - meta[1].lower() phải == owner_tag (default: bechjkjen)
#       - file stem phải match thư mục đang ở:
#           <Project>_<Station>.csv  ==> nằm trong  .../<Project>/<Station>/

#     Strict cleanup:
#       - CSV sai rule -> xoá luôn (unlink)
#       - Ảnh được reference trong cột image_guide:
#           + nếu file tồn tại nhưng không phải .png -> xoá
#           + nếu .png nhưng header không đúng PNG -> xoá
#         (ảnh chỉ được cleanup best-effort, không gate việc add CSV)
#     """
#     d = get_test_plan_dir(ini_path, test_plan_dirname=test_plan_dirname)
#     mp: Dict[str, Path] = {}
#     if not d.exists() or not d.is_dir():
#         return [], {}

#     owner = (owner_tag or "").strip().lower()

#     def _safe_unlink(fp: Path) -> None:
#         try:
#             if fp.exists() and fp.is_file():
#                 fp.unlink()
#         except Exception:
#             pass

#     def _split_plan_name(stem: str) -> Optional[Tuple[str, str]]:
#         """
#         stem: <Project>_<Station>
#         station có thể chứa underscore (vd: sample_test) => split 1 lần.
#         """
#         s = (stem or "").strip()
#         if not s or "_" not in s:
#             return None
#         proj, stn = s.split("_", 1)
#         proj = proj.strip()
#         stn = stn.strip()
#         if not proj or not stn:
#             return None
#         return proj, stn

#     def _path_matches_folder(csv_path: Path, proj: str, stn: str) -> bool:
#         """
#         .../<Project>/<Station>/<Project>_<Station>.csv
#         """
#         try:
#             st_dir = csv_path.parent
#             pr_dir = st_dir.parent
#             if not st_dir or not pr_dir:
#                 return False
#             # tolerant case (Windows)
#             return (pr_dir.name.lower() == proj.lower()) and (st_dir.name.lower() == stn.lower())
#         except Exception:
#             return False

#     def _is_valid_png_header(img_path: Path) -> bool:
#         try:
#             with img_path.open("rb") as f:
#                 sig = f.read(8)
#             return sig == b"\x89PNG\r\n\x1a\n"
#         except Exception:
#             return False

#     def _cleanup_images_referenced(csv_path: Path) -> None:
#         """
#         Read CSV (skip meta + header) and cleanup bad image files referenced in column image_guide.
#         Column index: 10
#         """
#         folder = csv_path.parent
#         try_strip_utf8_bom(csv_path)

#         refs: Set[str] = set()
#         try:
#             with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
#                 r = csv.reader(f)
#                 _meta = next(r, None)
#                 _hdr = next(r, None)
#                 for row in r:
#                     if not row:
#                         continue
#                     if len(row) < 11:
#                         continue
#                     im = (row[10] or "").strip()
#                     if im:
#                         refs.add(im)
#         except Exception:
#             return

#         for im in sorted(refs):
#             # chỉ cho phép filename nằm cùng folder (không cho path)
#             if ("/" in im) or ("\\" in im):
#                 continue
#             im_p = folder / im
#             suf = im_p.suffix.lower()

#             if not im_p.exists() or not im_p.is_file():
#                 continue

#             if suf != ".png":
#                 _safe_unlink(im_p)
#                 continue

#             if not _is_valid_png_header(im_p):
#                 _safe_unlink(im_p)

#     # NOTE: rglob để quét mọi folder con (FATP/PCBA/...)
#     # sort theo path string để deterministic; nếu trùng stem -> giữ file đầu tiên gặp.
#     for csv_p in sorted(d.rglob("*.csv"), key=lambda x: str(x).lower()):
#         try:
#             if not csv_p.is_file():
#                 continue

#             stem = csv_p.stem

#             # 1) validate stem pattern + folder match
#             ps = _split_plan_name(stem)
#             if not ps:
#                 _safe_unlink(csv_p)
#                 continue
#             proj, stn = ps
#             if not _path_matches_folder(csv_p, proj, stn):
#                 _safe_unlink(csv_p)
#                 continue

#             # 2) validate meta line (name + owner tag)
#             try_strip_utf8_bom(csv_p)
#             with csv_p.open("r", encoding="utf-8-sig", newline="") as f:
#                 r = csv.reader(f)
#                 meta = next(r, None)
#                 if not meta or len(meta) < 2:
#                     _safe_unlink(csv_p)
#                     continue
#                 name0 = (meta[0] or "").strip()
#                 tag0 = (meta[1] or "").strip().lower()

#             if not name0 or name0 != stem or tag0 != owner:
#                 _safe_unlink(csv_p)
#                 continue

#             # 3) cleanup images referenced by this csv (best-effort)
#             try:
#                 _cleanup_images_referenced(csv_p)
#             except Exception:
#                 pass

#             # 4) add to map (avoid overwrite on duplicates)
#             if stem not in mp:
#                 mp[stem] = csv_p

#         except Exception:
#             # lỗi đọc/parse -> bỏ qua, không xoá để tránh mất file do lỗi IO tạm
#             continue

#     names = sorted(mp.keys(), key=lambda s: s.lower())
#     return names, mp

# def _parse_test_plan_csv(
#     csv_path: Path,
#     *,
#     owner_tag: str = _TESTPLAN_OWNER_TAG,
#     slots: int = 12,
# ) -> Optional[TestPlan]:
#     """
#     Parse 1 file test plan .csv -> TestPlan
#     """
#     if not csv_path.exists():
#         return None

#     stem = csv_path.stem
#     try_strip_utf8_bom(csv_path)
#     with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
#         r = csv.reader(f)
#         meta = next(r, None)
#         if not meta or len(meta) < 2:
#             return None
#         name0 = (meta[0] or "").strip()
#         tag0 = (meta[1] or "").strip().lower()

#         if name0 != stem:
#             return None
#         if tag0 != (owner_tag or "").strip().lower():
#             return None

#         # optional meta commands (nếu có)
#         open_cmd = (meta[2].strip() if len(meta) > 2 else "") or "open"
#         close_cmd = (meta[3].strip() if len(meta) > 3 else "") or "close"
#         status_cmd = (meta[4].strip() if len(meta) > 4 else "") or "status"
#         raster_state_cmd = (meta[5].strip() if len(meta) > 5 else "") or "RASTER_STATE"

#         # skip header line
#         _hdr = next(r, None)

#         slot_test: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
#         slot_command: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
#         slot_guide: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
#         slot_image: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
#         slot_expect: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
#         slot_reject: Dict[int, str] = {i: "" for i in range(1, slots + 1)}

#         # station-level patterns: lấy theo dòng đầu tiên có giá trị
#         expect = reject = ""
#         sensor_expect = sensor_reject = ""
#         stop_expect = stop_reject = ""
#         raster_expect = raster_reject = ""

#         def _first_non_empty(cur: str, new: str) -> str:
#             return cur or (new or "").strip()

#         for row in r:
#             if not row:
#                 continue
#             # pad to 12 cols
#             if len(row) < 12:
#                 row = row + [""] * (12 - len(row))

#             # parse slot index
#             try:
#                 idx = int((row[0] or "").strip())
#             except Exception:
#                 continue
#             if not (1 <= idx <= slots):
#                 continue

#             st = (row[1] or "").strip()
#             sc = (row[2] or "").strip()

#             row_expect = (row[3] or "").strip()
#             row_reject = (row[4] or "").strip()

#             # NOTE: file đang gộp sensor/raster chung 1 cột
#             row_sensor_exp = (row[5] or "").strip()
#             row_sensor_rej = (row[6] or "").strip()

#             row_stop_exp = (row[7] or "").strip()
#             row_stop_rej = (row[8] or "").strip()

#             gd = _decode_guide_text(row[9] or "")
#             im = (row[10] or "").strip()

#             slot_test[idx] = st
#             slot_command[idx] = sc
#             slot_guide[idx] = gd
#             slot_image[idx] = im

#             # capture station-level patterns (first non-empty)
#             expect = _first_non_empty(expect, row_expect)
#             reject = _first_non_empty(reject, row_reject)

#             sensor_expect = _first_non_empty(sensor_expect, row_sensor_exp)
#             sensor_reject = _first_non_empty(sensor_reject, row_sensor_rej)

#             stop_expect = _first_non_empty(stop_expect, row_stop_exp)
#             stop_reject = _first_non_empty(stop_reject, row_stop_rej)

#             raster_expect = _first_non_empty(raster_expect, row_sensor_exp)   # share
#             raster_reject = _first_non_empty(raster_reject, row_sensor_rej)   # share

#             # derive per-slot expect/reject (để fill SLOT_EXPECT / SLOT_REJECT nếu muốn)
#             up_lbl = st.upper()
#             up_cmd = sc.upper()

#             if "STOP" in up_lbl or "FORCE" in up_lbl:
#                 e = row_stop_exp or row_expect
#                 rj = row_stop_rej or row_reject
#             elif "SENSOR" in up_lbl:
#                 e = row_sensor_exp or row_expect
#                 rj = row_sensor_rej or row_reject
#             elif "RASTER" in up_cmd or "RASTER" in up_lbl:
#                 e = row_sensor_exp or row_expect
#                 rj = row_sensor_rej or row_reject
#             else:
#                 e = row_expect
#                 rj = row_reject

#             slot_expect[idx] = (e or "").strip()
#             slot_reject[idx] = (rj or "").strip()

#         cmds = {k: "" for k in _STATION_CMD_KEYS}
#         cmds["open_cmd"] = open_cmd
#         cmds["close_cmd"] = close_cmd
#         cmds["status_cmd"] = status_cmd
#         cmds["raster_state_cmd"] = raster_state_cmd

#         cmds["expect"] = expect
#         cmds["reject"] = reject
#         cmds["sensor_expect"] = sensor_expect
#         cmds["sensor_reject"] = sensor_reject
#         cmds["stop_expect"] = stop_expect
#         cmds["stop_reject"] = stop_reject
#         cmds["raster_expect"] = raster_expect
#         cmds["raster_reject"] = raster_reject

#         st_obj = Station(
#             name=name0,
#             cmds=cmds,
#             slot_test=slot_test,
#             slot_command=slot_command,
#             slot_guide=slot_guide,
#             slot_image=slot_image,
#         )

#         return TestPlan(
#             name=name0,
#             station=st_obj,
#             slot_expect=slot_expect,
#             slot_reject=slot_reject,
#             source_csv=csv_path,
#         )

# def get_test_plan(
#     ini_path: Union[str, Path],
#     station_name: str,
#     *,
#     test_plan_dirname: str = "test_plan",
#     owner_tag: str = _TESTPLAN_OWNER_TAG,
#     slots: int = 12,
# ) -> Optional[TestPlan]:
#     """
#     Load 1 test plan theo tên trạm (tên == tên file stem).
#     """
#     _names, mp = list_test_plans(ini_path, test_plan_dirname=test_plan_dirname, owner_tag=owner_tag)
#     p = mp.get(station_name)
#     if not p:
#         return None
#     return _parse_test_plan_csv(p, owner_tag=owner_tag, slots=slots)

# def update_ini_selected_station(
#     ini_path: Union[str, Path],
#     station_name: str,
#     *,
#     section_name: str = "STATION",
#     key_name: str = "selected_station",
#     encoding: str = "utf-8-sig",
# ) -> None:
#     """
#     Text-based upsert:
#       [STATION]
#       selected_station = <station_name>
#     """
#     path = Path(ini_path)
#     raw = path.read_bytes() if path.exists() else b""
#     newline = _detect_newline(raw) if raw else "\n"
#     lines = raw.decode(_ini_encoding(encoding), errors="replace").splitlines() if raw else []

#     start, end = _find_section_bounds(lines, section_name)
#     if start is None:
#         if lines and lines[-1].strip() != "":
#             lines.append("")
#         lines.append(f"[{section_name}]")
#         start = len(lines)
#         end = len(lines)
#     if end is None:
#         end = len(lines)

#     kv_re = re.compile(_KEYVAL_RE_TEMPLATE.format(key=re.escape(key_name)), re.IGNORECASE)

#     found = False
#     new_sec: list[str] = []
#     for ln in lines[start:end]:
#         m = kv_re.match(ln)
#         if m:
#             indent, key, eq, _old, trail = m.groups()
#             new_sec.append(f"{indent}{key}{eq}{station_name}{trail}")
#             found = True
#         else:
#             new_sec.append(ln)

#     if not found:
#         if new_sec and new_sec[-1].strip() != "":
#             new_sec.append("")
#         new_sec.append(f"{key_name}={station_name}")

#     out_text = newline.join(lines[:start] + new_sec + lines[end:]) + newline
#     _atomic_write_text(path, out_text, encoding=encoding)

# def _bulk_upsert_slot_section(
#     lines: list[str],
#     *,
#     section_name: str,
#     values: Dict[int, str],
#     slots: int = 12,
#     value_encoder=lambda s: s,
# ) -> list[str]:
#     start, end = _find_section_bounds(lines, section_name)
#     if start is None:
#         if lines and lines[-1].strip() != "":
#             lines.append("")
#         lines.append(f"[{section_name}]")
#         start = len(lines)
#         end = len(lines)
#     if end is None:
#         end = len(lines)

#     seen: Set[int] = set()
#     new_sec: list[str] = []
#     for ln in lines[start:end]:
#         m = _SLOT_RE.match(ln)
#         if m:
#             indent, key, num_s, eq, _old, trail = m.groups()
#             try:
#                 idx = int(num_s)
#             except ValueError:
#                 new_sec.append(ln); continue
#             if 1 <= idx <= slots:
#                 v = value_encoder(values.get(idx, ""))
#                 new_sec.append(f"{indent}{key}{idx}{eq}{v}{trail}")
#                 seen.add(idx)
#                 continue
#         new_sec.append(ln)

#     missing = [i for i in range(1, slots + 1) if i not in seen]
#     if missing:
#         if new_sec and new_sec[-1].strip() != "":
#             new_sec.append("")
#         for i in missing:
#             v = value_encoder(values.get(i, ""))
#             new_sec.append(f"slot{i}={v}")

#     return lines[:start] + new_sec + lines[end:]

# def apply_test_plan_to_config_ini(
#     ini_path: Union[str, Path],
#     plan: TestPlan,
#     *,
#     slots: int = 12,
#     encoding: str = "utf-8-sig",
#     write_expect_reject: bool = True,
# ) -> None:
#     """
#     Ghi nội dung test plan vào config.ini:
#       - [STATION] selected_station
#       - [SLOT_TEST], [SLOT_COMMAND], [SLOT_GUIDE], [SLOT_IMAGE]
#       - optionally: [SLOT_EXPECT], [SLOT_REJECT]
#       - reset SLOT_STATUS -> idle/item theo SLOT_TEST (dùng helper có sẵn)
#     """
#     path = Path(ini_path)

#     # 1) update selected station (atomic)
#     update_ini_selected_station(path, plan.name, encoding=encoding)

#     # 2) bulk update slot sections (1 atomic)
#     raw = path.read_bytes() if path.exists() else b""
#     newline = _detect_newline(raw) if raw else "\n"
#     lines = raw.decode(_ini_encoding(encoding), errors="replace").splitlines() if raw else []

#     lines = _bulk_upsert_slot_section(lines, section_name="SLOT_TEST", values=plan.station.slot_test, slots=slots)
#     lines = _bulk_upsert_slot_section(lines, section_name="SLOT_COMMAND", values=plan.station.slot_command, slots=slots)
#     lines = _bulk_upsert_slot_section(lines, section_name="SLOT_GUIDE", values=plan.station.slot_guide, slots=slots, value_encoder=_encode_guide_for_ini)
#     lines = _bulk_upsert_slot_section(lines, section_name="SLOT_IMAGE", values=plan.station.slot_image, slots=slots)

#     if write_expect_reject:
#         lines = _bulk_upsert_slot_section(lines, section_name="SLOT_EXPECT", values=plan.slot_expect, slots=slots)
#         lines = _bulk_upsert_slot_section(lines, section_name="SLOT_REJECT", values=plan.slot_reject, slots=slots)

#     out_text = newline.join(lines) + newline
#     _atomic_write_text(path, out_text, encoding=encoding)

#     # 3) update SLOT_STATUS to idle/item based on SLOT_TEST
#     try:
#         reset_slot_status_section_to_idle(path, slots=slots, encoding=encoding)
#     except Exception:
#         pass


# def load_station_cfg(
#     path: Union[str, Path],
#     *,
#     encoding: str = "utf-8-sig",
#     station_root_section: str = "STATION",
#     station_prefix: str = "STATION_",
#     cmd_keys: Tuple[str, ...] = _STATION_CMD_KEYS,
#     slots: int = 12,
#     # NEW: test plan folder
#     test_plan_dirname: str = "test_plan",
#     owner_tag: str = _TESTPLAN_OWNER_TAG,
# ) -> Tuple[Optional[str], List[Station], Dict[str, Station]]:
#     """
#     Return: (selected_station_name, stations_list, station_map)

#     Ưu tiên:
#       1) test_plan/*.csv (theo rule meta: <stem>,bechjkjen)
#       2) fallback legacy ini: [STATION].stations + sections [STATION_<NAME>]

#     Notes:
#       - Khi dùng CSV: list station = danh sách file hợp lệ trong test_plan/
#       - selected_station vẫn lấy từ config.ini ([STATION].selected_station)
#     """
#     cfg = configparser.ConfigParser(strict=False)
#     try_strip_utf8_bom(path)
#     cfg.read(str(path), encoding=_ini_encoding(encoding))

#     selected = cfg.get(station_root_section, "selected_station", fallback="").strip() or None

#     # ===== 1) CSV test plan (preferred) =====
#     names, mp = list_test_plans(path, test_plan_dirname=test_plan_dirname, owner_tag=owner_tag)
#     if names:
#         stations_list: List[Station] = []
#         station_map: Dict[str, Station] = {}

#         for nm in names:
#             p = mp.get(nm)
#             if not p:
#                 continue
#             plan = _parse_test_plan_csv(p, owner_tag=owner_tag, slots=slots)
#             if not plan:
#                 continue
#             stations_list.append(plan.station)
#             station_map[nm] = plan.station

#         # normalize selected
#         if selected not in station_map:
#             selected = stations_list[0].name if stations_list else None

#         return selected, stations_list, station_map

#     # ===== 2) Legacy INI stations =====
#     station_names: List[str] = []
#     if cfg.has_section(station_root_section):
#         station_names = _split_csv(cfg.get(station_root_section, "stations", fallback=""))

#     if not station_names:
#         for sec in cfg.sections():
#             if sec.upper().startswith(station_prefix.upper()):
#                 name = sec[len(station_prefix):].strip()
#                 if name:
#                     station_names.append(name)
#         station_names.sort(key=lambda x: x.upper())

#     stations_list = []
#     station_map = {}

#     for name in station_names:
#         sec = f"{station_prefix}{name}"

#         cmds = {k: "" for k in cmd_keys}
#         slot_test: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
#         slot_command: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
#         slot_guide: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
#         slot_image: Dict[int, str] = {i: "" for i in range(1, slots + 1)}

#         if cfg.has_section(sec):
#             for k in cmd_keys:
#                 cmds[k] = cfg.get(sec, k, fallback="").strip()

#             for i in range(1, slots + 1):
#                 raw = cfg.get(sec, f"slot{i}", fallback="").strip()
#                 st, sc, gd, im = _parse_station_slot_line(raw)
#                 slot_test[i] = st
#                 slot_command[i] = sc
#                 slot_guide[i] = gd
#                 slot_image[i] = im

#         st_obj = Station(
#             name=name,
#             cmds=cmds,
#             slot_test=slot_test,
#             slot_command=slot_command,
#             slot_guide=slot_guide,
#             slot_image=slot_image,
#         )
#         stations_list.append(st_obj)
#         station_map[name] = st_obj

#     if selected not in station_map:
#         selected = stations_list[0].name if stations_list else None

#     return selected, stations_list, station_map


# def _split_csv(s: str) -> List[str]:
#     # "AFT, ADL1,ADL2" -> ["AFT","ADL1","ADL2"]
#     out: List[str] = []
#     for p in (s or "").split(","):
#         p = p.strip()
#         if p:
#             out.append(p)
#     return out


# def get_selected_station(
#     path: Union[str, Path],
#     *,
#     encoding: str = "utf-8-sig",
# ) -> Optional[Station]:
#     selected, _stations_list, station_map = load_station_cfg(path, encoding=encoding)
#     if not selected:
#         return None
#     return station_map.get(selected)

# # Xóa BOM
# def _ini_encoding(enc: str) -> str:
#     """Normalize encoding for reading INI:
#     - utf-8 / utf8 -> utf-8-sig (auto strip BOM if present)
#     - others: keep as-is
#     """
#     e = (enc or "utf-8-sig").strip().lower().replace("_", "-")
#     if e in ("utf8", "utf-8-sig"):
#         return "utf-8-sig"
#     return enc

from __future__ import annotations

import configparser
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Union, Literal, Optional, Set, List
import os
import re
import csv
from io import StringIO
import tempfile
from pathlib import Path

_UTF8_BOM = b"\xef\xbb\xbf"

def strip_utf8_bom_inplace(path: str | Path) -> bool:
    """
    Xóa UTF-8 BOM ở đầu file (nếu có) và ghi lại file.
    Return True nếu đã xóa BOM, False nếu không có BOM hoặc file không tồn tại.
    """
    p = Path(path)
    if not p.is_file():
        return False

    data = p.read_bytes()
    if not data.startswith(_UTF8_BOM):
        return False

    new_data = data[len(_UTF8_BOM):]

    # atomic write: ghi ra temp trong cùng thư mục rồi replace
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(p.parent), prefix=p.name + ".", suffix=".tmp") as f:
        tmp_path = Path(f.name)
        f.write(new_data)
        f.flush()
        os.fsync(f.fileno())

    os.replace(str(tmp_path), str(p))
    return True


def try_strip_utf8_bom(path: str | Path) -> None:
    """Không throw: có lỗi thì bỏ qua."""
    try:
        strip_utf8_bom_inplace(path)
    except Exception:
        pass

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
    slot_guide: Dict[int, str]
    slot_image: Dict[int, str]

def load_fixture_cfg(path: str) -> FixtureConfig:
    # strict=False để không crash nếu config có key trùng (slot8 bị lặp)
    cfg = configparser.ConfigParser(strict=False)
    # cfg.read(path, encoding="utf-8-sig")
    try_strip_utf8_bom(path)
    cfg.read(path, encoding=_ini_encoding("utf-8-sig"))


    port = cfg.get("FIXTURE", "port", fallback="").strip()
    baudrate = cfg.getint("FIXTURE", "baudrate", fallback=9600)
    ending_mode = cfg.get("FIXTURE", "ending_line", fallback="CRLF").strip().upper()
    ending_line = ENDING_MAP.get(ending_mode, "\r\n")
    timeout = cfg.getfloat("FIXTURE", "timeout", fallback=2.0)

    slot_text: Dict[int, str] = {}
    slot_command: Dict[int, str] = {}
    slot_status: Dict[int, str] = {}
    slot_guide: Dict[int, str] = {}
    slot_image: Dict[int, str] = {}
    for i in range(1, 13):
        slot_text[i] = cfg.get("SLOT_TEST", f"slot{i}", fallback="").strip()
        slot_command[i] = cfg.get("SLOT_COMMAND", f"slot{i}", fallback="").strip()
        slot_status[i] = cfg.get("SLOT_STATUS", f"slot{i}", fallback="idle").strip()

        g = cfg.get("SLOT_GUIDE", f"slot{i}", fallback="").strip()
        slot_guide[i] = g.replace(r"\n", "\n")
        slot_image[i] = cfg.get("SLOT_IMAGE", f"slot{i}", fallback="").strip()
    # for i in range(1, 13):
    #     slot_text[i] = cfg.get("SLOT_TEST", f"slot{i}", fallback="").strip()
    #     slot_command[i] = cfg.get("SLOT_COMMAND", f"slot{i}", fallback="").strip()
    #     slot_status[i] = cfg.get("SLOT_STATUS", f"slot{i}", fallback="idle").strip()

    return FixtureConfig(
        port=port,
        baudrate=baudrate,
        ending_line=ending_line,
        timeout=timeout,
        slot_text=slot_text,
        slot_command=slot_command,
        slot_status=slot_status,
        slot_guide=slot_guide,
        slot_image=slot_image,
    )

def update_ini_fixture_section(
    ini_path: Union[str, Path],
    *,
    port: Optional[str] = None,
    baudrate: Optional[int] = None,
    ending_line: Optional[str] = None,   # "CRLF"|"LF"|"CR"|"NONE"
    timeout: Optional[float] = None,
    section_name: str = "FIXTURE",
    encoding: str = "utf-8-sig",
) -> None:
    path = Path(ini_path)
    raw = path.read_bytes() if path.exists() else b""
    newline = "\r\n" if b"\r\n" in raw else "\n"
    lines = (raw.decode(_ini_encoding(encoding), errors="replace").splitlines() if raw else [])

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

def update_ini_slot_guide(
    ini_path: Union[str, Path],
    *,
    slot_idx: int,
    guide_text: str,
    section_name: str = "SLOT_GUIDE",
    slots: int = 12,
    encoding: str = "utf-8-sig",
) -> None:
    if not (1 <= int(slot_idx) <= int(slots)):
        raise ValueError(f"slot_idx out of range: {slot_idx}")

    path = Path(ini_path)
    if path.exists():
        raw = path.read_bytes()
        newline = _detect_newline(raw)
        lines = raw.decode(_ini_encoding(encoding), errors="replace").splitlines()
    else:
        newline = "\n"
        lines = []

    # encode \n to literal to keep single-line ini
    v = (guide_text or "").replace("\n", r"\n")

    # reuse your internal helper pattern from update_ini_manual_slot_info
    def _upsert(lines_in: list[str]) -> list[str]:
        start, end = _find_section_bounds(lines_in, section_name)
        if start is None:
            if lines_in and lines_in[-1].strip() != "":
                lines_in.append("")
            lines_in.append(f"[{section_name}]")
            start = len(lines_in)
            end = len(lines_in)
        if end is None:
            end = len(lines_in)

        found = False
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
                if num == int(slot_idx):
                    new_sec.append(f"{indent}{key}{num}{eq}{v}{trail}")
                    found = True
                    continue
            new_sec.append(ln)

        if not found:
            if new_sec and new_sec[-1].strip() != "":
                new_sec.append("")
            new_sec.append(f"slot{int(slot_idx)}={v}")

        return lines_in[:start] + new_sec + lines_in[end:]

    lines = _upsert(lines)
    out_text = newline.join(lines) + newline
    _atomic_write_text(path, out_text, encoding=encoding)

def update_ini_slot_image(
    ini_path: Union[str, Path],
    *,
    slot_idx: int,
    image_key: str,
    section_name: str = "SLOT_IMAGE",
    slots: int = 12,
    encoding: str = "utf-8-sig",
) -> None:
    path = Path(ini_path)
    if path.exists():
        raw = path.read_bytes()
        newline = _detect_newline(raw)
        lines = raw.decode(_ini_encoding(encoding), errors="replace").splitlines()
    else:
        newline = "\n"
        lines = []

    v = (image_key or "").strip()

    start, end = _find_section_bounds(lines, section_name)
    if start is None:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"[{section_name}]")
        start = len(lines)
        end = len(lines)
    if end is None:
        end = len(lines)

    found = False
    new_sec: list[str] = []
    for ln in lines[start:end]:
        m = _SLOT_RE.match(ln)
        if m:
            indent, key, num_s, eq, _old, trail = m.groups()
            try:
                num = int(num_s)
            except ValueError:
                new_sec.append(ln); continue
            if num == int(slot_idx):
                new_sec.append(f"{indent}{key}{num}{eq}{v}{trail}")
                found = True
                continue
        new_sec.append(ln)

    if not found:
        if new_sec and new_sec[-1].strip() != "":
            new_sec.append("")
        new_sec.append(f"slot{int(slot_idx)}={v}")

    out_text = newline.join(lines[:start] + new_sec + lines[end:]) + newline
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
    encoding: str = "utf-8-sig",
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

    text = raw.decode(_ini_encoding(encoding), errors="replace")
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

def _atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8-sig") -> None:
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
    encoding: str = "utf-8-sig",
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
        text = raw.decode(_ini_encoding(encoding), errors="replace")
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
    encoding: str = "utf-8-sig",
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
    encoding: str = "utf-8-sig",
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
        lines = raw.decode(_ini_encoding(encoding), errors="replace").splitlines()
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
    slot_guide: Dict[int, str]
    slot_image: Dict[int, str]  

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

# def _parse_station_slot_line(v: str) -> tuple[str, str, str]:
#     v = (v or "").strip()
#     if not v:
#         return "", "", ""
#     row = next(csv.reader(StringIO(v), skipinitialspace=True))
#     # row: [test, cmd, guide]  (guide có thể thiếu)
#     test = row[0].strip() if len(row) > 0 else ""
#     cmd  = row[1].strip() if len(row) > 1 else ""
#     guide = row[2] if len(row) > 2 else ""
#     guide = guide.strip()
#     # bỏ quote ngoài nếu còn
#     if len(guide) >= 2 and guide[0] == '"' and guide[-1] == '"':
#         guide = guide[1:-1]
#     guide = guide.replace(r"\n", "\n")
#     return test, cmd, guide

def _parse_station_slot_line(v: str) -> tuple[str, str, str, str]:
    v = (v or "").strip()
    if not v:
        return "", "", "", ""
    row = next(csv.reader(StringIO(v), skipinitialspace=True))

    test  = row[0].strip() if len(row) > 0 else ""
    cmd   = row[1].strip() if len(row) > 1 else ""
    guide = row[2].strip() if len(row) > 2 else ""
    img   = row[3].strip() if len(row) > 3 else ""

    # bỏ quote ngoài nếu còn (csv thường đã xử lý, nhưng giữ để chắc)
    if len(guide) >= 2 and guide[0] == '"' and guide[-1] == '"':
        guide = guide[1:-1]
    guide = guide.replace(r"\n", "\n")
    return test, cmd, guide, img


# ===================== TEST PLAN CSV (new) =====================
# Quy ước:
# - test_plan/ nằm cùng level với config.ini và file binary
# - mỗi file: <StationName>.csv
# - dòng đầu tiên (meta): StationName,bechjkjen,...
#   + StationName phải TRÙNG tên file (stem)
#   + cột 2 phải đúng "bechjkjen" (lowercase) -> nếu không thì bỏ qua file
#
# CSV format tối thiểu (sau meta + header):
# slot,slot_text,slot_cmd,expect,reject,sensor_expect/raster_expect,sensor_reject/raster_reject,stop_expect,stop_reject,guide,image_guide,note

_TESTPLAN_OWNER_TAG = "bechjkjen"

@dataclass(frozen=True)
class TestPlan:
    name: str
    station: Station
    slot_expect: Dict[int, str]
    slot_reject: Dict[int, str]
    source_csv: Path

_KEYVAL_RE_TEMPLATE = r"^(\s*)({key})(\s*=\s*)(.*?)(\s*)$"

def _strip_outer_quotes(s: str) -> str:
    s = (s or "").strip()
    # bỏ nhiều lớp quote nếu có (vd: """text""" )
    while len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        s = s[1:-1].strip()
    return s

def _decode_guide_text(s: str) -> str:
    s = _strip_outer_quotes(s)
    return (s or "").replace(r"\n", "\n").strip()

def _encode_guide_for_ini(s: str) -> str:
    # ini giữ 1 dòng, dùng literal \n
    return (s or "").replace("\n", r"\n")

def get_test_plan_dir(
    ini_path: Union[str, Path],
    *,
    test_plan_dirname: str = "test_plan",
) -> Path:
    """
    Trả về path thư mục test_plan/ cùng level với config.ini.
    """
    base_dir = Path(ini_path).resolve().parent
    return base_dir / test_plan_dirname



def _plan_parts_from_path(csv_path: Path) -> Tuple[str, str, str]:
    """
    Return (process, project, station_folder) from strict layout:
      test_plan/<Process>/<Project>/<Station>/<Project>_<Station>.csv
    If missing -> ("", "", "")
    """
    try:
        st_dir = csv_path.parent
        pr_dir = st_dir.parent
        proc_dir = pr_dir.parent
        if not st_dir or not pr_dir or not proc_dir:
            return ("", "", "")
        return (proc_dir.name or "", pr_dir.name or "", st_dir.name or "")
    except Exception:
        return ("", "", "")


def _read_selected_process_project_from_ini(
    ini_path: Union[str, Path],
    *,
    section_name: str = "STATION",
    encoding: str = "utf-8-sig",
) -> Tuple[str, str]:
    """
    Read filters from config.ini:
      [STATION]
      selected_process=
      selected_project=
    """
    try:
        cfg = configparser.ConfigParser(strict=False)
        try_strip_utf8_bom(ini_path)
        cfg.read(str(ini_path), encoding=_ini_encoding(encoding))
        proc_v = cfg.get(section_name, "selected_process", fallback="").strip()
        proj_v = cfg.get(section_name, "selected_project", fallback="").strip()
        return proc_v, proj_v
    except Exception:
        return ("", "")

def list_test_plans(
    ini_path: Union[str, Path],
    *,
    test_plan_dirname: str = "test_plan",
    owner_tag: str = _TESTPLAN_OWNER_TAG,
    selected_project: Optional[str] = None,
    selected_process: Optional[str] = None,
) -> Tuple[List[str], Dict[str, Path]]:
    """
    Scan test_plan/**.csv và trả về:
      (list_station_names, map_name_to_csv_path)

    Layout mới (strict):
      test_plan/
        FATP/ | PCBA/ | ...
          <Project>/
            <Station>/
              <Project>_<Station>.csv
              (optional) *.png  # ảnh guide nằm cùng thư mục CSV

    Rule CSV hợp lệ (giữ như cũ + strict thêm path):
      - file stem (VD: Hapuka_MT) phải == meta[0]
      - meta[1].lower() phải == owner_tag (default: bechjkjen)
      - file stem phải match thư mục đang ở:
          <Project>_<Station>.csv  ==> nằm trong  .../<Project>/<Station>/

    Strict cleanup:
      - CSV sai rule -> xoá luôn (unlink)
      - Ảnh được reference trong cột image_guide:
          + nếu file tồn tại nhưng không phải .png -> xoá
          + nếu .png nhưng header không đúng PNG -> xoá
        (ảnh chỉ được cleanup best-effort, không gate việc add CSV)
    """
    d = get_test_plan_dir(ini_path, test_plan_dirname=test_plan_dirname)
    mp: Dict[str, Path] = {}
    if not d.exists() or not d.is_dir():
        return [], {}

    owner = (owner_tag or "").strip().lower()

    # --- filter process/project (from config.ini [STATION] unless caller overrides) ---
    if selected_process is None or selected_project is None:
        proc_ini, proj_ini = _read_selected_process_project_from_ini(ini_path)
        if selected_process is None:
            selected_process = proc_ini
        if selected_project is None:
            selected_project = proj_ini

    proc_filter = (selected_process or "").strip()
    proj_filter = (selected_project or "").strip()
    proc_low = proc_filter.lower()
    proj_low = proj_filter.lower()

    def _safe_unlink(fp: Path) -> None:
        try:
            if fp.exists() and fp.is_file():
                fp.unlink()
        except Exception:
            pass

    def _split_plan_name(stem: str) -> Optional[Tuple[str, str]]:
        """
        stem: <Project>_<Station>
        station có thể chứa underscore (vd: sample_test) => split 1 lần.
        """
        s = (stem or "").strip()
        if not s or "_" not in s:
            return None
        proj, stn = s.split("_", 1)
        proj = proj.strip()
        stn = stn.strip()
        if not proj or not stn:
            return None
        return proj, stn

    def _path_matches_folder(csv_path: Path, proj: str, stn: str) -> bool:
        """
        .../<Project>/<Station>/<Project>_<Station>.csv
        """
        try:
            st_dir = csv_path.parent
            pr_dir = st_dir.parent
            if not st_dir or not pr_dir:
                return False
            # tolerant case (Windows)
            return (pr_dir.name.lower() == proj.lower()) and (st_dir.name.lower() == stn.lower())
        except Exception:
            return False

    def _is_valid_png_header(img_path: Path) -> bool:
        try:
            with img_path.open("rb") as f:
                sig = f.read(8)
            return sig == b"\x89PNG\r\n\x1a\n"
        except Exception:
            return False

    def _cleanup_images_referenced(csv_path: Path) -> None:
        """
        Read CSV (skip meta + header) and cleanup bad image files referenced in column image_guide.
        Column index: 10
        """
        folder = csv_path.parent
        try_strip_utf8_bom(csv_path)

        refs: Set[str] = set()
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
                r = csv.reader(f)
                _meta = next(r, None)
                _hdr = next(r, None)
                for row in r:
                    if not row:
                        continue
                    if len(row) < 11:
                        continue
                    im = (row[10] or "").strip()
                    if im:
                        refs.add(im)
        except Exception:
            return

        for im in sorted(refs):
            # chỉ cho phép filename nằm cùng folder (không cho path)
            if ("/" in im) or ("\\" in im):
                continue
            im_p = folder / im
            suf = im_p.suffix.lower()

            if not im_p.exists() or not im_p.is_file():
                continue

            if suf != ".png":
                _safe_unlink(im_p)
                continue

            if not _is_valid_png_header(im_p):
                _safe_unlink(im_p)

    # NOTE: rglob để quét mọi folder con (FATP/PCBA/...)
    # sort theo path string để deterministic; nếu trùng stem -> giữ file đầu tiên gặp.
    for csv_p in sorted(d.rglob("*.csv"), key=lambda x: str(x).lower()):
        try:
            if not csv_p.is_file():
                continue

            stem = csv_p.stem

            # 1) validate stem pattern + folder match
            ps = _split_plan_name(stem)
            if not ps:
                _safe_unlink(csv_p)
                continue
            proj, stn = ps
            if not _path_matches_folder(csv_p, proj, stn):
                _safe_unlink(csv_p)
                continue

            # 2) validate meta line (name + owner tag)
            try_strip_utf8_bom(csv_p)
            with csv_p.open("r", encoding="utf-8-sig", newline="") as f:
                r = csv.reader(f)
                meta = next(r, None)
                if not meta or len(meta) < 2:
                    _safe_unlink(csv_p)
                    continue
                name0 = (meta[0] or "").strip()
                tag0 = (meta[1] or "").strip().lower()

            if not name0 or name0 != stem or tag0 != owner:
                _safe_unlink(csv_p)
                continue

            # 3) cleanup images referenced by this csv (best-effort)
            try:
                _cleanup_images_referenced(csv_p)
            except Exception:
                pass

            # --- apply filters (không xoá file, chỉ lọc danh sách) ---
            # proc: thư mục level-1 dưới test_plan (FATP/PCBA/...)
            # proj: thư mục project (và cũng là prefix của stem: <Project>_<Station>)
            proc_name, proj_dir_name, _st_dir_name = _plan_parts_from_path(csv_p)

            if proc_low and (proc_low not in (proc_name or '').lower()):
                continue

            # project filter: match "tương tự" (substring, case-insensitive)
            if proj_low:
                if (proj_low not in (proj_dir_name or '').lower()) and (proj_low not in (proj or '').lower()):
                    continue

            # 4) add to map (avoid overwrite on duplicates)
            if stem not in mp:
                mp[stem] = csv_p

        except Exception:
            # lỗi đọc/parse -> bỏ qua, không xoá để tránh mất file do lỗi IO tạm
            continue

    names = sorted(mp.keys(), key=lambda s: s.lower())
    return names, mp

def list_test_plan_processes(
    ini_path: Union[str, Path],
    *,
    test_plan_dirname: str = "test_plan",
    owner_tag: str = _TESTPLAN_OWNER_TAG,
) -> List[str]:
    """List all unique process names (FATP/PCBA/...) that have at least 1 valid csv."""
    _names, mp = list_test_plans(
        ini_path,
        test_plan_dirname=test_plan_dirname,
        owner_tag=owner_tag,
        selected_project="",
        selected_process="",
    )
    procs: Set[str] = set()
    for p in mp.values():
        proc, _proj, _st = _plan_parts_from_path(p)
        if proc:
            procs.add(proc)
    return sorted(procs, key=lambda s: s.lower())


def list_test_plan_projects(
    ini_path: Union[str, Path],
    *,
    process_filter: str = "",
    test_plan_dirname: str = "test_plan",
    owner_tag: str = _TESTPLAN_OWNER_TAG,
) -> List[str]:
    """List all unique project names. If process_filter provided -> only under that process."""
    _names, mp = list_test_plans(
        ini_path,
        test_plan_dirname=test_plan_dirname,
        owner_tag=owner_tag,
        selected_project="",
        selected_process="",
    )
    pf = (process_filter or "").strip().lower()
    projs: Set[str] = set()
    for p in mp.values():
        proc, proj, _st = _plan_parts_from_path(p)
        if pf and pf not in (proc or "").lower():
            continue
        if proj:
            projs.add(proj)
    return sorted(projs, key=lambda s: s.lower())


def _parse_test_plan_csv(
    csv_path: Path,
    *,
    owner_tag: str = _TESTPLAN_OWNER_TAG,
    slots: int = 12,
) -> Optional[TestPlan]:
    """
    Parse 1 file test plan .csv -> TestPlan
    """
    if not csv_path.exists():
        return None

    stem = csv_path.stem
    try_strip_utf8_bom(csv_path)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        meta = next(r, None)
        if not meta or len(meta) < 2:
            return None
        name0 = (meta[0] or "").strip()
        tag0 = (meta[1] or "").strip().lower()

        if name0 != stem:
            return None
        if tag0 != (owner_tag or "").strip().lower():
            return None

        # optional meta commands (nếu có)
        open_cmd = (meta[2].strip() if len(meta) > 2 else "") or "open"
        close_cmd = (meta[3].strip() if len(meta) > 3 else "") or "close"
        status_cmd = (meta[4].strip() if len(meta) > 4 else "") or "status"
        raster_state_cmd = (meta[5].strip() if len(meta) > 5 else "") or "RASTER_STATE"

        # skip header line
        _hdr = next(r, None)

        slot_test: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
        slot_command: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
        slot_guide: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
        slot_image: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
        slot_expect: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
        slot_reject: Dict[int, str] = {i: "" for i in range(1, slots + 1)}

        # station-level patterns: lấy theo dòng đầu tiên có giá trị
        expect = reject = ""
        sensor_expect = sensor_reject = ""
        stop_expect = stop_reject = ""
        raster_expect = raster_reject = ""

        def _first_non_empty(cur: str, new: str) -> str:
            return cur or (new or "").strip()

        for row in r:
            if not row:
                continue
            # pad to 12 cols
            if len(row) < 12:
                row = row + [""] * (12 - len(row))

            # parse slot index
            try:
                idx = int((row[0] or "").strip())
            except Exception:
                continue
            if not (1 <= idx <= slots):
                continue

            st = (row[1] or "").strip()
            sc = (row[2] or "").strip()

            row_expect = (row[3] or "").strip()
            row_reject = (row[4] or "").strip()

            # NOTE: file đang gộp sensor/raster chung 1 cột
            row_sensor_exp = (row[5] or "").strip()
            row_sensor_rej = (row[6] or "").strip()

            row_stop_exp = (row[7] or "").strip()
            row_stop_rej = (row[8] or "").strip()

            gd = _decode_guide_text(row[9] or "")
            im = (row[10] or "").strip()

            slot_test[idx] = st
            slot_command[idx] = sc
            slot_guide[idx] = gd
            slot_image[idx] = im

            # capture station-level patterns (first non-empty)
            expect = _first_non_empty(expect, row_expect)
            reject = _first_non_empty(reject, row_reject)

            sensor_expect = _first_non_empty(sensor_expect, row_sensor_exp)
            sensor_reject = _first_non_empty(sensor_reject, row_sensor_rej)

            stop_expect = _first_non_empty(stop_expect, row_stop_exp)
            stop_reject = _first_non_empty(stop_reject, row_stop_rej)

            raster_expect = _first_non_empty(raster_expect, row_sensor_exp)   # share
            raster_reject = _first_non_empty(raster_reject, row_sensor_rej)   # share

            # derive per-slot expect/reject (để fill SLOT_EXPECT / SLOT_REJECT nếu muốn)
            up_lbl = st.upper()
            up_cmd = sc.upper()

            if "STOP" in up_lbl or "FORCE" in up_lbl:
                e = row_stop_exp or row_expect
                rj = row_stop_rej or row_reject
            elif "SENSOR" in up_lbl:
                e = row_sensor_exp or row_expect
                rj = row_sensor_rej or row_reject
            elif "RASTER" in up_cmd or "RASTER" in up_lbl:
                e = row_sensor_exp or row_expect
                rj = row_sensor_rej or row_reject
            else:
                e = row_expect
                rj = row_reject

            slot_expect[idx] = (e or "").strip()
            slot_reject[idx] = (rj or "").strip()

        cmds = {k: "" for k in _STATION_CMD_KEYS}
        cmds["open_cmd"] = open_cmd
        cmds["close_cmd"] = close_cmd
        cmds["status_cmd"] = status_cmd
        cmds["raster_state_cmd"] = raster_state_cmd

        cmds["expect"] = expect
        cmds["reject"] = reject
        cmds["sensor_expect"] = sensor_expect
        cmds["sensor_reject"] = sensor_reject
        cmds["stop_expect"] = stop_expect
        cmds["stop_reject"] = stop_reject
        cmds["raster_expect"] = raster_expect
        cmds["raster_reject"] = raster_reject

        st_obj = Station(
            name=name0,
            cmds=cmds,
            slot_test=slot_test,
            slot_command=slot_command,
            slot_guide=slot_guide,
            slot_image=slot_image,
        )

        return TestPlan(
            name=name0,
            station=st_obj,
            slot_expect=slot_expect,
            slot_reject=slot_reject,
            source_csv=csv_path,
        )

def get_test_plan(
    ini_path: Union[str, Path],
    station_name: str,
    *,
    test_plan_dirname: str = "test_plan",
    owner_tag: str = _TESTPLAN_OWNER_TAG,
    slots: int = 12,
) -> Optional[TestPlan]:
    """
    Load 1 test plan theo tên trạm (tên == tên file stem).
    """
    _names, mp = list_test_plans(ini_path, test_plan_dirname=test_plan_dirname, owner_tag=owner_tag)
    p = mp.get(station_name)
    if not p:
        return None
    return _parse_test_plan_csv(p, owner_tag=owner_tag, slots=slots)

def update_ini_selected_station(
    ini_path: Union[str, Path],
    station_name: str,
    *,
    section_name: str = "STATION",
    key_name: str = "selected_station",
    encoding: str = "utf-8-sig",
) -> None:
    """
    Text-based upsert:
      [STATION]
      selected_station = <station_name>
    """
    path = Path(ini_path)
    raw = path.read_bytes() if path.exists() else b""
    newline = _detect_newline(raw) if raw else "\n"
    lines = raw.decode(_ini_encoding(encoding), errors="replace").splitlines() if raw else []

    start, end = _find_section_bounds(lines, section_name)
    if start is None:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"[{section_name}]")
        start = len(lines)
        end = len(lines)
    if end is None:
        end = len(lines)

    kv_re = re.compile(_KEYVAL_RE_TEMPLATE.format(key=re.escape(key_name)), re.IGNORECASE)

    found = False
    new_sec: list[str] = []
    for ln in lines[start:end]:
        m = kv_re.match(ln)
        if m:
            indent, key, eq, _old, trail = m.groups()
            new_sec.append(f"{indent}{key}{eq}{station_name}{trail}")
            found = True
        else:
            new_sec.append(ln)

    if not found:
        if new_sec and new_sec[-1].strip() != "":
            new_sec.append("")
        new_sec.append(f"{key_name}={station_name}")

    out_text = newline.join(lines[:start] + new_sec + lines[end:]) + newline
    _atomic_write_text(path, out_text, encoding=encoding)



def update_ini_selected_project(
    ini_path: Union[str, Path],
    project_name: str,
    *,
    section_name: str = "STATION",
    key_name: str = "selected_project",
    encoding: str = "utf-8-sig",
) -> None:
    """
    Upsert:
      [STATION]
      selected_project = <project_name>   (empty string => clear filter)
    """
    update_ini_selected_station(
        ini_path,
        (project_name or "").strip(),
        section_name=section_name,
        key_name=key_name,
        encoding=encoding,
    )


def update_ini_selected_process(
    ini_path: Union[str, Path],
    process_name: str,
    *,
    section_name: str = "STATION",
    key_name: str = "selected_process",
    encoding: str = "utf-8-sig",
) -> None:
    """
    Upsert:
      [STATION]
      selected_process = <process_name>   (empty string => clear filter)
    """
    update_ini_selected_station(
        ini_path,
        (process_name or "").strip(),
        section_name=section_name,
        key_name=key_name,
        encoding=encoding,
    )

def _bulk_upsert_slot_section(
    lines: list[str],
    *,
    section_name: str,
    values: Dict[int, str],
    slots: int = 12,
    value_encoder=lambda s: s,
) -> list[str]:
    start, end = _find_section_bounds(lines, section_name)
    if start is None:
        if lines and lines[-1].strip() != "":
            lines.append("")
        lines.append(f"[{section_name}]")
        start = len(lines)
        end = len(lines)
    if end is None:
        end = len(lines)

    seen: Set[int] = set()
    new_sec: list[str] = []
    for ln in lines[start:end]:
        m = _SLOT_RE.match(ln)
        if m:
            indent, key, num_s, eq, _old, trail = m.groups()
            try:
                idx = int(num_s)
            except ValueError:
                new_sec.append(ln); continue
            if 1 <= idx <= slots:
                v = value_encoder(values.get(idx, ""))
                new_sec.append(f"{indent}{key}{idx}{eq}{v}{trail}")
                seen.add(idx)
                continue
        new_sec.append(ln)

    missing = [i for i in range(1, slots + 1) if i not in seen]
    if missing:
        if new_sec and new_sec[-1].strip() != "":
            new_sec.append("")
        for i in missing:
            v = value_encoder(values.get(i, ""))
            new_sec.append(f"slot{i}={v}")

    return lines[:start] + new_sec + lines[end:]

def apply_test_plan_to_config_ini(
    ini_path: Union[str, Path],
    plan: TestPlan,
    *,
    slots: int = 12,
    encoding: str = "utf-8-sig",
    write_expect_reject: bool = True,
) -> None:
    """
    Ghi nội dung test plan vào config.ini:
      - [STATION] selected_station
      - [SLOT_TEST], [SLOT_COMMAND], [SLOT_GUIDE], [SLOT_IMAGE]
      - optionally: [SLOT_EXPECT], [SLOT_REJECT]
      - reset SLOT_STATUS -> idle/item theo SLOT_TEST (dùng helper có sẵn)
    """
    path = Path(ini_path)

    # 1) update selected station (atomic)
    update_ini_selected_station(path, plan.name, encoding=encoding)

    # 2) bulk update slot sections (1 atomic)
    raw = path.read_bytes() if path.exists() else b""
    newline = _detect_newline(raw) if raw else "\n"
    lines = raw.decode(_ini_encoding(encoding), errors="replace").splitlines() if raw else []

    lines = _bulk_upsert_slot_section(lines, section_name="SLOT_TEST", values=plan.station.slot_test, slots=slots)
    lines = _bulk_upsert_slot_section(lines, section_name="SLOT_COMMAND", values=plan.station.slot_command, slots=slots)
    lines = _bulk_upsert_slot_section(lines, section_name="SLOT_GUIDE", values=plan.station.slot_guide, slots=slots, value_encoder=_encode_guide_for_ini)
    lines = _bulk_upsert_slot_section(lines, section_name="SLOT_IMAGE", values=plan.station.slot_image, slots=slots)

    if write_expect_reject:
        lines = _bulk_upsert_slot_section(lines, section_name="SLOT_EXPECT", values=plan.slot_expect, slots=slots)
        lines = _bulk_upsert_slot_section(lines, section_name="SLOT_REJECT", values=plan.slot_reject, slots=slots)

    out_text = newline.join(lines) + newline
    _atomic_write_text(path, out_text, encoding=encoding)

    # 3) update SLOT_STATUS to idle/item based on SLOT_TEST
    try:
        reset_slot_status_section_to_idle(path, slots=slots, encoding=encoding)
    except Exception:
        pass


def load_station_cfg(
    path: Union[str, Path],
    *,
    encoding: str = "utf-8-sig",
    station_root_section: str = "STATION",
    station_prefix: str = "STATION_",
    cmd_keys: Tuple[str, ...] = _STATION_CMD_KEYS,
    slots: int = 12,
    # NEW: test plan folder
    test_plan_dirname: str = "test_plan",
    owner_tag: str = _TESTPLAN_OWNER_TAG,
) -> Tuple[Optional[str], List[Station], Dict[str, Station]]:
    """
    Return: (selected_station_name, stations_list, station_map)

    Ưu tiên:
      1) test_plan/*.csv (theo rule meta: <stem>,bechjkjen)
      2) fallback legacy ini: [STATION].stations + sections [STATION_<NAME>]

    Notes:
      - Khi dùng CSV: list station = danh sách file hợp lệ trong test_plan/
      - selected_station vẫn lấy từ config.ini ([STATION].selected_station)
    """
    cfg = configparser.ConfigParser(strict=False)
    try_strip_utf8_bom(path)
    cfg.read(str(path), encoding=_ini_encoding(encoding))

    selected = cfg.get(station_root_section, "selected_station", fallback="").strip() or None

    # ===== 1) CSV test plan (preferred) =====
    names, mp = list_test_plans(path, test_plan_dirname=test_plan_dirname, owner_tag=owner_tag)
    if names:
        stations_list: List[Station] = []
        station_map: Dict[str, Station] = {}

        for nm in names:
            p = mp.get(nm)
            if not p:
                continue
            plan = _parse_test_plan_csv(p, owner_tag=owner_tag, slots=slots)
            if not plan:
                continue
            stations_list.append(plan.station)
            station_map[nm] = plan.station

        # normalize selected
        if selected not in station_map:
            selected = stations_list[0].name if stations_list else None

        return selected, stations_list, station_map

    # ===== 2) Legacy INI stations =====
    station_names: List[str] = []
    if cfg.has_section(station_root_section):
        station_names = _split_csv(cfg.get(station_root_section, "stations", fallback=""))

    if not station_names:
        for sec in cfg.sections():
            if sec.upper().startswith(station_prefix.upper()):
                name = sec[len(station_prefix):].strip()
                if name:
                    station_names.append(name)
        station_names.sort(key=lambda x: x.upper())

    stations_list = []
    station_map = {}

    for name in station_names:
        sec = f"{station_prefix}{name}"

        cmds = {k: "" for k in cmd_keys}
        slot_test: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
        slot_command: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
        slot_guide: Dict[int, str] = {i: "" for i in range(1, slots + 1)}
        slot_image: Dict[int, str] = {i: "" for i in range(1, slots + 1)}

        if cfg.has_section(sec):
            for k in cmd_keys:
                cmds[k] = cfg.get(sec, k, fallback="").strip()

            for i in range(1, slots + 1):
                raw = cfg.get(sec, f"slot{i}", fallback="").strip()
                st, sc, gd, im = _parse_station_slot_line(raw)
                slot_test[i] = st
                slot_command[i] = sc
                slot_guide[i] = gd
                slot_image[i] = im

        st_obj = Station(
            name=name,
            cmds=cmds,
            slot_test=slot_test,
            slot_command=slot_command,
            slot_guide=slot_guide,
            slot_image=slot_image,
        )
        stations_list.append(st_obj)
        station_map[name] = st_obj

    if selected not in station_map:
        selected = stations_list[0].name if stations_list else None

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
    encoding: str = "utf-8-sig",
) -> Optional[Station]:
    selected, _stations_list, station_map = load_station_cfg(path, encoding=encoding)
    if not selected:
        return None
    return station_map.get(selected)

# Xóa BOM
def _ini_encoding(enc: str) -> str:
    """Normalize encoding for reading INI:
    - utf-8 / utf8 -> utf-8-sig (auto strip BOM if present)
    - others: keep as-is
    """
    e = (enc or "utf-8-sig").strip().lower().replace("_", "-")
    if e in ("utf8", "utf-8-sig"):
        return "utf-8-sig"
    return enc