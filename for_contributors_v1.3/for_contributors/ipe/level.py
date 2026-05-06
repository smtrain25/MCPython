"""
level.py — Level class managing sprite collections and metadata.
"""

from __future__ import annotations

import copy
from typing import Any, List, Optional

from .enums import BlockingMode, PlaceableArea
from .sprites import Sprite


class Level:
    """A level manages a collection of sprites, metadata, and placeable areas."""

    def __init__(
        self,
        sprites: list[Sprite] | None = None,
        grid_size: tuple[int, int] | None = None,
        data: dict[str, Any] | None = None,
        name: str = "Level",
        placeable_areas: list[PlaceableArea] | None = None,
    ):
        self._sprites: list[Sprite] = []
        self._grid_size = grid_size
        self._data = data if data is not None else {}
        self._name = name
        self._placeable_areas = placeable_areas if placeable_areas is not None else []
        self._sorted_sprites: list[Sprite] | None = None
        self._need_sort = True

        if sprites:
            self._sprites.extend(sprites)
            self._merge_static_sprites()

    def _merge_static_sprites(self) -> None:
        """Merge sys_static + PIXEL_PERFECT sprites per layer at init time."""
        by_layer: dict[int, list[Sprite]] = {}
        others: list[Sprite] = []

        for s in self._sprites:
            if s.blocking == BlockingMode.PIXEL_PERFECT and "sys_static" in s.tags:
                by_layer.setdefault(s.layer, []).append(s)
            else:
                others.append(s)

        merged: list[Sprite] = []
        for layer, group in by_layer.items():
            if len(group) <= 1:
                merged.extend(group)
                continue
            base = group[0]
            for nxt in group[1:]:
                base = base.merge(nxt)
            base.set_layer(layer)
            if "sys_static" not in base.tags:
                base.tags.append("sys_static")
            merged.append(base)

        self._sprites = others + merged

    # --- Properties ---

    @property
    def name(self) -> str:
        return self._name

    @property
    def grid_size(self) -> tuple[int, int] | None:
        return self._grid_size

    @property
    def placeable_areas(self) -> list[PlaceableArea]:
        return self._placeable_areas

    # --- Sprite management ---

    def add_sprite(self, sprite: Sprite) -> None:
        self._sprites.append(sprite)
        self._need_sort = True

    def remove_sprite(self, sprite: Sprite) -> None:
        if sprite in self._sprites:
            self._sprites.remove(sprite)
            self._need_sort = True

    def remove_all_sprites(self) -> None:
        self._sprites = []
        self._need_sort = True

    def get_sprites(self) -> list[Sprite]:
        return self._sprites.copy()

    def get_sprites_by_name(self, name: str) -> list[Sprite]:
        return [s for s in self._sprites if s.name == name]

    def get_sprites_by_tag(self, tag: str) -> list[Sprite]:
        return [s for s in self._sprites if tag in s.tags]

    def get_sprites_by_tags(self, tags: list[str]) -> list[Sprite]:
        """Get sprites that have ALL of the given tags."""
        if not tags:
            return []
        return [s for s in self._sprites if all(t in s.tags for t in tags)]

    def get_sprites_by_any_tag(self, tags: list[str]) -> list[Sprite]:
        """Get sprites that have ANY of the given tags."""
        return [s for s in self._sprites if any(t in s.tags for t in tags)]

    def get_all_tags(self) -> set[str]:
        """Get all unique tags from all sprites in the level."""
        all_tags: set[str] = set()
        for sprite in self._sprites:
            all_tags.update(sprite.tags)
        return all_tags

    def get_sprite_at(
        self,
        x: int,
        y: int,
        tag: str | None = None,
        ignore_collidable: bool = False,
    ) -> Sprite | None:
        """Get the topmost sprite at (x, y).

        Args:
            x, y: Coordinates to check.
            tag: If set, only return sprites with this tag.
            ignore_collidable: If True, check all sprites, not just collidable ones.
        """
        if self._need_sort or self._sorted_sprites is None or len(self._sorted_sprites) != len(self._sprites):
            self._sorted_sprites = sorted(
                self._sprites, key=lambda s: s.layer, reverse=True
            )
            self._need_sort = False

        for sprite in self._sorted_sprites:
            if not ignore_collidable and not sprite.is_collidable:
                continue
            if (x >= sprite.x and y >= sprite.y and
                    x < sprite.x + sprite.width and
                    y < sprite.y + sprite.height):
                if sprite.blocking == BlockingMode.PIXEL_PERFECT:
                    pixels = sprite.render()
                    if pixels[y - sprite.y][x - sprite.x] == -1:
                        continue
                if tag is None or tag in sprite.tags:
                    return sprite
        return None

    def collides_with(self, sprite: Sprite, ignore_mode: bool = False) -> list[Sprite]:
        """Find all sprites in this level that collide with the given sprite."""
        return [s for s in self._sprites if sprite.collides_with(s, ignore_mode=ignore_mode)]

    def get_data(self, key: str) -> Any:
        return self._data.get(key)

    def clone(self) -> "Level":
        return Level(
            name=self._name,
            sprites=[s.clone() for s in self._sprites],
            grid_size=self._grid_size,
            data=copy.deepcopy(self._data),
            placeable_areas=self._placeable_areas,
        )
