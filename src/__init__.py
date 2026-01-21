# src.__init__.py
from __future__ import annotations

import sys
import os
import time
from pathlib import Path
from src.utils.resource_path import app_dir
from typing import Callable, Dict, List, Optional, Tuple, Union, Set

src = Path(__file__).resolve()
root = Path(__file__).resolve().parent.parent.parent 
while not src.name.endswith("src") and not src.name.startswith("src"):
    src = src.parent
    if(root.name == src.name):
        break

sys.path.insert(0, src)