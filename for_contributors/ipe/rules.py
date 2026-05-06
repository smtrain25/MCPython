"""
rules.py — Validation pipeline and runtime tracking for mechanics rules.

RuleValidator: checks placement + introduction rules against a Level.
RuntimeRuleTracker: tracks interaction compliance during gameplay.
verify_level_with_mechanics: convenience combining validation + BFS solvability.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .mechanics import (
    GameMechanics,
    MechanicSpec,
    Rule,
    RuleCategory,
    RulePhase,
)
from .utils import manhattan, chebyshev

if TYPE_CHECKING:
    from .level import Level
    from .base_game import BaseGame
    from .solver import BFSSolver


# ---------------------------------------------------------------------------
# Validation Result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def merge(self, other: ValidationResult) -> ValidationResult:
        return ValidationResult(
            valid=self.valid and other.valid,
            errors=self.errors + other.errors,
            warnings=self.warnings + other.warnings,
        )


# ---------------------------------------------------------------------------
# Rule Validator — placement + introduction rules
# ---------------------------------------------------------------------------

class RuleValidator:
    """Validates a Level against a GameMechanics specification.

    Usage::

        validator = RuleValidator(game_mechanics)
        result = validator.validate_level(level, level_index=0)
    """

    def __init__(self, mechanics: GameMechanics):
        self.mechanics = mechanics

    # -- public API --------------------------------------------------------

    def validate_level(self, level: Level, level_index: int) -> ValidationResult:
        result = ValidationResult()

        for rule in self.mechanics.get_placement_rules(level_index):
            ctx = self._build_context(rule, level, level_index)
            if rule.condition and not rule.condition(ctx):
                continue
            r = self._check_placement_rule(rule, level)
            result = result.merge(r)

        for rule in self.mechanics.get_introduction_rules(level_index):
            ctx = self._build_context(rule, level, level_index)
            if rule.condition and not rule.condition(ctx):
                continue
            r = self._check_introduction_rule(rule, level)
            result = result.merge(r)

        return result

    # -- context building --------------------------------------------------

    def _build_context(
        self, rule: Rule, level: Level, level_index: int,
    ) -> dict[str, Any]:
        """Build the context dict passed to rule conditions."""
        spec = self.mechanics.get_spec(rule.mechanic_name)
        count = 0
        if spec:
            count = len(level.get_sprites_by_tag(spec.mechanic_type.tag))
        return {
            "count": count,
            "level_index": level_index,
            "mechanic_name": rule.mechanic_name,
        }

    # -- placement dispatch ------------------------------------------------

    _PLACEMENT_HANDLERS: dict[RuleCategory, str] = {
        RuleCategory.PLACEMENT_COUNT: "_check_count",
        RuleCategory.PLACEMENT_POSITION: "_check_position",
        RuleCategory.PLACEMENT_PROXIMITY: "_check_proximity",
        RuleCategory.PLACEMENT_PAIRING: "_check_pairing",
        RuleCategory.PLACEMENT_REGION: "_check_region",
        RuleCategory.PLACEMENT_SYMMETRY: "_check_symmetry",
    }

    def _check_placement_rule(self, rule: Rule, level: Level) -> ValidationResult:
        handler_name = self._PLACEMENT_HANDLERS.get(rule.category)
        if handler_name:
            handler = getattr(self, handler_name)
            return handler(rule, level)
        return ValidationResult()

    # -- placement handlers ------------------------------------------------

    def _check_count(self, rule: Rule, level: Level) -> ValidationResult:
        spec = self.mechanics.get_spec(rule.mechanic_name)
        if not spec:
            return ValidationResult()
        count = len(level.get_sprites_by_tag(spec.mechanic_type.tag))
        min_count = rule.params.get("min", 0)
        max_count = rule.params.get("max")
        errors: list[str] = []
        if count < min_count:
            errors.append(
                f"[{rule.mechanic_name}] PLACEMENT_COUNT: found {count}, "
                f"need at least {min_count}"
            )
        if max_count is not None and count > max_count:
            errors.append(
                f"[{rule.mechanic_name}] PLACEMENT_COUNT: found {count}, "
                f"max allowed is {max_count}"
            )
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _check_position(self, rule: Rule, level: Level) -> ValidationResult:
        spec = self.mechanics.get_spec(rule.mechanic_name)
        if not spec:
            return ValidationResult()
        sprites = level.get_sprites_by_tag(spec.mechanic_type.tag)
        mode = rule.params.get("mode", "random")
        errors: list[str] = []

        if mode == "fixed":
            fixed = rule.params.get("fixed_positions", [])
            positions = {(s.x, s.y) for s in sprites}
            for pos in fixed:
                if tuple(pos) not in positions:
                    errors.append(
                        f"[{rule.mechanic_name}] PLACEMENT_POSITION: "
                        f"expected sprite at {pos}"
                    )
        elif mode == "confined":
            region = rule.params.get("region")
            if region:
                rx, ry, rw, rh = region
                for s in sprites:
                    if not (rx <= s.x < rx + rw and ry <= s.y < ry + rh):
                        errors.append(
                            f"[{rule.mechanic_name}] PLACEMENT_POSITION: "
                            f"sprite at ({s.x},{s.y}) outside confined "
                            f"region {region}"
                        )
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _check_proximity(self, rule: Rule, level: Level) -> ValidationResult:
        spec = self.mechanics.get_spec(rule.mechanic_name)
        if not spec:
            return ValidationResult()
        target_name = rule.params.get("target", "")
        target_spec = self.mechanics.get_spec(target_name)
        if not target_spec:
            return ValidationResult()

        sprites_a = level.get_sprites_by_tag(spec.mechanic_type.tag)
        sprites_b = level.get_sprites_by_tag(target_spec.mechanic_type.tag)
        min_dist = rule.params.get("min_distance", 0)
        max_dist = rule.params.get("max_distance", float("inf"))
        metric_name = rule.params.get("metric", "manhattan")
        metric_fn = manhattan if metric_name == "manhattan" else chebyshev

        errors: list[str] = []
        for sa in sprites_a:
            for sb in sprites_b:
                dist = metric_fn((sa.x, sa.y), (sb.x, sb.y))
                if dist < min_dist:
                    errors.append(
                        f"[{rule.mechanic_name}] PROXIMITY: ({sa.x},{sa.y})"
                        f"↔({sb.x},{sb.y}) distance {dist} < min {min_dist}"
                    )
                if dist > max_dist:
                    errors.append(
                        f"[{rule.mechanic_name}] PROXIMITY: ({sa.x},{sa.y})"
                        f"↔({sb.x},{sb.y}) distance {dist} > max {max_dist}"
                    )
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _check_pairing(self, rule: Rule, level: Level) -> ValidationResult:
        spec = self.mechanics.get_spec(rule.mechanic_name)
        partner_name = rule.params.get("partner", "")
        partner_spec = self.mechanics.get_spec(partner_name)
        if not spec or not partner_spec:
            return ValidationResult()

        count_a = len(level.get_sprites_by_tag(spec.mechanic_type.tag))
        count_b = len(level.get_sprites_by_tag(partner_spec.mechanic_type.tag))
        ratio = rule.params.get("ratio", (1, 1))

        errors: list[str] = []
        if count_b > 0 and count_a * ratio[1] != count_b * ratio[0]:
            errors.append(
                f"[{rule.mechanic_name}] PAIRING: {count_a}:{count_b} "
                f"doesn't match ratio {ratio[0]}:{ratio[1]}"
            )
        elif count_b == 0 and count_a > 0:
            errors.append(
                f"[{rule.mechanic_name}] PAIRING: has {count_a} but "
                f"partner '{partner_name}' has 0"
            )
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _check_region(self, rule: Rule, level: Level) -> ValidationResult:
        spec = self.mechanics.get_spec(rule.mechanic_name)
        if not spec:
            return ValidationResult()
        region = rule.params.get("region")
        if not region:
            return ValidationResult()

        sprites = level.get_sprites_by_tag(spec.mechanic_type.tag)
        rx, ry, rw, rh = region
        errors: list[str] = []
        for s in sprites:
            if not (rx <= s.x < rx + rw and ry <= s.y < ry + rh):
                errors.append(
                    f"[{rule.mechanic_name}] REGION: sprite at ({s.x},{s.y}) "
                    f"outside required region"
                )
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _check_symmetry(self, rule: Rule, level: Level) -> ValidationResult:
        # Stub — logs warning, ready for future implementation
        warnings.warn(
            f"[{rule.mechanic_name}] PLACEMENT_SYMMETRY: not yet implemented",
            stacklevel=2,
        )
        return ValidationResult(warnings=[
            f"[{rule.mechanic_name}] PLACEMENT_SYMMETRY check skipped (not implemented)"
        ])

    # -- introduction dispatch ---------------------------------------------

    _INTRODUCTION_HANDLERS: dict[RuleCategory, str] = {
        RuleCategory.FORCED_INTERACTION: "_check_forced_interaction",
        RuleCategory.CONFINED_CELL: "_check_confined_cell",
        RuleCategory.RELATED_PLACEMENT: "_check_related_placement",
    }

    def _check_introduction_rule(self, rule: Rule, level: Level) -> ValidationResult:
        handler_name = self._INTRODUCTION_HANDLERS.get(rule.category)
        if handler_name:
            handler = getattr(self, handler_name)
            return handler(rule, level)
        return ValidationResult()

    # -- introduction handlers ---------------------------------------------

    def _check_forced_interaction(self, rule: Rule, level: Level) -> ValidationResult:
        spec = self.mechanics.get_spec(rule.mechanic_name)
        if not spec:
            return ValidationResult()

        mechanic_sprites = level.get_sprites_by_tag(spec.mechanic_type.tag)
        agent_sprites = level.get_sprites_by_tag("mech_agent")
        errors: list[str] = []

        if not mechanic_sprites:
            errors.append(
                f"[{rule.mechanic_name}] FORCED_INTERACTION: no "
                f"'{spec.mechanic_type.tag}' sprites in introduction level"
            )
            return ValidationResult(valid=False, errors=errors)

        if not agent_sprites:
            errors.append(
                f"[{rule.mechanic_name}] FORCED_INTERACTION: no agent sprite found"
            )
            return ValidationResult(valid=False, errors=errors)

        region = rule.params.get("confined_region")
        if region:
            rx, ry, rw, rh = region
            agent = agent_sprites[0]

            if not (rx <= agent.x < rx + rw and ry <= agent.y < ry + rh):
                errors.append(
                    f"[{rule.mechanic_name}] FORCED_INTERACTION: agent at "
                    f"({agent.x},{agent.y}) not in confined region {region}"
                )

            # At least one mechanic sprite must be in the confined region
            if not any(
                rx <= ms.x < rx + rw and ry <= ms.y < ry + rh
                for ms in mechanic_sprites
            ):
                errors.append(
                    f"[{rule.mechanic_name}] FORCED_INTERACTION: no mechanic "
                    f"sprite found inside confined region {region}"
                )

            if rule.params.get("non_overlapping", True):
                positions: set[tuple[int, int]] = set()
                all_sprites = list(agent_sprites) + list(mechanic_sprites)
                for s in all_sprites:
                    pos = (s.x, s.y)
                    if pos in positions:
                        errors.append(
                            f"[{rule.mechanic_name}] FORCED_INTERACTION: "
                            f"overlapping sprites at {pos}"
                        )
                    positions.add(pos)

        # Check related blocks inside cell
        for related_name in rule.params.get("related_inside", []):
            related_spec = self.mechanics.get_spec(related_name)
            if not related_spec:
                continue
            related_sprites = level.get_sprites_by_tag(related_spec.mechanic_type.tag)
            if not related_sprites:
                errors.append(
                    f"[{rule.mechanic_name}] FORCED_INTERACTION: related "
                    f"'{related_name}' not found in level"
                )
            elif region:
                rx, ry, rw, rh = region
                if not any(
                    rx <= s.x < rx + rw and ry <= s.y < ry + rh
                    for s in related_sprites
                ):
                    errors.append(
                        f"[{rule.mechanic_name}] FORCED_INTERACTION: "
                        f"'{related_name}' must have at least one sprite "
                        f"inside confined region"
                    )

        # Check related blocks outside cell
        for related_name in rule.params.get("related_outside", []):
            related_spec = self.mechanics.get_spec(related_name)
            if not related_spec:
                continue
            related_sprites = level.get_sprites_by_tag(related_spec.mechanic_type.tag)
            if region:
                rx, ry, rw, rh = region
                if not any(
                    not (rx <= s.x < rx + rw and ry <= s.y < ry + rh)
                    for s in related_sprites
                ):
                    errors.append(
                        f"[{rule.mechanic_name}] FORCED_INTERACTION: "
                        f"'{related_name}' must have at least one sprite "
                        f"outside confined region"
                    )

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _check_confined_cell(self, rule: Rule, level: Level) -> ValidationResult:
        region = rule.params.get("region")
        mechanic_names = rule.params.get("mechanics", [rule.mechanic_name])
        if not region:
            return ValidationResult()

        rx, ry, rw, rh = region
        errors: list[str] = []
        for name in mechanic_names:
            spec = self.mechanics.get_spec(name)
            if not spec:
                continue
            for s in level.get_sprites_by_tag(spec.mechanic_type.tag):
                if not (rx <= s.x < rx + rw and ry <= s.y < ry + rh):
                    errors.append(
                        f"[{name}] CONFINED_CELL: sprite at ({s.x},{s.y}) "
                        f"outside confined region"
                    )
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _check_related_placement(self, rule: Rule, level: Level) -> ValidationResult:
        # Flexible version of forced_interaction's related checks
        region = rule.params.get("region")
        if not region:
            return ValidationResult()

        rx, ry, rw, rh = region
        errors: list[str] = []

        for name in rule.params.get("inside", []):
            spec = self.mechanics.get_spec(name)
            if not spec:
                continue
            sprites = level.get_sprites_by_tag(spec.mechanic_type.tag)
            if not any(rx <= s.x < rx + rw and ry <= s.y < ry + rh for s in sprites):
                errors.append(
                    f"[{rule.mechanic_name}] RELATED_PLACEMENT: '{name}' "
                    f"must have sprite inside region"
                )

        for name in rule.params.get("outside", []):
            spec = self.mechanics.get_spec(name)
            if not spec:
                continue
            sprites = level.get_sprites_by_tag(spec.mechanic_type.tag)
            if not any(
                not (rx <= s.x < rx + rw and ry <= s.y < ry + rh)
                for s in sprites
            ):
                errors.append(
                    f"[{rule.mechanic_name}] RELATED_PLACEMENT: '{name}' "
                    f"must have sprite outside region"
                )

        return ValidationResult(valid=len(errors) == 0, errors=errors)


# ---------------------------------------------------------------------------
# Runtime Rule Tracker — interaction compliance during gameplay
# ---------------------------------------------------------------------------

class RuntimeRuleTracker:
    """Tracks runtime rule satisfaction during gameplay.

    Instantiated per-level in ``on_set_level()``.
    Updated in ``step()`` via ``record_interaction()`` and ``record_step()``.
    """

    def __init__(self, rules: list[Rule]):
        self._rules = rules
        self._interaction_counts: dict[str, int] = {}
        self._interaction_sequence: list[str] = []
        self._carried_items: list[str] = []
        self._step_count: int = 0
        self._timers: dict[str, int] = {}       # sprite_id → steps remaining
        self._cooldowns: dict[str, int] = {}     # mechanic_name → steps until usable

    def record_interaction(self, mechanic_name: str) -> None:
        self._interaction_counts[mechanic_name] = (
            self._interaction_counts.get(mechanic_name, 0) + 1
        )
        self._interaction_sequence.append(mechanic_name)

    def record_step(self) -> list[str]:
        """Tick timers. Returns list of expired sprite IDs for removal."""
        self._step_count += 1

        # Tick cooldowns
        for name in list(self._cooldowns):
            self._cooldowns[name] -= 1
            if self._cooldowns[name] <= 0:
                del self._cooldowns[name]

        # Tick decay timers
        expired: list[str] = []
        for sprite_id in list(self._timers):
            self._timers[sprite_id] -= 1
            if self._timers[sprite_id] <= 0:
                expired.append(sprite_id)
                del self._timers[sprite_id]

        return expired

    def start_timer(self, sprite_id: str, steps: int) -> None:
        self._timers[sprite_id] = steps

    def start_cooldown(self, mechanic_name: str, steps: int) -> None:
        self._cooldowns[mechanic_name] = steps

    def is_on_cooldown(self, mechanic_name: str) -> bool:
        return mechanic_name in self._cooldowns

    def pickup_item(self, item_name: str) -> None:
        self._carried_items.append(item_name)

    def drop_item(self, item_name: str) -> None:
        if item_name in self._carried_items:
            self._carried_items.remove(item_name)

    def check_runtime_rules(self) -> ValidationResult:
        """Check all runtime rules. Errors = violated, warnings = not yet met."""
        errors: list[str] = []
        rule_warnings: list[str] = []

        for rule in self._rules:
            if rule.category == RuleCategory.INTERACTION_REQUIRED:
                min_req = rule.params.get("min_interactions", 0)
                count = self._interaction_counts.get(rule.mechanic_name, 0)
                if count < min_req:
                    rule_warnings.append(
                        f"[{rule.mechanic_name}] needs {min_req} "
                        f"interactions, has {count}"
                    )

            elif rule.category == RuleCategory.INTERACTION_SEQUENCE:
                required_order = rule.params.get("order", [])
                if not _is_subsequence(required_order, self._interaction_sequence):
                    errors.append(
                        f"[{rule.mechanic_name}] SEQUENCE: interactions "
                        f"not in required order {required_order}"
                    )

            elif rule.category == RuleCategory.INTERACTION_CAPACITY:
                max_carry = rule.params.get("max", 1)
                if len(self._carried_items) > max_carry:
                    errors.append(
                        f"[{rule.mechanic_name}] CAPACITY: carrying "
                        f"{len(self._carried_items)} > max {max_carry}"
                    )

            elif rule.category in (
                RuleCategory.VISIBILITY_HIDDEN,
                RuleCategory.MEMORY_REQUIRED,
                RuleCategory.PATTERN_MATCH,
                RuleCategory.TRIGGER_EFFECT,
                RuleCategory.CHAIN_REACTION,
            ):
                # Stub categories — log warning
                rule_warnings.append(
                    f"[{rule.mechanic_name}] {rule.category.name}: "
                    f"runtime check not yet implemented"
                )

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=rule_warnings,
        )

    def are_runtime_goals_met(self) -> bool:
        """Check if all interaction requirements are satisfied (for win gating)."""
        for rule in self._rules:
            if rule.category == RuleCategory.INTERACTION_REQUIRED:
                min_req = rule.params.get("min_interactions", 0)
                count = self._interaction_counts.get(rule.mechanic_name, 0)
                if count < min_req:
                    return False
        return True

    @property
    def interaction_counts(self) -> dict[str, int]:
        return dict(self._interaction_counts)

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def carried_items(self) -> list[str]:
        return list(self._carried_items)


# ---------------------------------------------------------------------------
# Convenience: full verification (placement + solvability)
# ---------------------------------------------------------------------------

def verify_level_with_mechanics(
    env: BaseGame,
    mechanics: GameMechanics,
    level_index: int,
    solver: BFSSolver,
) -> ValidationResult:
    """Placement validation + BFS solvability check.

    1. Check all placement and introduction rules.
    2. Run BFS solver to verify solvability.
    3. Return combined result.
    """
    validator = RuleValidator(mechanics)
    result = validator.validate_level(env.current_level, level_index)

    if not result.valid:
        return result

    solver_result = solver.solve(env)
    if not solver_result.solvable:
        result = result.merge(ValidationResult(
            valid=False,
            errors=[f"Level is not solvable: {solver_result.notes}"],
        ))

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_subsequence(required: list[str], actual: list[str]) -> bool:
    it = iter(actual)
    return all(item in it for item in required)
