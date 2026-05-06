"""
my_game.py — YOUR GAME HERE
==============================
Edit this file to create your puzzle game.

Quick start:
  1. Edit the class attributes (game_name, description, etc.)
  2. Edit _generate_level() to create your level content
  3. Edit step() to handle player actions
  4. Run:  python run.py
  5. Open: http://127.0.0.1:5000

See CONTRIBUTING.md for the full guide.
"""

from __future__ import annotations

import random
from ipe import BaseGame, Camera, GameAction, Level, Sprite


# ── Define your levels ──────────────────────────────────────────────

LEVELS = [
    Level(sprites=[], grid_size=(16, 16), name="Level 1"),
    Level(sprites=[], grid_size=(16, 16), name="Level 2"),
    Level(sprites=[], grid_size=(16, 16), name="Level 3"),
]


class MyGame(BaseGame):
    """
    YOUR GAME — edit this class.

    The engine calls step() on every player action.
    Your job: check self.action.id, update sprites, call
    self.next_level() on success or self.lose() on failure.
    """

    # ── Edit these ──────────────────────────────────────────────────
    game_name = "My Puzzle Game"
    description = "A puzzle where you navigate to the green goal."
    category = "agentic"           # "agentic" | "non_agentic" | "orchestration"
    primitive_tags = ["navigation"]
    feedback_tier = 1

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)

        camera = Camera(
            background=0,       # black background
            letter_box=5,       # gray letterbox padding
            width=16,           # viewport width (auto-scales to 64x64)
            height=16,          # viewport height
        )

        super().__init__(
            game_id="my_game",
            levels=LEVELS,
            camera=camera,
            available_actions=[1, 2, 3, 4],  # Up, Down, Left, Right
            seed=seed,
        )

    def on_set_level(self, level: Level) -> None:
        """Called when a level starts. Build your level content here."""
        self._generate_level(level)

    def _generate_level(self, level: Level) -> None:
        """Populate the level with sprites."""
        grid_w, grid_h = level.grid_size or (16, 16)

        # Player (blue)
        player = Sprite(pixels=[[1]], name="player", x=1, y=1, tags=["player"])
        level.add_sprite(player)

        # Goal (green, 2x2)
        goal = Sprite(
            pixels=[[3, 3], [3, 3]], name="goal",
            x=grid_w - 4, y=grid_h - 4, tags=["goal"],
        )
        level.add_sprite(goal)

        # Random walls (gray)
        for _ in range(3 + self._rng.randint(0, 3)):
            wx = self._rng.randint(2, grid_w - 3)
            wy = self._rng.randint(2, grid_h - 3)
            wall = Sprite(pixels=[[5]], name=f"wall_{wx}_{wy}", x=wx, y=wy, tags=["wall"])
            level.add_sprite(wall)

    def step(self) -> None:
        """Game logic — called on every action."""
        action = self.action.id

        if action in (GameAction.ACTION1, GameAction.ACTION2,
                      GameAction.ACTION3, GameAction.ACTION4):
            dx, dy = {
                GameAction.ACTION1: (0, -1),   # Up
                GameAction.ACTION2: (0, 1),    # Down
                GameAction.ACTION3: (-1, 0),   # Left
                GameAction.ACTION4: (1, 0),    # Right
            }[action]

            collisions = self.try_move("player", dx, dy)
            if not collisions:
                player = self.current_level.get_sprites_by_name("player")[0]
                goal = self.current_level.get_sprites_by_name("goal")[0]
                if (player.x >= goal.x and player.x < goal.x + goal.width and
                        player.y >= goal.y and player.y < goal.y + goal.height):
                    self.next_level()

        self.complete_action()
