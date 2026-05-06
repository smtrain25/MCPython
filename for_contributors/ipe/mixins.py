"""
mixins.py — Game mechanic mixins.

FogMixin: Visibility regimes (full, chambers, radius fog, flashlight).
SymbolCarrierMixin: Symbol transport mechanic (transformers, blockers, goals).
MechanicsRuleMixin: Data-driven mechanics rules (validation + runtime tracking).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .palette import PALETTE_RGB, COLOR_CHARS


# =========================================================================
# PART 1: FOG-OF-WAR / VISIBILITY
# =========================================================================

class VisibilityMode(Enum):
    FULL       = "full"
    CHAMBERS   = "chambers"
    RADIUS_FOG = "radius_fog"
    FLASHLIGHT = "flashlight"


def apply_visibility(
    frame: list[list[int]],
    mode: VisibilityMode,
    agent_pos: tuple[int, int] | None = None,
    facing: str | None = None,
    radius: int = 6,
    room_map: list[list[int]] | None = None,
    memory: list[list[int]] | None = None,
    cone_depth: int = 8,
    cone_half_width: int = 3,
    fog_color: int = 0,
) -> list[list[int]]:
    """Apply visibility regime to a frame. Returns a new frame."""
    if mode == VisibilityMode.FULL:
        return [row[:] for row in frame]

    if agent_pos is None:
        raise ValueError("agent_pos required for fog modes")

    if mode == VisibilityMode.CHAMBERS:
        if room_map is None:
            raise ValueError("room_map required for CHAMBERS mode")
        return _apply_chambers(frame, agent_pos, room_map, memory, fog_color)

    if mode == VisibilityMode.RADIUS_FOG:
        return _apply_radius_fog(frame, agent_pos, radius, memory, fog_color)

    if mode == VisibilityMode.FLASHLIGHT:
        if facing is None:
            raise ValueError("facing required for FLASHLIGHT mode")
        return _apply_flashlight(
            frame, agent_pos, facing, cone_depth, cone_half_width, memory, fog_color
        )

    return [row[:] for row in frame]


def _apply_chambers(frame, agent_pos, room_map, memory, fog_color):
    rows = len(frame)
    cols = len(frame[0]) if rows > 0 else 0
    ar, ac = agent_pos
    agent_room = room_map[ar][ac] if (0 <= ar < rows and 0 <= ac < cols) else -1
    result = [[fog_color] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            if room_map[r][c] == agent_room:
                result[r][c] = frame[r][c]
                if memory is not None:
                    memory[r][c] = frame[r][c]
    return result


def _apply_radius_fog(frame, agent_pos, radius, memory, fog_color):
    rows = len(frame)
    cols = len(frame[0]) if rows > 0 else 0
    ar, ac = agent_pos
    result = [[fog_color] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            if abs(r - ar) + abs(c - ac) <= radius:
                result[r][c] = frame[r][c]
                if memory is not None:
                    memory[r][c] = frame[r][c]
    return result


def _apply_flashlight(frame, agent_pos, facing, depth, half_width, memory, fog_color):
    rows = len(frame)
    cols = len(frame[0]) if rows > 0 else 0
    ar, ac = agent_pos
    result = [[fog_color] * cols for _ in range(rows)]

    if 0 <= ar < rows and 0 <= ac < cols:
        result[ar][ac] = frame[ar][ac]
        if memory is not None:
            memory[ar][ac] = frame[ar][ac]

    forward = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
    perp = {"up": (0, 1), "down": (0, -1), "left": (-1, 0), "right": (1, 0)}
    fdr, fdc = forward.get(facing, (-1, 0))
    pdr, pdc = perp.get(facing, (0, 1))

    for d in range(1, depth + 1):
        w = min(d - 1, half_width)
        for offset in range(-w, w + 1):
            r = ar + fdr * d + pdr * offset
            c = ac + fdc * d + pdc * offset
            if 0 <= r < rows and 0 <= c < cols:
                result[r][c] = frame[r][c]
                if memory is not None:
                    memory[r][c] = frame[r][c]

    return result


def build_room_map(
    frame: list[list[int]], wall_colors: set[int] | None = None,
) -> list[list[int]]:
    """Auto-generate a room_map using flood-fill on non-wall cells."""
    if wall_colors is None:
        wall_colors = {0, 5}
    rows = len(frame)
    cols = len(frame[0]) if rows > 0 else 0
    room_map = [[-1] * cols for _ in range(rows)]
    next_room = 0
    for sr in range(rows):
        for sc in range(cols):
            if room_map[sr][sc] != -1 or frame[sr][sc] in wall_colors:
                continue
            room_id = next_room
            next_room += 1
            q = deque([(sr, sc)])
            room_map[sr][sc] = room_id
            while q:
                r, c = q.popleft()
                for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < rows and 0 <= nc < cols:
                        if room_map[nr][nc] == -1 and frame[nr][nc] not in wall_colors:
                            room_map[nr][nc] = room_id
                            q.append((nr, nc))
    return room_map


def make_fog_memory(grid_size: tuple[int, int], fill: int = 0) -> list[list[int]]:
    rows, cols = grid_size
    return [[fill] * cols for _ in range(rows)]


class FogMixin:
    """Mixin for BaseGame subclasses to add fog-of-war.

    Set on your class:
      visibility_mode, fog_radius, fog_cone_depth, fog_cone_width
    """
    visibility_mode: VisibilityMode = VisibilityMode.RADIUS_FOG
    fog_radius: int = 6
    fog_cone_depth: int = 8
    fog_cone_width: int = 3

    def _init_fog(self, grid_size: tuple[int, int]):
        self._fog_memory: list[list[int]] = make_fog_memory(grid_size)
        self._facing: str = "up"
        self._room_map: list[list[int]] | None = None

    def _build_room_map_from_frame(self, frame: list[list[int]]):
        self._room_map = build_room_map(frame)

    def _apply_fog(self, raw_frame: list[list[int]]) -> list[list[int]]:
        agent_pos = getattr(self, "_agent_pos", (0, 0))
        return apply_visibility(
            raw_frame,
            mode=self.visibility_mode,
            agent_pos=agent_pos,
            facing=getattr(self, "_facing", "up"),
            radius=self.fog_radius,
            room_map=getattr(self, "_room_map", None),
            memory=getattr(self, "_fog_memory", None),
            cone_depth=self.fog_cone_depth,
            cone_half_width=self.fog_cone_width,
        )

    def _track_facing(self, action_id: int):
        """Update _facing from directional actions (ACTION1-4)."""
        facing_map = {1: "up", 2: "down", 3: "left", 4: "right"}
        if action_id in facing_map:
            self._facing = facing_map[action_id]


# =========================================================================
# PART 2: SYMBOL TRANSPORT
# =========================================================================

STATE_COLORS: dict[str, int] = {
    "blue": 1, "red": 2, "green": 3, "yellow": 4,
    "gray": 5, "magenta": 6, "orange": 7, "teal": 11,
    "maroon": 10, "pink": 14, "white": 15, "neutral": 13,
}


def state_to_color(state: str) -> int:
    return STATE_COLORS.get(state.lower(), 1)


@dataclass
class Transformer:
    """Grid object that changes the agent's carried symbol state."""
    pos: tuple[int, int]
    input_state: str = "any"
    output_state: str = "red"
    color: int = 6
    size: tuple[int, int] = (3, 3)
    uses: int = -1
    is_decoy: bool = False
    label: str = "M"
    _uses_remaining: int = field(init=False, default=-1)

    def __post_init__(self):
        self._uses_remaining = self.uses

    def can_fire(self, current_state: str) -> bool:
        if self.is_decoy or self._uses_remaining == 0:
            return False
        return self.input_state == "any" or self.input_state == current_state

    def fire(self, current_state: str) -> str:
        if not self.can_fire(current_state):
            return current_state
        if self._uses_remaining > 0:
            self._uses_remaining -= 1
        return self.output_state

    def occupies(self, pos: tuple[int, int]) -> bool:
        r, c = pos
        tr, tc = self.pos
        h, w = self.size
        return tr <= r < tr + h and tc <= c < tc + w

    def reset_uses(self):
        self._uses_remaining = self.uses


@dataclass
class Blocker:
    """Impassable wall that opens when symbol matches required_state."""
    pos: tuple[int, int]
    required_state: str
    size: tuple[int, int] = (1, 3)
    color_locked: int = 5
    color_unlocked: int = 13

    def is_passable(self, current_state: str) -> bool:
        return current_state == self.required_state

    def current_color(self, current_state: str) -> int:
        return self.color_unlocked if self.is_passable(current_state) else self.color_locked

    def occupies(self, pos: tuple[int, int]) -> bool:
        r, c = pos
        tr, tc = self.pos
        h, w = self.size
        return tr <= r < tr + h and tc <= c < tc + w


@dataclass
class SymbolGoal:
    """Goal object. WIN when agent is here with correct symbol state."""
    pos: tuple[int, int]
    required_state: str
    size: tuple[int, int] = (3, 3)
    color: int = 3

    def is_reachable(self, current_state: str) -> bool:
        return current_state == self.required_state

    def occupies(self, pos: tuple[int, int]) -> bool:
        r, c = pos
        tr, tc = self.pos
        h, w = self.size
        return tr <= r < tr + h and tc <= c < tc + w


class SymbolCarrierMixin:
    """Mixin for BaseGame subclasses implementing symbol transport.

    Call _init_symbol_state() from on_set_level().
    Call _apply_symbol_logic(pos) after each movement.
    Call _check_symbol_win() to check WIN condition.
    """

    _symbol_state: str = "neutral"
    _goal_state: str = "green"
    _transformers: list[Transformer] = []
    _blockers: list[Blocker] = []
    _symbol_goal: SymbolGoal | None = None

    def _init_symbol_state(
        self,
        initial_state: str,
        goal_state: str,
        transformers: list[Transformer],
        blockers: list[Blocker] | None = None,
        symbol_goal: SymbolGoal | None = None,
    ):
        self._symbol_state = initial_state
        self._goal_state = goal_state
        self._transformers = list(transformers)
        self._blockers = list(blockers) if blockers else []
        self._symbol_goal = symbol_goal

    def _apply_symbol_logic(self, new_agent_pos: tuple[int, int]) -> bool:
        """Returns True if the move should be blocked."""
        for blocker in self._blockers:
            if blocker.occupies(new_agent_pos):
                if not blocker.is_passable(self._symbol_state):
                    return True
        for transformer in self._transformers:
            if transformer.occupies(new_agent_pos):
                if transformer.can_fire(self._symbol_state):
                    self._symbol_state = transformer.fire(self._symbol_state)
                break
        return False

    def _check_symbol_win(self, agent_pos: tuple[int, int]) -> bool:
        if self._symbol_goal is not None:
            return (
                self._symbol_goal.occupies(agent_pos)
                and self._symbol_goal.is_reachable(self._symbol_state)
            )
        return self._symbol_state == self._goal_state

    def _render_symbol_ui(
        self,
        frame: list[list[int]],
        carried_icon_pos: tuple[int, int] = (1, 1),
        target_icon_pos: tuple[int, int] | None = None,
        icon_size: int = 3,
    ):
        rows = len(frame)
        cols = len(frame[0]) if rows > 0 else 0
        if target_icon_pos is None:
            target_icon_pos = (1, cols - icon_size - 1)
        self._stamp_icon(frame, state_to_color(self._symbol_state), carried_icon_pos, icon_size)
        self._stamp_icon(frame, state_to_color(self._goal_state), target_icon_pos, icon_size)

    def _stamp_icon(self, frame, fill_color, top_left, size):
        rows = len(frame)
        cols = len(frame[0]) if rows > 0 else 0
        tr, tc = top_left
        for dr in range(size):
            for dc in range(size):
                r, c = tr + dr, tc + dc
                if not (0 <= r < rows and 0 <= c < cols):
                    continue
                is_border = dr == 0 or dr == size - 1 or dc == 0 or dc == size - 1
                frame[r][c] = 13 if is_border else fill_color

    def _render_transformers_on_grid(self, frame: list[list[int]]):
        rows = len(frame)
        cols = len(frame[0]) if rows > 0 else 0
        for t in self._transformers:
            tr, tc = t.pos
            h, w = t.size
            color = t.color if (t.is_decoy or t._uses_remaining != 0) else 5
            for dr in range(h):
                for dc in range(w):
                    r, c = tr + dr, tc + dc
                    if 0 <= r < rows and 0 <= c < cols:
                        frame[r][c] = color

    def _render_blockers_on_grid(self, frame: list[list[int]]):
        rows = len(frame)
        cols = len(frame[0]) if rows > 0 else 0
        for b in self._blockers:
            br, bc = b.pos
            h, w = b.size
            color = b.current_color(self._symbol_state)
            for dr in range(h):
                for dc in range(w):
                    r, c = br + dr, bc + dc
                    if 0 <= r < rows and 0 <= c < cols:
                        frame[r][c] = color

    def _snapshot_symbol(self) -> dict:
        return {
            "symbol_state": self._symbol_state,
            "transformer_uses": [t._uses_remaining for t in self._transformers],
        }

    def _restore_symbol(self, snap: dict):
        self._symbol_state = snap.get("symbol_state", self._symbol_state)
        for i, t in enumerate(self._transformers):
            uses = snap.get("transformer_uses", [])
            if i < len(uses):
                t._uses_remaining = uses[i]

    def get_required_transform_chain(self) -> list[str] | None:
        """BFS over symbol state space to find minimum transform sequence."""
        all_states = {self._symbol_state, self._goal_state}
        for t in self._transformers:
            if not t.is_decoy:
                all_states.add(t.input_state)
                all_states.add(t.output_state)

        edges: dict[str, list[tuple[str, int]]] = {s: [] for s in all_states}
        for i, t in enumerate(self._transformers):
            if t.is_decoy:
                continue
            for state in all_states:
                if t.input_state == "any" or t.input_state == state:
                    edges.setdefault(state, []).append((t.output_state, i))

        q = deque([(self._symbol_state, [])])
        visited = {self._symbol_state}
        while q:
            current, path = q.popleft()
            if current == self._goal_state:
                return path
            for next_state, _ in edges.get(current, []):
                if next_state not in visited:
                    visited.add(next_state)
                    q.append((next_state, path + [next_state]))
        return None

    def symbol_state_summary(self) -> str:
        match = "MATCH" if self._symbol_state == self._goal_state else "mismatch"
        return f"Symbol: {self._symbol_state} | Goal: {self._goal_state} | {match}"


# =========================================================================
# PART 3: MECHANICS RULES
# =========================================================================

class MechanicsRuleMixin:
    """Mixin for BaseGame subclasses that use the data-driven mechanics/rules system.

    Integration points::

        # In __init__ or class body:
        self._init_mechanics(game_mechanics)

        # In on_set_level():
        self._setup_level_mechanics(level_index)
        result = self._validate_current_level(level, level_index)

        # In step(), when agent interacts with a mechanic:
        self._record_mechanic_interaction("portal")

        # In step(), each tick:
        expired = self._tick_mechanics()

        # In step(), for win condition:
        if at_goal and self._check_mechanics_win():
            self.next_level()

    Works alongside FogMixin and SymbolCarrierMixin (composable).
    """

    _game_mechanics: Any = None      # GameMechanics | None
    _rule_tracker: Any = None        # RuntimeRuleTracker | None
    _rule_validator: Any = None      # RuleValidator | None

    def _init_mechanics(self, mechanics: Any) -> None:
        """Call once during game setup with a GameMechanics instance."""
        from .mechanics import GameMechanics
        from .rules import RuleValidator
        assert isinstance(mechanics, GameMechanics)
        self._game_mechanics = mechanics
        self._rule_validator = RuleValidator(mechanics)

    def _setup_level_mechanics(self, level_index: int) -> None:
        """Call from on_set_level(). Sets up runtime tracking for this level."""
        if not self._game_mechanics:
            return
        from .rules import RuntimeRuleTracker
        runtime_rules = self._game_mechanics.get_runtime_rules(level_index)
        self._rule_tracker = RuntimeRuleTracker(runtime_rules)

    def _validate_current_level(self, level: Any, level_index: int) -> Any:
        """Validate level against all placement/introduction rules.

        Returns a ValidationResult.
        """
        if not self._rule_validator:
            from .rules import ValidationResult
            return ValidationResult()
        return self._rule_validator.validate_level(level, level_index)

    def _record_mechanic_interaction(self, mechanic_name: str) -> None:
        """Call when agent interacts with a mechanic instance."""
        if self._rule_tracker:
            self._rule_tracker.record_interaction(mechanic_name)

    def _tick_mechanics(self) -> list[str]:
        """Call each step. Returns expired sprite IDs for removal."""
        if self._rule_tracker:
            return self._rule_tracker.record_step()
        return []

    def _check_mechanics_win(self) -> bool:
        """Check if all runtime interaction goals are met."""
        if self._rule_tracker:
            return self._rule_tracker.are_runtime_goals_met()
        return True

    def _start_decay_timer(self, sprite_id: str, steps: int) -> None:
        """Start a decay timer for a sprite."""
        if self._rule_tracker:
            self._rule_tracker.start_timer(sprite_id, steps)

    def _start_cooldown(self, mechanic_name: str, steps: int) -> None:
        """Start a cooldown for a mechanic (can't interact for N steps)."""
        if self._rule_tracker:
            self._rule_tracker.start_cooldown(mechanic_name, steps)

    def _is_on_cooldown(self, mechanic_name: str) -> bool:
        """Check if a mechanic is on cooldown."""
        if self._rule_tracker:
            return self._rule_tracker.is_on_cooldown(mechanic_name)
        return False

    def _pickup_item(self, item_name: str) -> None:
        """Track picking up a carried item (for capacity rules)."""
        if self._rule_tracker:
            self._rule_tracker.pickup_item(item_name)

    def _drop_item(self, item_name: str) -> None:
        """Track dropping a carried item."""
        if self._rule_tracker:
            self._rule_tracker.drop_item(item_name)
