# GUI Check Fixture – Reusable blocks & notes for “Auto Extract Commands” tool

> File này tổng hợp các **hàm / class / pattern** có thể tái sử dụng trong project GUI hiện tại (Tkinter + Canvas assets),
> phục vụ mục tiêu: **tự động tìm COM fixture → mở listener RX liên tục → gửi command tuần tự → trích command list/help → health-check**.

---

## 1) Mục tiêu tool “Auto Extract Commands từ COM Fixture”

### Yêu cầu cốt lõi
1. **Resolve COM fixture** (ưu tiên cache trong `config.ini`, fallback scan tất cả `/dev/ttyUSB*` / `COM*`).
2. **Listen RX liên tục** (một worker chỉ đọc COM, không block UI).
3. **Send command an toàn**:
   - gửi nhiều lệnh khác nhau (từ UI, từ script, từ bước trích commands…)
   - **không được gửi chồng** (fixture dễ lỗi nếu 2 luồng gửi cùng lúc)
   - gom response theo từng command (để parse chính xác).
4. **Trích commands**:
   - gửi “help / ? / SHOW_COMMAND …”
   - parse output để tạo danh sách command (và/hoặc mô tả tham số).
5. **Broadcast UI state**:
   - nhiều màn hình (root + Toplevel) luôn sync: COM status, logs, slot status.

---

## 2) Các block tái sử dụng (đang có trong codebase)

### 2.1. Config: đọc/ghi `config.ini` (giữ format, atomic write)
**Nguồn:** `src/utils/config_go.py`

- `load_fixture_cfg(path) -> FixtureConfig`
  - lấy `port`, `baudrate`, `ending_line`, `timeout`
  - lấy text command trên từng slot: `[SLOT_TEST]`
  - lấy status từng slot: `[SLOT_STATUS]`

- `update_ini_fixture_section(..., port, baudrate, ending_line, timeout)`
  - update section `[FIXTURE]` **atomic** (ghi file tạm rồi replace)

- `load_slot_status_from_ini(...) -> Dict[int, str]`
  - parse kiểu “text-based”, chịu được key trùng (slot8 lặp)
  - rule: slot có bài trong `[SLOT_TEST]` mà status idle → đổi thành `item`

- `update_ini_slot_status(ini_path, slot_idx, status)`
  - chỉ cho phép status thuộc tập `_ALLOWED_STATUS`
  - update *tất cả dòng trùng* `slot{idx}=...` trong `[SLOT_STATUS]` (tránh lệch)

- `reset_slot_status_section_to_idle(...)`
  - reset status 12 slot về `idle/item` tuỳ slot có bài hay không.

**Tái sử dụng cho tool:**
- cache COM/baud/ending_line để lần sau mở nhanh hơn
- persist “health-check summary” (nếu muốn) dưới section mới (vd `[FIXTURE_HEALTH]`)

---

### 2.2. List serial ports (đa nền tảng)
**Nguồn:** `src/gui/fixture/get_serial_list.py`

- `get_serial_ports(include_details=False)`
  - Windows: dùng `serial.tools.list_ports`
  - Linux: glob `/dev/ttyUSB*`

**Tái sử dụng cho tool:**
- scan nhanh danh sách cổng trước khi probe fixture

---

### 2.3. Probe “đây có phải fixture không?”
**Nguồn:** `src/gui/fixture/get_fixture_port.py`

- `get_fixture_port(ports, probe_cmds=["?","help",...], baudrates=(...), per_cmd_wait_s=3.0, ...)`
  - thử nhiều baud
  - thử nhiều line ending (`\r\n`, `\n`, `\r`, ``)
  - heuristic “fixture response” dựa trên marker help + command-like lines + keyword score
  - trả về `port` fixture đầu tiên match

**Tái sử dụng cho tool:**
- dùng y hệt để “resolve COM fixture” hoặc làm “self-check” trước khi chạy test.

> Tip: tool trích command nên gọi probe trước để tránh lỡ “bắn command” vào thiết bị khác.

---

### 2.4. Serial IO nền: 1 thread đọc + queue request gửi
**Nguồn:** `src/gui/fixture/listen_port.py`

`ListenPort` là block quan trọng nhất để đảm bảo:
- **đọc liên tục** (RX) trong 1 thread riêng
- mọi thao tác TX/flush/clear buffer đi qua **request queue** để tránh race
- có `send_and_collect()` gom response theo “seq snapshot” (không phụ thuộc timing chung)

**API đáng dùng:**
- `start() / stop() / reset() / is_ready()`
- `send(cmd, append_crlf=True, wait_written=True)`
- `send_and_collect(cmd, timeout=..., idle_after_last_rx=..., expect=regex, clear_before_send=True)`

**Tái sử dụng cho tool:**
- worker chỉ đọc COM fixture (đảm bảo “lắng nghe liên tục mà vẫn gửi được lệnh”)
- trích help output: `send_and_collect("help")`

---

### 2.5. Task queue + runner (để UI không lag)
**Nguồn:** `src/utils/sub_thread.py`

- `SubThreadRunner`: chạy job trong thread, callback về Tk main thread bằng `root.after`.
- `SubProcessRunner`: chạy job trong process (CPU-bound), callback về Tk main thread.
- `SequentialTaskQueue`: **xếp hàng tuần tự** (chỉ chạy 1 job mỗi lần).

**Tái sử dụng cho tool:**
- Tạo **một queue dành riêng cho IO** (send command, trích help, health-check) để đảm bảo command không bị gửi chồng.
- Ví dụ pattern trong `AppGUI`:
  - `io_runner = SubThreadRunner(root)`
  - `io_taskq = SequentialTaskQueue(root=root, runner=io_runner)`
  - mọi `send_to_com()` đều submit vào `io_taskq`

---

### 2.6. Logging pipeline: buffer + widget UI log
**Nguồn:** 
- `src/utils/buffer_logger.py` (`build_log_buffer`)
- `src/gui/widgets/canvas_log_widget.py` (`CanvasLogWidget`)

**Ý tưởng:**
- Logger ghi ra stdout + ghi vào list buffer (giữ tối đa N dòng).
- UI log widget nhận `emit(line, color)` thread-safe qua `queue.Queue`, pump định kỳ (after loop).

**Tái sử dụng cho tool:**
- Tool trích command/health-check nên log theo màu:
  - `yellow`: progress / running step
  - `blue`: TX
  - `white`: RX raw
  - `green`: ok / found
  - `red`: error

---

### 2.7. Slot status + UI indicator
**Nguồn:** `src/gui/widgets/fixture_check_slot_test.py`

- `FixtureCheckSlotTest.set_status(status)`
  - status tolerant: lạ → fallback idle
- `set_disabled(True/False)`

**Tái sử dụng cho tool:**
- broadcast trạng thái test từng slot (nếu tool có chạy test nhiều slot)
- hiển thị “item” nếu slot có bài

---

### 2.8. Multi-window broadcasting (root + extra windows)
**Nguồn:** `gui_check_fixture.py`

Pattern rất đáng giữ:
- `_iter_windows()` → yield root + tất cả Toplevel còn sống
- `_get_widgets(win)` → lấy dict widget map của window
- `_update_logs_panel(...)` → log 1 lần và broadcast xuống mọi window

**Tái sử dụng cho tool:**
- mọi update UI nên gọi qua 1 “broadcast helper” (xem mục 4).

---

### 2.9. Modal overlay: chặn click phía sau dialog
**Nguồn:** `src/gui/widgets/dialog.py`

`ModalOverlay`:
- phủ canvas lên toàn root
- bind event để “eat event” → không click lọt xuống dưới
- vẽ “dim background” bằng rectangle + stipple (giả lập trong suốt)

**Tái sử dụng cho tool:**
- khi đang “scan COM” hoặc “extract commands”, show overlay để user không bấm lung tung.

---

## 3) Design đề xuất cho “Auto Extract Commands” (module mới)

### 3.1. Interface tối thiểu (khuyến nghị)
Tạo module mới, ví dụ: `src/gui/fixture/fixture_command_tool.py`

**Chức năng:**
- `resolve_fixture(cfg_path) -> (port, baudrate, ending_line)`
- `start_listener(port, baudrate)`
- `extract_commands() -> List[str]`
- `health_check(commands_subset) -> Dict[str, Any]`
- `save_commands(path, commands)`

### 3.2. Skeleton code (pseudo)
```python
import re
from typing import List, Dict

COMMAND_PATTERNS = [
    re.compile(r"^\s*[A-Za-z0-9_?]+\s*:\s*.+$"),         # CMD: description
    re.compile(r"^\s*[A-Za-z0-9_?]+(?:\s+[A-Za-z0-9_?]+)?\s*$"),  # single/2 tokens
    re.compile(r"^\s*CMD=.*$", re.IGNORECASE),
]

def parse_help_to_commands(lines: List[str]) -> List[str]:
    out = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        # bỏ các dòng banner, timestamp, etc nếu cần
        if any(p.match(s) for p in COMMAND_PATTERNS):
            out.append(s)
    # dedup (giữ thứ tự)
    seen = set()
    uniq = []
    for x in out:
        k = x.upper()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    return uniq

def extract_commands(listenport) -> List[str]:
    ok, lines = listenport.send_and_collect("help", timeout=5.0, idle_after_last_rx=0.8)
    cmds = parse_help_to_commands(lines)
    # fallback nếu help không ra:
    if len(cmds) < 3:
        ok, lines = listenport.send_and_collect("?", timeout=5.0, idle_after_last_rx=0.8)
        cmds = max(cmds, parse_help_to_commands(lines), key=len)
    return cmds
```

### 3.3. Chỗ “điểm nghẽn” cần tránh
- **Không gọi `send_and_collect` trực tiếp trên Tk main thread** (sẽ block UI).
- Không để 2 luồng gọi send cùng lúc (dễ “dính response” hoặc fixture sai).
- Khi parse help:
  - có thể có log banner, timestamp, “OK”…
  - cần lọc command-like lines + dedup

---

## 4) Broadcast UI state: pattern đề xuất

### 4.1. Một hàm broadcast chung
```python
def broadcast(self, fn):
    for w in self._iter_windows():
        ws = self._get_widgets(w)
        fn(w, ws)
```

### 4.2. Broadcast log
- Source-of-truth: logger buffer (`build_log_buffer`)
- UI: `CanvasLogWidget.emit(...)` trên tất cả window

### 4.3. Broadcast COM status
- com widget: `bind_fixture_circle_com_status`
- states: `stand_by / listening / not_found / error`

---

## 5) Concurrency guideline (để “test mượt”)

1. **Một listener RX duy nhất** (ListenPort thread).
2. **Một queue IO duy nhất**:
   - mọi “send command” đều đi qua `io_taskq` (SequentialTaskQueue).
   - các thao tác “extract commands”, “health-check” cũng submit vào queue này.
3. **UI update phải chạy trên Tk thread**:
   - `ListenPort` đã có `dispatch=lambda fn: root.after(0, fn)` để callback về Tk.
4. **Throttle logs**:
   - CanvasLogWidget pump theo batch + trim (đã có), tránh spam UI.

---

## 6) Test cases nên có cho tool

- [ ] Có cache COM trong config → mở nhanh, không scan.
- [ ] Cache sai → fallback scan, tìm đúng COM.
- [ ] Fixture trả help dài → parse được >= N commands.
- [ ] Gửi 20 command liên tiếp → không lẫn response (tuần tự).
- [ ] Rút cáp/COM mất → `ListenPort` báo lỗi, UI chuyển `error/not_found`.
- [ ] Multi-window: log & status luôn sync.

---

## 7) TODO gợi ý (next steps)

- (A) Viết `parse_fixture_port_text()` chuẩn (nếu muốn parse chuỗi debug từ probe thành `{port, baud, ending}`).
- (B) Add “Export Commands” button:
  - chạy `extract_commands()` → lưu `commands.json` hoặc `commands.md`.
- (C) Add “Health Check” button:
  - chạy subset commands: VERSION/STATE/RESET… và hiển thị kết quả.

---