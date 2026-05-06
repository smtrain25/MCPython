"""
enums.py — Core enums, data models, and action types.
Pydantic-validated where data crosses trust boundaries.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Literal, Optional, Type, Union

from pydantic import BaseModel, Field, PrivateAttr, field_validator

MAX_DIMENSION = 64
MAX_FRAME_PER_ACTION = 1000
MAX_REASONING_BYTES = 16 * 1024  # 16 KB guard-rail

CATEGORY = Literal["agentic", "non_agentic", "orchestration"]


# ---------------------------------------------------------------------------
# Collision & Interaction
# ---------------------------------------------------------------------------

class BlockingMode(Enum):
    NOT_BLOCKED = auto()
    BOUNDING_BOX = auto()
    PIXEL_PERFECT = auto()


class InteractionMode(Enum):
    TANGIBLE = auto()
    INTANGIBLE = auto()
    INVISIBLE = auto()
    REMOVED = auto()


# ---------------------------------------------------------------------------
# Game State
# ---------------------------------------------------------------------------

class GameState(str, Enum):
    NOT_PLAYED = "NOT_PLAYED"
    NOT_FINISHED = "NOT_FINISHED"
    WIN = "WIN"
    GAME_OVER = "GAME_OVER"


# ---------------------------------------------------------------------------
# Action Types (Pydantic validated)
# ---------------------------------------------------------------------------

class SimpleAction(BaseModel):
    """Action data for simple (no-payload) actions."""
    game_id: str = ""


class ComplexAction(BaseModel):
    """Action data for ACTION6 (click/place) — requires x,y in 0–63."""
    game_id: str = ""
    x: int = Field(0, ge=0, le=63)
    y: int = Field(0, ge=0, le=63)


class GameAction(Enum):
    """
    Seven standard actions + RESET.

    Keybindings:
      W / Up    = ACTION1    S / Down  = ACTION2
      A / Left  = ACTION3    D / Right = ACTION4
      Space / F = ACTION5    Click     = ACTION6 (x,y)
      Ctrl+Z    = ACTION7    R         = RESET
    """
    RESET   = (0, SimpleAction)
    ACTION1 = (1, SimpleAction)
    ACTION2 = (2, SimpleAction)
    ACTION3 = (3, SimpleAction)
    ACTION4 = (4, SimpleAction)
    ACTION5 = (5, SimpleAction)
    ACTION6 = (6, ComplexAction)
    ACTION7 = (7, SimpleAction)

    action_type: Union[Type[SimpleAction], Type[ComplexAction]]

    def __init__(
        self,
        action_id: int,
        action_type: Union[Type[SimpleAction], Type[ComplexAction]],
    ) -> None:
        self._value_ = action_id
        self.action_type = action_type

    def __reduce_ex__(self, protocol):
        """Make pickle work by reconstructing from name."""
        return (self.__class__.__getitem__, (self._name_,))

    def is_complex(self) -> bool:
        return self.action_type is ComplexAction

    def is_simple(self) -> bool:
        return not self.is_complex()

    def validate_data(self, data: dict[str, Any]) -> bool:
        """Raise on invalid data for this action type."""
        self.action_type.model_validate(data)
        return True

    @classmethod
    def from_id(cls, action_id: int) -> GameAction:
        for action in cls:
            if action.value == action_id:
                return action
        raise ValueError(f"No GameAction with id {action_id}")

    @classmethod
    def from_name(cls, name: str) -> GameAction:
        try:
            return cls[name.upper()]
        except KeyError:
            raise ValueError(f"No GameAction with name '{name}'")

    @classmethod
    def all_simple(cls) -> list[GameAction]:
        return [a for a in cls if a.is_simple()]

    @classmethod
    def all_complex(cls) -> list[GameAction]:
        return [a for a in cls if a.is_complex()]


# ---------------------------------------------------------------------------
# Action Input (Pydantic validated)
# ---------------------------------------------------------------------------

class ActionInput(BaseModel):
    """An action submitted to the game engine."""
    id: GameAction = GameAction.RESET
    data: dict[str, Any] = {}
    reasoning: Optional[Any] = Field(
        default=None,
        description="Opaque client blob; stored and echoed back verbatim.",
    )

    @field_validator("reasoning")
    @classmethod
    def _check_reasoning(cls, v: Any) -> Any:
        if v is None:
            return v
        try:
            raw = json.dumps(v, separators=(",", ":")).encode("utf-8")
        except (TypeError, ValueError):
            raise ValueError("reasoning must be JSON-serialisable")
        if len(raw) > MAX_REASONING_BYTES:
            raise ValueError(f"reasoning exceeds {MAX_REASONING_BYTES} bytes")
        return v

    def get_x(self) -> int:
        return self.data.get("x", 0)

    def get_y(self) -> int:
        return self.data.get("y", 0)


# ---------------------------------------------------------------------------
# Frame Data (Pydantic validated)
# ---------------------------------------------------------------------------

class FrameData(BaseModel):
    """Response from perform_action()."""
    game_id: str = ""
    frame: list[list[list[int]]] = []
    state: GameState = GameState.NOT_PLAYED
    levels_completed: int = Field(0, ge=0, le=254)
    win_levels: int = Field(0, ge=0, le=254)
    action_input: ActionInput = Field(default_factory=lambda: ActionInput())
    full_reset: bool = False
    available_actions: list[int] = []
    # Extensions for text/visual agents
    text_observation: str = ""
    image_observation: bytes = b""

    model_config = {"arbitrary_types_allowed": True}

    def is_empty(self) -> bool:
        return len(self.frame) == 0


class FrameDataRaw(BaseModel):
    """FrameData with numpy arrays instead of lists."""
    game_id: str = ""
    state: GameState = GameState.NOT_PLAYED
    levels_completed: int = 0
    win_levels: int = 0
    action_input: ActionInput = Field(default_factory=ActionInput)
    full_reset: bool = False
    available_actions: list[int] = Field(default_factory=list)
    _frame: list = PrivateAttr(default_factory=list)

    @property
    def frame(self) -> list:
        return self._frame

    @frame.setter
    def frame(self, value: list) -> None:
        self._frame = value

    def is_empty(self) -> bool:
        return len(self._frame) == 0


# ---------------------------------------------------------------------------
# Placeable Area
# ---------------------------------------------------------------------------

class PlaceableArea:
    """Defines a grid-aligned area where sprites can be placed."""
    def __init__(
        self,
        x: int = 0, y: int = 0,
        width: int = 0, height: int = 0,
        x_scale: int = 1, y_scale: int = 1,
    ):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.x_scale = x_scale
        self.y_scale = y_scale
