# src/gui/widgets/text_area.py
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class TextAreaOptions:
    anchor: str = "n"
    pad_w: int = 43
    pad_h: int = 43

    font: Any = ("Tektur", 9, "normal")
    wrap: str = "word"
    bg: str = "white"

    readonly: bool = True
    auto_scroll: bool = True
    use_var_sync: bool = False

    wheel_units: int = 2
    max_lines: int = 500  # 0/negative => no trim

        # --- NEW: label like entry ---
    field_label: str = ""
    field_label_fill: str = "black"
    field_label_font: Any = ("Tektur", 9)
    lbl_dx: int = 48
    lbl_dy: int = 10


# Helper: auto choose skins by label length (giữ y chang logic của bạn)
def choose_area_skins_by_label(field_label: str) -> str:
    if len(field_label) <= 7:
        return "text_area"
    if len(field_label) <= 12:
         return "text_wide_1_area"
    if len(field_label) <= 17:
        return "text_wide_2_area"
    
    if len(field_label) <= 22:
        return "text_wide_3_area"
    
    # fallback default (bạn có thể mở rộng wide_2, wide_3...)
    return "text_wide_3_area"

class CanvasTextArea:
    """
    Canvas based text area:
      - background image (canvas image item)
      - tk.Frame containing tk.Text (and optional hidden scrollbar)
      - canvas window embeds the frame

    API:
      - append(text)
      - clear()
      - set(text) / get()
      - configure(state=..., readonly=..., auto_scroll=..., max_lines=...)
      - ids, widget, var

    Usage:
        from src.gui.widgets.text_area import bind_canvas_text_area

        self.logs = bind_canvas_text_area(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            x=320,
            y=120,
            bg_key="log_panel_bg",
            name="logs",
            anchor="n",
            readonly=True,
            auto_scroll=True,
            max_lines=500,
        )

        self.logs.append("~/ 01-27 10:12:00 | hello")
        self.logs.clear()
        text_now = self.logs.get()

        # nếu vẫn muốn var.set() sync full:
        self.logs.configure(readonly=False)
        self.logs.var.set("full replace text")  # chỉ có tác dụng nếu use_var_sync=True lúc create

    """

    def __init__(
        self,
        *,
        root: tk.Misc,
        canvas: tk.Canvas,
        assets: Dict[str, Any],
        x: int,
        y: int,
        bg_key: str,
        name: str = "logs",
        opts: TextAreaOptions = TextAreaOptions(),
    ) -> None:
        
        self.bg_key = choose_area_skins_by_label(name)
        self.root = root
        self.canvas = canvas
        self.assets = assets
        self.x = x
        self.y = y
        self.bg_label = bg_key
        self.name = name
        self.opts = opts

        self.var = tk.StringVar()

        # --- frame + text ---
        self.frame = tk.Frame(self.root, bg=self.opts.bg)

        self.text = tk.Text(
            self.frame,
            bg=self.opts.bg,
            highlightthickness=0,
            wrap=self.opts.wrap,
            bd=0,
            font=self.opts.font,
        )
        self.text.pack(expand=True, fill="both")

        # optional hidden scrollbar
        self.scroll = tk.Scrollbar(self.frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=self.scroll.set)

        # --- mousewheel bindings (cross-platform) ---
        self.text.bind("<MouseWheel>", self._on_mousewheel, add="+")  # Win/mac
        self.text.bind("<Button-4>", self._on_mousewheel, add="+")    # Linux up
        self.text.bind("<Button-5>", self._on_mousewheel, add="+")    # Linux down

        # --- optional sync var -> full text ---
        if self.opts.use_var_sync:
            self.var.trace_add("write", lambda *_: self.set(self.var.get()))

        # readonly init
        if self.opts.readonly:
            self.text.configure(state="disabled")

        # --- canvas bg image ---
        self.bg_id = self.canvas.create_image(
            x, y,
            image=self.assets[self.bg_key],
            anchor=self.opts.anchor,
            tags=(f"text_area_bg_{name}",),
        )

        # compute window size
        bg_img = self.assets[self.bg_key]
        w = bg_img.width() - int(self.opts.pad_w)
        h = bg_img.height() - int(self.opts.pad_h)

        # keep your original "center_offset" approach
        center_offset = bg_img.height() // 2

        # ---- field label ----
        # --- NEW: field label like entry (in notch) --
        # 
         # compute bg bbox => stable for ANY anchor
        x1, y1, x2, y2 = self.canvas.bbox(self.bg_id)  # type: ignore[assignment]
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        
        self.label_id = 0
        if self.opts.field_label:
            label_x = x1 + int(self.opts.lbl_dx)
            label_y = y1 + int(self.opts.lbl_dy)
            self.label_id = self.canvas.create_text(
                label_x,
                label_y,
                text=self.opts.field_label,
                anchor="w",
                fill=self.opts.field_label_fill,
                font=self.opts.field_label_font,
                tags=(f"text_area_lbl_{name}",),
            )
            # ensure label above everything
            try:
                self.canvas.tag_raise(self.label_id)
            except Exception:
                pass

        # --- canvas window embedding frame ---
        self.win_id = self.canvas.create_window(
            cx,
            cy,
            width=w,
            height=h,
            window=self.frame,
            tags=(f"text_area_win_{name}",),
        )

    # ---------------------------
    # Public API
    # ---------------------------
    @property
    def ids(self) -> Tuple[int, int]:
        return (self.bg_id, self.win_id)

    @property
    def widget(self) -> tk.Text:
        return self.text

    def configure(self, **kw):
        # behavior toggles
        if "readonly" in kw:
            self.opts.readonly = bool(kw["readonly"])
            # keep current content but change state accordingly
            self._apply_readonly()

        if "auto_scroll" in kw:
            self.opts.auto_scroll = bool(kw["auto_scroll"])

        if "max_lines" in kw:
            self.opts.max_lines = int(kw["max_lines"])

        # label update
        if "field_label" in kw:
            self.opts.field_label = str(kw["field_label"])
            if self.label_id:
                self.canvas.itemconfig(self.label_id, text=self.opts.field_label)
            else:
                # create if not exist yet
                try:
                    x1, y1, *_ = self.canvas.bbox(self.bg_id)
                    self.label_id = self.canvas.create_text(
                        x1 + int(self.opts.lbl_dx),
                        y1 + int(self.opts.lbl_dy),
                        text=self.opts.field_label,
                        anchor="w",
                        fill=self.opts.field_label_fill,
                        font=self.opts.field_label_font,
                        tags=(f"text_area_lbl_{self.name}",),
                    )
                    self.canvas.tag_raise(self.label_id)
                except Exception:
                    pass

        # visual styling
        if "bg" in kw:
            self.opts.bg = str(kw["bg"])
            self.frame.configure(bg=self.opts.bg)
            self.text.configure(bg=self.opts.bg)

        if "wrap" in kw:
            self.opts.wrap = str(kw["wrap"])
            self.text.configure(wrap=self.opts.wrap)

        if "font" in kw:
            self.opts.font = kw["font"]
            self.text.configure(font=self.opts.font)

        # programmatic state override (tk-like)
        if "state" in kw:
            st = kw["state"]
            self.text.configure(state=st)

    def get(self) -> str:
        # "end-1c" to drop implicit trailing newline
        return self.text.get("1.0", "end-1c")

    def set(self, s: str):
        self._set_text_full(s or "")

    def clear(self):
        self._set_text_full("")

    def append(self, s: str):
        if not s:
            return
        self._set_state_normal_temporarily()

        # ensure newline separation if needed
        if self.text.index("end-1c") != "1.0":
            last_char = self.text.get("end-2c", "end-1c")
            if last_char and not last_char.endswith("\n"):
                self.text.insert("end", "\n")

        self.text.insert("end", s)

        self._trim_to_max_lines()

        if self.opts.auto_scroll:
            self.text.see("end")

        self._restore_readonly_if_needed()

    def destroy(self):
        # delete canvas items
        try:
            self.canvas.delete(self.bg_id)
        except Exception:
            pass
        try:
            self.canvas.delete(self.win_id)
        except Exception:
            pass

        # destroy tk widgets
        try:
            self.text.destroy()
        except Exception:
            pass
        try:
            self.scroll.destroy()
        except Exception:
            pass
        try:
            self.frame.destroy()
        except Exception:
            pass

    # ---------------------------
    # Internals
    # ---------------------------
    def _apply_readonly(self):
        if self.opts.readonly:
            try:
                self.text.configure(state="disabled")
            except Exception:
                pass
        else:
            try:
                self.text.configure(state="normal")
            except Exception:
                pass

    def _set_state_normal_temporarily(self):
        # only enable if readonly is True; if already normal, ok
        try:
            self.text.configure(state="normal")
        except Exception:
            pass

    def _restore_readonly_if_needed(self):
        if self.opts.readonly:
            try:
                self.text.configure(state="disabled")
            except Exception:
                pass

    def _set_text_full(self, s: str):
        self._set_state_normal_temporarily()
        self.text.delete("1.0", "end")
        if s:
            self.text.insert("end", s)
        if self.opts.auto_scroll:
            self.text.see("end")
        self._restore_readonly_if_needed()

    def _trim_to_max_lines(self):
        max_lines = int(self.opts.max_lines)
        if max_lines <= 0:
            return
        try:
            line_count = int(self.text.index("end-1c").split(".")[0])
        except Exception:
            return
        if line_count > max_lines:
            cut_to = line_count - max_lines
            # delete from start up to beginning of line cut_to
            self.text.delete("1.0", f"{cut_to}.0")

    def _on_mousewheel(self, event):
        # Linux: Button-4/5
        if getattr(event, "num", None) == 4:
            self.text.yview_scroll(-int(self.opts.wheel_units), "units")
            return "break"
        if getattr(event, "num", None) == 5:
            self.text.yview_scroll(int(self.opts.wheel_units), "units")
            return "break"

        # Windows/mac: event.delta
        try:
            delta = int(-1 * (event.delta / 120))
        except Exception:
            delta = 0
        if delta:
            self.text.yview_scroll(delta, "units")
        return "break"


def bind_canvas_text_area(
    *,
    root: tk.Misc,
    canvas: tk.Canvas,
    assets: Dict[str, Any],
    x: int,
    y: int,
    bg_key: str,
    name: str = "logs",
    anchor: str = "n",
    pad_w: int = 43,
    pad_h: int = 43,
    font: Any = ("Tektur", 9, "normal"),
    wrap: str = "word",
    bg: str = "white",
    readonly: bool = True,
    auto_scroll: bool = True,
    use_var_sync: bool = False,
    wheel_units: int = 2,
    max_lines: int = 500,
    # NEW: label args
    field_label: str = "Kết quả",
    field_label_fill: str = "black",
    field_label_font: Any = ("Tektur", 13, "bold"),
    lbl_dx: int = 48,
    lbl_dy: int = 10,
) -> CanvasTextArea:
    """
    Canvas based text area:
      - background image (canvas image item)
      - tk.Frame containing tk.Text (and optional hidden scrollbar)
      - canvas window embeds the frame

    API:
      - append(text)
      - clear()
      - set(text) / get()
      - configure(state=..., readonly=..., auto_scroll=..., max_lines=...)
      - ids, widget, var

    Usage:
        from src.gui.widgets.text_area import bind_canvas_text_area

        self.logs = bind_canvas_text_area(
            root=self.root,
            canvas=self._canvas,
            assets=self.assets,
            x=320,
            y=120,
            bg_key="log_panel_bg",
            name="logs",
            anchor="n",
            readonly=True,
            auto_scroll=True,
            max_lines=500,
        )

        self.logs.append("~/ 01-27 10:12:00 | hello")
        self.logs.clear()
        text_now = self.logs.get()

        # nếu vẫn muốn var.set() sync full:
        self.logs.configure(readonly=False)
        self.logs.var.set("full replace text")  # chỉ có tác dụng nếu use_var_sync=True lúc create

    """
    opts = TextAreaOptions(
        anchor=anchor,
        pad_w=pad_w,
        pad_h=pad_h,
        font=font,
        wrap=wrap,
        bg=bg,
        readonly=readonly,
        auto_scroll=auto_scroll,
        use_var_sync=use_var_sync,
        wheel_units=wheel_units,
        max_lines=max_lines,
        field_label=field_label,
        field_label_fill=field_label_fill,
        field_label_font=field_label_font,
        lbl_dx=lbl_dx,
        lbl_dy=lbl_dy,
    )
    return CanvasTextArea(
        root=root,
        canvas=canvas,
        assets=assets,
        x=x,
        y=y,
        bg_key=bg_key,
        name=name,
        opts=opts,
    )
