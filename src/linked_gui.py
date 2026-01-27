import tkinter as tk
from src.gui import gui
from src.gui import gui204_count_primes
from src.gui import gui279_perfect_squares
from src.gui import gui_check_fixture


def main_gui():
	root = tk.Tk()  
	# app = gui204_count_primes.LeetCode204_Gui(root)
	# app = gui279_perfect_squares.LeetCode279_Gui(root)
	app = gui_check_fixture.AppGUI(root)
	# app = gui.AppGUI(root)
	root.mainloop()

if __name__ == "__main__":
	main_gui()
	
