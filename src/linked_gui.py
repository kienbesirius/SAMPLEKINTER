import tkinter as tk

from sympy import root
from src.gui import gui
from src.gui import gui204_count_primes
from src.gui import gui279_perfect_squares
from src.gui import gui_check_fixture
from src.gui import gui_bypass

def main_gui():
	APP_NAME = "BypassSampleKinterApp"
	root = tk.Tk(className=APP_NAME)  # <- quan trọng
	try:
		root.wm_class(APP_NAME, APP_NAME)
	except Exception:
		pass

	# app = gui204_count_primes.LeetCode204_Gui(root)
	# app = gui279_perfect_squares.LeetCode279_Gui(root)
	app = gui_check_fixture.AppGUI(root)
	# app = gui_bypass.AppGUI(root)
	# app = gui.AppGUI(root)
	root.mainloop()

if __name__ == "__main__":
	main_gui()
	
