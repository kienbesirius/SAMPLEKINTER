from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import serial  # pip install pyserial


# --- Heuristic keywords (không bắt buộc phải đủ hết, chỉ dùng để chấm điểm) ---
_STRONG_KEYWORDS = {
    "IN", "OUT", "OPEN", "CLOSE", "UP", "DOWN",
    "RESET", "CLEAR", "STATE", "PRODUCT", "VERSION",
    "HELP", "FIXTURE", "EMPTY", "EMPTY_IN",
    "STOP", "EMC", "POWER", "PWR", "RELAY", "UART", "USB", "RJ45",
    "INPUT", "CHECK", "SET", "SN", "READSN",
}

# Các cụm “đánh dấu help” hay gặp
_HELP_MARKERS = (
    "CONTROL CAMMAND",          # typo in logs but appears
    "CONTROL COMMAND",          
    "THIS IS THE HELP COMMAND",
    "SHOW ALL THE COMMANDS",
    "GET CAMMAND INFO",
    "GET COMMAND INFO",
)

# Regex để nhận dòng command-like
_RE_COLON_CMD = re.compile(r"^\s*[A-Za-z0-9_?]+\s*:\s*.+$")
_RE_SIMPLE_CMD = re.compile(r"^\s*[A-Za-z0-9_?]+(?:\s+[A-Za-z0-9_?]+)?\s*$")
_RE_TIMESTAMP_PREFIX = re.compile(r"^\s*\[\d{2}:\d{2}:\d{2}:\d{3}\]\s*")


@dataclass
class ProbeResult:
    port: str
    is_fixture: bool
    score: int
    command_lines: int
    matched_keywords: List[str]
    sample: str  # một đoạn response để debug


def _normalize_lines(raw: str) -> List[str]:
    raw = raw.replace("\r", "\n")
    lines = []
    for ln in raw.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        ln = _RE_TIMESTAMP_PREFIX.sub("", ln).strip()
        lines.append(ln)
    return lines


def _is_command_like(line: str) -> bool:
    # Bỏ qua các noise cực ngắn kiểu "OK", "NG", "STOP!" vẫn có thể xuất hiện
    # nhưng không dùng để tính command-lines trừ khi nó giống command.
    if _RE_COLON_CMD.match(line):
        return True

    # cho phép "power on", "uarten off" dạng 2 từ
    if _RE_SIMPLE_CMD.match(line):
        # loại bớt các token không giúp ích
        if line.upper() in {"OK", "NG"}:
            return False
        return True

    # Một số fixture có dòng kiểu "CMD=StartAll|PanelSN=1"
    if line.upper().startswith("CMD="):
        return True

    return False


def _extract_keywords(lines: List[str]) -> List[str]:
    text = " ".join(lines).upper()
    matched = []
    for kw in _STRONG_KEYWORDS:
        # match theo word boundary “gần đúng”
        if re.search(rf"(^|[^A-Z0-9_]){re.escape(kw)}([^A-Z0-9_]|$)", text):
            matched.append(kw)
    matched.sort()
    return matched


def _is_fixture_response(lines: List[str]) -> Tuple[bool, int, int, List[str]]:
    """
    Return: (is_fixture, score, command_lines_count, matched_keywords)
    """
    if not lines:
        return (False, 0, 0, [])

    text_up = " ".join(lines).upper()

    # Marker help rõ ràng
    has_help_marker = any(m in text_up for m in _HELP_MARKERS)

    command_lines = [ln for ln in lines if _is_command_like(ln)]
    cmd_count = len(command_lines)

    # Keyword score
    matched = _extract_keywords(lines)
    score = len(matched)

    # “Dạng colon cmd” hay gặp ở fixture (OPEN:..., SET_...:...)
    colon_defs = sum(1 for ln in lines if _RE_COLON_CMD.match(ln))

    # Heuristic quyết định:
    # - có help marker -> gần như chắc fixture nếu có thêm chút command-lines
    if has_help_marker and cmd_count >= 4:
        return (True, score, cmd_count, matched)

    # - nhiều colon defs là cực mạnh
    if colon_defs >= 5 and score >= 3:
        return (True, score, cmd_count, matched)

    # - dạng list command thuần: cần đủ “lượng” + đủ keywords
    #   (tránh nhầm thiết bị nào đó chỉ trả vài token)
    if (cmd_count >= 10 and score >= 3) or (cmd_count >= 6 and score >= 5):
        return (True, score, cmd_count, matched)

    return (False, score, cmd_count, matched)


def _read_for(ser: serial.Serial, duration_s: float) -> str:
    """
    Read whatever comes within duration_s (non-blocking-ish).
    """
    end = time.monotonic() + duration_s
    chunks: List[bytes] = []
    while time.monotonic() < end:
        try:
            n = ser.in_waiting
        except Exception:
            n = 0

        if n:
            chunks.append(ser.read(n))
        else:
            # ngủ nhỏ để không busy loop
            time.sleep(0.03)

    try:
        return b"".join(chunks).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _probe_one_port(
    port: str,
    probe_cmds: Sequence[str],
    baudrates: Sequence[int],
    per_cmd_wait_s: float,
    write_line_endings: Sequence[str],
) -> ProbeResult:
    best = ProbeResult(port=port, is_fixture=False, score=0, command_lines=0, matched_keywords=[], sample="")

    for br in baudrates:
        try:
            ser = serial.Serial(
                port=port,
                baudrate=br,
                timeout=0.2,
                write_timeout=0.6,
            )
        except Exception:
            continue

        try:
            # settle
            time.sleep(0.15)
            try:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
            except Exception:
                pass

            for cmd in probe_cmds:
                for le in write_line_endings:
                    # clear before each attempt
                    try:
                        ser.reset_input_buffer()
                    except Exception:
                        pass

                    payload = (cmd + le).encode("utf-8", errors="ignore")
                    try:
                        ser.write(payload)
                        ser.flush()
                    except Exception:
                        continue

                    raw = _read_for(ser, per_cmd_wait_s)
                    lines = _normalize_lines(raw)

                    is_fix, score, cmd_count, matched = _is_fixture_response(lines)

                    # lưu best để debug
                    if score > best.score or (score == best.score and cmd_count > best.command_lines):
                        best = ProbeResult(
                            port=port,
                            is_fixture=is_fix,
                            score=score,
                            command_lines=cmd_count,
                            matched_keywords=matched,
                            sample="\n".join(lines[:60]),  # đủ để nhìn pattern
                        )

                    if is_fix:
                        return best

        finally:
            try:
                ser.close()
            except Exception:
                pass

    return best


def get_fixture_port(
    ports: Sequence[str],
    probe_cmds: Optional[Sequence[str]] = None,
    *,
    baudrates: Sequence[int] = (115200, 9600, 57600, 38400, 19200),
    per_cmd_wait_s: float = 3.0,
    prefer_first: Optional[Sequence[str]] = None,
    return_debug: bool = False,
) -> Optional[str] | Tuple[Optional[str], List[ProbeResult]]:
    """
    - ports: list port bạn muốn scan (COMx hoặc /dev/ttyUSBx)
    - probe_cmds: list lệnh để thử (mặc định theo bạn mô tả)
    - baudrates: thử nhiều baud để tránh “im lặng” vì sai baud
    - per_cmd_wait_s: mỗi lệnh chờ đọc response (vd 3s)
    - prefer_first: list port ưu tiên thử trước (vd ["COM1"])
    - return_debug: True -> trả thêm danh sách ProbeResult để xem vì sao fail/pass
    """
    if probe_cmds is None:
        probe_cmds = ["?", "help", "HELP", "Help", "SHOW_COMMAND"]

    # line endings hay gặp (nhiều fixture cần CRLF, nhưng có cái chỉ LF)
    line_endings = ["\r\n", "\n", "\r", ""]

    # sắp xếp ưu tiên
    ordered = list(ports)
    if prefer_first:
        pref = [p for p in prefer_first if p in ordered]
        rest = [p for p in ordered if p not in set(pref)]
        ordered = pref + rest

    results: List[ProbeResult] = []
    for p in ordered:
        r = _probe_one_port(
            port=p,
            probe_cmds=probe_cmds,
            baudrates=baudrates,
            per_cmd_wait_s=per_cmd_wait_s,
            write_line_endings=line_endings,
        )
        results.append(r)
        if r.is_fixture:
            return (r.port, results) if return_debug else r.port

    return (None, results) if return_debug else None
