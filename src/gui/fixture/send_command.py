import time
import serial
from typing import Callable, Optional, Tuple

LogCB = Callable[[str], None]


def _write_all(ser: serial.Serial, data: bytes) -> None:
    """Đảm bảo write hết data (tránh lỡ command nếu write trả về short)."""
    mv = memoryview(data)
    total = 0
    while total < len(mv):
        n = ser.write(mv[total:])
        if n is None:
            n = 0
        if n <= 0:
            # nếu thiết bị/driver kẹt, nhường 1 nhịp rồi thử tiếp (write_timeout sẽ cứu)
            time.sleep(0.002)
            continue
        total += n
    ser.flush()


def _read_with_tail(
    ser: serial.Serial,
    *,
    first_byte_timeout: float,
    tail_timeout: float,
    log_cb: Optional[LogCB] = None,
    break_predicate: Optional[Callable[[bytes], bool]] = None,
    max_after_first_data: float = 12.0,
    sleep_s: float = 0.01,
) -> bytes:
    """
    - Chờ tối đa first_byte_timeout để có byte đầu tiên.
    - Khi đã có data: kéo deadline theo "tail window" (now + tail_timeout) mỗi lần nhận thêm data.
    - Nếu break_predicate True: freeze tail window tại now + tail_timeout (không kéo dài nữa).
    - Có cap max_after_first_data để tránh treo nếu device stream vô hạn.
    """
    start = time.monotonic()
    first_deadline = start + max(0.0, float(first_byte_timeout))

    got_any = False
    first_data_t: Optional[float] = None

    terminator_seen = False
    tail_deadline: Optional[float] = None

    buf = bytearray()

    while True:
        now = time.monotonic()

        if not got_any:
            if now >= first_deadline:
                break
        else:
            # tránh treo nếu stream vô hạn mà không bao giờ "quiet"
            if first_data_t is not None and (now - first_data_t) >= max_after_first_data:
                if log_cb:
                    log_cb("[debug] max_after_first_data reached, stop collecting.")
                break
            if tail_deadline is not None and now >= tail_deadline:
                break

        n = 0
        try:
            n = int(ser.in_waiting or 0)
        except Exception:
            n = 0

        if n > 0:
            chunk = ser.read(n)
            if chunk:
                buf.extend(chunk)

                if not got_any:
                    got_any = True
                    first_data_t = now
                    # bắt đầu tail window ngay khi có data đầu tiên
                    tail_deadline = now + float(tail_timeout)

                # nếu chưa gặp terminator => tail window “trượt” theo data
                if not terminator_seen:
                    tail_deadline = now + float(tail_timeout)

                if break_predicate and (not terminator_seen) and break_predicate(bytes(buf)):
                    terminator_seen = True
                    # freeze tail window: giữ đúng now + tail_timeout tại thời điểm thấy terminator
                    tail_deadline = now + float(tail_timeout)

        else:
            time.sleep(sleep_s)

    return bytes(buf)


def send_text_and_wait(
    text: str,
    port: str = "COM7",
    baudrate: int = 9600,
    write_append_crlf: bool = True,
    read_timeout: float = 5.0,
    tail_timeout: float = 2.0,
    log_callback: LogCB = print,
    *,
    # tuỳ chọn: nếu muốn break sớm khi thấy keyword
    terminators: Tuple[str, ...] = ("PASS", "FAIL", "ERRO"),
    # tránh treo nếu thiết bị spam data liên tục
    max_after_first_data: float = 12.0,
) -> Tuple[bool, str]:
    """
    Text-based serial:
    - Chờ byte đầu tiên tối đa read_timeout.
    - Có data => kéo thêm tail_timeout (2s) để gom đủ, trượt theo data.
    - Nếu thấy terminator => freeze tail window rồi trả kết quả.
    - Không trả "timeout" nữa: chỉ trả No data nếu không có byte nào.
    """
    try:
        with serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=0,            # non-blocking read
            write_timeout=1.0,    # chống kẹt write
        ) as ser:
            # clear stale
            try:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
            except Exception:
                pass

            send_str = text + ("\r\n" if write_append_crlf else "")
            payload = send_str.encode("utf-8", errors="replace")

            _write_all(ser, payload)

            def _break_pred(raw: bytes) -> bool:
                if not terminators:
                    return False
                up = raw.decode("utf-8", errors="ignore").upper()
                return any(t in up for t in terminators)

            raw = _read_with_tail(
                ser,
                first_byte_timeout=read_timeout,
                tail_timeout=tail_timeout,
                log_cb=None,  # tránh spam; debug nếu cần thì bật
                break_predicate=_break_pred if terminators else None,
                max_after_first_data=max_after_first_data,
            )

            if not raw:
                return False, "No data"

            # decode an toàn
            resp = raw.decode("utf-8", errors="replace").strip()

            # log debug (gọn)
            log_callback(f"[debug][{port}] RX({len(raw)}B): {resp!r}")

            return True, resp

    except serial.SerialException as e:
        log_callback(f"[ERROR] Serial error on {port}: {e}")
        return False, f"Serial error: {e}"


def control_comscan(
    port: str = "COM5",
    baudrate: int = 9600,
    timeout_sec: float = 5.0,
    tail_timeout: float = 2.0,
    log_callback: LogCB = print,
    *,
    cmd: Optional[bytes] = None,
    max_after_first_data: float = 12.0,
) -> Optional[bytes]:
    """
    Binary-based COMScan:
    - Chờ byte đầu tiên tối đa timeout_sec.
    - Có data => kéo thêm tail_timeout (2s) để gom đủ, trượt theo data.
    - Không trả None vì "timeout" nếu đã có data; chỉ None nếu không có byte nào.
    """
    if cmd is None:
        cmd = bytes([0x16, 0x54, 0x0D])  # default như bạn đang dùng

    try:
        with serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=0,
            write_timeout=1.0,
        ) as ser:
            try:
                ser.reset_input_buffer()
                ser.reset_output_buffer()
            except Exception:
                pass

            _write_all(ser, cmd)

            raw = _read_with_tail(
                ser,
                first_byte_timeout=timeout_sec,
                tail_timeout=tail_timeout,
                log_cb=None,
                break_predicate=None,  # binary: thường không có keyword; nếu có frame end thì bạn có thể tự thêm
                max_after_first_data=max_after_first_data,
            )

            if not raw:
                return None

            # debug hex ngắn
            preview = raw[:64].hex(" ")
            log_callback(f"[debug][{port}] RX({len(raw)}B): {preview}{' ...' if len(raw) > 64 else ''}")
            return raw

    except serial.SerialException as e:
        log_callback(f"[ERROR] Serial error on {port}: {e}")
        return None


# send_text_and_wait(
#     "?", "/dev/ttyUSB3", 9600, True, 5.0, 2.0, print,)

# import serial
# import time
# from typing import Callable, Optional, Tuple

# def send_text_and_wait(
#     text: str,
#     port: str = "COM7",
#     baudrate: int = 9600,
#     write_append_crlf: bool = True,
#     read_timeout: float = 5.0,
#     log_callback: Callable[[str], None] = print,
# ) -> Tuple[bool, str]:
#     """
#     [TEXT / LINE-BASED SERIAL PROTOCOL]
#     Gửi chuỗi text ra cổng COM rồi chờ response dạng TEXT (thường có ký tự xuống dòng).

#     Khi nào dùng hàm này?
#     ---------------------
#     - Thiết bị giao tiếp bằng ASCII/UTF-8 (hoặc text tương đương)
#     - Thiết bị trả về theo dòng (có '\\n') => đọc bằng ser.readline() là hợp lý
#     - Bạn có “dấu hiệu kết thúc” trong response, ví dụ: PASS / FAIL / ERRO
#       -> để dừng sớm, không cần chờ hết timeout.

#     Tại sao COMScan (thiết bị scan SN chuyên dụng) KHÔNG dùng được hàm này?
#     -----------------------------------------------------------------------
#     - COMScan thường dùng giao thức binary: gửi các byte điều khiển (HEX) như 0x16 0x54 0x0D
#     - Response của COMScan có thể là raw bytes và KHÔNG có newline '\\n'
#       => ser.readline() có thể không trả gì cho đến khi timeout.
#     - Nếu bạn encode text rồi gửi, thiết bị có thể không hiểu lệnh.

#     Tại sao hàm này KHÔNG phù hợp cho mọi COM?
#     ------------------------------------------
#     - Vì nó giả định:
#       (1) Gửi text (encode UTF-8)
#       (2) Response có newline
#       (3) Kết thúc bằng keyword PASS/FAIL/ERRO

#     Return
#     ------
#         (True, response_str)  nếu nhận được dữ liệu hợp lệ
#         (False, message)      nếu timeout hoặc response chứa FAIL/ERRO hoặc lỗi serial
#     """
#     try:

#         # CFG.com.COM_SFC
#         # CFG.com.COM_SCAN
#         # CFG.com.COM_LASER
#         # timeout=0: non-blocking read. Ta tự quản timeout bằng vòng while + deadline
#         # Lý do: đọc nhiều lần, gom response, dừng sớm khi gặp keyword
#         with serial.Serial(port, baudrate, timeout=0) as ser:
#             # ---- SEND ----
#             # Nhiều thiết bị text-based yêu cầu CRLF để kết thúc frame/lệnh.
#             send_str = text + ("\r\n" if write_append_crlf else "")
#             send_bytes = send_str.encode("utf-8", errors="replace")

#             # Reset buffer để tránh dính data cũ (stale) từ lần trước
#             ser.reset_input_buffer()
#             ser.reset_output_buffer()

#             ser.write(send_bytes)
#             ser.flush()

#             # ---- WAIT RESPONSE ----
#             deadline = time.time() + read_timeout
#             response = ""

#             while time.time() < deadline:
#                 # readline() phù hợp khi thiết bị có '\n' kết thúc dòng
#                 line = ser.readline()
#                 if line:
#                     # Decode text: ưu tiên utf-8, fallback latin-1 để không crash
#                     try:
#                         decoded = line.decode("utf-8")
#                     except UnicodeDecodeError:
#                         decoded = line.decode("latin-1", errors="ignore")

#                     response += decoded
#                     log_callback(f"[debug][{port}] -> {decoded!r}")
            
#                 else:
#                     # Ngủ nhẹ để tránh while loop ăn CPU 100%
#                     time.sleep(0.01)

#             # upper = response.upper()
#             # if "FAIL" in upper or "ERRO" in upper:
#             #     return False, f"{port} FAIL/ERRO - {response.strip()}"

#             if response.strip():
#                 return True, response.strip()

#             return False, "No response (timeout)"

#     except serial.SerialException as e:
#         log_callback(f"[ERROR] Serial error on {port}: {e}")
#         return False, f"Serial error: {e}"


# def control_comscan(
#     port: str = "COM5",
#     baudrate: int = 9600,
#     timeout_sec: float = 5.0,
#     log_callback: Callable[[str], None] = print,
# ) -> Optional[bytes]:
#     """
#     [BINARY / COMMAND-BASED SERIAL PROTOCOL FOR COMSCAN]
#     Điều khiển thiết bị COMScan (chuyên scan SN) bằng lệnh nhị phân (raw bytes).

#     Khi nào dùng hàm này?
#     ---------------------
#     - Thiết bị không nhận “text command”, mà nhận “binary command frame”
#       Ví dụ: cmd = 0x16 0x54 0x0D
#     - Response trả về dạng bytes, có thể KHÔNG có '\\n'
#       => Không dùng readline(), mà dùng read() theo in_waiting.

#     Tại sao hàm này KHÔNG dùng cho COM7 kiểu Laser/SFC?
#     ---------------------------------------------------
#     - COM7 text-based thường chờ chuỗi ASCII + CRLF.
#     - Nếu bạn gửi 0x16 0x54 0x0D vào thiết bị text-based:
#       + thiết bị có thể hiểu sai, trả về garbage, hoặc “kẹt state machine”.
#     - Vì protocol khác nhau nên phải tách riêng.

#     Response bytes là gì?
#     ---------------------
#     - Bạn sẽ nhận bytes dạng ví dụ: b"GT542A0154530005" hoặc bytes raw khác
#     - Việc “decode”/“parse” SN tuỳ vào spec của COMScan.

#     Return
#     ------
#     - bytes nếu nhận được dữ liệu
#     - None nếu timeout / lỗi
#     """
#     # Lệnh điều khiển dạng HEX (control code)
#     # 0x16 (SYN), 0x54 ('T'), 0x0D (CR) - chỉ là ví dụ theo thiết bị của bạn
#     cmd = bytes([0x16, 0x54, 0x0D])

#     try:
#         with serial.Serial(port, baudrate, timeout=0) as ser:
#             ser.reset_input_buffer()
#             ser.reset_output_buffer()

#             # ---- SEND BINARY CMD ----
#             ser.write(cmd)
#             ser.flush()

#             # ---- READ RAW BYTES ----
#             deadline = time.time() + timeout_sec
#             recv = bytearray()

#             while time.time() < deadline:
#                 n = ser.in_waiting
#                 if n:
#                     recv.extend(ser.read(n))
#                     # Nhiều scanner trả về “1 frame” rồi dừng,
#                     # nên chỉ cần có data là break.
#                     break

#                 time.sleep(0.01)

#             if recv:
#                 return bytes(recv)
#             return None

#     except serial.SerialException as e:
#         log_callback(f"[ERROR] Serial error on {port}: {e}")
#         return None


