#!/usr/bin/env python3
import time
import serial

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
[08:31:41:011] NG
[08:31:41:011] <break>
[08:32:00:084] MCU Flash Size:256 KB,APP MAX Size:244 KB
[08:32:00:100] BJ_F1_BootLoader_FW_V203,Date:May 21 2025_10:18:26
[08:32:00:116] APP_ADDR:0x5000
[08:32:00:372] APP
[08:32:00:867] SN:BU1-ZHBJ-A04-F887
[08:32:03:886] INITIAL OK
[08:32:03:886] SET VOLUME 5 OK
[08:32:03:886] MOTOR_R ORIGIN OK
[08:32:03:902] MOTOR_C ORIGIN OK
[08:32:03:902] MOTOR_L ORIGIN OK
[08:32:08:109] <break>
[08:32:09:865] MCU Flash Size:256 KB,APP MAX Size:244 KB
[08:32:09:881] BJ_F1_BootLoader_FW_V203,Date:May 21 2025_10:18:26
[08:32:09:881] APP_ADDR:0x5000
[08:32:10:153] APP
[08:32:10:648] SN:BU1-ZHBJ-A04-F887
[08:32:13:667] INITIAL OK
[08:32:13:667] SET VOLUME 5 OK
[08:32:13:667] MOTOR_R ORIGIN OK
[08:32:13:683] MOTOR_C ORIGIN OK
[08:32:13:683] MOTOR_L ORIGIN OK
[08:32:17:005] OK
[08:32:17:005] MOTOR_R ORIGIN OK
[08:32:17:005] MOTOR_C ORIGIN OK
[08:32:17:005] MOTOR_L ORIGIN OK
"""

HELP_BYTES = (HELP_RESPONSE.strip("\n").replace("\n", "\r\n") + "\r\n").encode("utf-8", errors="replace")

def write_all(
    ser: serial.Serial,
    data: bytes,
    *,
    chunk_size: int = 128,        # 128B @9600baud ~0.13s để transmit
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
                # Hết thời gian cho lần write hiện tại -> chờ rồi thử tiếp
                time.sleep(retry_sleep)
        i += len(chunk)

    # flush() có thể block lâu (chờ transmit hết). Nếu không cần “đảm bảo ra dây hết”
    # thì bạn có thể bỏ flush().
    ser.flush()

def main() -> None:
    print(f"Listening on {PORT} @ {BAUDRATE} ... (Ctrl+C to stop)")
    with serial.Serial(
        PORT,
        BAUDRATE,
        timeout=0,         # non-blocking read
        write_timeout=1.0, # tránh kẹt write
    ) as ser:
        buf = bytearray()
        last_rx = time.monotonic()

        while True:
            n = ser.in_waiting or 0
            if n:
                chunk = ser.read(n)
                if chunk:
                    buf.extend(chunk)
                    last_rx = time.monotonic()

                # tách theo CR/LF (nếu bên kia gửi theo dòng)
                while True:
                    # tìm vị trí CR hoặc LF đầu tiên
                    pos_cr = buf.find(b"\r")
                    pos_lf = buf.find(b"\n")
                    positions = [p for p in (pos_cr, pos_lf) if p != -1]
                    if not positions:
                        break

                    pos = min(positions)
                    line = bytes(buf[:pos]).strip()

                    # consume hết CR/LF liên tiếp
                    j = pos
                    while j < len(buf) and buf[j] in (10, 13):
                        j += 1
                    del buf[:j]

                    if line == b"?":
                        print("RX '?' -> send HELP")
                        write_all(ser, HELP_BYTES)

            else:
                # trường hợp chỉ gửi đúng 1 byte '?' không có newline:
                now = time.monotonic()
                if buf.strip() == b"?" and (now - last_rx) > 0.05:
                    buf.clear()
                    print("RX '?' (no newline) -> send HELP")
                    write_all(ser, HELP_BYTES)

                time.sleep(0.01)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
