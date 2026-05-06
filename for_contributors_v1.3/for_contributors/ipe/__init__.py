"""
ipe — Turn-based puzzle game framework.

64x64 pixel output, 16-color palette, 7 standard actions,
sprite-based rendering with camera auto-scaling.

Usage:
    from ipe import BaseGame, Camera, GameAction, Level, Sprite
"""

from .enums import (
    BlockingMode,
    InteractionMode,
    GameState,
    GameAction,
    SimpleAction,
    ComplexAction,
    ActionInput,
    FrameData,
    FrameDataRaw,
    PlaceableArea,
    CATEGORY,
    MAX_DIMENSION,
    MAX_FRAME_PER_ACTION,
)
from .palette import (
    PALETTE_RGB,
    PALETTE_HEX,
    COLOR_NAMES,
    COLOR_CHARS,
    CHAR_TO_COLOR,
)
from .sprites import Sprite
from .level import Level
from .camera import Camera
from .interfaces import RenderableUserDisplay, ToggleableUserDisplay
from .base_game import BaseGame
from .rendering import (
    render_ascii_64,
    render_png_64,
    frame_hash,
    frames_equal,
    frame_diff,
    ascii_to_frame,
    validate_frame,
    make_empty_frame,
    clone_frame,
    # UI helpers
    stamp_target_box,
    stamp_state_box,
    stamp_step_bar,
    stamp_progress_bar,
    stamp_label_row,
    stamp_mini_grid,
    stamp_separator,
)
from .mechanics import (
    BlockRole,
    MechanicType,
    RulePhase,
    RuleCategory,
    Rule,
    MechanicSpec,
    GameMechanics,
)
from .rules import (
    ValidationResult,
    RuleValidator,
    RuntimeRuleTracker,
    verify_level_with_mechanics,
)

__version__ = "2.0.0"
__all__ = [
    # Enums
    "BlockingMode", "InteractionMode", "GameState", "GameAction",
    "SimpleAction", "ComplexAction", "ActionInput",
    "FrameData", "FrameDataRaw", "PlaceableArea",
    # Core classes
    "Sprite", "Level", "Camera", "BaseGame",
    # Interfaces
    "RenderableUserDisplay", "ToggleableUserDisplay",
    # Palette
    "PALETTE_RGB", "PALETTE_HEX", "COLOR_NAMES", "COLOR_CHARS", "CHAR_TO_COLOR",
    # Rendering + UI helpers
    "render_ascii_64", "render_png_64",
    "frame_hash", "frames_equal", "frame_diff", "ascii_to_frame",
    "validate_frame", "make_empty_frame", "clone_frame",
    "stamp_target_box", "stamp_state_box", "stamp_step_bar",
    "stamp_progress_bar", "stamp_label_row", "stamp_mini_grid", "stamp_separator",
    # Constants
    "MAX_DIMENSION", "MAX_FRAME_PER_ACTION",
    # Mechanics & Rules
    "BlockRole", "MechanicType", "RulePhase", "RuleCategory",
    "Rule", "MechanicSpec", "GameMechanics",
    "ValidationResult", "RuleValidator", "RuntimeRuleTracker",
    "verify_level_with_mechanics",
]
