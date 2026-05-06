"""
mechanics.py — Data-driven mechanics and rules system.

Defines what block types ARE (MechanicType), what constraints govern them (Rule),
and how they compose into game specifications (MechanicSpec, GameMechanics).

Usage:
    from .mechanics import (
        BlockRole, MechanicType, RulePhase, RuleCategory,
        Rule, MechanicSpec, GameMechanics,
    )

    portal = MechanicSpec(
        mechanic_type=MechanicType("portal", BlockRole.PORTAL, color=8),
        rules=[
            Rule(RuleCategory.PLACEMENT_COUNT, RulePhase.PLACEMENT, "portal",
                 params={"min": 2, "max": 2}),
        ],
    )
    mechanics = GameMechanics(specs=[portal])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Block Role — semantic role a block type plays in the game
# ---------------------------------------------------------------------------

class BlockRole(Enum):
    AGENT       = auto()
    GOAL        = auto()
    WALL        = auto()
    HAZARD      = auto()
    PORTAL      = auto()
    KEY         = auto()
    DOOR        = auto()
    TRANSFORMER = auto()
    RESOURCE    = auto()
    SWITCH      = auto()
    GATE        = auto()
    DECORATION  = auto()
    CUSTOM      = auto()


# ---------------------------------------------------------------------------
# MechanicType — "type card" for a game entity
# ---------------------------------------------------------------------------

@dataclass
class MechanicType:
    """Defines what a block type IS and what intrinsic properties it has.

    Multiple sprites can share a MechanicType (e.g. two portals are both
    MechanicType(role=PORTAL)). Sprites of this type are tagged with ``tag``.
    """
    name: str
    role: BlockRole
    color: int                             # palette index 0-15
    tag: str = ""                          # applied to sprites; auto: "mech_{name}"
    paired_with: str | None = None         # name of paired MechanicType (key→door)
    size: tuple[int, int] = (1, 1)         # default sprite dimensions (w, h)
    collectible: bool = False
    consumable: bool = False
    blocking: bool = True
    description: str = ""

    def __post_init__(self):
        if not self.tag:
            self.tag = f"mech_{self.name}"


# ---------------------------------------------------------------------------
# Rule Phase — when a rule is evaluated
# ---------------------------------------------------------------------------

class RulePhase(Enum):
    PLACEMENT     = auto()   # during level generation
    INTRODUCTION  = auto()   # when mechanic first appears in curriculum
    RUNTIME       = auto()   # during gameplay (step-by-step)
    VALIDATION    = auto()   # post-generation verification


# ---------------------------------------------------------------------------
# Rule Category — what kind of constraint
# ---------------------------------------------------------------------------

class RuleCategory(Enum):
    # Spatial / Placement
    PLACEMENT_COUNT      = auto()
    PLACEMENT_POSITION   = auto()
    PLACEMENT_PROXIMITY  = auto()
    PLACEMENT_PAIRING    = auto()
    PLACEMENT_REGION     = auto()
    PLACEMENT_SYMMETRY   = auto()

    # Introduction / Teaching
    FORCED_INTERACTION   = auto()
    CONFINED_CELL        = auto()
    RELATED_PLACEMENT    = auto()

    # Runtime / Interaction
    INTERACTION_REQUIRED = auto()
    INTERACTION_SEQUENCE = auto()
    INTERACTION_CAPACITY = auto()

    # Temporal
    TIMER_DECAY          = auto()
    DELAYED_EFFECT       = auto()
    COOLDOWN             = auto()

    # Information
    VISIBILITY_HIDDEN    = auto()
    MEMORY_REQUIRED      = auto()
    PATTERN_MATCH        = auto()

    # Causality
    TRIGGER_EFFECT       = auto()
    CHAIN_REACTION       = auto()


# ---------------------------------------------------------------------------
# Rule — universal constraint container
# ---------------------------------------------------------------------------

@dataclass
class Rule:
    """A single constraint on a mechanic.

    Parameters
    ----------
    category : RuleCategory
        What kind of constraint.
    phase : RulePhase
        When the rule is evaluated.
    mechanic_name : str
        Which MechanicType this applies to (by name).
    params : dict
        Category-specific parameters (see taxonomy in plan).
    description : str
        Human-readable explanation.
    condition : callable or None
        Optional guard — receives a context dict (``{"count": N,
        "level_index": M, ...}``) and returns bool. Rule is skipped
        when condition returns False.
    priority : int
        Higher = checked first.
    """
    category: RuleCategory
    phase: RulePhase
    mechanic_name: str
    params: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    condition: Callable[[dict[str, Any]], bool] | None = None
    priority: int = 0


# ---------------------------------------------------------------------------
# MechanicSpec — bundled mechanic definition
# ---------------------------------------------------------------------------

@dataclass
class MechanicSpec:
    """Complete specification of a game mechanic: type + rules.

    Parameters
    ----------
    mechanic_type : MechanicType
        The block type definition.
    rules : list[Rule]
        All constraints for this mechanic.
    introduction_level : int
        First level index where this mechanic appears.
    required_after_intro : bool
        If True, mechanic must appear in all levels after introduction.
    """
    mechanic_type: MechanicType
    rules: list[Rule] = field(default_factory=list)
    introduction_level: int = 0
    required_after_intro: bool = True

    def get_rules_by_phase(self, phase: RulePhase) -> list[Rule]:
        return [r for r in self.rules if r.phase == phase]

    def get_rules_by_category(self, category: RuleCategory) -> list[Rule]:
        return [r for r in self.rules if r.category == category]


# ---------------------------------------------------------------------------
# GameMechanics — top-level container for all mechanics in a game
# ---------------------------------------------------------------------------

@dataclass
class GameMechanics:
    """All mechanics for a game. Passed to level generator and validator."""

    specs: list[MechanicSpec] = field(default_factory=list)
    global_rules: list[Rule] = field(default_factory=list)

    def get_spec(self, name: str) -> MechanicSpec | None:
        for spec in self.specs:
            if spec.mechanic_type.name == name:
                return spec
        return None

    def get_active_specs(self, level_index: int) -> list[MechanicSpec]:
        """Mechanics active at a given level (introduced at or before it)."""
        return [s for s in self.specs if s.introduction_level <= level_index]

    def get_placement_rules(self, level_index: int) -> list[Rule]:
        rules: list[Rule] = []
        for spec in self.get_active_specs(level_index):
            rules.extend(spec.get_rules_by_phase(RulePhase.PLACEMENT))
        rules.extend(r for r in self.global_rules if r.phase == RulePhase.PLACEMENT)
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    def get_introduction_rules(self, level_index: int) -> list[Rule]:
        """Rules for mechanics introduced at exactly this level."""
        rules: list[Rule] = []
        for spec in self.specs:
            if spec.introduction_level == level_index:
                rules.extend(spec.get_rules_by_phase(RulePhase.INTRODUCTION))
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    def get_runtime_rules(self, level_index: int) -> list[Rule]:
        rules: list[Rule] = []
        for spec in self.get_active_specs(level_index):
            rules.extend(spec.get_rules_by_phase(RulePhase.RUNTIME))
        rules.extend(r for r in self.global_rules if r.phase == RulePhase.RUNTIME)
        return sorted(rules, key=lambda r: r.priority, reverse=True)

    def get_validation_rules(self, level_index: int) -> list[Rule]:
        rules: list[Rule] = []
        for spec in self.get_active_specs(level_index):
            rules.extend(spec.get_rules_by_phase(RulePhase.VALIDATION))
        rules.extend(r for r in self.global_rules if r.phase == RulePhase.VALIDATION)
        return sorted(rules, key=lambda r: r.priority, reverse=True)
