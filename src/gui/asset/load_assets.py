from __future__ import annotations
import sys, os
import hashlib
import shutil
import subprocess
from pathlib import Path
import tkinter as tk

try:
    from src.utils.resource_path import RESOURCE_PATH
    from src.utils.resource_path import FONT_PATH
    from src.utils.resource_path import ICONS_PATH
    from src.utils.resource_path import IMAGES_PATH
    from src.utils.resource_path import ASSETS_PATH
except:
    # TÌM THƯ MỤC SRC
    src = Path(__file__).resolve()
    root = Path(__file__).resolve().parent.parent.parent 
    while not src.name.endswith("src") and not src.name.startswith("src"):
        SRC_PATH = src = src.parent
        if(root.name == src.name):
            break

    ASSETS_PATH = SRC_PATH / "assets"
    ICONS_PATH = ASSETS_PATH / "icons"
    IMAGES_PATH = ASSETS_PATH / "images"
    RESOURCE_PATH = ASSETS_PATH / "resources"
    FONT_PATH = ASSETS_PATH / "fonts"

ICON_ASSET = {
    "app_icon": ICONS_PATH / "treasure-svgrepo-com.ico",
    "check_fixture_icon": ICONS_PATH / "delphi-svgrepo-com.ico"
}

FONT_ASSET = {
    "regular": FONT_PATH / "Tektur-Reg.ttf",
    "medium": FONT_PATH / "Tektur-Med.ttf",
    "bold": FONT_PATH / "Tektur-Bold.ttf",
    "black": FONT_PATH / "Tektur-Black.ttf",
}

ASSET_FILES = {

    # Fixture design
    "fixture_button_confirm_normal_0.5": RESOURCE_PATH / "fixture" / "button_confirm_0_5.png",
    "fixture_button_confirm_hover_0.5": RESOURCE_PATH / "fixture" / "button_confirm_hover_0_5.png",
    "fixture_button_confirm_pressed_0.5": RESOURCE_PATH / "fixture" / "button_confirm_pressed_0_5.png",
    "fixture_button_confirm_disabled_0.5": RESOURCE_PATH / "fixture" / "button_confirm_disabled_0_5.png",

    "fixture_button_confirm_normal_0.75": RESOURCE_PATH / "fixture" / "button_confirm_0_75.png",
    "fixture_button_confirm_hover_0.75": RESOURCE_PATH / "fixture" / "button_confirm_hover_0_75.png",
    "fixture_button_confirm_pressed_0.75": RESOURCE_PATH / "fixture" / "button_confirm_pressed_0_75.png",
    "fixture_button_confirm_disabled_0.75": RESOURCE_PATH / "fixture" / "button_confirm_disabled_0_75.png",

    "fixture_button_confirm_normal": RESOURCE_PATH / "fixture" / "button_confirm.png",
    "fixture_button_confirm_hover": RESOURCE_PATH / "fixture" / "button_confirm_hover.png",
    "fixture_button_confirm_pressed": RESOURCE_PATH / "fixture" / "button_confirm_pressed.png",
    "fixture_button_confirm_disabled": RESOURCE_PATH / "fixture" / "button_confirm_disabled.png",

    # Arrow _0.5 _0_5
    "fixture_arrow_to_right_0.5": RESOURCE_PATH / "fixture" / "arrow_to_right_0_5.png",
    "fixture_arrow_to_left_0.5": RESOURCE_PATH / "fixture" / "arrow_to_left_0_5.png",
    "fixture_dock_check_0.5": RESOURCE_PATH / "fixture" / "DOCK_CHECK_0_5.png",
    
    # Arrow _0.75 _0_75
    "fixture_arrow_to_right_0.75": RESOURCE_PATH / "fixture" / "arrow_to_right_0_75.png",
    "fixture_arrow_to_left_0.75": RESOURCE_PATH / "fixture" / "arrow_to_left_0_75.png",
    "fixture_dock_check_0.75": RESOURCE_PATH / "fixture" / "DOCK_CHECK_0_75.png",

    "fixture_arrow_to_right": RESOURCE_PATH / "fixture" / "arrow_to_right.png",
    "fixture_arrow_to_left": RESOURCE_PATH / "fixture" / "arrow_to_left.png",
    "fixture_dock_check": RESOURCE_PATH / "fixture" / "DOCK_CHECK.png",
    
    "fixture_slot_test_0.5": RESOURCE_PATH / "fixture" / "slot_test_0_5.png",
    "fixture_slot_test_idle_0.5": RESOURCE_PATH / "fixture" / "slot_test_0_5.png",
    "fixture_slot_test_fail_0.5": RESOURCE_PATH / "fixture" / "slot_test_fail_0_5.png",
    "fixture_slot_test_pass_0.5": RESOURCE_PATH / "fixture" / "slot_test_pass_0_5.png",
    "fixture_slot_test_testing_0.5": RESOURCE_PATH / "fixture" / "slot_test_stand_by_0_5.png",

    "fixture_slot_test_0.75": RESOURCE_PATH / "fixture" / "slot_test_0_75.png",
    "fixture_slot_test_idle_0.75": RESOURCE_PATH / "fixture" / "slot_test_0_75.png",
    "fixture_slot_test_fail_0.75": RESOURCE_PATH / "fixture" / "slot_test_fail_0_75.png",
    "fixture_slot_test_pass_0.75": RESOURCE_PATH / "fixture" / "slot_test_pass_0_75.png",
    "fixture_slot_test_testing_0.75": RESOURCE_PATH / "fixture" / "slot_test_stand_by_0_75.png",

    "fixture_slot_test": RESOURCE_PATH / "fixture" / "slot_test.png",
    "fixture_slot_test_idle": RESOURCE_PATH / "fixture" / "slot_test.png",
    "fixture_slot_test_fail": RESOURCE_PATH / "fixture" / "slot_test_fail.png",
    "fixture_slot_test_pass": RESOURCE_PATH / "fixture" / "slot_test_pass.png",
    "fixture_slot_test_testing": RESOURCE_PATH / "fixture" / "slot_test_stand_by.png",
    
    "fixture_info_frame_bg_333": RESOURCE_PATH / "fixture" / "info_frame_bg_333.png",
    "fixture_info_frame_bg_337": RESOURCE_PATH / "fixture" / "info_frame_bg_337.png",
    "fixture_info_frame_bg_480": RESOURCE_PATH / "fixture" / "info_frame_bg_480.png",
    "fixture_info_frame_bg_640": RESOURCE_PATH / "fixture" / "info_frame_bg_640.png",

    "fixture_info_frame_bg_0.5": RESOURCE_PATH / "fixture" / "info_frame_bg_0_5.png",
    "fixture_info_frame_bg_0.75": RESOURCE_PATH / "fixture" / "info_frame_bg_0_75.png",
    "fixture_info_frame_bg": RESOURCE_PATH / "fixture" / "info_frame_bg.png",

    # _0.5 _0_5
    "fixture_circle_dock_status_listening_0.5": RESOURCE_PATH / "fixture" / "COM_STATUS_LISTENING_0_5.png",
    "fixture_circle_dock_status_stand_by_0.5": RESOURCE_PATH / "fixture" / "COM_STATUS_STAND_BY_0_5.png",
    "fixture_circle_dock_status_not_found_0.5": RESOURCE_PATH / "fixture" / "COM_STATUS_NOT_FOUND_0_5.png",

    # _0.75 _0_75
    "fixture_circle_dock_status_listening_0.75": RESOURCE_PATH / "fixture" / "COM_STATUS_LISTENING_0_75.png",
    "fixture_circle_dock_status_stand_by_0.75": RESOURCE_PATH / "fixture" / "COM_STATUS_STAND_BY_0_75.png",
    "fixture_circle_dock_status_not_found_0.75": RESOURCE_PATH / "fixture" / "COM_STATUS_NOT_FOUND_0_75.png",
    
    "fixture_circle_dock_status_listening": RESOURCE_PATH / "fixture" / "COM_STATUS_LISTENING.png",
    "fixture_circle_dock_status_stand_by": RESOURCE_PATH / "fixture" / "COM_STATUS_STAND_BY.png",
    "fixture_circle_dock_status_not_found": RESOURCE_PATH / "fixture" / "COM_STATUS_NOT_FOUND.png",

    # _0.5 _0_5
    "fixture_text_com999_0.5": RESOURCE_PATH / "fixture" / "TEXT_COMX_0_5.png",
    "fixture_text_com1_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM1_0_5.png",
    "fixture_text_com2_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM2_0_5.png",
    "fixture_text_com3_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM3_0_5.png",
    "fixture_text_com4_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM4_0_5.png",
    "fixture_text_com5_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM5_0_5.png",
    "fixture_text_com6_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM6_0_5.png",
    "fixture_text_com7_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM7_0_5.png",
    "fixture_text_com8_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM8_0_5.png",
    "fixture_text_com9_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM9_0_5.png",
    "fixture_text_com10_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM10_0_5.png",
    "fixture_text_com11_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM11_0_5.png",
    "fixture_text_com12_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM12_0_5.png", 
    "fixture_text_com13_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM13_0_5.png",
    "fixture_text_com14_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM14_0_5.png",
    "fixture_text_com15_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM15_0_5.png",
    "fixture_text_com16_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM16_0_5.png",
    "fixture_text_com17_0.5": RESOURCE_PATH / "fixture" / "TEXT_COM17_0_5.png",
    
    # _0.75 _0_75
    "fixture_text_com999_0.75": RESOURCE_PATH / "fixture" / "TEXT_COMX_0_75.png",
    "fixture_text_com1_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM1_0_75.png",
    "fixture_text_com2_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM2_0_75.png",
    "fixture_text_com3_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM3_0_75.png",
    "fixture_text_com4_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM4_0_75.png",
    "fixture_text_com5_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM5_0_75.png",
    "fixture_text_com6_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM6_0_75.png",
    "fixture_text_com7_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM7_0_75.png",
    "fixture_text_com8_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM8_0_75.png",
    "fixture_text_com9_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM9_0_75.png",
    "fixture_text_com10_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM10_0_75.png",
    "fixture_text_com11_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM11_0_75.png",
    "fixture_text_com12_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM12_0_75.png", 
    "fixture_text_com13_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM13_0_75.png",
    "fixture_text_com14_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM14_0_75.png",
    "fixture_text_com15_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM15_0_75.png",
    "fixture_text_com16_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM16_0_75.png",
    "fixture_text_com17_0.75": RESOURCE_PATH / "fixture" / "TEXT_COM17_0_75.png",

    "fixture_text_com999": RESOURCE_PATH / "fixture" / "TEXT_COMX.png",
    "fixture_text_com1": RESOURCE_PATH / "fixture" / "TEXT_COM1.png",
    "fixture_text_com2": RESOURCE_PATH / "fixture" / "TEXT_COM2.png",
    "fixture_text_com3": RESOURCE_PATH / "fixture" / "TEXT_COM3.png",
    "fixture_text_com4": RESOURCE_PATH / "fixture" / "TEXT_COM4.png",
    "fixture_text_com5": RESOURCE_PATH / "fixture" / "TEXT_COM5.png",
    "fixture_text_com6": RESOURCE_PATH / "fixture" / "TEXT_COM6.png",
    "fixture_text_com7": RESOURCE_PATH / "fixture" / "TEXT_COM7.png",
    "fixture_text_com8": RESOURCE_PATH / "fixture" / "TEXT_COM8.png",
    "fixture_text_com9": RESOURCE_PATH / "fixture" / "TEXT_COM9.png",
    "fixture_text_com10": RESOURCE_PATH / "fixture" / "TEXT_COM10.png",
    "fixture_text_com11": RESOURCE_PATH / "fixture" / "TEXT_COM11.png",
    "fixture_text_com12": RESOURCE_PATH / "fixture" / "TEXT_COM12.png", 
    "fixture_text_com13": RESOURCE_PATH / "fixture" / "TEXT_COM13.png",
    "fixture_text_com14": RESOURCE_PATH / "fixture" / "TEXT_COM14.png",
    "fixture_text_com15": RESOURCE_PATH / "fixture" / "TEXT_COM15.png",
    "fixture_text_com16": RESOURCE_PATH / "fixture" / "TEXT_COM16.png",
    "fixture_text_com17": RESOURCE_PATH / "fixture" / "TEXT_COM17.png",
    # Blank design
    "button_normal": RESOURCE_PATH / "blank" / "button-normal.png",
    "button_hover": RESOURCE_PATH / "blank" / "button-hover.png",
    "button_active": RESOURCE_PATH / "blank" / "button-active.png",
    "button_disabled": RESOURCE_PATH / "blank" / "button-disabled.png",
    
    "entry_normal": RESOURCE_PATH / "blank" / "entry-normal.png", 
    "entry_focused": RESOURCE_PATH / "blank" / "entry-focused.png",
    "entry_disabled": RESOURCE_PATH / "blank" / "entry-disabled.png", # 7 char

    "entry_wide_1_normal": RESOURCE_PATH / "blank" / "entry-wide-1-normal.png",
    "entry_wide_1_focused": RESOURCE_PATH / "blank" / "entry-wide-1-focused.png",
    "entry_wide_1_disabled": RESOURCE_PATH / "blank" / "entry-wide-1-disabled.png", # 12 char (+5)

    "entry_wide_2_normal": RESOURCE_PATH / "blank" / "entry-wide-2-normal.png",
    "entry_wide_2_focused": RESOURCE_PATH / "blank" / "entry-wide-2-focused.png",
    "entry_wide_2_disabled": RESOURCE_PATH / "blank" / "entry-wide-2-disabled.png", # 17 char (+5)

    "entry_wide_3_normal": RESOURCE_PATH / "blank" / "entry-wide-3-normal.png", 
    "entry_wide_3_focused": RESOURCE_PATH / "blank" / "entry-wide-3-focused.png",
    "entry_wide_3_disabled": RESOURCE_PATH / "blank" / "entry-wide-3-disabled.png", # 22 char (+5)

    "text_area": RESOURCE_PATH / "blank" / "text-area.png", # 7 char
    "text_wide_1_area": RESOURCE_PATH / "blank" / "text-wide-1-area.png", # 12 char (+5)
    "text_wide_2_area": RESOURCE_PATH / "blank" / "text-wide-2-area.png", # 17 char (+5)
    "text_wide_3_area": RESOURCE_PATH / "blank" / "text-wide-3-area.png", # 22 char (+5)

    # Specific designs
    "images_dimension": IMAGES_PATH / "dimension_constraints.png",
    "notice_title": RESOURCE_PATH / "gui204_count_primes" / "Notice_Title.png",
    "279_notice_title": RESOURCE_PATH / "gui279_perfect_squares" / "279_Notice_Title.png",
    "entry_field_normal": RESOURCE_PATH / "gui204_count_primes" / "entry-field-normal.png",
    "entry_field_disabled": RESOURCE_PATH / "gui204_count_primes" / "entry-field-disabled.png",
    "entry_field_focused": RESOURCE_PATH / "gui204_count_primes" / "entry-field-focused.png",
    "279_entry_field_normal": RESOURCE_PATH / "gui279_perfect_squares" / "279-entry-field-normal.png",
    "279_entry_field_disabled": RESOURCE_PATH / "gui279_perfect_squares" / "279-entry-field-disabled.png",
    "279_entry_field_focused": RESOURCE_PATH / "gui279_perfect_squares" / "279-entry-field-focused.png",
    "button_start_normal": RESOURCE_PATH / "gui204_count_primes" / "button-start-normal.png",
    "button_start_hover": RESOURCE_PATH / "gui204_count_primes" / "button-start-hover.png",
    "button_start_active": RESOURCE_PATH / "gui204_count_primes" / "button-start-active.png",
    "button_cancel_normal": RESOURCE_PATH / "gui204_count_primes" / "button-cancel-normal.png",
    "button_cancel_hover": RESOURCE_PATH / "gui204_count_primes" / "button-cancel-hover.png",
    "button_cancel_active": RESOURCE_PATH / "gui204_count_primes" / "button-cancel-active.png",
    "background_gui204_640x480": RESOURCE_PATH / "gui204_count_primes" / "background-gui204_count_primes.png",
    "background_gui279_640x480": RESOURCE_PATH / "gui279_perfect_squares" / "background-gui279_perfect_squares.png",
    "result_field": RESOURCE_PATH / "gui204_count_primes" / "result-field.png",
    "279_result_field": RESOURCE_PATH / "gui279_perfect_squares" / "279-result-field.png",
}

def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _collect_font_files() -> list[Path]:
    font_files: list[Path] = []
    for _, p in FONT_ASSET.items():
        fp = Path(p)
        if fp.exists():
            font_files.append(fp.resolve())
    return font_files

def _load_fonts_windows(font_files: list[Path]) -> None:
    import ctypes
    try:
        gdi32 = ctypes.windll.gdi32
        FR_PRIVATE = 0x10
        FR_NOT_ENUM = 0x20
        flags = FR_PRIVATE | FR_NOT_ENUM

        num_added = 0
        for fp in font_files:
            try:
                num_added += gdi32.AddFontResourceExW(ctypes.c_wchar_p(str(fp)), flags, 0)
            except Exception:
                try:
                    buf = ctypes.create_unicode_buffer(str(fp))
                    num_added += gdi32.AddFontResourceExW(ctypes.byref(buf), flags, 0)
                except Exception:
                    pass

        if num_added > 0:
            print(f"Đã nạp thành công {num_added} font từ FONT_ASSET vào GDI.")
    except Exception as e:
        print(f"Ngoại lệ khi nạp font Windows: {e}")

def _load_fonts_linux_user(font_files: list[Path], app_subdir: str = "myapp_fonts") -> bool:
    """
    Cài font cho user (không sudo) để Tkinter thấy được qua fontconfig.
    - Copy vào: ~/.local/share/fonts/<app_subdir> (hoặc $XDG_DATA_HOME/fonts/<app_subdir>)
    - Chạy: fc-cache -f <dir>
    Trả về True nếu đã copy và/hoặc fc-cache OK.
    """
    if not font_files:
        return False

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data_home).expanduser() if xdg_data_home else (Path.home() / ".local" / "share")
    dst_dir = (base / "fonts" / app_subdir).expanduser()
    dst_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for src in font_files:
        dst = dst_dir / src.name
        try:
            if (not dst.exists()) or (_sha256(dst) != _sha256(src)):
                shutil.copy2(src, dst)
                copied += 1
        except Exception as e:
            print(f"[fonts] Copy fail: {src} -> {dst}: {e}")

    # fc-cache per-user, không cần sudo
    fc_cache = shutil.which("fc-cache")
    if not fc_cache:
        print("[fonts] Không thấy fc-cache. Cài gói fontconfig để tự rebuild cache.")
        # vẫn return True nếu copy được (để user restart / OS tự scan)
        return copied > 0

    try:
        # chỉ cache thư mục mình vừa copy để nhanh
        r = subprocess.run(
            [fc_cache, "-f", str(dst_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if r.returncode == 0:
            if copied > 0:
                print(f"[fonts] Đã nạp {copied} font vào {dst_dir} và rebuild cache OK.")
            return True
        else:
            print("[fonts] fc-cache lỗi:\n", r.stderr.strip() or r.stdout.strip())
            return copied > 0
    except Exception as e:
        print(f"[fonts] Ngoại lệ khi chạy fc-cache: {e}")
        return copied > 0

def _load_fonts():
    font_files = _collect_font_files()
    if not font_files:
        return

    if sys.platform.startswith("win"):
        _load_fonts_windows(font_files)
    elif sys.platform.startswith("linux"):
        # đổi app_subdir theo tên project của bạn cho gọn
        _load_fonts_linux_user(font_files, app_subdir="tektur_fonts")
    else:
        # macOS hoặc OS khác: để trống hoặc bạn có thể bổ sung sau
        pass

_load_fonts()

def tk_load_image_resources():
    imgs = {}
    for k, fname in ASSET_FILES.items():
        path = str(fname)
        if not Path(path).exists():
            raise FileNotFoundError(f"Không tìm thấy asset: {fname} (đã tìm ở ./assets và cùng thư mục script)")
        imgs[k] = tk.PhotoImage(file=path)
    return imgs

def tk_get_loaded_fonts():
    fonts = {}
    for k, fpath in FONT_ASSET.items():
        font_name = Path(fpath).stem
        fonts[k] = font_name
    return fonts
