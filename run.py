import sys
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from src import linked_gui

def main():
    linked_gui.main_gui()

if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()  # important on Windows
    main()