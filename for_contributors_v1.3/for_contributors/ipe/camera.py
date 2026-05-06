"""
camera.py — Camera class. Always outputs 64x64 with auto-scaling and letterboxing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

import numpy as np

from .enums import MAX_DIMENSION
from .sprites import Sprite

if TYPE_CHECKING:
    from .interfaces import RenderableUserDisplay


class Camera:
    """
    Viewport into the game world. Always renders to 64x64 output.

    Pipeline:
      1. Render sprites at camera resolution (width x height)
      2. Uniform upscale to fit within 64x64 (nearest neighbour)
      3. Letterbox padding with letter_box colour
      4. Render UI overlay interfaces on top
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 64,
        height: int = 64,
        background: int = 0,
        letter_box: int = 0,
        interfaces: list["RenderableUserDisplay"] | None = None,
    ):
        if width > MAX_DIMENSION or height > MAX_DIMENSION or width < 1 or height < 1:
            raise ValueError(f"Camera dimensions must be 1-{MAX_DIMENSION}")

        self._x = x
        self._y = y
        self._width = width
        self._height = height
        self._background = background
        self._letter_box = letter_box
        self._interfaces: list["RenderableUserDisplay"] = []
        if interfaces:
            for iface in interfaces:
                self._interfaces.append(iface)

    # --- Properties ---

    @property
    def x(self) -> int:
        return self._x

    @x.setter
    def x(self, value: int) -> None:
        self._x = int(value)

    @property
    def y(self) -> int:
        return self._y

    @y.setter
    def y(self, value: int) -> None:
        self._y = int(value)

    @property
    def width(self) -> int:
        return self._width

    @width.setter
    def width(self, value: int) -> None:
        v = int(value)
        if v > MAX_DIMENSION or v < 1:
            raise ValueError(f"Width must be 1-{MAX_DIMENSION}")
        self._width = v

    @property
    def height(self) -> int:
        return self._height

    @height.setter
    def height(self, value: int) -> None:
        v = int(value)
        if v > MAX_DIMENSION or v < 1:
            raise ValueError(f"Height must be 1-{MAX_DIMENSION}")
        self._height = v

    @property
    def background(self) -> int:
        return self._background

    @background.setter
    def background(self, value: int) -> None:
        self._background = value

    @property
    def letter_box(self) -> int:
        return self._letter_box

    @letter_box.setter
    def letter_box(self, value: int) -> None:
        self._letter_box = value

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height

    def move(self, dx: int, dy: int) -> None:
        self._x += int(dx)
        self._y += int(dy)

    def replace_interface(self, new_interfaces: list["RenderableUserDisplay"]) -> None:
        """Replace all current interfaces with new ones."""
        self._interfaces = list(new_interfaces) if new_interfaces else []

    # --- Rendering ---

    def _calculate_scale_and_offset(self) -> tuple[int, int, int]:
        """Returns (scale, x_offset, y_offset) for letterboxing."""
        scale_x = MAX_DIMENSION // self._width
        scale_y = MAX_DIMENSION // self._height
        scale = min(scale_x, scale_y)
        scaled_w = self._width * scale
        scaled_h = self._height * scale
        x_off = (MAX_DIMENSION - scaled_w) // 2
        y_off = (MAX_DIMENSION - scaled_h) // 2
        return scale, x_off, y_off

    def _raw_render(self, sprites: list[Sprite]) -> np.ndarray:
        """Render sprites at camera resolution (width x height)."""
        output = np.full(
            (self._height, self._width), self._background, dtype=np.int8
        )

        if not sprites:
            return output

        sorted_sprites = sorted(
            (s for s in sprites if s.is_visible), key=lambda s: s.layer
        )

        for sprite in sorted_sprites:
            sp = sprite.render()
            sh, sw = sp.shape

            rx = sprite.x - self._x
            ry = sprite.y - self._y

            dx_s = max(0, rx)
            dx_e = min(self._width, rx + sw)
            dy_s = max(0, ry)
            dy_e = min(self._height, ry + sh)

            if dx_e <= dx_s or dy_e <= dy_s:
                continue

            sx_s = max(0, -rx)
            sy_s = max(0, -ry)
            sx_e = sw - max(0, (rx + sw) - self._width)
            sy_e = sh - max(0, (ry + sh) - self._height)

            region = sp[sy_s:sy_e, sx_s:sx_e]
            mask = region >= 0
            output[dy_s:dy_e, dx_s:dx_e][mask] = region[mask]

        return output

    def render(self, sprites: list[Sprite]) -> np.ndarray:
        """Render to 64x64 with auto-scaling, letterboxing, and UI overlays."""
        output = np.full(
            (MAX_DIMENSION, MAX_DIMENSION), self._letter_box, dtype=np.int8
        )

        view = self._raw_render(sprites)
        scale, x_off, y_off = self._calculate_scale_and_offset()

        if scale > 1:
            view = np.repeat(np.repeat(view, scale, axis=0), scale, axis=1)

        output[y_off:y_off + view.shape[0], x_off:x_off + view.shape[1]] = view

        # UI overlay interfaces (final rendering step)
        for interface in self._interfaces:
            output = interface.render_interface(output)

        return output

    def display_to_grid(
        self, display_x: int, display_y: int
    ) -> tuple[int, int] | None:
        """Convert 64x64 display coordinates to camera grid coordinates.

        Returns None if the coordinates fall within the letterbox area.
        """
        scale, x_pad, y_pad = self._calculate_scale_and_offset()

        gx = (display_x - x_pad) // scale if display_x >= x_pad else -1
        gy = (display_y - y_pad) // scale if display_y >= y_pad else -1

        if gx < 0 or gy < 0 or gx >= self._width or gy >= self._height:
            return None

        return gx + self._x, gy + self._y
