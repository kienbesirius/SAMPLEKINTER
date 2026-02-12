from __future__ import annotations

"""
Xác định fixture qua Ethernet (TCP):
- thử connect tới từng host trong list (và port)
- gửi probe_cmd (giống như đã làm với COM)
- đọc response (line-based) và match expect_regex

Return: "TCP://<ip>:<port>" hoặc None

Config.ini (không bắt buộc):

[FIXTURE_ETHERNET]
hosts = 192.168.1.100, 192.168.1.101
port = 5000
timeout = 1.2
ending_line = CRLF
probe_cmd = ?
expect_regex = FIXTURE|OK
"""

import configparser
import re
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence, Tuple


_ENDING_MAP = {"CRLF": "\r\n", "LF": "\n", "CR": "\r", "NONE": ""}
_TCP_ENDPOINT_RE = re.compile(r"(?i)^(?:tcp|eth)://([^/:]+)(?::(\d+))?$")


@dataclass(frozen=True)
class EthernetProbeCfg:
    hosts: Tuple[str, ...]
    port: int
    timeout: float
    ending: str
    probe_cmd: str
    expect_regex: str


def parse_tcp_endpoint(s: str) -> Optional[Tuple[str, int]]:
    m = _TCP_ENDPOINT_RE.match((s or "").strip())
    if not m:
        return None
    host = m.group(1)
    port = int(m.group(2) or 0)
    return host, port


def _load_cfg(cfg_path: Path) -> Optional[EthernetProbeCfg]:
    cp = configparser.ConfigParser()
    cp.read(cfg_path, encoding="utf-8")
    if not cp.has_section("FIXTURE_ETHERNET"):
        return None

    sec = cp["FIXTURE_ETHERNET"]
    hosts_raw = (sec.get("hosts") or sec.get("host") or "").strip()
    if not hosts_raw:
        return None

    hosts = tuple([x.strip() for x in hosts_raw.split(",") if x.strip()])
    port = int(sec.get("port", "0"))
    timeout = float(sec.get("timeout", "1.2"))
    ending_key = (sec.get("ending_line", "CRLF") or "CRLF").strip().upper()
    ending = _ENDING_MAP.get(ending_key, "\r\n")
    probe_cmd = (sec.get("probe_cmd", "?") or "").strip()
    expect_regex = (sec.get("expect_regex", "") or "").strip()

    if not hosts or port <= 0:
        return None

    return EthernetProbeCfg(hosts, port, timeout, ending, probe_cmd, expect_regex)


def _recv_lines(sock: socket.socket, *, timeout: float) -> list[str]:
    sock.setblocking(False)
    t0 = time.monotonic()
    last_data = 0.0
    buf = bytearray()
    lines: list[str] = []
    idle_after = 0.25

    while True:
        now = time.monotonic()
        if now - t0 >= timeout:
            break
        if last_data and (now - last_data) >= idle_after:
            break

        try:
            chunk = sock.recv(4096)
        except BlockingIOError:
            time.sleep(0.01)
            continue
        except Exception:
            break

        if not chunk:
            break

        last_data = now
        buf += chunk

        # normalize CRLF/CR -> LF để split ổn định
        if b"\r" in buf:
            buf = bytearray(bytes(buf).replace(b"\r\n", b"\n").replace(b"\r", b"\n"))

        while b"\n" in buf:
            raw, _, rest = buf.partition(b"\n")
            buf = bytearray(rest)
            s = raw.decode("utf-8", errors="replace").strip()
            if s:
                lines.append(s)

    # flush tail (trường hợp không có '\n')
    tail = bytes(buf).strip()
    if tail:
        s = tail.decode("utf-8", errors="replace").strip()
        if s:
            lines.append(s)

    return lines


def probe_fixture_tcp(
    host: str,
    port: int,
    *,
    probe_cmd: str,
    ending: str,
    timeout: float,
    expect_regex: str = "",
) -> tuple[bool, list[str]]:
    expect = re.compile(expect_regex) if expect_regex else None
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            payload = (probe_cmd.rstrip("\r\n") + ending).encode("utf-8", errors="replace")
            s.sendall(payload)

            lines = _recv_lines(s, timeout=timeout)
            if not lines:
                return False, []

            if expect is None:
                return True, lines

            return any(expect.search(ln) for ln in lines), lines
    except Exception:
        return False, []


def get_fixture_ethernet(
    *,
    cfg_path: Optional[Path] = None,
    hosts: Optional[Sequence[str]] = None,
    port: int = 0,
    timeout: float = 1.2,
    ending: str = "\r\n",
    probe_cmd: str = "?",
    expect_regex: str = "",
    endpoint_hint: str = "",
    emit: Callable[[str], None] = print,
    progress_cb: Optional[Callable[[dict], None]] = None,
) -> Optional[str]:
    if cfg_path is not None and (hosts is None or port <= 0):
        cfg = _load_cfg(cfg_path)
        if cfg:
            hosts = list(hosts or cfg.hosts)
            port = port or cfg.port
            timeout = cfg.timeout
            ending = cfg.ending
            probe_cmd = cfg.probe_cmd
            expect_regex = cfg.expect_regex

    if not hosts or port <= 0:
        return None

    cand: list[tuple[str, int]] = []

    hint = parse_tcp_endpoint(endpoint_hint)
    if hint:
        h, p = hint
        cand.append((h, p or port))

    for h in hosts:
        h = (h or "").strip()
        if not h:
            continue
        if ":" in h and h.count(":") == 1:
            ip, p = h.split(":", 1)
            try:
                cand.append((ip.strip(), int(p.strip())))
                continue
            except Exception:
                pass
        cand.append((h, int(port)))

    seen = set()
    uniq = []
    for h, p in cand:
        if (h, p) not in seen:
            seen.add((h, p))
            uniq.append((h, p))

    for (h, p) in uniq:
        if progress_cb:
            progress_cb({"message": f"Checking ethernet {h}:{p}...", "port": f"{h}:{p}"})
        emit(f"[eth] probing {h}:{p}")

        ok, _lines = probe_fixture_tcp(
            h, p,
            probe_cmd=probe_cmd,
            ending=ending,
            timeout=timeout,
            expect_regex=expect_regex,
        )

        if ok:
            ep = f"TCP://{h}:{p}"
            emit(f"[eth] FOUND fixture at {ep}")
            if progress_cb:
                progress_cb({"message": f"Found ethernet: {ep}", "port": ep, "baudrate": 0, "ending_line": ending})
            return ep

    return None
