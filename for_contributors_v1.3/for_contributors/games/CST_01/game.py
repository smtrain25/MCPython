"""
CST_01 — Click to Clear
========================
Non-agentic click-elimination puzzle.

Coloured target sprites are scattered across the grid. Click each one
to remove it. Clear all targets to complete the level. Grid size and
target count increase with each level.

Style : CST (constraint satisfaction — the constraint is "clear all")
Actions: ACTION6 (click only)
Levels : 5
"""

from __future__ import annotations

import random
from ipe import BaseGame, Camera, GameAction, Level, Sprite, BlockingMode


# ---------------------------------------------------------------------------
# Palette roles
# ---------------------------------------------------------------------------
BACKGROUND = 0       # black
PADDING    = 5       # gray
TARGET_COLORS = [1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 14, 15]

# ---------------------------------------------------------------------------
# Levels — grid grows each level
# ---------------------------------------------------------------------------
LEVELS = [
    Level(sprites=[], grid_size=(8,  8),  name="Level 1"),
    Level(sprites=[], grid_size=(16, 16), name="Level 2"),
    Level(sprites=[], grid_size=(24, 24), name="Level 3"),
    Level(sprites=[], grid_size=(32, 32), name="Level 4"),
    Level(sprites=[], grid_size=(64, 64), name="Level 5"),
]


class ClickToClear(BaseGame):
    """Click every coloured target to clear the board."""

    game_name    = "Click to Clear"
    description  = (
        "Coloured squares are scattered on the grid. "
        "Click each one to remove it. "
        "Clear all squares to advance to the next level."
    )
    category       = "non_agentic"
    primitive_tags = ["click", "spatial_recognition", "elimination"]
    feedback_tier  = 0

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

        camera = Camera(
            background=BACKGROUND,
            letter_box=PADDING,
            width=8,              # initial viewport (resized per level)
            height=8,
        )

        super().__init__(
            game_id="CST_01",
            levels=LEVELS,
            camera=camera,
            available_actions=[6],   # ACTION6 (click) only
            seed=seed,
        )

    # ── Level setup ─────────────────────────────────────────────────

    def on_set_level(self, level: Level) -> None:
        """Populate the level with random targets."""
        grid_w, grid_h = level.grid_size or (8, 8)
        cell_count = grid_w * grid_h

        # Scale target count with grid area
        target_count = max(1, cell_count // 64)

        # Track occupied cells to avoid overlap
        occupied: set[tuple[int, int]] = set()

        for idx in range(target_count):
            # Random size: 1x1 to 4x4 (capped to half grid)
            max_scale = min(4, grid_w // 2)
            scale = self._rng.randint(1, max(1, max_scale))

            # Random colour
            color = self._rng.choice(TARGET_COLORS)

            # Random position (keep within bounds after scaling)
            x = self._rng.randint(0, max(0, grid_w - scale))
            y = self._rng.randint(0, max(0, grid_h - scale))

            # Build sprite
            target = Sprite(
                pixels=[[color]],
                name=f"target_{idx}",
                x=x,
                y=y,
                scale=scale,
                visible=True,
                collidable=True,
                tags=["sys_click", "target"],
            )
            level.add_sprite(target)

    # ── Game logic ──────────────────────────────────────────────────

    def step(self) -> None:
        if self.action.id == GameAction.ACTION6:
            # Convert 64x64 display coordinates to grid coordinates
            display_x = self.action.data.get("x", 0)
            display_y = self.action.data.get("y", 0)

            coords = self.camera.display_to_grid(display_x, display_y)
            if coords:
                grid_x, grid_y = coords

                # Find the topmost clickable sprite at this position
                clicked = self.current_level.get_sprite_at(grid_x, grid_y, tag="target")
                if clicked:
                    self.current_level.remove_sprite(clicked)

                    # Win when all targets are gone
                    remaining = self.current_level.get_sprites_by_tag("target")
                    if len(remaining) == 0:
                        self.next_level()

        self.complete_action()
