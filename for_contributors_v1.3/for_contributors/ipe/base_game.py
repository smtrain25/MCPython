"""
base_game.py — BaseGame: the core game engine.

Subclass and override step() + on_set_level(). The engine handles
the game loop, rendering, level management, and reset logic.
"""

from __future__ import annotations

import os
from abc import ABC
from typing import List, Optional, final

import numpy as np
from numpy import ndarray

from .enums import (
    ActionInput,
    FrameData,
    FrameDataRaw,
    GameAction,
    GameState,
    CATEGORY,
    MAX_FRAME_PER_ACTION,
)
from .camera import Camera
from .level import Level
from .sprites import Sprite
from .rendering import render_ascii_64, render_png_64


class BaseGame(ABC):
    """
    Core game engine. Subclass and override:
      - step()         — game logic (call self.complete_action() when done)
      - on_set_level() — level setup / procedural generation (optional)

    The game loop (perform_action) is fixed and must not be overridden.
    """

    # --- Subclass metadata ---
    game_name: str = "Unnamed Game"
    description: str = "A puzzle game."
    category: CATEGORY = "agentic"
    primitive_tags: list[str] = []
    feedback_tier: int = 1

    _game_id: str
    _levels: list[Level]
    _clean_levels: list[Level]
    _current_level_index: int
    _camera: Camera
    _debug_mode: bool
    _action: ActionInput
    _action_complete: bool
    _action_count: int
    _state: GameState
    _score: int
    _next_level_flag: bool
    _full_reset: bool
    _win_score: int
    _available_actions: list[int]
    _placeable_sprite: Optional[Sprite]
    _seed: int

    def __init__(
        self,
        game_id: str,
        levels: list[Level],
        camera: Camera | None = None,
        debug: bool = False,
        win_score: int = 0,
        available_actions: list[int] | None = None,
        seed: int = 0,
    ):
        if not levels:
            raise ValueError("Game must have at least one level")

        self._game_id = game_id
        self._levels = [level.clone() for level in levels]
        self._clean_levels = [level.clone() for level in levels]
        self._current_level_index = 0

        self._debug_mode = debug
        self._camera = camera if camera is not None else Camera()
        self._state = GameState.NOT_PLAYED
        self._score = 0
        self._next_level_flag = False
        self._action = ActionInput()
        self._action_complete = False
        self._action_count = 0
        self._full_reset = False
        self._win_score = win_score if win_score > 1 else len(levels)
        self._available_actions = available_actions or [1, 2, 3, 4, 5, 6]
        self._placeable_sprite = None
        self._seed = seed

        self.set_level(0)

    # --- Properties (final — cannot be overridden) ---

    @property
    @final
    def game_id(self) -> str:
        return self._game_id

    @property
    @final
    def current_level(self) -> Level:
        return self._levels[self._current_level_index]

    @property
    @final
    def camera(self) -> Camera:
        return self._camera

    @property
    @final
    def action(self) -> ActionInput:
        return self._action

    @property
    @final
    def level_index(self) -> int:
        return self._current_level_index

    @property
    @final
    def win_score(self) -> int:
        return self._win_score

    @property
    @final
    def num_levels(self) -> int:
        return len(self._levels)

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def score(self) -> int:
        return self._score

    # --- Debug ---

    def debug(self, message: str) -> None:
        """Print message if debug mode is enabled."""
        if self._debug_mode:
            print(message)

    # --- Level management ---

    @final
    def set_level(self, index: int) -> None:
        if not 0 <= index < len(self._levels):
            raise IndexError(f"Level index {index} out of range [0, {len(self._levels)})")
        self._current_level_index = index
        self._action_count = 0
        level = self.current_level
        if level.grid_size:
            self.camera.resize(level.grid_size[0], level.grid_size[1])
        self.on_set_level(level)

    def set_level_by_name(self, name: str) -> None:
        """Set level by name. Raises ValueError if not found."""
        for index, level in enumerate(self._levels):
            if level.name == name:
                self.set_level(index)
                return
        raise ValueError(f"Level with name {name} not found")

    def is_last_level(self) -> bool:
        return self._current_level_index == len(self._levels) - 1

    def next_level(self) -> None:
        """Advance to next level. Call from step() when level is complete."""
        self._score += 1
        if not self.is_last_level():
            self._next_level_flag = True
        else:
            self.win()

    def _really_set_next_level(self) -> None:
        self.set_level(self._current_level_index + 1)
        self._next_level_flag = False

    def on_set_level(self, level: Level) -> None:
        """Override to set up level-specific data. Called on init and level change."""
        pass

    # --- Game state ---

    @final
    def win(self) -> None:
        """Call when the player has beaten the game."""
        self._state = GameState.WIN

    @final
    def lose(self) -> None:
        """Call when the player has lost the game."""
        self._state = GameState.GAME_OVER

    @final
    def complete_action(self) -> None:
        """Signal that the current action is fully resolved."""
        self._action_complete = True

    @final
    def is_action_complete(self) -> bool:
        return not self._next_level_flag and self._action_complete

    # --- Reset ---

    def handle_reset(self) -> None:
        """Handle reset. Respects ONLY_RESET_LEVELS env var."""
        if os.getenv("ONLY_RESET_LEVELS") == "true" and self._state != GameState.WIN:
            self.level_reset()
        elif self._action_count == 0 or self._state == GameState.WIN:
            self.full_reset()
        else:
            self.level_reset()

    def full_reset(self) -> None:
        self._levels = [level.clone() for level in self._clean_levels]
        self._score = 0
        self._action_count = 0
        self._full_reset = True
        self.set_level(0)
        self._state = GameState.NOT_FINISHED

    def level_reset(self) -> None:
        self._levels[self._current_level_index] = (
            self._clean_levels[self._current_level_index].clone()
        )
        self.set_level(self._current_level_index)
        self._state = GameState.NOT_FINISHED

    # --- Core game loop (DO NOT OVERRIDE) ---

    @final
    def perform_action(
        self, action_input: ActionInput, raw: bool = False
    ) -> FrameData | FrameDataRaw:
        """Execute an action and return frame data.

        DO NOT OVERRIDE. Put your game logic in step().
        """
        self._full_reset = False

        if action_input.id == GameAction.RESET:
            self.handle_reset()
        elif self._state in (GameState.GAME_OVER, GameState.WIN):
            return FrameData(
                game_id=self._game_id,
                frame=[],
                state=self._state,
                levels_completed=self._score,
                win_levels=self._win_score,
                action_input=action_input,
                available_actions=self._available_actions,
            )

        self._set_action(action_input)

        frame_list: list = []
        count = 0

        while not self.is_action_complete():
            if count > MAX_FRAME_PER_ACTION:
                raise ValueError("Action took too many frames")
            count += 1

            if self._next_level_flag:
                self._really_set_next_level()
            else:
                self.step()

            rendered = self.camera.render(self.current_level.get_sprites())
            if raw:
                frame_list.append(rendered)
            else:
                frame_list.append(rendered.tolist())

        if raw:
            fdr = FrameDataRaw(
                game_id=self._game_id,
                state=self._state,
                levels_completed=self._score,
                win_levels=self._win_score,
                action_input=action_input,
                full_reset=self._full_reset,
                available_actions=self._available_actions,
            )
            fdr.frame = frame_list
            return fdr

        last_frame = frame_list[-1] if frame_list else [[0] * 64 for _ in range(64)]

        return FrameData(
            game_id=self._game_id,
            frame=frame_list,
            state=self._state,
            levels_completed=self._score,
            win_levels=self._win_score,
            action_input=action_input,
            full_reset=self._full_reset,
            available_actions=self._available_actions,
            text_observation=render_ascii_64(last_frame),
            image_observation=render_png_64(last_frame),
        )

    @final
    def _set_action(self, action_input: ActionInput) -> None:
        self._state = GameState.NOT_FINISHED
        self._action = action_input
        self._action_complete = False
        if action_input.id != GameAction.RESET:
            self._action_count += 1

    def step(self) -> None:
        """Override with your game logic.

        REQUIRED: Call self.complete_action() when the action is fully resolved.
        The engine calls step() repeatedly until complete_action() is called.
        Each call produces one rendered frame.
        """
        self.complete_action()

    # --- Movement helpers ---

    def try_move(self, sprite_name: str, dx: int, dy: int) -> List[Sprite]:
        """Try to move a named sprite. Returns collisions (empty = moved ok)."""
        sprites = self.current_level.get_sprites_by_name(sprite_name)
        if not sprites:
            raise ValueError(f"No sprite found with name: {sprite_name}")
        return self.try_move_sprite(sprites[0], dx, dy)

    def try_move_sprite(self, sprite: Sprite, dx: int, dy: int) -> List[Sprite]:
        """Try to move a sprite. Returns list of collided sprites (empty = success)."""
        original_x = sprite.x
        original_y = sprite.y
        sprite.move(dx, dy)

        collisions = []
        for other in self.current_level.get_sprites():
            if sprite.collides_with(other):
                collisions.append(other)

        if collisions:
            sprite.set_position(original_x, original_y)

        return collisions

    # --- Pixel access ---

    def get_pixels_at_sprite(self, sprite: Sprite) -> ndarray:
        """Get the camera pixels at a sprite's location."""
        return self.get_pixels(
            sprite.x - self.camera.x, sprite.y - self.camera.y,
            sprite.width, sprite.height,
        )

    def get_pixels(self, x: int, y: int, width: int, height: int) -> ndarray:
        """Sample a region from the camera's raw render."""
        frame = self.camera._raw_render(self.current_level.get_sprites())
        return frame[y:y + height, x:x + width]

    # --- Placeable sprite ---

    def set_placeable_sprite(self, sprite: Sprite | None) -> None:
        self._placeable_sprite = sprite

    # --- Valid actions (internal, not exposed to agents) ---

    def _get_valid_actions(self) -> list[ActionInput]:
        """Get the valid actions for the current game state.

        Internal use only — not exposed via API or to agents.
        """
        valid_actions: list[ActionInput] = []

        for action_id in self._available_actions:
            ga = GameAction.from_id(action_id)
            if ga.is_simple():
                valid_actions.append(ActionInput(id=ga))
            elif ga == GameAction.ACTION6:
                if self._placeable_sprite:
                    valid_actions.extend(self._get_valid_placeable_actions())
                else:
                    valid_actions.extend(self._get_valid_clickable_actions())

        return valid_actions

    def _get_valid_placeable_actions(self) -> list[ActionInput]:
        """Get valid placeable actions from PlaceableArea definitions."""
        scale, x_offset, y_offset = self.camera._calculate_scale_and_offset()
        valid_actions: list[ActionInput] = []

        for area in self.current_level.placeable_areas:
            for y in range(area.y, area.y + area.height, area.y_scale):
                for x in range(area.x, area.x + area.width, area.x_scale):
                    valid_actions.append(ActionInput(
                        id=GameAction.ACTION6,
                        data={"x": x * scale + x_offset, "y": y * scale + y_offset},
                    ))

        return valid_actions

    def _get_valid_clickable_actions(self) -> list[ActionInput]:
        """Get valid click actions from sprites tagged 'sys_click' or 'sys_place'.

        Supports 'sys_every_pixel' tag for per-pixel clickability.
        """
        valid_actions: list[ActionInput] = []

        clickable = self.current_level.get_sprites_by_tag("sys_click")
        clickable.extend(self.current_level.get_sprites_by_tag("sys_place"))

        scale, x_offset, y_offset = self.camera._calculate_scale_and_offset()

        for sprite in clickable:
            if not self._is_sprite_clickable_now(sprite):
                continue

            has_every_pixel = "sys_every_pixel" in sprite.tags
            rendered = sprite.render()

            if has_every_pixel:
                for y in range(rendered.shape[0]):
                    for x in range(rendered.shape[1]):
                        if rendered[y, x] >= 0:
                            screen_x = (sprite.x + x) * scale + x_offset
                            screen_y = (sprite.y + y) * scale + y_offset
                            valid_actions.append(ActionInput(
                                id=GameAction.ACTION6,
                                data={"x": screen_x, "y": screen_y},
                            ))
            else:
                # Single representative pixel per sprite
                for y in range(rendered.shape[0]):
                    for x in range(rendered.shape[1]):
                        if rendered[y, x] >= 0:
                            screen_x = (sprite.x + x) * scale + x_offset
                            screen_y = (sprite.y + y) * scale + y_offset
                            valid_actions.append(ActionInput(
                                id=GameAction.ACTION6,
                                data={"x": screen_x, "y": screen_y},
                            ))
                            break
                    else:
                        continue
                    break

        return valid_actions

    def _is_sprite_clickable_now(self, sprite: Sprite) -> bool:
        """Override to add context-dependent clickability logic.

        By default all sys_click sprites are always clickable.
        Override in games where clickability depends on game state.
        """
        return True
