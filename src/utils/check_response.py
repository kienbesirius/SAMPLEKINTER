#!/usr/bin/env python3
import time
import serial
import random
import re

PORT = "/dev/ttyUSB4"
BAUDRATE = 9600

# Nội dung trả về khi nhận '?'
HELP_RESPONSE = """[08:31:32:400] CONTROL CAMMAND:
[08:31:32:400] ?:GET CAMMAND INFO
[08:31:32:494] HELP:GET CAMMAND INFO
[08:31:32:494] VERSION:GET FIRMWARE INFO
[08:31:32:494] S_SYSTEM_RST:CONTROL BOARD RESET
[08:31:32:494] SET_U1BR:SET_U1BR:XXX:SET UART1 BAUDRATE
[08:31:32:494] SET_U2BR:SET_U2BR:XXX:SET UART2 BAUDRATE
[08:31:32:494] SET_U3BR:SET_U3BR:XXX:SET UART3 BAUDRATE
[08:31:32:494] READ_PARA:GET CONTROL BOARD PARAMETER
[08:31:32:494] CLEAR_PARA:CLEAR CONTROL BOARD PARAMETER
[08:31:32:494] OUTPUTH:OUTPUTHXX:SET YXX OUTPUT HIGH
[08:31:32:494] OUTPUTL:OUTPUTLXX:SET YXX OUTPUT LOW
[08:31:32:494] INPUT:INPUTXX:GET XXX STATE
[08:31:32:494] FIXTURE_IN:FIXTURE IN
[08:31:32:494] FIXTURE_OUT:FIXTURE OUT
[08:31:32:494] U_NEED_UP:PLUG UP
[08:31:32:494] U_NEED_DOWN:PLUG DOWN
[08:31:32:588] D_NEED_UP:PLUG UP
[08:31:32:588] D_NEED_DOWN:PLUG DOWN
[08:31:32:588] FASTEN_ON:FASTEN ON
[08:31:32:588] FASTEN_OFF:FASTEN OFF
[08:31:32:588] BUTTON_IN:BUTTON ON
[08:31:32:588] BUTTON_OUT:BUTTON OUT
[08:31:32:588] PWR_ON:PWR ON
[08:31:32:588] PWR_OFF:PWR OFF
[08:31:32:588] LIGHHT_ON:LIGHT ON
[08:31:32:588] LIGHHT_OFF:LIGHT OFF
[08:31:32:588] GET_CURRENT:GET CURRENT
[08:31:32:588] CHECK_SENSOR:CHECK SENSOR
[08:31:32:588] AUDIO_OPEN:PLAY AUDIO FILES
[08:31:32:588] AUDIO_CLOSE:STOP PLAY AUDIO
[08:31:32:588] SET_VOLUME_5:SET VOLUME 5
[08:31:32:588] SET_VOLUME_10:SET VOLUME 10
[08:31:32:588] SET_VOLUME_20:SET VOLUME 20
[08:31:32:588] SET_AUDIO_ADDR:SET AUDIO ADDR
[08:31:32:588] VOLUME_ADD:VOLUME ADD
[08:31:32:588] VOLUME_DEC:VOLUME DECREASE
[08:31:32:588] IN:FIXTURE IN
[08:31:32:675] OUT:FIXTURE OUT
[08:31:32:675] OPEN:FIXTURE IN
[08:31:32:675] CLOSE:FIXTURE OUT
[08:31:32:675] SET_PRANGE:SET_PRANGE_MX:XX,SET POSITIVE RANGE
[08:31:32:675] SET_NRANGE:SET_NRANGE_MX:XX,SET NEGATIVE RANGE
[08:31:32:675] SET_SPEED:SET_SPEED_MX:XX,SET SPEED
[08:31:32:675] SET_POSI:SET POSITION
[08:31:32:675] REL_MOVE:MOTOR_RELATIVEMOVE
[08:31:32:675] ABS_MOVE:MOTOR_ABSOLUTEMOVE
[08:31:32:675] GOHOME:MOTOR_GOHOME
[08:31:32:675] GO_POSI:GO_POSIX_MX
[08:31:32:675] GET_POSI_:GET_POSI_
[08:31:32:675] READ_PARA_MOTOR:GET MOTOR PARAMETER
[08:31:32:675] CLEAR_PARA_MOTOR:CLEAR MOTOR PARAMETER
"""

OK_BYTES = "ok"

HELP_BYTES = (HELP_RESPONSE.strip("\n").replace("\n", "\r\n") + "\r\n").encode("utf-8", errors="replace")

OK_BYTES = (OK_BYTES.strip("\n").replace("\n", "\r\n") + "\r\n").encode("utf-8", errors="replace")


FAIL_BYTES = b"fail\r\n"

def write_all(
    ser: serial.Serial,
    data: bytes,
    *,
    chunk_size: int = 128,
    retry_sleep: float = 0.01,
) -> None:
    mv = memoryview(data)
    i = 0
    while i < len(mv):
        chunk = mv[i:i + chunk_size]
        sent = 0
        while sent < len(chunk):
            try:
                n = ser.write(chunk[sent:])
                if n:
                    sent += n
                else:
                    time.sleep(retry_sleep)
            except serial.SerialTimeoutException:
                time.sleep(retry_sleep)
        i += len(chunk)
    ser.flush()

def _send_line(ser: serial.Serial, s: str) -> None:
    # luôn trả về theo CRLF cho giống fixture style
    payload = (s.strip() + "\r\n").encode("utf-8", errors="replace")
    write_all(ser, payload)

def _norm_cmd(raw: bytes) -> str:
    # decode + normalize: IN_CLOSE, IN:CLOSE, "IN   CLOSE" -> "IN CLOSE"
    try:
        s = raw.decode("utf-8", errors="replace").strip()
    except Exception:
        s = str(raw).strip()
    s = s.upper()
    s = re.sub(r"[\t:_]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def main() -> None:
    print(f"Listening on {PORT} @ {BAUDRATE} ... (Ctrl+C to stop)")
    with serial.Serial(
        PORT,
        BAUDRATE,
        timeout=0,         # non-blocking read
        write_timeout=1.0,
    ) as ser:
        buf = bytearray()
        last_rx = time.monotonic()

        # FORCE STOP spam state (không block loop)
        spam_active = False
        spam_end = 0.0
        spam_next = 0.0

        def _handle_command(line_bytes: bytes) -> None:
            nonlocal spam_active, spam_end, spam_next

            cmd = _norm_cmd(line_bytes)
            if not cmd:
                return

            # '?' -> HELP
            if cmd == "?":
                print("RX '?' -> send HELP")
                write_all(ser, HELP_BYTES)
                return

            # --- CASES bạn yêu cầu ---
            if cmd == "IN CLOSE" or cmd == "CLOSE" or cmd == "IN":
                print("RX 'IN CLOSE' -> close fixture ok")
                _send_line(ser, "ok")
                return

            if cmd == "OUT OPEN" or cmd == "OPEN" or cmd == "OUT":
                print("RX 'OUT OPEN' -> open fixture ok")
                _send_line(ser, "open fixture ok")
                return

            if cmd == "FORCE STOP":
                # random: hoặc trả STOPPED, hoặc spam NG/timeout/EMC trong 3 giây
                choice = random.choice(["STOPPED", "SPAM"])
                if choice == "STOPPED":
                    print("RX 'FORCE STOP' -> STOPPED")
                    _send_line(ser, "STOPPED")
                else:
                    print("RX 'FORCE STOP' -> spam NG/timeout/EMC for 3s")
                    spam_active = True
                    now = time.monotonic()
                    spam_end = now + 3.0
                    spam_next = now  # send ngay
                return

            if cmd in ("RESET", "S_SYSTEM_RST", "SYSTEM RST"):
                out = random.choice(["reset ok", "fixture reset ok"])
                print(f"RX '{cmd}' -> {out}")
                _send_line(ser, out)
                return

            if ("SENSOR" in cmd) or (cmd in ("CHECK SENSOR", "CHECK_SENSOR")):
                out = random.choice(["close failed", "not ok"])
                print(f"RX '{cmd}' -> {out}")
                _send_line(ser, out)
                return

            # fallback: echo nhẹ để debug (tuỳ bạn muốn bỏ)
            print(f"RX '{cmd}' -> (no rule)")

        while True:
            # tick spam (nếu đang spam FORCE STOP)
            if spam_active:
                now = time.monotonic()
                if now >= spam_end:
                    spam_active = False
                elif now >= spam_next:
                    spam_next = now + random.uniform(0.12, 0.35)
                    _send_line(ser, random.choice(["NG", "timeout", "EMC"]))

            n = ser.in_waiting or 0
            if n:
                chunk = ser.read(n)
                if chunk:
                    buf.extend(chunk)
                    last_rx = time.monotonic()

                # tách theo CR/LF
                while True:
                    pos_cr = buf.find(b"\r")
                    pos_lf = buf.find(b"\n")
                    positions = [p for p in (pos_cr, pos_lf) if p != -1]
                    if not positions:
                        break

                    pos = min(positions)
                    line = bytes(buf[:pos]).strip()

                    # consume CR/LF liên tiếp
                    j = pos
                    while j < len(buf) and buf[j] in (10, 13):
                        j += 1
                    del buf[:j]

                    if line:
                        _handle_command(line)

            else:
                # trường hợp gửi đúng 1 byte '?' không có newline:
                now = time.monotonic()
                if buf.strip() == b"?" and (now - last_rx) > 0.05:
                    buf.clear()
                    _handle_command(b"?")

                time.sleep(0.01)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
