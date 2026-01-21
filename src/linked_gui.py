import tkinter as tk
from src.gui import gui204_count_primes


def main_gui():
	root = tk.Tk()  
	app = gui204_count_primes.LeetCode204_Gui(root)
	root.mainloop()

if __name__ == "__main__":
	main_gui()
	
