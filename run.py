from src import linked_gui

def main():
    linked_gui.main_gui()

if __name__ == "__main__":
    import multiprocessing as mp
    mp.freeze_support()  # important on Windows
    main()