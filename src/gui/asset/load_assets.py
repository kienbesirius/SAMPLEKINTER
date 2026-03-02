from __future__ import annotations
import sys, os
import hashlib
from collections import deque
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
    "fixture_sensor_top_right_guide_240x240": RESOURCE_PATH / "fixture" / "fixture_sensor_top_right_guide_240x240.png",
    "fixture_sensor_top_left_guide_240x240": RESOURCE_PATH / "fixture" / "fixture_sensor_top_left_guide_240x240.png",
    "fixture_sensor_bottom_left_guide_240x240": RESOURCE_PATH / "fixture" / "fixture_sensor_bottom_left_guide_240x240.png",
    "fixture_sensor_bottom_right_guide_240x240": RESOURCE_PATH / "fixture" / "fixture_sensor_bottom_right_guide_240x240.png",
    "fixture_fail_to_check_240x240": RESOURCE_PATH / "fixture" / "fixture_fail_to_check_240x240.png",
    "fixture_pass_guide_240x240": RESOURCE_PATH / "fixture" / "fixture_pass_guide_240x240.png",
    "fixture_sensor_in_guide_240x240": RESOURCE_PATH / "fixture" / "fixture_sensor_in_guide_240x240.png",
    "fixture_close_guide_240x240": RESOURCE_PATH / "fixture" / "fixture_close_guide_240x240.png",
    "fixture_stop_guide_240x240": RESOURCE_PATH / "fixture" / "fixture_stop_guide_240x240.png",
    "fixture_reset_guide_240x240": RESOURCE_PATH / "fixture" / "fixture_reset_guide_240x240.png",
    "fixture_240x240": RESOURCE_PATH / "fixture" / "fixture_240x240.png",


    # Button no_label
    "fixture_button_no_label_normal_0.5": RESOURCE_PATH / "fixture" / "button_no_label_0_5.png",
    "fixture_button_no_label_hover_0.5": RESOURCE_PATH / "fixture" / "button_no_label_hover_0_5.png",
    "fixture_button_no_label_pressed_0.5": RESOURCE_PATH / "fixture" / "button_no_label_pressed_0_5.png",
    "fixture_button_no_label_disabled_0.5": RESOURCE_PATH / "fixture" / "button_no_label_disabled_0_5.png",

    "fixture_button_no_label_normal_0.75": RESOURCE_PATH / "fixture" / "button_no_label_0_75.png",
    "fixture_button_no_label_hover_0.75": RESOURCE_PATH / "fixture" / "button_no_label_hover_0_75.png",
    "fixture_button_no_label_pressed_0.75": RESOURCE_PATH / "fixture" / "button_no_label_pressed_0_75.png",
    "fixture_button_no_label_disabled_0.75": RESOURCE_PATH / "fixture" / "button_no_label_disabled_0_75.png",

    "fixture_button_no_label_normal": RESOURCE_PATH / "fixture" / "button_no_label.png",
    "fixture_button_no_label_hover": RESOURCE_PATH / "fixture" / "button_no_label_hover.png",
    "fixture_button_no_label_pressed": RESOURCE_PATH / "fixture" / "button_no_label_pressed.png",
    "fixture_button_no_label_disabled": RESOURCE_PATH / "fixture" / "button_no_label_disabled.png",


    # Button confirm
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

    # Button cancel
    "fixture_button_cancel_normal_0.5": RESOURCE_PATH / "fixture" / "button_cancel_0_5.png",
    "fixture_button_cancel_hover_0.5": RESOURCE_PATH / "fixture" / "button_cancel_hover_0_5.png",
    "fixture_button_cancel_pressed_0.5": RESOURCE_PATH / "fixture" / "button_cancel_pressed_0_5.png",
    "fixture_button_cancel_disabled_0.5": RESOURCE_PATH / "fixture" / "button_cancel_disabled_0_5.png",

    "fixture_button_cancel_normal_0.75": RESOURCE_PATH / "fixture" / "button_cancel_0_75.png",
    "fixture_button_cancel_hover_0.75": RESOURCE_PATH / "fixture" / "button_cancel_hover_0_75.png",
    "fixture_button_cancel_pressed_0.75": RESOURCE_PATH / "fixture" / "button_cancel_pressed_0_75.png",
    "fixture_button_cancel_disabled_0.75": RESOURCE_PATH / "fixture" / "button_cancel_disabled_0_75.png",

    "fixture_button_cancel_normal": RESOURCE_PATH / "fixture" / "button_cancel.png",    
    "fixture_button_cancel_hover": RESOURCE_PATH / "fixture" / "button_cancel_hover.png",    
    "fixture_button_cancel_pressed": RESOURCE_PATH / "fixture" / "button_cancel_pressed.png",    
    "fixture_button_cancel_disabled": RESOURCE_PATH / "fixture" / "button_cancel_disabled.png",    

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
    "fixture_slot_test_item_0.5": RESOURCE_PATH / "fixture" / "slot_test_item_0_5.png",
    "fixture_slot_test_idle_0.5": RESOURCE_PATH / "fixture" / "slot_test_0_5.png",
    "fixture_slot_test_fail_0.5": RESOURCE_PATH / "fixture" / "slot_test_fail_0_5.png",
    "fixture_slot_test_pass_0.5": RESOURCE_PATH / "fixture" / "slot_test_pass_0_5.png",
    "fixture_slot_test_testing_0.5": RESOURCE_PATH / "fixture" / "slot_test_stand_by_0_5.png",

    "fixture_slot_test_0.75": RESOURCE_PATH / "fixture" / "slot_test_0_75.png",
    "fixture_slot_test_item_0.75": RESOURCE_PATH / "fixture" / "slot_test_item_0_75.png",
    "fixture_slot_test_idle_0.75": RESOURCE_PATH / "fixture" / "slot_test_0_75.png",
    "fixture_slot_test_fail_0.75": RESOURCE_PATH / "fixture" / "slot_test_fail_0_75.png",
    "fixture_slot_test_pass_0.75": RESOURCE_PATH / "fixture" / "slot_test_pass_0_75.png",
    "fixture_slot_test_testing_0.75": RESOURCE_PATH / "fixture" / "slot_test_stand_by_0_75.png",

    "fixture_slot_test": RESOURCE_PATH / "fixture" / "slot_test.png",
    "fixture_slot_test_item": RESOURCE_PATH / "fixture" / "slot_test_item.png",
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
    "fixture_circle_dock_status_error_0.5": RESOURCE_PATH / "fixture" / "COM_STATUS_ERROR_0_5.png",

    # _0.75 _0_75
    "fixture_circle_dock_status_listening_0.75": RESOURCE_PATH / "fixture" / "COM_STATUS_LISTENING_0_75.png",
    "fixture_circle_dock_status_stand_by_0.75": RESOURCE_PATH / "fixture" / "COM_STATUS_STAND_BY_0_75.png",
    "fixture_circle_dock_status_not_found_0.75": RESOURCE_PATH / "fixture" / "COM_STATUS_NOT_FOUND_0_75.png",
    "fixture_circle_dock_status_error_0.75": RESOURCE_PATH / "fixture" / "COM_STATUS_ERROR_0_75.png",

    "fixture_circle_dock_status_listening": RESOURCE_PATH / "fixture" / "COM_STATUS_LISTENING.png",
    "fixture_circle_dock_status_stand_by": RESOURCE_PATH / "fixture" / "COM_STATUS_STAND_BY.png",
    "fixture_circle_dock_status_not_found": RESOURCE_PATH / "fixture" / "COM_STATUS_NOT_FOUND.png",
    "fixture_circle_dock_status_error": RESOURCE_PATH / "fixture" / "COM_STATUS_ERROR.png",

    # _0.5 _0_5
    "fixture_text_comx_0.5": RESOURCE_PATH / "fixture" / "TEXT_COMX_0_5.png",
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
    "fixture_text_comx_0.75": RESOURCE_PATH / "fixture" / "TEXT_COMX_0_75.png",
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
    
    "fixture_text_comx": RESOURCE_PATH / "fixture" / "TEXT_COMX.png",
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

    "guide_sensor_top_left": RESOURCE_PATH / "fixture" / "guide_sensor_top_left.png",
    "guide_sensor_top_right": RESOURCE_PATH / "fixture" / "guide_sensor_top_right.png",
    "guide_sensor_bottom_left": RESOURCE_PATH / "fixture" / "guide_sensor_bottom_left.png",
    "guide_sensor_bottom_right": RESOURCE_PATH / "fixture" / "guide_sensor_bottom_right.png",
    
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
    "bg_248x148": RESOURCE_PATH / "blank" / "bg_248x148.png", # 7 char
    "bg_480x148": RESOURCE_PATH / "blank" / "bg_480x148.png", # 7 char
    "bg_248x148_0.75": RESOURCE_PATH / "blank" / "bg_248x148.png", # 7 char
    "bg_480x148_0.75": RESOURCE_PATH / "blank" / "bg_480x148.png", # 7 char
    "bg_248x148_0.5": RESOURCE_PATH / "blank" / "bg_248x148.png", # 7 char
    "bg_480x148_0.5": RESOURCE_PATH / "blank" / "bg_480x148.png", # 7 char
    "text_wide_1_area": RESOURCE_PATH / "blank" / "text-wide-1-area.png", # 12 char (+5)
    "text_wide_2_area": RESOURCE_PATH / "blank" / "text-wide-2-area.png", # 17 char (+5)
    "text_wide_3_area": RESOURCE_PATH / "blank" / "text-wide-3-area.png", # 22 char (+5)
    "bypass_notice_title": RESOURCE_PATH / "blank" / "bypass_Notice_Title.png",
    "pass_title": RESOURCE_PATH / "blank" / "PASS.png",
    "fail_title": RESOURCE_PATH / "blank" / "FAIL.png",
    "standby_title": RESOURCE_PATH / "blank" / "STANDBY.png",



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


def _tp_img_key(station_name: str, img_filename: str) -> str:
    st = (station_name or "").strip()
    fn = (img_filename or "").strip()
    stem = Path(fn).stem  # bỏ .png
    return f"tp__{st}__{stem}".lower()

def _tp_img_path(test_plan_dir: Path, station_name: str, img_filename: str) -> Path:
    return (test_plan_dir / station_name / img_filename).resolve()

def preload_testplan_images(
    *,
    root: tk.Misc,
    assets: dict,
    test_plan_dir: Path,
    station_name: str,
    image_filenames: list[str],
    log: callable | None = None,
    batch_ms: int = 1,          # nhịp nhỏ để không đơ UI
    max_per_tick: int = 3,      # mỗi tick load vài ảnh

    # --- NEW (optional): nếu caller biết sẵn thì truyền để khỏi rglob ---
    station_dir: Path | None = None,       # folder chứa csv + images
    plan_csv_path: Path | None = None,     # path đến <Project>_<Station>.csv
    case_insensitive_lookup: bool = True,  # Linux hay lệch case tên file
    force_reload: bool = False,
    cv_img_w: int =0,
    cv_img_h: int =0,
) -> dict[str, str]:
    """
    Return mapping: original filename -> assets_key

    Logic resolve ảnh:
      1) Nếu station_dir được truyền -> dùng nó
      2) Nếu plan_csv_path được truyền -> dùng plan_csv_path.parent
      3) Fallback legacy: test_plan_dir/<station_name>/
      4) Layout mới: tìm <station_name>.csv trong test_plan_dir/** rồi lấy parent folder
    """
    from src.utils.resolve_fit_img import pad_to_16x9_landscape_no_scale

    test_plan_dir = Path(test_plan_dir).resolve()
    station_name = (station_name or "").strip()

    # unique + keep order
    seen = set()
    queue_files: list[str] = []
    for s in image_filenames:
        s = (s or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        queue_files.append(s)

    pending = deque(queue_files)
    mapping: dict[str, str] = {}

    # -------------------------
    # Resolve base folder
    # -------------------------
    def _resolve_station_folder() -> Path | None:
        # 1) caller provided exact folder
        if station_dir is not None:
            try:
                p = Path(station_dir).resolve()
                if p.is_dir():
                    return p
            except Exception:
                pass

        # 2) caller provided csv path
        if plan_csv_path is not None:
            try:
                p = Path(plan_csv_path).resolve()
                if p.is_file():
                    return p.parent
            except Exception:
                pass

        # 3) legacy layout: test_plan/<station_name>/
        if station_name:
            legacy = test_plan_dir / station_name
            if legacy.is_dir():
                return legacy

        # 4) new layout: test_plan/<Process>/<Project>/<Station>/<Project>_<Station>.csv
        #    => rglob station_name.csv rồi lấy parent
        if not station_name:
            return None

        # cache per (root, station) để khỏi rglob lặp
        cache = getattr(preload_testplan_images, "_station_dir_cache", None)
        if cache is None:
            cache = {}
            setattr(preload_testplan_images, "_station_dir_cache", cache)

        ck = (str(test_plan_dir), station_name.lower())
        if ck in cache:
            p = cache[ck]
            return p if isinstance(p, Path) and p.is_dir() else None

        cand: list[Path] = []
        try:
            # ưu tiên match strict theo <Project>/<Station>/ nếu parse được
            proj = stn = ""
            if "_" in station_name:
                proj, stn = station_name.split("_", 1)
                proj = proj.strip()
                stn = stn.strip()

            for csv_p in test_plan_dir.rglob(f"{station_name}.csv"):
                if not csv_p.is_file():
                    continue
                if proj and stn:
                    try:
                        if csv_p.parent.name.lower() == stn.lower() and csv_p.parent.parent.name.lower() == proj.lower():
                            cand.append(csv_p)
                            continue
                    except Exception:
                        pass
                # fallback: cứ nhận
                cand.append(csv_p)

            cand.sort(key=lambda p: str(p).lower())
        except Exception:
            cand = []

        if cand:
            folder = cand[0].parent
            cache[ck] = folder
            if log:
                try:
                    log(f"[img] resolved plan folder: {folder}")
                except Exception:
                    pass
            return folder

        cache[ck] = None
        return None

    base_dir = _resolve_station_folder()

    if log:
        try:
            log(f"[img] base_dir={base_dir if base_dir else '(none)'} | station={station_name}")
        except Exception:
            pass

    # -------------------------
    # Helpers
    # -------------------------
    def _safe_join_filename(base: Path, fn: str) -> Path | None:
        # chỉ cho filename, không cho path traversal
        if ("/" in fn) or ("\\" in fn):
            if log:
                log(f"[img] skip (not a filename): {fn!r}")
            return None
        return base / fn

    def _find_case_insensitive(base: Path, fn: str) -> Path | None:
        if not case_insensitive_lookup:
            return None
        try:
            low = fn.lower()
            for x in base.iterdir():
                if x.is_file() and x.name.lower() == low:
                    return x
        except Exception:
            pass
        return None

    # -------------------------
    # Batched loader
    # -------------------------
    def _tick():
        nonlocal pending
        n = 0
        while pending and n < max_per_tick:
            fn = pending.popleft()
            key = _tp_img_key(station_name, fn)   # giữ nguyên key scheme của bạn
            mapping[fn] = key

            # đã có rồi thì skip (cache)
            if key in assets and not force_reload:
                n += 1
                continue

            if base_dir is None:
                if log:
                    log(f"[img] missing base_dir -> skip: {fn}")
                n += 1
                continue

            p = _safe_join_filename(base_dir, fn)
            if p is None:
                n += 1
                continue

            if not p.is_file():
                # thử case-insensitive (Linux)
                alt = _find_case_insensitive(base_dir, fn)
                if alt is not None:
                    p = alt

            if not p.is_file():
                if log:
                    log(f"[img] missing: {p}")
                n += 1
                continue

            try:
                # assets[key] = tk.PhotoImage(file=str(p))
                raw = tk.PhotoImage(master=root, file=str(p))
                # padded = pad_to_16x9_landscape_no_scale(raw, master=root)

                # assets[key] = padded
                # # ✅ để _pick_scaled_key không pick nhầm ảnh cũ
                # assets[f"{key}_0.5"] = padded
                # assets[f"{key}_0.75"] = padded
                def _downsample_to_fit(src: tk.PhotoImage, box_w: int, box_h: int) -> tk.PhotoImage:
                    import math
                    sw, sh = int(src.width()), int(src.height())
                    k = max(1, math.ceil(max(sw / box_w, sh / box_h)))
                    return src.subsample(k, k) if k > 1 else src

                # def _pad_to_box(src: tk.PhotoImage, box_w: int, box_h: int, bg: str = "#471800") -> tk.PhotoImage:
                #     out = tk.PhotoImage(master=root, width=box_w, height=box_h)
                #     out.put(bg, to=(0, 0, box_w, box_h))
                #     sw, sh = int(src.width()), int(src.height())
                #     x0 = (box_w - sw) // 2
                #     y0 = (box_h - sh) // 2
                #     try:
                #         out.tk.call(out, "copy", src, "-to", x0, y0, "-compositingrule", "overlay")
                #     except tk.TclError:
                #         out.tk.call(out, "copy", src, "-to", x0, y0)
                #     return out

                def _make(box_w: int, box_h: int) -> tk.PhotoImage:
                    small = _downsample_to_fit(raw, box_w, box_h)
                    return small

                assets[key] = _make(cv_img_w, cv_img_h)
                assets[f"{key}_0.75"] = _make(cv_img_w, cv_img_h)
                assets[f"{key}_0.5"] = _make(cv_img_w, cv_img_h)
                if log:
                    log(f"[img] loaded: {fn} -> {key}")
            except Exception as e:
                if log:
                    log(f"[img] load failed: {p} ({e})")

            n += 1

        if pending:
            root.after(batch_ms, _tick)

    _tick()
    return mapping

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

import multiprocessing as mp

if mp.current_process().name == "MainProcess":
    _load_fonts()


def tk_load_image_resources(root: tk.Misc | None = None):
    imgs = {}
    for k, fname in ASSET_FILES.items():
        path = str(fname)
        if not Path(path).exists():
            raise FileNotFoundError(f"Không tìm thấy asset: {fname} (đã tìm ở ./assets và cùng thư mục script)")
        # imgs[k] = tk.PhotoImage(file=path)
        imgs[k] = tk.PhotoImage(master=root, file=path) if root else tk.PhotoImage(file=path)
    return imgs

def tk_get_loaded_fonts():
    fonts = {}
    for k, fpath in FONT_ASSET.items():
        font_name = Path(fpath).stem
        fonts[k] = font_name
    return fonts
