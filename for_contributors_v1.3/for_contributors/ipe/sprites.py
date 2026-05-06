"""
sprites.py — Sprite class with transforms, collision detection, and merging.
"""

from __future__ import annotations

import uuid

import numpy as np

from .enums import BlockingMode, InteractionMode


def _interaction_from(visible: bool, collidable: bool) -> InteractionMode:
    if visible and collidable:
        return InteractionMode.TANGIBLE
    elif visible and not collidable:
        return InteractionMode.INTANGIBLE
    elif not visible and collidable:
        return InteractionMode.INVISIBLE
    else:
        return InteractionMode.REMOVED


def _downscale_mode(arr: np.ndarray, factor: int) -> np.ndarray:
    """Nearest-neighbour downscaling. Keeps block transparent when majority is transparent.

    Pixel semantics: -1 = fully transparent, -2 = transparent-but-collidable,
    0-15 = visible palette colours. In downscaling, -1 is the only fully
    transparent value; -2 is treated as "has content" for mode selection.
    """
    H, W = arr.shape
    if H % factor != 0 or W % factor != 0:
        raise ValueError(f"Dimensions ({H},{W}) not divisible by {factor}")

    blocks = arr.reshape(H // factor, factor, -1, factor).swapaxes(1, 2)
    blocks = blocks.reshape(-1, factor * factor)

    out = np.empty(len(blocks), dtype=arr.dtype)
    for i, blk in enumerate(blocks):
        non_transparent = blk[blk != -1]  # -2 counts as content
        transparent = blk[blk == -1]      # only -1 is fully transparent
        # Transparent when majority is fully transparent
        if transparent.size > non_transparent.size:
            out[i] = -1
        elif non_transparent.size == 0:
            out[i] = -1
        else:
            cnts = np.bincount(non_transparent.astype(np.int16))
            max_count = cnts.max()
            max_indices = np.where(cnts == max_count)[0]
            out[i] = max_indices[-1]  # break ties by highest index

    return out.reshape(H // factor, W // factor)


class Sprite:
    """
    A 2D sprite with position, scale, rotation, collision detection.

    pixels: 2D numpy array (int8). 0–15 = palette colours, -1 = transparent.
    """
    VALID_ROTATIONS = {0, 90, 180, 270}

    def __init__(
        self,
        pixels: list[list[int]] | np.ndarray,
        name: str | None = None,
        x: int = 0,
        y: int = 0,
        layer: int = 0,
        scale: int = 1,
        rotation: int = 0,
        mirror_ud: bool = False,
        mirror_lr: bool = False,
        blocking: BlockingMode = BlockingMode.PIXEL_PERFECT,
        interaction: InteractionMode | None = None,
        visible: bool = True,
        collidable: bool = True,
        tags: list[str] | None = None,
    ):
        if isinstance(pixels, np.ndarray):
            if pixels.ndim != 2:
                raise ValueError("Pixels must be a 2D array")
            if pixels.dtype != np.int8:
                base = pixels.astype(np.int8, copy=False)
            else:
                base = pixels
        else:
            if not isinstance(pixels, list) or not all(isinstance(row, list) for row in pixels):
                raise ValueError("Pixels must be a 2D list or a 2D numpy array")
            base = np.array(pixels, dtype=np.int8)

        self.pixels = base.copy()
        if self.pixels.ndim != 2:
            raise ValueError("Pixels must be a 2D array")

        self._name = name if name is not None else str(uuid.uuid4())
        self._x = int(x)
        self._y = int(y)
        self._layer = int(layer)
        self._scale = 1
        self.rotation = 0
        self._mirror_ud = mirror_ud
        self._mirror_lr = mirror_lr
        self._blocking = blocking
        self._tags = list(tags) if tags else []

        if interaction is not None:
            self._interaction = interaction
        else:
            self._interaction = _interaction_from(visible, collidable)

        self._set_rotation(rotation)
        self.set_scale(scale)

    # --- Properties ---

    @property
    def name(self) -> str:
        return self._name

    @property
    def x(self) -> int:
        return self._x

    @property
    def y(self) -> int:
        return self._y

    @property
    def scale(self) -> int:
        return self._scale

    @property
    def layer(self) -> int:
        return self._layer

    @property
    def tags(self) -> list[str]:
        return self._tags

    @property
    def blocking(self) -> BlockingMode:
        return self._blocking

    @property
    def interaction(self) -> InteractionMode:
        return self._interaction

    @property
    def mirror_ud(self) -> bool:
        return self._mirror_ud

    @property
    def mirror_lr(self) -> bool:
        return self._mirror_lr

    @property
    def is_visible(self) -> bool:
        return self._interaction in (InteractionMode.TANGIBLE, InteractionMode.INTANGIBLE)

    @property
    def is_collidable(self) -> bool:
        return self._interaction in (InteractionMode.TANGIBLE, InteractionMode.INVISIBLE)

    @property
    def width(self) -> int:
        return int(self.render().shape[1])

    @property
    def height(self) -> int:
        return int(self.render().shape[0])

    # --- Setters (fluent API, validated) ---

    def set_position(self, x: int, y: int) -> "Sprite":
        self._x = int(x)
        self._y = int(y)
        return self

    def set_scale(self, scale: int) -> "Sprite":
        """Set scale. Positive = upscale, negative = downscale (-1=half, -2=third)."""
        s = int(scale)
        if s == 0:
            raise ValueError("Scale cannot be zero")
        if s < 0:
            H, W = self.pixels.shape
            factor = -s + 1
            if H % factor != 0 or W % factor != 0:
                raise ValueError(
                    f"Array dimensions ({H}, {W}) must be divisible by scale factor {factor}"
                )
        self._scale = s
        return self

    def adjust_scale(self, delta: int) -> None:
        """Adjust scale by delta, stepping one at a time and skipping zero.

        Examples:
          scale=1, delta=+2 -> 1 -> 2 -> 3
          scale=1, delta=-2 -> 1 -> -1 (half)
          scale=-2, delta=+3 -> -2 -> -1 -> 1 -> 2
        """
        if delta == 0:
            return
        step = 1 if delta > 0 else -1
        target = self._scale + delta
        while self._scale != target:
            next_scale = self._scale + step
            if next_scale == 0:
                next_scale = step  # skip zero
            self.set_scale(next_scale)

    def _set_rotation(self, rotation: int) -> None:
        normalized = rotation % 360
        if normalized not in self.VALID_ROTATIONS:
            raise ValueError(
                f"Rotation must be one of {self.VALID_ROTATIONS}, got {rotation}"
            )
        self.rotation = normalized

    def set_rotation(self, rotation: int) -> "Sprite":
        self._set_rotation(int(rotation))
        return self

    def rotate(self, delta: int) -> "Sprite":
        if delta < 0:
            delta = 360 + (delta % 360)
        self._set_rotation((self.rotation + delta) % 360)
        return self

    def set_layer(self, layer: int) -> "Sprite":
        self._layer = int(layer)
        return self

    def set_name(self, name: str) -> "Sprite":
        if not name:
            raise ValueError("Name cannot be empty")
        self._name = name
        return self

    def set_blocking(self, blocking: BlockingMode) -> "Sprite":
        if not isinstance(blocking, BlockingMode):
            raise ValueError("blocking must be a BlockingMode enum value")
        self._blocking = blocking
        return self

    def set_interaction(self, interaction: InteractionMode) -> "Sprite":
        if not isinstance(interaction, InteractionMode):
            raise ValueError("interaction must be an InteractionMode enum value")
        self._interaction = interaction
        return self

    def set_visible(self, visible: bool) -> "Sprite":
        self._interaction = _interaction_from(visible, self.is_collidable)
        return self

    def set_collidable(self, collidable: bool) -> "Sprite":
        self._interaction = _interaction_from(self.is_visible, collidable)
        return self

    def set_mirror_ud(self, mirror_ud: bool) -> "Sprite":
        self._mirror_ud = mirror_ud
        return self

    def set_mirror_lr(self, mirror_lr: bool) -> "Sprite":
        self._mirror_lr = mirror_lr
        return self

    def move(self, dx: int, dy: int) -> None:
        self._x += int(dx)
        self._y += int(dy)

    def color_remap(self, old_color: int | None, new_color: int) -> "Sprite":
        """Remap colours. old_color=None remaps all non-transparent pixels."""
        if old_color is None:
            self.pixels = np.where(self.pixels >= 0, new_color, self.pixels)
        else:
            self.pixels = np.where(self.pixels == old_color, new_color, self.pixels)
        return self

    # --- Rendering ---

    def render(self) -> np.ndarray:
        """Render the sprite with current transforms applied."""
        result = self.pixels.copy()

        if self.rotation != 0:
            k = int((-self.rotation % 360) / 90)
            if k != 0:
                result = np.rot90(result, k=k)

        if self._mirror_ud:
            result = np.flipud(result)
        if self._mirror_lr:
            result = np.fliplr(result)

        if self._scale != 1:
            if self._scale > 1:
                result = np.repeat(
                    np.repeat(result, self._scale, axis=0), self._scale, axis=1
                )
            else:
                factor = -self._scale + 1
                result = _downscale_mode(result, factor)

        return result

    # --- Cloning ---

    def clone(self, new_name: str | None = None) -> "Sprite":
        return Sprite(
            pixels=self.pixels.copy(),
            name=new_name if new_name is not None else self._name,
            x=self._x,
            y=self._y,
            scale=self._scale,
            rotation=self.rotation,
            mirror_ud=self._mirror_ud,
            mirror_lr=self._mirror_lr,
            blocking=self._blocking,
            layer=self._layer,
            interaction=self._interaction,
            tags=self._tags.copy(),
        )

    # --- Collision ---

    def collides_with(self, other: "Sprite", ignore_mode: bool = False) -> bool:
        """Check collision. Returns True if sprites overlap.

        Args:
            other: The other sprite.
            ignore_mode: If True, skip interaction/blocking mode checks.
        """
        if self is other:
            return False

        if not ignore_mode:
            if not (self.is_collidable and other.is_collidable):
                return False
            if (self._blocking == BlockingMode.NOT_BLOCKED or
                    other._blocking == BlockingMode.NOT_BLOCKED):
                return False

        self_px = self.render()
        other_px = other.render()
        sh, sw = self_px.shape
        oh, ow = other_px.shape

        # Bounding box check
        if (self._x >= other._x + ow or self._x + sw <= other._x or
                self._y >= other._y + oh or self._y + sh <= other._y):
            return False

        # Pixel-perfect
        if (self._blocking == BlockingMode.PIXEL_PERFECT or
                other._blocking == BlockingMode.PIXEL_PERFECT):
            x_min = max(self._x, other._x)
            x_max = min(self._x + sw, other._x + ow)
            y_min = max(self._y, other._y)
            y_max = min(self._y + sh, other._y + oh)

            s_region = self_px[
                y_min - self._y:y_max - self._y,
                x_min - self._x:x_max - self._x,
            ]
            o_region = other_px[
                y_min - other._y:y_max - other._y,
                x_min - other._x:x_max - other._x,
            ]
            return bool(np.any((s_region != -1) & (o_region != -1)))

        return True  # bounding box collision

    # --- Merging ---

    def merge(self, other: "Sprite") -> "Sprite":
        """Merge two sprites. Self's pixels take priority.

        Blocking/interaction resolution:
          - PIXEL_PERFECT promoted over BOUNDING_BOX
          - TANGIBLE promoted over INVISIBLE/INTANGIBLE
        """
        self_px = self.render()
        other_px = other.render()

        min_x = min(self._x, other._x)
        min_y = min(self._y, other._y)
        max_x = max(self._x + self_px.shape[1], other._x + other_px.shape[1])
        max_y = max(self._y + self_px.shape[0], other._y + other_px.shape[0])

        merged = np.full((max_y - min_y, max_x - min_x), -1, dtype=np.int8)

        # Other first (lower priority)
        oy, ox = other._y - min_y, other._x - min_x
        region = merged[oy:oy + other_px.shape[0], ox:ox + other_px.shape[1]]
        merged[oy:oy + other_px.shape[0], ox:ox + other_px.shape[1]] = np.where(
            other_px != -1, other_px, region
        )

        # Self on top
        sy, sx = self._y - min_y, self._x - min_x
        region = merged[sy:sy + self_px.shape[0], sx:sx + self_px.shape[1]]
        merged[sy:sy + self_px.shape[0], sx:sx + self_px.shape[1]] = np.where(
            self_px != -1, self_px, region
        )

        # Resolve blocking: prefer stricter mode
        blocking = self._blocking
        if blocking == BlockingMode.NOT_BLOCKED:
            blocking = other._blocking
        elif (blocking == BlockingMode.BOUNDING_BOX and
              other._blocking == BlockingMode.PIXEL_PERFECT):
            blocking = BlockingMode.PIXEL_PERFECT

        # Resolve interaction: prefer more "real" mode
        interaction = self._interaction
        if interaction == InteractionMode.REMOVED:
            interaction = other._interaction
        elif (interaction == InteractionMode.INVISIBLE and
              other._interaction == InteractionMode.TANGIBLE):
            interaction = InteractionMode.TANGIBLE
        elif (interaction == InteractionMode.INTANGIBLE and
              other._interaction == InteractionMode.TANGIBLE):
            interaction = InteractionMode.TANGIBLE

        return Sprite(
            name=self._name,
            pixels=merged,
            x=min_x,
            y=min_y,
            layer=max(self._layer, other._layer),
            blocking=blocking,
            interaction=interaction,
            tags=list(set(self._tags + other._tags)),
        )
