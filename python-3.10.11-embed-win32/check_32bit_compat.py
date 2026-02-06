# # check_32bit_compat.py
# # Quét site-packages để kiểm tra .pyd/.dll là x86 hay x64, có khớp với Python hiện tại không.

# from __future__ import annotations
# import os
# import sys
# import struct
# import site
# import subprocess
# from dataclasses import dataclass
# from typing import Optional, List, Tuple, Dict


# @dataclass
# class BinInfo:
#     path: str
#     arch: str          # "x86", "x64", "unknown", "not-pe"
#     reason: str        # message for debugging
#     is_match: Optional[bool]  # True/False/None


# def python_bits() -> int:
#     return struct.calcsize("P") * 8


# def try_import_pefile():
#     try:
#         import pefile  # type: ignore
#         return pefile
#     except Exception:
#         return None


# def arch_from_pe_manual(filepath: str) -> Tuple[str, str]:
#     """
#     Return (arch, reason)
#     arch: x86 / x64 / unknown / not-pe
#     """
#     try:
#         with open(filepath, "rb") as f:
#             mz = f.read(2)
#             if mz != b"MZ":
#                 return ("not-pe", "Missing MZ header")

#             f.seek(0x3C)
#             e_lfanew_bytes = f.read(4)
#             if len(e_lfanew_bytes) != 4:
#                 return ("unknown", "Cannot read e_lfanew")
#             e_lfanew = struct.unpack("<I", e_lfanew_bytes)[0]

#             f.seek(e_lfanew)
#             sig = f.read(4)
#             if sig != b"PE\x00\x00":
#                 return ("unknown", "Missing PE signature")

#             machine_bytes = f.read(2)
#             if len(machine_bytes) != 2:
#                 return ("unknown", "Cannot read Machine field")
#             machine = struct.unpack("<H", machine_bytes)[0]

#             # Common Machine values:
#             # 0x014c = IMAGE_FILE_MACHINE_I386 (x86)
#             # 0x8664 = IMAGE_FILE_MACHINE_AMD64 (x64)
#             if machine == 0x014C:
#                 return ("x86", "PE Machine=I386")
#             if machine == 0x8664:
#                 return ("x64", "PE Machine=AMD64")

#             return ("unknown", f"PE Machine=0x{machine:04x}")
#     except Exception as e:
#         return ("unknown", f"Error: {e}")


# def arch_from_pefile(pefile_mod, filepath: str) -> Tuple[str, str]:
#     try:
#         pe = pefile_mod.PE(filepath, fast_load=True)
#         machine = pe.FILE_HEADER.Machine
#         if machine == 0x014C:
#             return ("x86", "pefile Machine=I386")
#         if machine == 0x8664:
#             return ("x64", "pefile Machine=AMD64")
#         return ("unknown", f"pefile Machine=0x{machine:04x}")
#     except Exception as e:
#         return ("unknown", f"pefile error: {e}")


# def collect_site_packages() -> List[str]:
#     paths = []
#     # Prefer site.getsitepackages(); fallback to sys.path scan
#     try:
#         paths.extend(site.getsitepackages())
#     except Exception:
#         pass

#     # Ensure current interpreter's site-packages in sys.path are included
#     for p in sys.path:
#         if p and ("site-packages" in p.lower()) and os.path.isdir(p):
#             paths.append(p)

#     # De-dup while preserving order
#     seen = set()
#     out = []
#     for p in paths:
#         p = os.path.abspath(p)
#         if p not in seen:
#             seen.add(p)
#             out.append(p)
#     return out


# def scan_binaries(root: str, pefile_mod=None) -> List[BinInfo]:
#     pybits = python_bits()
#     expected = "x86" if pybits == 32 else "x64"

#     results: List[BinInfo] = []
#     for dirpath, _, filenames in os.walk(root):
#         for fn in filenames:
#             low = fn.lower()
#             if not (low.endswith(".pyd") or low.endswith(".dll")):
#                 continue
#             fp = os.path.join(dirpath, fn)

#             if pefile_mod:
#                 arch, reason = arch_from_pefile(pefile_mod, fp)
#             else:
#                 arch, reason = arch_from_pe_manual(fp)

#             if arch in ("x86", "x64"):
#                 is_match = (arch == expected)
#             else:
#                 is_match = None

#             results.append(BinInfo(path=fp, arch=arch, reason=reason, is_match=is_match))
#     return results


# def top_level_import_candidates(site_pkg: str) -> List[str]:
#     """
#     Lấy danh sách module/package top-level trong site-packages để thử import.
#     Bỏ qua dist-info, __pycache__, và các file không import trực tiếp.
#     """
#     items = []
#     try:
#         for name in os.listdir(site_pkg):
#             if name.endswith(".dist-info") or name.endswith(".egg-info"):
#                 continue
#             if name in ("__pycache__",):
#                 continue
#             if name.startswith("_distutils_hack"):
#                 continue

#             full = os.path.join(site_pkg, name)
#             if os.path.isdir(full):
#                 # folder package
#                 items.append(name)
#             elif name.endswith(".py"):
#                 # top-level module file
#                 items.append(os.path.splitext(name)[0])
#     except Exception:
#         pass

#     # De-dup
#     out = []
#     seen = set()
#     for x in items:
#         if x not in seen:
#             seen.add(x)
#             out.append(x)
#     return out


# def import_check_subprocess(modname: str) -> Tuple[bool, str]:
#     """
#     Dùng subprocess để import an toàn (tránh crash interpreter nếu DLL lỗi nặng).
#     """
#     code = (
#         "import importlib, sys\n"
#         f"m=importlib.import_module('{modname}')\n"
#         "print('OK')\n"
#     )
#     try:
#         p = subprocess.run(
#             [sys.executable, "-c", code],
#             capture_output=True,
#             text=True,
#             timeout=30,
#         )
#         if p.returncode == 0 and "OK" in (p.stdout or ""):
#             return True, ""
#         msg = (p.stderr or p.stdout or "").strip()
#         return False, msg[:800]
#     except Exception as e:
#         return False, str(e)


# def main():
#     pybits = python_bits()
#     expected = "x86" if pybits == 32 else "x64"
#     print(f"[Python] exe={sys.executable}")
#     print(f"[Python] bits={pybits} (expected binaries: {expected})")

#     pefile_mod = try_import_pefile()
#     print(f"[PE parser] {'pefile' if pefile_mod else 'manual'}")

#     sps = collect_site_packages()
#     if not sps:
#         print("No site-packages found in this interpreter.")
#         sys.exit(1)

#     print("\n[site-packages]")
#     for p in sps:
#         print(" -", p)

#     # 1) Scan binaries
#     all_bins: List[BinInfo] = []
#     for sp in sps:
#         print(f"\n[Scan] {sp}")
#         bins = scan_binaries(sp, pefile_mod=pefile_mod)
#         print(f"  Found {len(bins)} binary files (.pyd/.dll)")
#         all_bins.extend(bins)

#     mismatches = [b for b in all_bins if b.is_match is False]
#     unknowns = [b for b in all_bins if b.is_match is None]

#     print("\n===== SUMMARY (Binaries) =====")
#     print(f"Total binaries: {len(all_bins)}")
#     print(f"Mismatch (wrong arch): {len(mismatches)}")
#     print(f"Unknown/Not-PE: {len(unknowns)}")

#     if mismatches:
#         print("\n--- MISMATCH LIST (needs fixing) ---")
#         for b in mismatches:
#             print(f"[{b.arch}] {b.path}")

#     # 2) Optional: import checks
#     #    Bạn có thể tắt nếu không muốn import hàng loạt:
#     DO_IMPORT_CHECK = True

#     if DO_IMPORT_CHECK:
#         # Dùng site-packages đầu tiên làm nguồn candidates (thường là đúng)
#         primary_sp = sps[0]
#         cands = top_level_import_candidates(primary_sp)

#         print("\n===== IMPORT CHECK (top-level) =====")
#         print(f"Candidates from: {primary_sp}")
#         print(f"Total candidates: {len(cands)}")
#         fail = []

#         for m in cands:
#             ok, msg = import_check_subprocess(m)
#             if not ok:
#                 fail.append((m, msg))

#         print(f"Import failures: {len(fail)}")
#         if fail:
#             print("\n--- IMPORT FAILURES ---")
#             for m, msg in fail:
#                 print(f"* {m}: {msg.splitlines()[-1] if msg else 'unknown error'}")

#     print("\nDone.")


# if __name__ == "__main__":
#     main()

# check_embed_sitepackages.py
# Chỉ quét C:\...\python-3.10.11-embed-win32\Lib\site-packages
# Kiểm tra .pyd/.dll là x86 hay x64 và có khớp với Python hiện tại không.

from __future__ import annotations
import os
import sys
import struct
from dataclasses import dataclass
from typing import Optional, Tuple, List

try:
    import pefile  # type: ignore
except Exception:
    pefile = None


@dataclass
class BinInfo:
    path: str
    arch: str                 # x86 / x64 / unknown / not-pe
    is_match: Optional[bool]  # True/False/None
    note: str


def python_arch() -> Tuple[int, str]:
    bits = struct.calcsize("P") * 8
    return bits, ("x86" if bits == 32 else "x64")


def get_machine_arch(filepath: str) -> Tuple[str, str]:
    """
    Return (arch, note)
    arch: x86/x64/unknown/not-pe
    """
    # Prefer pefile if available
    if pefile is not None:
        try:
            pe = pefile.PE(filepath, fast_load=True)
            m = pe.FILE_HEADER.Machine
            if m == 0x014C:
                return "x86", "pefile Machine=I386"
            if m == 0x8664:
                return "x64", "pefile Machine=AMD64"
            return "unknown", f"pefile Machine=0x{m:04x}"
        except Exception as e:
            return "unknown", f"pefile error: {e}"

    # Manual PE parse fallback
    try:
        with open(filepath, "rb") as f:
            if f.read(2) != b"MZ":
                return "not-pe", "Missing MZ header"
            f.seek(0x3C)
            e_lfanew = int.from_bytes(f.read(4), "little", signed=False)
            f.seek(e_lfanew)
            if f.read(4) != b"PE\x00\x00":
                return "unknown", "Missing PE signature"
            machine = int.from_bytes(f.read(2), "little", signed=False)
            if machine == 0x014C:
                return "x86", "PE Machine=I386"
            if machine == 0x8664:
                return "x64", "PE Machine=AMD64"
            return "unknown", f"PE Machine=0x{machine:04x}"
    except Exception as e:
        return "unknown", f"Error: {e}"


def scan_folder(root: str) -> List[BinInfo]:
    bits, expected = python_arch()
    results: List[BinInfo] = []

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            low = fn.lower()
            if not (low.endswith(".pyd") or low.endswith(".dll")):
                continue

            fp = os.path.join(dirpath, fn)
            arch, note = get_machine_arch(fp)

            if arch in ("x86", "x64"):
                is_match = (arch == expected)
            else:
                is_match = None

            results.append(BinInfo(fp, arch, is_match, note))

    return results


def main():
    # Default: lấy site-packages đúng theo cấu trúc embed: ..\Lib\site-packages
    # Bạn có thể truyền path khác qua argv[1]
    if len(sys.argv) > 1:
        target = os.path.abspath(sys.argv[1])
    else:
        # Nếu chạy từ bất cứ đâu, target vẫn tính theo vị trí python.exe
        py_dir = os.path.dirname(os.path.abspath(sys.executable))
        target = os.path.join(py_dir, "Lib", "site-packages")
        target = os.path.abspath(target)

    bits, expected = python_arch()
    print(f"[Python] {sys.executable}")
    print(f"[Python] bits={bits} expected={expected}")
    print(f"[Target] {target}")
    print(f"[PE parser] {'pefile' if pefile is not None else 'manual'}")

    if not os.path.isdir(target):
        print("ERROR: target folder not found.")
        sys.exit(2)

    bins = scan_folder(target)
    mismatches = [b for b in bins if b.is_match is False]
    unknowns = [b for b in bins if b.is_match is None]

    print("\n===== SUMMARY =====")
    print(f"Binary files (.pyd/.dll): {len(bins)}")
    print(f"Mismatch (wrong arch):    {len(mismatches)}")
    print(f"Unknown/Not-PE:           {len(unknowns)}")

    if mismatches:
        print("\n--- MISMATCH LIST ---")
        for b in mismatches:
            print(f"[{b.arch}] {b.path}")

    # Exit code hữu ích cho CI/script:
    # 0 = OK (không mismatch)
    # 1 = có mismatch
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()

