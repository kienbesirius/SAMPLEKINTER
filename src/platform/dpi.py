import os
import ctypes
# -----------------------------------------------------------------------------
# PHẦN 1: CẤU HÌNH HỆ THỐNG VÀ XỬ LÝ DPI/ICON (THE CRITICAL FIX)
# -----------------------------------------------------------------------------
def setup_windows_dpi_awareness():
    """
    Thiết lập môi trường Windows để khắc phục lỗi mờ icon và UI.
    Hàm này PHẢI được gọi trước khi tk.Tk() được khởi tạo.
    """
    if os.name == 'nt': # Chỉ chạy trên Windows
        # 1. Tách rời Process ID khỏi python.exe
        # Giúp Taskbar nhận diện đây là app riêng biệt, không phải script Python chung
        myappid = 'dear.sample.kinter.v1.0'
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f" Không thể thiết lập AppUserModelID: {e}")

        # 2. Bật High-DPI Awareness
        # Ngăn Windows tự động co giãn (stretch) cửa sổ gây mờ
        try:
            # Gọi shcore.dll (Windows 8.1/10/11)
            # 1 = PROCESS_SYSTEM_DPI_AWARE
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            # Fallback cho Windows 7/8 cũ
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
            
def setup_linux_dpi_awareness():
    """
    Thiết lập môi trường Linux để khắc phục lỗi mờ icon và UI.
    Hàm này PHẢI được gọi trước khi tk.Tk() được khởi tạo.
    """
    if os.name == 'posix':
        # Thiết lập biến môi trường để yêu cầu ứng dụng sử dụng DPI cao
        os.environ['GDK_SCALE'] = '1'  # Tỷ lệ giao diện
        os.environ['GDK_DPI_SCALE'] = '1'  # Tỷ lệ DPI  

def set_dpi_awareness():
    """
    Thiết lập môi trường hệ điều hành để khắc phục lỗi mờ icon và UI.
    Hàm này PHẢI được gọi trước khi tk.Tk() được khởi tạo.
    """
    if os.name == 'nt':
        setup_windows_dpi_awareness()
    elif os.name == 'posix':
        setup_linux_dpi_awareness()

set_dpi_awareness()