from __future__ import annotations

import glob
import os
import platform
from typing import List, Tuple, Union

PortList = Union[List[str], List[Tuple[str, str, str]]]

def get_serial_ports(include_details: bool = False) -> PortList:
    """
    Returns:
      - if include_details=False: List[str] of port names (e.g., ["COM3"] or ["/dev/ttyUSB0"])
      - if include_details=True:  List[Tuple[port, description, hwid/realpath]]
    """
    system = platform.system()

    if system == "Windows":
        # Best practice: enumerate COM ports via pyserial
        try:
            from serial.tools import list_ports  # pip install pyserial
        except ImportError as e:
            raise RuntimeError(
                "Windows cần 'pyserial' để list COM chính xác. Cài: pip install pyserial"
            ) from e

        ports = list_ports.comports()
        if include_details:
            return [(p.device, p.description or "", p.hwid or "") for p in ports]
        return [p.device for p in ports]

    # Ubuntu / Linux (bao gồm WSL nếu nó report là Linux)
    ports = sorted(glob.glob("/dev/ttyUSB*"))
    if include_details:
        return [(p, "ttyUSB", os.path.realpath(p)) for p in ports]
    return ports