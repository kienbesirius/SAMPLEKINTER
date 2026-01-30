import tkinter as tk


class ModalOverlay:
    def __init__(self, root: tk.Misc):
        self.root = root

        # Overlay canvas phủ toàn bộ root
        self.overlay = tk.Canvas(
            root,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        self.overlay.place_forget()

        # Chặn mọi tương tác rơi xuống phía sau
        for ev in (
            "<ButtonPress>", "<ButtonRelease>", "<Button-1>", "<Button-2>", "<Button-3>",
            "<Double-Button-1>", "<Motion>", "<MouseWheel>",
            "<Button-4>", "<Button-5>",  # Linux scroll
            "<KeyPress>", "<KeyRelease>",
        ):
            self.overlay.bind(ev, self._eat_event)

        self._rect_id = None

        # Khung dialog nằm TRÊN overlay (vẽ bằng create_window)
        self.dialog = tk.Frame(self.overlay, bg="#222222", bd=0, highlightthickness=0)
        self._dialog_win_id = self.overlay.create_window(0, 0, window=self.dialog, anchor="center")

        # Tự resize + canh giữa dialog theo root
        self.root.bind("<Configure>", self._on_resize, add="+")

        self._shown = False

    def _eat_event(self, _e):
        return "break"

    def _stipple_by_level(self, level: float) -> str:
        # 0..1 (mờ -> đậm)
        if level <= 0.15:
            return "gray12"
        if level <= 0.35:
            return "gray25"
        if level <= 0.6:
            return "gray50"
        return "gray75"

    def _on_resize(self, _e=None):
        if not self._shown:
            return
        self._redraw()

    def _redraw(self, dim_level: float = 0.45, dim_color: str = "black"):
        w = max(1, self.root.winfo_width())
        h = max(1, self.root.winfo_height())

        self.overlay.config(width=w, height=h)
        self.overlay.coords(self._dialog_win_id, w // 2, h // 2)

        # Dim nền (giả lập trong suốt)
        stipple = self._stipple_by_level(dim_level)
        if self._rect_id is None:
            self._rect_id = self.overlay.create_rectangle(
                0, 0, w, h,
                fill=dim_color,
                stipple=stipple,
                outline="",
            )
            self.overlay.tag_lower(self._rect_id)  # rectangle nằm dưới dialog
        else:
            self.overlay.coords(self._rect_id, 0, 0, w, h)
            self.overlay.itemconfig(self._rect_id, fill=dim_color, stipple=stipple)

        self.overlay.lift()
        self.dialog.lift()

    def show(self, *, dim_level: float = 0.45):
        if self._shown:
            return
        self._shown = True
        self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self._redraw(dim_level=dim_level)

        # Grab để đảm bảo modal (keyboard/mouse không rơi xuống widget khác)
        self.overlay.focus_set()
        self.overlay.grab_set()

    def hide(self):
        if not self._shown:
            return
        self._shown = False
        try:
            self.overlay.grab_release()
        except Exception:
            pass
        self.overlay.place_forget()

    def clear_dialog(self):
        for child in list(self.dialog.winfo_children()):
            child.destroy()
