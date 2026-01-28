# src/gui/widgets/arrow.py
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class ArrowSkins:
    """
    Key ảnh mũi tên trong assets dict.
    Nếu có biến thể scale thì dùng key dạng:
      - <right>_0.5
      - <right>_0.75
    """
    right: str = "arrow_to_right"


def _pick_scaled_key(canvas: tk.Canvas, assets: Dict[str, Any], base_key: str) -> str:
    """Chọn _0.5/_0.75 nếu tồn tại trong assets; không có thì dùng base_key."""
    # nếu caller đã truyền key có suffix thì giữ nguyên
    if base_key.endswith("_0.5") or base_key.endswith("_0.75"):
        return base_key

    try:
        w = int(canvas.winfo_width())
    except Exception:
        w = 0

    # match style scaling như button binder :contentReference[oaicite:1]{index=1}
    if w <= 800:
        k = f"{base_key}_0.5"
        if k in assets:
            return k
    if w <= 1200:
        k = f"{base_key}_0.75"
        if k in assets:
            return k

    return base_key


class CanvasArrow:
    """
    Canvas image widget: chỉ vẽ arrow tại vị trí (x,y).

    API:
      - configure(x=..., y=..., key=..., state=...)
      - move_to(x, y)
      - set_visible(True/False)
      - destroy()

    Uasge: 

    from src.gui.widgets.arrow import bind_canvas_arrow

    self.arrow = bind_canvas_arrow(
        root=self.root,
        canvas=self._canvas,
        assets=self.assets,
        tag="arrow_1",
        x=400, y=200,
        right_key="arrow_to_right",   # sẽ auto dùng arrow_to_right_0.5/_0.75 nếu có
    )

    # move
    self.arrow.move_to(420, 210)

    # hide/show
    self.arrow.set_visible(False)
    self.arrow.set_visible(True)

    """

    def __init__(
        self,
        *,
        root: tk.Misc,
        canvas: tk.Canvas,
        assets: Dict[str, Any],
        tag: str,
        x: int,
        y: int,
        anchor: str = "center",
        skins: ArrowSkins = ArrowSkins(),
        state: str = "normal",
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.assets = assets
        self.tag = tag
        self.anchor = anchor
        self.skins = skins

        key = _pick_scaled_key(self.canvas, self.assets, self.skins.right)

        self.img_id = self.canvas.create_image(
            x, y,
            image=self.assets[key],
            anchor=self.anchor,
            state=state,
            tags=(self.tag, f"{self.tag}__img"),
        )

    def configure(self, **kw):
        if "x" in kw or "y" in kw:
            x, y = self.canvas.coords(self.img_id)
            nx = kw.get("x", x)
            ny = kw.get("y", y)
            self.canvas.coords(self.img_id, nx, ny)

        if "anchor" in kw:
            self.anchor = kw["anchor"]
            self.canvas.itemconfig(self.img_id, anchor=self.anchor)

        if "state" in kw:
            self.canvas.itemconfig(self.img_id, state=kw["state"])

        # đổi sang 1 key ảnh khác (nếu muốn)
        if "key" in kw:
            k = str(kw["key"])
            k = _pick_scaled_key(self.canvas, self.assets, k)
            if k in self.assets:
                self.canvas.itemconfig(self.img_id, image=self.assets[k])

        # đổi skins (vd: skins.right = "arrow_to_right_alt")
        if "skins" in kw and isinstance(kw["skins"], ArrowSkins):
            self.skins = kw["skins"]
            k = _pick_scaled_key(self.canvas, self.assets, self.skins.right)
            if k in self.assets:
                self.canvas.itemconfig(self.img_id, image=self.assets[k])

    def move_to(self, x: int, y: int):
        self.canvas.coords(self.img_id, x, y)

    def set_visible(self, visible: bool = True):
        self.canvas.itemconfig(self.img_id, state=("normal" if visible else "hidden"))

    def destroy(self):
        try:
            self.canvas.delete(self.img_id)
        except Exception:
            pass

    @property
    def ids(self) -> Tuple[int]:
        return (self.img_id,)


def bind_canvas_asset(
    *,
    root: tk.Misc,
    canvas: tk.Canvas,
    assets: Dict[str, Any],
    tag: str,
    x: int,
    y: int,
    anchor: str = "center",
    right_key: str = "arrow_to_right",
    state: str = "normal",
) -> CanvasArrow:
    """
    Canvas image widget: chỉ vẽ arrow tại vị trí (x,y).

    API:
      - configure(x=..., y=..., key=..., state=...)
      - move_to(x, y)
      - set_visible(True/False)
      - destroy()

    Uasge: 

    from src.gui.widgets.arrow import bind_canvas_arrow

    self.arrow = bind_canvas_arrow(
        root=self.root,
        canvas=self._canvas,
        assets=self.assets,
        tag="arrow_1",
        x=400, y=200,
        right_key="arrow_to_right",   # sẽ auto dùng arrow_to_right_0.5/_0.75 nếu có
    )

    # move
    self.arrow.move_to(420, 210)

    # hide/show
    self.arrow.set_visible(False)
    self.arrow.set_visible(True)

    """
    skins = ArrowSkins(right=right_key)
    return CanvasArrow(
        root=root,
        canvas=canvas,
        assets=assets,
        tag=tag,
        x=x,
        y=y,
        anchor=anchor,
        skins=skins,
        state=state,
    )
