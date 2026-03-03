#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

# 5 hậu tố cố định (giữ nguyên như bạn yêu cầu)
FIXED_PREFIXES = [
    "Force_Stop",
    "Sensor_bottom_left",
    "Sensor_bottom_right",
    "Sensor_top_left",
    "Sensor_top_right",
]

# PNG 1x1 trong suốt (fallback khi không có template)
TRANSPARENT_1X1_PNG = bytes.fromhex(
    "89504E470D0A1A0A0000000D4948445200000001000000010806000000"
    "1F15C4890000000A49444154789C6360000002000100"
    "05FE02FEA24D5D7A0000000049454E44AE426082"
)

def safe_name(s: str) -> str:
    """Giữ nguyên tên thư mục, chỉ strip khoảng trắng 2 đầu."""
    return (s or "").strip()

def default_template_map() -> dict[str, Path]:
    """
    Map prefix -> template path.
    Bạn có thể đổi sang template trong repo của bạn nếu muốn.
    """
    base = Path("/home/te/SampleKinter/test_plan/FATP/Hapuka/AFT")
    return {
        "Force_Stop": base / "Hapuka_AFT_Force_Stop.png",
        "Sensor_bottom_left": base / "Hapuka_AFT_Sensor_bottom_left.png",
        "Sensor_bottom_right": base / "Hapuka_AFT_Sensor_bottom_right.png",
        "Sensor_top_left": base / "Hapuka_AFT_Sensor_top_left.png",
        "Sensor_top_right": base / "Hapuka_AFT_Sensor_top_right.png",
    }

def write_dummy_png(dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(TRANSPARENT_1X1_PNG)

def ensure_images_in_station_dir(
    station_dir: Path,
    project_name: str,
    station_name: str,
    templates: dict[str, Path],
    *,
    overwrite: bool,
    dry_run: bool,
) -> int:
    made = 0
    project_name = safe_name(project_name)
    station_name = safe_name(station_name)

    for prefix in FIXED_PREFIXES:
        out_name = f"{project_name}_{station_name}_{prefix}.png"
        out_path = station_dir / out_name

        if out_path.exists() and not overwrite:
            continue

        tpl = templates.get(prefix)
        if dry_run:
            print(f"[DRY] {out_path}")
            made += 1
            continue

        if tpl and tpl.is_file():
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tpl, out_path)
        else:
            # fallback: tạo ảnh trong suốt 1x1
            write_dummy_png(out_path)

        made += 1

    return made

def iter_station_dirs(test_plan_root: Path, processes: list[str] | None) -> list[tuple[Path, str, str]]:
    """
    Return list of (station_dir, project_name, station_name)
    theo cấu trúc: root/PROCESS/Project/Station
    """
    out: list[tuple[Path, str, str]] = []

    if processes:
        proc_dirs = [test_plan_root / p for p in processes]
    else:
        # nếu không chỉ định, tự lấy tất cả thư mục con (FATP, PCBA, ...)
        proc_dirs = [p for p in test_plan_root.iterdir() if p.is_dir()]

    for proc in proc_dirs:
        if not proc.is_dir():
            continue
        for project_dir in proc.iterdir():
            if not project_dir.is_dir():
                continue
            project_name = project_dir.name
            for station_dir in project_dir.iterdir():
                if not station_dir.is_dir():
                    continue
                station_name = station_dir.name
                out.append((station_dir, project_name, station_name))

    return out

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Create 5 dummy pngs in each station folder under test_plan/<PROCESS>/<Project>/<Station>/"
    )
    ap.add_argument(
        "test_plan_root",
        help="Path to test_plan (vd: /home/te/SampleKinter/test_plan)",
    )
    ap.add_argument(
        "--process",
        action="append",
        default=[],
        help="Chỉ chạy trong process này (vd: --process FATP --process PCBA). Không truyền thì quét hết.",
    )
    ap.add_argument(
        "--overwrite",
        action="store_true",
        help="Ghi đè nếu file đã tồn tại.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ in ra những file sẽ tạo, không ghi gì.",
    )
    ap.add_argument(
        "--template-dir",
        default="",
        help="(Optional) thư mục chứa 5 template PNG. Tên file phải đúng: "
             "Hapuka_AFT_Force_Stop.png, Hapuka_AFT_Sensor_bottom_left.png, ...",
    )
    args = ap.parse_args()

    root = Path(args.test_plan_root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    # templates
    templates = default_template_map()
    if args.template_dir:
        td = Path(args.template_dir).expanduser().resolve()
        templates = {
            "Force_Stop": td / "Hapuka_AFT_Force_Stop.png",
            "Sensor_bottom_left": td / "Hapuka_AFT_Sensor_bottom_left.png",
            "Sensor_bottom_right": td / "Hapuka_AFT_Sensor_bottom_right.png",
            "Sensor_top_left": td / "Hapuka_AFT_Sensor_top_left.png",
            "Sensor_top_right": td / "Hapuka_AFT_Sensor_top_right.png",
        }

    processes = args.process if args.process else None
    stations = iter_station_dirs(root, processes)

    total_dirs = 0
    total_files = 0

    for station_dir, project_name, station_name in stations:
        total_dirs += 1
        n = ensure_images_in_station_dir(
            station_dir,
            project_name,
            station_name,
            templates,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
        total_files += n

    print(f"Done. station_dirs={total_dirs}, files_created_or_overwritten={total_files}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())