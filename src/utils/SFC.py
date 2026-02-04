from __future__ import annotations
import configparser
import re
import socket
import os
from src.utils.resource_path import app_dir

CONFIG_PATH = app_dir() / "config.ini"
configparser = configparser.ConfigParser()
configparser.read(CONFIG_PATH, encoding="utf-8")

TEST_GROUP=configparser.get("Bypass_VI3", "TEST_GROUP", fallback="VI3")
SEQ_MD5=configparser.get("Bypass_VI3", "SEQ_MD5", fallback="GOLDFISHVI3")
errorCode=configparser.get("Bypass_VI3", "errorCode", fallback="")
routeCheck=configparser.getint("Bypass_VI3", "routeCheck", fallback=1)
testResult=configparser.get("Bypass_VI3", "testResult", fallback="P")
TESTER = configparser.get("Bypass_VI3", "TESTER", fallback="OPER")

# Load SFCConfig
linkAPIGet = configparser.get("SFCConfig", "linkAPIGet", fallback="http://10.72.76.65:8088/api/smo/config")
linkAPIPost = configparser.get("SFCConfig", "linkAPIPost", fallback="http://10.72.76.65:8088/api/smo/HandleData")
timeout = configparser.getint("SFCConfig", "timeout", fallback=3)
max_retries = configparser.getint("SFCConfig", "max_retries", fallback=2)

from typing import List, Optional
import re

_IPV4_FULL_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")

def _is_valid_full_ipv4(ip: str) -> bool:
    if not _IPV4_FULL_RE.match(ip):
        return False
    parts = ip.split(".")
    try:
        return all(0 <= int(p) <= 255 for p in parts)
    except Exception:
        return False


def _get_from_hostname() -> List[str]:
    ips = []
    try:
        name = socket.gethostname()
        _, _, addrs = socket.gethostbyname_ex(name)
        for a in addrs:
            ips.append(a)
    except Exception:
        pass

    try:
        ai = socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET)
        for entry in ai:
            addr = entry[4][0]
            ips.append(addr)
    except Exception:
        pass

    return list(dict.fromkeys(ips))

def _get_primary_via_udp() -> Optional[str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packets actually sent
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None

import subprocess
import platform
from typing import List, Dict, Any, Optional

def _no_console_subprocess_kwargs() -> Dict[str, Any]:
    """
    Windows: không bật console window (không popup terminal).
    Linux/macOS: trả về rỗng.
    """
    if os.name != "nt":
        return {}

    creationflags = 0
    startupinfo = None

    # Ẩn hoàn toàn console window của child process
    creationflags |= subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    # (optional) thêm STARTUPINFO cho chắc
    startupinfo = subprocess.STARTUPINFO()        # type: ignore[attr-defined]
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # type: ignore[attr-defined]

    return {"creationflags": creationflags, "startupinfo": startupinfo}

# def _get_by_cli() -> List[str]:
#     out = ""
#     ips = []
#     try:
#         system = platform.system().lower()
#         if system == "windows":
#             p = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=2)
#             out = p.stdout
#         else:
#             try:
#                 p = subprocess.run(["ip", "addr"], capture_output=True, text=True, timeout=2)
#                 out = p.stdout
#             except Exception:
#                 p = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=2)
#                 out = p.stdout
#     except Exception:
#         return ips

def _get_by_cli() -> List[str]:
    out = ""
    ips: List[str] = []

    kw = _no_console_subprocess_kwargs()

    try:
        system = platform.system().lower()
        if system == "windows":
            p = subprocess.run(
                ["ipconfig"],
                capture_output=True,
                text=True,
                timeout=2,
                shell=False,
                **kw,
            )
            out = p.stdout or ""
        else:
            try:
                p = subprocess.run(
                    ["ip", "addr"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    shell=False,
                    **kw,   # harmless trên linux (kw = {})
                )
                out = p.stdout or ""
            except Exception:
                p = subprocess.run(
                    ["ifconfig"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    shell=False,
                    **kw,
                )
                out = p.stdout or ""
    except Exception:
        return ips
    
    for m in re.finditer(r"(?:inet\s|IPv4 Address[.\s]*:\s*)(\d{1,3}(?:\.\d{1,3}){3})", out):
        ip = m.group(1)
        if ip and not ip.startswith("127."):
            ips.append(ip)
    return list(dict.fromkeys(ips))

def get_all_ipv4_addresses() -> List[str]:
    ips = []
    # 1) primary via UDP trick
    primary = _get_primary_via_udp()
    if primary and not primary.startswith("127."):
        ips.append(primary)
    # 2) hostname resolution
    for ip in _get_from_hostname():
        if ip and not ip.startswith("127."):
            ips.append(ip)
    # 3) CLI parsing fallback
    for ip in _get_by_cli():
        if ip and not ip.startswith("127."):
            ips.append(ip)
    # dedupe preserve order
    seen = set()
    result = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            result.append(ip)
    return result

def ip_matches_prefix(ip: str, prefix: str) -> bool:
    """Match initial octets. prefix like '172', '172.24', '192.65.3'."""
    if not ip or not prefix:
        return False
    ip_parts = ip.split('.')
    pref_parts = prefix.split('.')
    for i, p in enumerate(pref_parts):
        if i >= len(ip_parts) or ip_parts[i] != p:
            return False
    return True

def choose_ip_by_prefix_list(prefixes: List[str], candidates: Optional[List[str]] = None) -> Optional[str]:
    """Choose best IP matching any prefix in prefixes.
       Preference: candidate order (primary, hostname, cli)."""
    if not candidates:
        candidates = get_all_ipv4_addresses()
    if not candidates:
        return None
    # Trim and normalize prefixes
    prefs = [p.strip() for p in prefixes if p and p.strip()]
    if not prefs:
        return None
    # First try to find match for the most-specific prefix (longest) among candidates
    # sort prefs by length desc so more specific prefixes tested first
    prefs.sort(key=lambda s: -len(s))
    for pref in prefs:
        for ip in candidates:
            if ip_matches_prefix(ip, pref):
                return ip
    return None

def get_full_ip_from_head_ip(
    head_ip: Optional[str],
    *,
    candidates: Optional[List[str]] = None,
    fallback_primary: bool = True,
) -> Optional[str]:
    """
    Convert HEAD_IP prefix -> full local IPv4.

    - head_ip có thể là:
        + full ip: "172.24.10.55"
        + prefix: "172", "172.24", "192.168.1"
        + hoặc danh sách prefix csv: "172.24,192.168"
    - candidates: truyền vào list IP nếu bạn muốn test/override; nếu None sẽ tự detect.
    - fallback_primary: nếu không match prefix nào thì fallback về primary IP (UDP trick).

    Return: full IPv4 string hoặc None.
    """
    # lấy danh sách IP của máy
    if candidates is None:
        candidates = get_all_ipv4_addresses()

    if not candidates:
        # fallback: primary route IP
        if fallback_primary:
            p = _get_primary_via_udp()
            return p if p and not p.startswith("127.") else None
        return None

    if not head_ip:
        # không có prefix -> ưu tiên primary (đã đứng đầu candidates), hoặc fallback_primary
        return candidates[0] if candidates else None

    head_ip = head_ip.strip()
    if not head_ip:
        return candidates[0] if candidates else None

    # Nếu user đã đưa full IP thì chỉ accept nếu đúng là IP đang có trên máy
    if _is_valid_full_ipv4(head_ip):
        return head_ip if head_ip in candidates else None

    # Cho phép nhập nhiều prefix dạng CSV
    prefixes = [p.strip() for p in head_ip.split(",") if p.strip()]
    if not prefixes:
        return candidates[0] if candidates else None

    chosen = choose_ip_by_prefix_list(prefixes, candidates)
    if chosen:
        return chosen

    if fallback_primary:
        p = _get_primary_via_udp()
        return p if p and not p.startswith("127.") else None

    return None

try:
    import requests  # type: ignore
except Exception:
    from pip._vendor import requests

from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

class SourceIPAdapter(HTTPAdapter):
    def __init__(self, source_ip: str | None, **kwargs):
        # GÁN TRƯỚC — để init_poolmanager có thể dùng được
        self._source_ip = source_ip
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        # Chỉ bind nếu có IP hợp lệ
        if self._source_ip:
            pool_kwargs["source_address"] = (self._source_ip, 0)
        self.poolmanager = PoolManager(
            num_pools=connections,
            maxsize=maxsize,
            block=block,
            **pool_kwargs
        )

def get_bound_session(source_ip: str | None) -> requests.Session:
    s = requests.Session()
    if source_ip:
        adapter = SourceIPAdapter(source_ip)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
    return s

_session = get_bound_session(get_full_ip_from_head_ip(configparser.get("SFCConfig", "source_ip", fallback="172.24")))


from pathlib import Path
from datetime import datetime
import os, sys

# Cho phép dùng nếu có, không thì vẫn chạy bình thường
try:
    import fcntl  # Linux file lock
    _HAS_FLOCK = True
except Exception:
    _HAS_FLOCK = False

# Nhãn log mặc định (dùng được cả khi thiếu log_label.py)
try:
    from log_label import errorlog, infolog, debuglog  # type: ignore
except Exception:
    errorlog, infolog, debuglog = "[ERROR]", "[INFO]", "[DEBUG]"

def _resolve_base_dir(path_log: os.PathLike | str | None) -> Path:
    """Xác định thư mục gốc chứa file .py/.pyc/.exe đang chạy."""
    if path_log:
        return Path(path_log).expanduser().resolve()

    # PyInstaller / đóng gói: ưu tiên thư mục của executable
    if getattr(sys, "frozen", False) and hasattr(sys, "executable"):
        return Path(sys.executable).resolve().parent

    # Module/Script thông thường
    try:
        return Path(__file__).resolve().parent
    except NameError:
        argv0 = Path(sys.argv[0]).resolve() if sys.argv and sys.argv[0] else Path.cwd()
        return argv0.parent if argv0.is_file() else argv0

def _now(tz: str | object | None) -> datetime:
    """Trả về datetime hiện tại theo tz (chuỗi zone, tzinfo, hoặc None)."""
    if tz is None:
        return datetime.now()
    if isinstance(tz, str):
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(tz))
        except Exception:
            # Fallback localtime nếu không có zoneinfo/không tìm thấy tz
            return datetime.now()
    # tz là tzinfo
    try:
        return datetime.now(tz)  # type: ignore[arg-type]
    except Exception:
        return datetime.now()

def write_log(
    log_text: object | None = None,
    *,
    label: str | None = None,
    path_log: os.PathLike | str | None = None,
    prefix: str = "HERMES_LOGS_",
    tz: str | object | None = None,
    encoding: str = "utf-8",
    autoflush: bool = False,
    also_print: bool = False,
) -> str | None:
    """
    Ghi log vào [THƯ_MỤC_CHỨA_FILE_CHẠY]/LOGS/YYYYMM/<prefix>YYYYMMDD.txt

    - Nếu không truyền path_log: tự xác định dựa vào file .py/.pyc/.exe đang thực thi.
    - Nếu không truyền log_text: không làm gì (trả về None).
    - label mặc định: [INFO] (hoặc từ log_label.py nếu có).
    - tz: "Asia/Bangkok" hoặc tzinfo; None = localtime.
    - also_print: True để in ra stdout song song.
    - autoflush: True để fsync() ngay sau khi ghi.

    Trả về: đường dẫn tuyệt đối tới file log (str) hoặc None nếu không ghi.
    """
    if log_text is None:
        return None

    base_dir = _resolve_base_dir(path_log)
    now = _now(tz)

    logs_dir = base_dir / "LOGS" / now.strftime("%Y%m")
    logs_dir.mkdir(parents=True, exist_ok=True)

    file_name = f"{prefix}{now.strftime('%Y%m%d')}.txt"
    log_path = logs_dir / file_name

    label = label or infolog
    ts = now.strftime("%Y-%m-%d %H:%M:%S")

    # Hỗ trợ nhiều dòng: mỗi dòng có timestamp + label
    lines = str(log_text).splitlines() or [""]
    to_write = "".join(f"{ts} {label} {line}\n" for line in lines)

    # Ghi + khoá file (nếu có fcntl) để an toàn khi nhiều tiến trình
    with open(log_path, "a", encoding=encoding) as f:
        if _HAS_FLOCK:
            try:
                fcntl.flock(f, fcntl.LOCK_EX)
            except Exception:
                pass
        f.write(to_write)
        f.flush()
        if autoflush:
            try:
                os.fsync(f.fileno())
            except Exception:
                pass
        if _HAS_FLOCK:
            try:
                fcntl.flock(f, fcntl.LOCK_UN)
            except Exception:
                pass

    if also_print:
        try:
            print(to_write, end="")
        except Exception:
            pass

    return str(log_path.resolve())

LOG_TZ = "Asia/Bangkok"   # timezone for timestamps
LOG_AUTOFUSH = False      # fsync after each write (False for speed)
LOG_ALSO_PRINT = False    # echo logs to stdout as well

def _log(msg: object, label: str | None = None) -> None:
    # label=None will use write_log's default [INFO]
    write_log(
        msg, label=label, tz=LOG_TZ,
        autoflush=LOG_AUTOFUSH, also_print=LOG_ALSO_PRINT,
        path_log=app_dir()
    )


def Get():  # Get information of IP from SFC system
    _log(f"GET {linkAPIGet}")
    try:
        # res = requests.get(linkAPIGet, timeout=(timeout, timeout))
        res = _session.get(linkAPIGet, timeout=(timeout, timeout))
        raw = res.text
        _log(f"SFC GET raw: {raw}", label=debuglog)
        try:
            res_json = res.json()
        except Exception as e_json:
            _log(f"SFC GET json() failed: {e_json}", label=errorlog)
            return None

        status = res_json.get("Status")
        if status != "Pass":  # if Fail -> IP haven't config in SMO_API yet
            _log(f"SFC GET not Pass: {res_json}", label="[WARN]")
            return None

        _log(f"SFC GET Pass: {res_json}", label=infolog)
        return res_json
    except Exception as e:
        _log(f"SFC GET exception: {e}", label=errorlog)
        return None

def Post(lineName, groupName, sp, requestBody):  # Post data to SFC
    payload = {
        "LINE_NAME": f"{lineName}",
        "GROUP_NAME": f"{groupName}",
        "SP": f"{sp}",
        "DATA": f"{requestBody}",
    }
    _log(f"SFC POST {linkAPIPost} payload: {payload}", label=debuglog)
    try:
        # res = requests.post(linkAPIPost, json=payload, timeout=(timeout, timeout))
        res = _session.post(linkAPIPost, json=payload, timeout=(timeout, timeout))
        raw = res.text
        _log(f"SFC POST raw: {raw}", label=debuglog)
        try:
            js = res.json()
        except Exception as e_json:
            _log(f"SFC POST json() failed: {e_json}", label=errorlog)
            return None

        _log(f"SFC POST response: {js}", label=infolog)
        return js
    except Exception as e:
        _log(f"SFC POST exception: {e}", label=errorlog)
        return None

# Get specific Station
def sendDataAPI(requestBody):
    """Gửi chuỗi requestBody lên SFC theo cấu hình SMO và in kết quả ra stdout."""
    try:
        _log(f"bypass [ ] start. body='{requestBody}'", "DEBUG")

        resGet = Get()  # Get SMO config of IP in SMO_API SFC
        if resGet is None:
            msg = "FAIL|This IP haven't config in SFC yet!"
            print(msg)
            _log(msg, "ERROR")
            return None

        SMOConfig = resGet
        # get SMOConfig with GROUP_NAME=VI3
        dataSMO = next((item for item in SMOConfig["Data"] if item["GROUP_NAME"] == TEST_GROUP), None)
        if dataSMO is None:
            msg = "FAIL|This GROUP_NAME=VI3 haven't config in SFC yet!"
            print(msg)
            _log(msg, "ERROR")
            return None
        
        line_name = dataSMO["LINE_NAME"]
        group_name = dataSMO["GROUP_NAME"]
        sp = dataSMO["SP"]

        _log(f"SMO Config -> LINE='{line_name}', GROUP='{group_name}', SP='{sp}'", "DEBUG")
        _log(f"POST body: {requestBody}", "DEBUG")

        resPost = Post(line_name, group_name, sp, requestBody)
        dataPostRespon = resPost['Data']  # giữ nguyên cấu trúc gốc  :contentReference[oaicite:1]{index=1}

        dataCommand1 = dataPostRespon['COMMAND1']
        _log(f"COMMAND1 <- '{dataCommand1.strip()}'", "DEBUG")

        result = checkOutput(dataCommand1.strip())
        _log("bypass [ ] done.", "DEBUG")

        return result
    except Exception as e:
        msg = f"FAIL|{e}"
        print(msg)
        _log(f"bypass [ ] Exception in sendDataAPI: {e}", "ERROR")
        return None

def checkOutput(data):
    """Kiểm tra chuỗi phản hồi cuối cùng từ SFC."""
    pattern = r"^.+PASSED=1,PASS$"  # Exist PASSED=1,PASS at last string
    match = re.match(pattern, data)
    if match:
        out = f"Result=PASS|{data}"
        print(out)
        _log(out, "INFO")
    else:
        out = f"Result=FAIL|Return={data}"
        print(out)
        _log(out, "ERROR")

    return out

def getDataTestingFormatte(SN):
    parts = [
        f"SN={SN}",
        f"TEST_GROUP={TEST_GROUP}",
        f'SEQ_MD5="{SEQ_MD5}"',
        f",TESTER={TESTER}",
        ",PASSED=1",
    ]
    return ",".join(parts) if parts else None

def do_bypass_simple(SN):
    dataTesting = getDataTestingFormatte(SN)
    sendDataAPI(dataTesting)