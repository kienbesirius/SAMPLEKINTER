import tkinter as tk
from src.gui import gui204_count_primes
from src.gui import gui279_perfect_squares


def main_gui():
	root = tk.Tk()  
	app = gui204_count_primes.LeetCode204_Gui(root)
	# app = gui279_perfect_squares.LeetCode279_Gui(root)
	root.mainloop()

if __name__ == "__main__":
	main_gui()
	
