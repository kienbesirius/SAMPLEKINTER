from __future__ import annotations
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple, Union, Callable

import serial  # pip install pyserial

# dùng tail-read từ send_command.py
try:
    from .send_command import _read_with_tail  # type: ignore
except Exception:
    # fallback for running from project root
    from src.gui.fixture.send_command import _read_with_tail  # type: ignore


# --- Heuristic keywords (không bắt buộc phải đủ hết, chỉ dùng để chấm điểm) ---
_STRONG_KEYWORDS = {
    "IN", "OUT", "OPEN", "CLOSE", "UP", "DOWN",
    "RESET", "CLEAR", "STATE", "PRODUCT", "VERSION",
    "HELP", "FIXTURE", "EMPTY", "EMPTY_IN",
    "STOP", "EMC", "POWER", "PWR", "RELAY", "UART", "USB", "RJ45",
    "INPUT", "CHECK", "SET", "SN", "READSN",
    # --- nhóm HELP kiểu list đơn ---
    "VERSIONS", "BOX_STATUS", "RELAY_ALL_ON",
    "COUNTER_RESET", "COUNTER_ADD", "COUNTER_SUB", "READ_COUNT",
    "COUNT", "READ_COUNT_ALL", "CLEAR_COUNT", "RST_SET_COUNT",

    # --- nhóm ON/OFF + đo đạc (xuất hiện trong help list) ---
    "BATTERY_CYLINDER", "LED_CYLINDER", "BUTTON_CYLINDER", "HEATER_PLATE_CYLINDER",
    "DEBUGBOARD", "TYPEC_BOARD",
    "SBU_PULL_DOWN",
    "BATTERY_CHARGE", "DEBUG_VBUS_5V",
    "TYPEC_VBUS_PC", "TYPEC_VBUS_POE", "TYPEC_USB_PC", "TYPEC_USB_POE",
    "SYSTEM_VOL_GET", "SYSTEM_CUR_GET", "BATTERY_CHARGE_VOL_GET",
    "CUR_MODE", "READ_CUR", "LOAD",

    # --- nhóm menu help (có command + mô tả) ---
    "STATUS", "TEMP", "LIGHT_ON", "LIGHT_OFF", "ALL_LED_OFF",
    "RED_ON", "GREEN_ON", "BLUE_ON",
    "DEBUG_POWER_ON", "DEBUG_POWER_OFF",
    "TYPEC_POWER_ON", "TYPEC_POWER_OFF",
    "OPEN_DOOR", "CLOSE_DOOR",
    "SIDE_IN", "SIDE_OUT",

    # --- nhóm “CONTROL CAMMAND” kiểu CMD:DESC ---
    "S_SYSTEM_RST",
    "SET_U1BR", "SET_U2BR", "SET_U3BR",
    "SET_DEBUG_MODE", "SET_BTN_DELAY",
    "READ_PARA", "CLEAR_PARA",
    "OUTPUTH", "OUTPUTL",
    "FIXTURE_IN", "FIXTURE_OUT",
    "POGOPIN_UP", "POGOPIN_DOWN",
    "USB_UP", "USB_DOWN",
    "FASTEN_ON", "FASTEN_OFF",
    "BUTTON_TEST",
    "POWER_ON", "POWER_OFF", "LED_ON", "LED_OFF",
    "EMPTY_OUT",
    "CHECK_DUT", "CHECK_STATE", "CHECK_RASTER",
    "READ_MAX_FORCE", "READ_REAL_FORCE", "SET_FORCE_BAUDRATE",
    "AUDIO_OPEN", "AUDIO_CLOSE",
    "SET_VOLUME_5", "SET_VOLUME_10", "SET_VOLUME_20",
    "SET_AUDIO_ADDR", "VOLUME_ADD", "VOLUME_DEC",
    "AGING_TEST",

    # --- nhóm help list khác ---
    "FIND", "GS_PWR_ON", "GS_PWR_OFF",
    "DUT_SENSOR", "RASTER_STATE",
    "POWER_ON1", "POWER_ON2", "POWER_OFF1", "POWER_OFF2",
    "UART_DL_ON", "UART_DL_OFF",
    "BUTTON_ON", "BUTTON_OFF", "BTN_ON",
    "LCD_ON", "LCD_OFF",
    "COUNTS", "COUNT", "CLEAR_COUNTER",
    "L_HOT_ON", "L_HOT_OFF", "M_HOT_ON", "M_HOT_OFF", "R_HOT_ON", "R_HOT_OFF",
}

# Các cụm “đánh dấu help” hay gặp (bắt cả typo trong log)
_HELP_MARKERS = (
    "CONTROL CAMMAND",
    "CONTROL COMMAND",
    "THIS IS THE HELP COMMAND",
    "SHOW ALL THE COMMANDS",
    "GET CAMMAND INFO",
    "GET COMMAND INFO",
    "SHOW_COMMAND",
    "?(SHOW ALL THE COMMANDS)",
    "<--------------- Main ---------------------------->",
    "<-------------- Product --------------------------->",
    "<--------------Other------------------------------->",
    "-- Main --",
    "-- Product --",
    "--Other--",

)

# Token command “một dòng 1 lệnh” thường gặp của fixture
_FIXTURE_TOKENS = {
    "?", "HELP", "SHOW_COMMAND",
    "OPEN", "CLOSE", "IN", "OUT", "UP", "DOWN",
    "EMPTY_IN", "EMPTY", "PRODUCT", "STATE", "VERSION",
    "POWER_ON", "POWER_OFF", "PWR_ON", "PWR_OFF",
    "USB_IN", "USB_OUT", "RJ45_IN", "RJ45_OUT",
    "READSN", "SN", "RESET", "CHECK_DOOR",
    "OPEN_DOOR", "CLOSE_DOOR",
    "LOCK_DUT", "UNLOCK_DUT",
    "PROBE_ON", "PROBE_OFF",

    "PRESS_ON", "PRESS_OFF",

    "RED_ON", "GREEN_ON", "YELLOW_ON",

    "RASTER_STATE", "RASTER_UP", "RASTER_DOWN",
    "RASTER_IN", "RASTER_OUT",

    "CLEAR_COUNT",
    # --- nhóm HELP kiểu list đơn ---
    "VERSIONS", "BOX_STATUS", "RELAY_ALL_ON", "RELAY",
    "COUNTER_RESET", "COUNTER_ADD", "COUNTER_SUB", "READ_COUNT",
    "COUNT", "READ_COUNT_ALL", "CLEAR_COUNT", "RST_SET_COUNT",

    # --- nhóm ON/OFF + đo đạc (xuất hiện trong help list) ---
    "BATTERY_CYLINDER", "LED_CYLINDER", "BUTTON_CYLINDER", "HEATER_PLATE_CYLINDER",
    "DEBUGBOARD", "TYPEC_BOARD",
    "SBU_PULL_DOWN",
    "BATTERY_CHARGE", "DEBUG_VBUS_5V",
    "TYPEC_VBUS_PC", "TYPEC_VBUS_POE", "TYPEC_USB_PC", "TYPEC_USB_POE",
    "SYSTEM_VOL_GET", "SYSTEM_CUR_GET", "BATTERY_CHARGE_VOL_GET",
    "CUR_MODE", "READ_CUR", "LOAD",

    # --- nhóm menu help (có command + mô tả) ---
    "STATUS", "TEMP", "LIGHT_ON", "LIGHT_OFF", "ALL_LED_OFF",
    "RED_ON", "GREEN_ON", "BLUE_ON",
    "DEBUG_POWER_ON", "DEBUG_POWER_OFF",
    "TYPEC_POWER_ON", "TYPEC_POWER_OFF",
    "OPEN_DOOR", "CLOSE_DOOR",
    "SIDE_IN", "SIDE_OUT",

    # --- nhóm “CONTROL CAMMAND” kiểu CMD:DESC ---
    "S_SYSTEM_RST",
    "SET_U1BR", "SET_U2BR", "SET_U3BR",
    "SET_DEBUG_MODE", "SET_BTN_DELAY",
    "READ_PARA", "CLEAR_PARA",
    "OUTPUTH", "OUTPUTL",
    "FIXTURE_IN", "FIXTURE_OUT",
    "POGOPIN_UP", "POGOPIN_DOWN",
    "USB_UP", "USB_DOWN",
    "FASTEN_ON", "FASTEN_OFF",
    "BUTTON_TEST",
    "POWER_ON", "POWER_OFF", "LED_ON", "LED_OFF",
    "EMPTY_OUT",
    "CHECK_DUT", "CHECK_STATE", "CHECK_RASTER",
    "READ_MAX_FORCE", "READ_REAL_FORCE", "SET_FORCE_BAUDRATE",
    "AUDIO_OPEN", "AUDIO_CLOSE",
    "SET_VOLUME_5", "SET_VOLUME_10", "SET_VOLUME_20",
    "SET_AUDIO_ADDR", "VOLUME_ADD", "VOLUME_DEC",
    "AGING_TEST",

    # --- nhóm help list khác ---
    "FIND", "GS_PWR_ON", "GS_PWR_OFF",
    "DUT_SENSOR", "RASTER_STATE",
    "POWER_ON1", "POWER_ON2", "POWER_OFF1", "POWER_OFF2",
    "UART_DL_ON", "UART_DL_OFF",

}

# Các dòng info/boot thường thấy (không phải command list)
_INFO_PREFIX = (
    "MCU FLASH SIZE", "APP MAX SIZE", "APP_ADDR",
    "BJ_F1_BOOTLOADER", "BOOTLOADER", "DATE:",
    "INITIAL OK", "MOTOR_", "SET VOLUME",
)

# Regex để nhận dòng command-like
_RE_COLON_CMD = re.compile(r"^\s*[A-Za-z0-9_?]+\s*:\s*.+$")
_RE_SIMPLE_CMD = re.compile(r"^\s*[A-Za-z0-9_?]+(?:\s+[A-Za-z0-9_?]+)?\s*$")
_RE_TIMESTAMP_PREFIX = re.compile(r"^\s*\[\d{2}:\d{2}:\d{2}:\d{3}\]\s*")


@dataclass
class ProbeResult:
    port: str
    baudrate: int = 0
    line_ending: str = ""  # raw ending string: "\r\n", "\n", "\r", ""
    is_fixture: bool = False
    score: int = 0
    command_lines: int = 0
    matched_keywords: List[str] = field(default_factory=list)
    sample: str = ""


def _ending_name(le: str) -> str:
    return {
        "\r\n": "CRLF",
        "\n": "LF",
        "\r": "CR",
        "": "NONE",
    }.get(le, repr(le))


def _normalize_ports(ports: Union[str, Sequence[str]]) -> List[str]:
    # Nếu ai đó truyền "/dev/ttyUSB3" (string) thì wrap lại thành list 1 phần tử
    if isinstance(ports, str):
        return [ports]
    return list(ports)


def _normalize_lines(raw: str) -> List[str]:
    # Chuẩn hoá về \n để split
    raw = raw.replace("\r", "\n")
    lines: List[str] = []
    for ln in raw.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        # strip timestamp dạng [08:31:32:400]
        ln = _RE_TIMESTAMP_PREFIX.sub("", ln).strip()
        if ln:
            lines.append(ln)
    return lines


def _is_command_like(line: str) -> bool:
    up = line.upper()

    # Loại các line info/boot phổ biến để tránh chấm nhầm
    if any(up.startswith(p) for p in _INFO_PREFIX):
        return False

    if _RE_COLON_CMD.match(line):
        return True

    # Cho phép "power on" dạng 2 từ / token đơn
    if _RE_SIMPLE_CMD.match(line):
        # loại bớt các token không giúp ích
        if up in {"OK", "NG", "<BREAK>"}:
            return False
        return True

    # Một số fixture có dòng kiểu "CMD=StartAll|PanelSN=1"
    if up.startswith("CMD="):
        return True

    return False


def _extract_keywords(lines: List[str]) -> List[str]:
    text = " ".join(lines).upper()
    matched: List[str] = []
    for kw in _STRONG_KEYWORDS:
        # match theo word boundary “gần đúng”
        if re.search(rf"(^|[^A-Z0-9_]){re.escape(kw)}([^A-Z0-9_]|$)", text):
            matched.append(kw)
    matched.sort()
    return matched


def _is_fixture_response(lines: List[str]) -> Tuple[bool, int, int, List[str]]:
    """
    Return: (is_fixture, score, command_lines_count, matched_keywords)

    Heuristic bám sát pattern của fixture:
    - Có help marker + có list command
    - Hoặc nhiều dòng colon-def (OPEN:..., SET_...:...)
    - Hoặc list token command (SHOW_COMMAND/OPEN/CLOSE/IN/OUT/UP/DOWN/...)
    """
    if not lines:
        return (False, 0, 0, [])

    text_up = " ".join(lines).upper()

    has_help_marker = any(m in text_up for m in _HELP_MARKERS)

    matched = _extract_keywords(lines)
    kw_score = len(matched)

    colon_defs = sum(1 for ln in lines if _RE_COLON_CMD.match(ln))
    cmd_like = [ln for ln in lines if _is_command_like(ln)]
    cmd_count = len(cmd_like)

    token_lines = 0
    for ln in lines:
        tok = ln.strip().upper()
        if tok in _FIXTURE_TOKENS:
            token_lines += 1

    # score tổng hợp: marker + colon defs mạnh hơn keyword
    score = kw_score + (2 * colon_defs) + token_lines + (6 if has_help_marker else 0)

    # 1) Có marker help + có dấu hiệu list command rõ ràng
    if has_help_marker and (colon_defs >= 3 or token_lines >= 6 or cmd_count >= 8):
        return (True, score, cmd_count, matched)

    # 2) Dạng colon list mạnh
    if colon_defs >= 6:
        return (True, score, cmd_count, matched)

    # 3) Dạng token list (Windows style)
    if token_lines >= 8 and kw_score >= 2:
        return (True, score, cmd_count, matched)

    # 4) Có CMD=... (fixture protocol style)
    if any(ln.upper().startswith("CMD=") for ln in lines) and (token_lines >= 4 or kw_score >= 2):
        return (True, score, cmd_count, matched)

    return (False, score, cmd_count, matched)


def _write_all_noflush(ser: serial.Serial, data: bytes) -> None:
    """
    Gửi hết bytes nhưng KHÔNG gọi ser.flush() (tránh tcdrain gây kẹt / write timeout).
    Payload probe thường ngắn, nhưng vẫn xử lý partial write.
    """
    mv = memoryview(data)
    total = 0
    while total < len(mv):
        try:
            n = ser.write(mv[total:])
        except serial.SerialTimeoutException:
            n = 0
        if not n:
            time.sleep(0.002)
            continue
        total += n


def _send_and_wait_text(
    ser: serial.Serial,
    payload: bytes,
    *,
    read_timeout: float,
    tail_timeout: float = 0.5,
    max_after_first_data: float = 0.5,
    break_predicate: Optional[Callable[[bytes], bool]] = None,
) -> str:
    """
    - Gửi payload
    - Đọc response theo cơ chế is_ready_to_break + tail window (dùng _read_with_tail)
    """
    _write_all_noflush(ser, payload)

    raw = _read_with_tail(
        ser,
        first_byte_timeout=read_timeout,
        tail_timeout=tail_timeout,
        log_cb=None,
        break_predicate=break_predicate,
        max_after_first_data=max_after_first_data,
    )
    return raw.decode("utf-8", errors="ignore")


def _probe_one_port(
    port: str,
    probe_cmds: Sequence[str],
    baudrates: Sequence[int],
    per_cmd_wait_s: float,
    write_line_endings: Sequence[str],
) -> ProbeResult:
    best = ProbeResult(port=port)

    for br in baudrates:
        try:
            ser = serial.Serial(
                port=port,
                baudrate=br,
                timeout=0,          # non-blocking read
                write_timeout=0.5,  # probe cmd ngắn
                exclusive=True,  
            )
        except Exception:
            continue

        try:
            # Nhiều board reset khi open port -> đợi + xả boot log
            time.sleep(0.6)
            try:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
            except Exception:
                pass

            # Drain rác nhanh (nếu board tự bắn log khi mới mở)
            _ = _read_with_tail(
                ser,
                first_byte_timeout=0.2,
                tail_timeout=0.2,
                log_cb=None,
                break_predicate=None,
                max_after_first_data=0.5,
            )

            for cmd in probe_cmds:
                for le in write_line_endings:
                    try:
                        ser.reset_input_buffer()
                    except Exception:
                        pass

                    payload = (cmd + le).encode("utf-8", errors="ignore")

                    try:
                        raw = _send_and_wait_text(
                            ser,
                            payload,
                            read_timeout=per_cmd_wait_s,
                            tail_timeout=0.75,
                        )

                        raw += _send_and_wait_text(
                            ser,
                            payload,
                            read_timeout=per_cmd_wait_s,
                            tail_timeout=0.75,
                        )

                        raw += _send_and_wait_text(
                            ser,
                            payload,
                            read_timeout=per_cmd_wait_s,
                            tail_timeout=0.75,
                        )
                    except Exception:
                        continue

                    lines = _normalize_lines(raw)
                    is_fix, score, cmd_count, matched = _is_fixture_response(lines)

                    # ---- chọn best: ưu tiên fixture True trước ----
                    better = False
                    if is_fix and not best.is_fixture:
                        better = True
                    elif is_fix == best.is_fixture:
                        if score > best.score or (score == best.score and cmd_count > best.command_lines):
                            better = True

                    if better:
                        best = ProbeResult(
                            port=port,
                            baudrate=br,
                            line_ending=le,
                            is_fixture=is_fix,
                            score=score,
                            command_lines=cmd_count,
                            matched_keywords=matched,
                            sample="\n".join(lines[:60]),
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
    ports: Union[str, Sequence[str]],
    probe_cmds: Optional[Sequence[str]] = None,
    *,
    baudrates: Sequence[int] = (115200, 9600, 57600, 38400, 19200),
    per_cmd_wait_s: float = 1.0,
    prefer_first: Optional[Sequence[str]] = None,
    return_debug: bool = False,
) -> Optional[str] | Tuple[Optional[str], List[ProbeResult]]:
    """
    - ports: list port bạn muốn scan (COMx hoặc /dev/ttyUSBx) hoặc 1 string "/dev/ttyUSB3"
    - probe_cmds: list lệnh để thử
    - baudrates: thử nhiều baud để tránh “im lặng” vì sai baud
    - per_cmd_wait_s: mỗi lệnh chờ đọc response
    - prefer_first: list port ưu tiên thử trước
    - return_debug: True -> trả thêm danh sách ProbeResult
    """
    if probe_cmds is None:
        probe_cmds = ["?", "help", "HELP", "Help", "SHOW_COMMAND"]

    # line endings hay gặp (nhiều fixture cần CRLF, nhưng có cái chỉ LF)
    line_endings = ["\r\n", "\n", "\r", ""]

    ordered = _normalize_ports(ports)
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
            found = f"{r.port}@{r.baudrate}@{_ending_name(r.line_ending)}"
            return (found, results) if return_debug else found

    return (None, results) if return_debug else None


_ENDING_TO_LE = {
    "CRLF": "\r\n",
    "LF": "\n",
    "CR": "\r",
    "NONE": "",
}

_LE_TO_ENDING = {v: k for k, v in _ENDING_TO_LE.items()}

@dataclass(frozen=True)
class ParsedFixturePort:
    port: str
    baudrate: int
    line_ending: str  # actual bytes string: "\r\n" | "\n" | "\r" | ""


def parse_fixture_port_text(s: str) -> ParsedFixturePort:
    """
    Parse: "<port>@<baudrate>@<MODE>"
    Example:
      "/dev/ttyUSB3@9600@CRLF" -> ("/dev/ttyUSB3", 9600, "\\r\\n")
      "COM7@115200@LF"         -> ("COM7", 115200, "\\n")

    Raises ValueError if invalid.
    """
    if not s or "@" not in s:
        raise ValueError(f"Invalid fixture port text: {s!r}")

    parts = s.rsplit("@", 2)  # from right, so port may contain '@' in rare cases
    if len(parts) != 3:
        raise ValueError(f"Invalid fixture port text: {s!r}")

    port, baud_s, mode = parts[0].strip(), parts[1].strip(), parts[2].strip().upper()

    if not port:
        raise ValueError(f"Missing port in {s!r}")

    try:
        baudrate = int(baud_s)
    except ValueError as e:
        raise ValueError(f"Invalid baudrate {baud_s!r} in {s!r}") from e

    if mode not in _ENDING_TO_LE:
        raise ValueError(f"Invalid line ending mode {mode!r} in {s!r}. "
                         f"Allowed: {sorted(_ENDING_TO_LE)}")

    return ParsedFixturePort(port=port, baudrate=baudrate, line_ending=_ENDING_TO_LE[mode])


def format_fixture_port_text(port: str, baudrate: int, line_ending: str) -> str:
    """
    Build: "<port>@<baudrate>@<MODE>" from (port, baudrate, line_ending).
    """
    mode = _LE_TO_ENDING.get(line_ending)
    if mode is None:
        raise ValueError(f"Unsupported line_ending: {line_ending!r} (expected one of {list(_LE_TO_ENDING)})")
    return f"{port}@{int(baudrate)}@{mode}"
