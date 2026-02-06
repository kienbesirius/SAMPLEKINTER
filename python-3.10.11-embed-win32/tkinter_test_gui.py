import os
import sys
import time
import threading
import queue
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from typing import Optional

W, H = 640, 480


# ----------------------------
# Helpers: DPI, Topmost, Icon
# ----------------------------
def set_dpi_awareness_windows():
    """Try to enable DPI awareness on Windows to avoid blurry UI."""
    if sys.platform != "win32":
        return
    try:
        import ctypes  # noqa

        # Per-monitor DPI aware (Win 8.1+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes  # noqa

            # System DPI aware (older)
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def topmost_window(root: tk.Tk):
    try:
        root.attributes("-topmost", True)
    except Exception:
        try:
            root.wm_attributes("-topmost", 1)
        except Exception:
            pass


def set_app_icon(root: tk.Tk, icon_path: Optional[Path] = None):
    """Set .ico icon if available."""
    if icon_path is None:
        icon_path = Path(__file__).with_name("treasure-svgrepo-com.ico")
    if not icon_path.exists():
        return
    try:
        root.iconbitmap(default=str(icon_path))
    except Exception as e:
        print(f"Không thể đặt icon ứng dụng: {e}")


def set_default_font(font: tkfont.Font):
    tkfont.nametofont("TkDefaultFont").configure(
        family=font.actual("family"),
        size=font.actual("size"),
        weight=font.actual("weight"),
        slant=font.actual("slant"),
    )


# ----------------------------
# Background task runner
# ----------------------------
class BackgroundRunner:
    """Run long tasks on a thread; post messages back to GUI safely."""
    def __init__(self, out_queue: "queue.Queue[str]"):
        self.out_queue = out_queue
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start_demo_task(self, seconds: int = 5):
        if self.is_running():
            self.out_queue.put("[WARN] Task is already running.")
            return
        self._stop.clear()

        def worker():
            self.out_queue.put("[TASK] Started background task")
            for i in range(seconds):
                if self._stop.is_set():
                    self.out_queue.put("[TASK] Stopped by user.")
                    return
                self.out_queue.put(f"[TASK] Tick {i+1}/{seconds}")
                time.sleep(1)
            self.out_queue.put("[TASK] Done ✅")

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def stop(self):
        if self.is_running():
            self._stop.set()
        else:
            self.out_queue.put("[INFO] No running task.")


# ----------------------------
# Main GUI
# ----------------------------
class AppGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Tkinter Embed Test (1-file)")
        self.root.geometry(f"{W}x{H}")
        self.root.resizable(False, False)

        # Font
        self.app_font = tkfont.Font(family="Segoe UI", size=10)
        set_default_font(self.app_font)

        # Window behaviors
        topmost_window(self.root)
        set_app_icon(self.root)

        # Canvas
        self.canvas = tk.Canvas(self.root, width=W, height=H, bg="white", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Message queue from background thread
        self.msg_queue: "queue.Queue[str]" = queue.Queue()
        self.runner = BackgroundRunner(self.msg_queue)

        # Draw UI elements on canvas
        self._draw_header()
        self._draw_controls()
        self._draw_log_area()

        # Start polling queue
        self._poll_queue()

        # Close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Initial log
        self.log("[INFO] GUI started.")
        self.log(f"[INFO] Python: {sys.version.split()[0]} | exe={sys.executable}")
        self.log(f"[INFO] Platform: {sys.platform} | bits={8 * (8 if sys.maxsize > 2**32 else 4)}")

    def _draw_header(self):
        self.canvas.create_rectangle(0, 0, W, 55, fill="#f2f2f2", outline="")
        self.canvas.create_text(15, 18, anchor="w", text="Tkinter Test GUI", font=("Segoe UI", 14, "bold"))
        self.canvas.create_text(15, 40, anchor="w", text="1 file • Canvas UI • Background Thread • Log", font=("Segoe UI", 9))

    def _draw_controls(self):
        y = 70

        # Entry label
        self.canvas.create_text(15, y, anchor="w", text="Input:", font=("Segoe UI", 10, "bold"))

        # Entry widget placed onto canvas
        self.entry = tk.Entry(self.root, width=40)
        self.entry.insert(0, "Hello Tkinter!")
        self.canvas.create_window(70, y, anchor="w", window=self.entry, height=24)

        # Buttons
        self.btn_echo = tk.Button(self.root, text="Echo", width=10, command=self.on_echo)
        self.canvas.create_window(400, y, anchor="w", window=self.btn_echo, height=26)

        self.btn_run = tk.Button(self.root, text="Run Task", width=10, command=self.on_run_task)
        self.canvas.create_window(485, y, anchor="w", window=self.btn_run, height=26)

        self.btn_stop = tk.Button(self.root, text="Stop", width=8, command=self.on_stop_task)
        self.canvas.create_window(570, y, anchor="w", window=self.btn_stop, height=26)

        # Divider
        self.canvas.create_line(0, 105, W, 105, fill="#dddddd")

    def _draw_log_area(self):
        # Label
        self.canvas.create_text(15, 120, anchor="w", text="Log:", font=("Segoe UI", 10, "bold"))

        # Text widget for logs
        self.log_text = tk.Text(self.root, width=80, height=18, wrap="word")
        self.log_text.configure(state="disabled")
        self.canvas.create_window(15, 140, anchor="nw", window=self.log_text, width=W - 30, height=H - 160)

        # Scrollbar
        self.scroll = tk.Scrollbar(self.root, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=self.scroll.set)
        self.canvas.create_window(W - 15, 140, anchor="ne", window=self.scroll, height=H - 160)

    # ----------------------------
    # Actions
    # ----------------------------
    def log(self, msg: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def on_echo(self):
        text = self.entry.get().strip()
        self.log(f"[ECHO] {text if text else '(empty)'}")

    def on_run_task(self):
        self.runner.start_demo_task(seconds=8)

    def on_stop_task(self):
        self.runner.stop()

    def _poll_queue(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self.log(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def on_close(self):
        try:
            self.runner.stop()
        except Exception:
            pass
        self.root.destroy()


def main():
    set_dpi_awareness_windows()
    root = tk.Tk()
    AppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

# .\python.exe -c "import tkinter as tk; r=tk.Tk(); r.title('tk ok'); r.after(1000, r.destroy); r.mainloop(); print('done')"
