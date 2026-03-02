import tkinter as tk
from pathlib import Path
from typing import Tuple, Optional


def _ceil_div(a: int, b: int) -> int:
    return (a + b - 1) // b


def pad_to_16x9_landscape_no_scale(
    src: tk.PhotoImage,
    *,
    master: tk.Misc | None = None,
    bg: str = "#471800",
) -> tk.PhotoImage:
    """
    Tạo ảnh 16:9 landscape KHÔNG scale/crop:
      - Khung output tỷ lệ 16:9
      - Output đủ lớn để chứa src nguyên vẹn
      - Dán src vào giữa, phần còn lại fill bg
    """
    w = int(src.width())
    h = int(src.height())
    if w <= 0 or h <= 0:
        raise ValueError("src PhotoImage has invalid size")

    # Chọn "gốc" theo hướng nào ít phải nới hơn, nhưng luôn đảm bảo chứa ảnh
    # Nếu ảnh đã "wide" hơn hoặc bằng 16:9 => lấy width làm gốc, tăng height
    # Ngược lại => lấy height làm gốc, tăng width
    if w * 9 >= h * 16:
        out_w = w
        out_h = _ceil_div(out_w * 9, 16)
    else:
        out_h = h
        out_w = _ceil_div(out_h * 16, 9)

    # Tạo nền + fill màu
    # out = tk.PhotoImage(width=out_w, height=out_h)
    out = tk.PhotoImage(master=master, width=out_w, height=out_h)
    out.put(bg, to=(0, 0, out_w, out_h))

    # Tính tọa độ dán ở giữa
    x0 = (out_w - w) // 2
    y0 = (out_h - h) // 2

    # Dán ảnh gốc lên nền (overlay để giữ alpha nếu PNG có trong suốt)
    try:
        out.tk.call(out, "copy", src, "-to", x0, y0, "-compositingrule", "overlay")
    except tk.TclError:
        out.tk.call(out, "copy", src, "-to", x0, y0)

    return out


def save_photoimage_png(img: tk.PhotoImage, out_path: str | Path) -> str:
    """
    Lưu PhotoImage ra PNG để kiểm tra (Tk 8.6+ thường hỗ trợ PNG).
    """
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix.lower() != ".png":
        p = p.with_suffix(".png")
    img.write(str(p), format="png")
    return str(p)


# ===== Demo chạy thử không cần GUI =====
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # không mở cửa sổ

    raw = tk.PhotoImage(file="/home/te/SampleKinter/test_plan/FATP/Hapuka/AFT/Hapuka_AFT_Force_Stop.png")
    out = pad_to_16x9_landscape_no_scale(raw, bg="#471800")
    saved = save_photoimage_png(out, "out_16x9.png")
    print("Saved:", saved)

    # giữ reference nếu bạn chạy lâu (tránh GC trong vài trường hợp)
    root._keep = (raw, out)

    root.destroy()