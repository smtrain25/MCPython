"""
interfaces.py — UI overlay interfaces for the camera rendering pipeline.

RenderableUserDisplay: Abstract base for UI elements rendered on top of the 64x64 frame.
ToggleableUserDisplay: Manages sprite pairs (enabled/disabled states) for buttons/toggles.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from .enums import InteractionMode
from .sprites import Sprite


class RenderableUserDisplay(ABC):
    """Abstract base class for UI elements rendered by the camera.

    Called as the final step in the camera pipeline, after sprite rendering
    and scaling to 64x64. Receives and returns the full output frame.
    """

    @abstractmethod
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        """Render this UI element onto the given 64x64 frame.

        Args:
            frame: The 64x64 numpy array to render onto.

        Returns:
            The modified frame (may be the same object or a new one).
        """
        return frame

    def draw_sprite(
        self, frame: np.ndarray, sprite: Sprite, start_x: int, start_y: int
    ) -> np.ndarray:
        """Helper to draw a sprite onto a frame with boundary clipping.

        Args:
            frame: The 64x64 output frame.
            sprite: The sprite to draw.
            start_x, start_y: Top-left position on the frame.

        Returns:
            The modified frame.
        """
        sprite_pixels = sprite.render()
        sprite_height, sprite_width = sprite_pixels.shape

        end_x = start_x + sprite_width
        end_y = start_y + sprite_height

        if start_x < 64 and start_y < 64 and end_x > 0 and end_y > 0:
            sprite_start_y = max(0, -start_y)
            sprite_start_x = max(0, -start_x)
            sprite_end_y = sprite_height - max(0, end_y - 64)
            sprite_end_x = sprite_width - max(0, end_x - 64)

            frame_start_y = max(0, start_y)
            frame_start_x = max(0, start_x)
            frame_end_y = min(64, end_y)
            frame_end_x = min(64, end_x)

            sprite_region = sprite_pixels[
                sprite_start_y:sprite_end_y, sprite_start_x:sprite_end_x
            ]
            frame[frame_start_y:frame_end_y, frame_start_x:frame_end_x] = np.where(
                sprite_region >= 0,
                sprite_region,
                frame[frame_start_y:frame_end_y, frame_start_x:frame_end_x],
            )
        return frame


class ToggleableUserDisplay(RenderableUserDisplay):
    """UI element managing sprite pairs (enabled/disabled visual states).

    Each pair has two sprites:
      - First sprite: shown when enabled
      - Second sprite: shown when disabled
    """

    def __init__(self, sprite_pairs: list[tuple[Sprite, Sprite]] | None = None):
        self._sprite_pairs: list[tuple[Sprite, Sprite]] = []
        if sprite_pairs:
            for pair in sprite_pairs:
                self._sprite_pairs.append((pair[0].clone(), pair[1].clone()))

    def clone(self) -> "ToggleableUserDisplay":
        cloned_pairs = [(p[0].clone(), p[1].clone()) for p in self._sprite_pairs]
        return ToggleableUserDisplay(cloned_pairs)

    def is_enabled(self, index: int) -> bool:
        if index < 0 or index >= len(self._sprite_pairs):
            raise ValueError(f"Index {index} is out of bounds")
        return self._sprite_pairs[index][0].interaction != InteractionMode.REMOVED

    def enable(self, index: int) -> None:
        if index < 0 or index >= len(self._sprite_pairs):
            raise ValueError(f"Index {index} is out of bounds")
        self._enable_pair(self._sprite_pairs[index])

    def disable(self, index: int) -> None:
        if index < 0 or index >= len(self._sprite_pairs):
            raise ValueError(f"Index {index} is out of bounds")
        self._disable_pair(self._sprite_pairs[index])

    def enable_all_by_tag(self, tag: str) -> None:
        for pair in self._find_by_tag(tag):
            self._enable_pair(pair)

    def disable_all_by_tag(self, tag: str) -> None:
        for pair in self._find_by_tag(tag):
            self._disable_pair(pair)

    def enable_first_by_tag(self, tag: str) -> bool:
        for pair in self._find_by_tag(tag):
            if pair[0].interaction == InteractionMode.REMOVED:
                self._enable_pair(pair)
                return True
        return False

    def disable_first_by_tag(self, tag: str) -> bool:
        for pair in self._find_by_tag(tag):
            if pair[0].interaction == InteractionMode.INTANGIBLE:
                self._disable_pair(pair)
                return True
        return False

    def _find_by_tag(self, tag: str) -> list[tuple[Sprite, Sprite]]:
        return [p for p in self._sprite_pairs if tag in p[0].tags]

    def _enable_pair(self, pair: tuple[Sprite, Sprite]) -> None:
        pair[0].set_interaction(InteractionMode.INTANGIBLE)
        pair[1].set_interaction(InteractionMode.REMOVED)

    def _disable_pair(self, pair: tuple[Sprite, Sprite]) -> None:
        pair[0].set_interaction(InteractionMode.REMOVED)
        pair[1].set_interaction(InteractionMode.INTANGIBLE)

    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        for pair in self._sprite_pairs:
            for sprite in pair:
                if sprite.interaction != InteractionMode.REMOVED:
                    frame = self.draw_sprite(frame, sprite, sprite.x, sprite.y)
        return frame
