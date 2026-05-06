"""
utils.py — Utility functions: JSON parsing, state hashing, environment cloning,
           session logging, action helpers.
"""

from __future__ import annotations

import copy
import hashlib
import json
import pickle
import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .base_game import BaseGame
    from .enums import GameAction


# ---------------------------------------------------------------------------
# 1. parse_json_response
# ---------------------------------------------------------------------------

def parse_json_response(raw: str) -> dict[str, Any]:
    """
    Robustly parse a JSON dict from an LLM response string.

    Handles markdown fences, prose around JSON, single quotes,
    trailing commas. Returns safe fallback on failure.
    """
    if not raw or not isinstance(raw, str):
        return _fallback_response("empty response")

    text = raw.strip()

    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    text = text.strip()

    # Extract first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return _fallback_response(f"no JSON object found in: {text[:80]}")

    candidate = match.group(0)

    # Fix trailing commas
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)

    # Attempt 1: standard parse
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    # Attempt 2: replace single quotes
    try:
        fixed = candidate.replace("'", '"')
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    return _fallback_response(f"could not parse: {candidate[:80]}")


def _fallback_response(reason: str) -> dict[str, Any]:
    return {
        "action": "reset",
        "thought": f"[parse_json_response fallback: {reason}]",
        "hypothesis": "",
        "plan": [],
        "_parse_error": True,
    }


# ---------------------------------------------------------------------------
# 2. state_hash
# ---------------------------------------------------------------------------

def state_hash(metadata: dict[str, Any]) -> str:
    """Produce a stable hash from a game state dict for BFS dedup."""
    return _hash_object(metadata)


def frame_state_hash(
    frame: list[list[int]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Hash a (frame, metadata) pair together."""
    combined = {"frame": frame, "meta": metadata or {}}
    return _hash_object(combined)


def _hash_object(obj: Any) -> str:
    try:
        raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=repr)
    except (TypeError, ValueError):
        raw = repr(obj)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"sha256:{digest[:20]}"


# ---------------------------------------------------------------------------
# 3. clone_env
# ---------------------------------------------------------------------------

def clone_env(env: "BaseGame") -> "BaseGame":
    """
    Deep clone a game environment. Stepping the clone does not affect the original.
    """
    try:
        return pickle.loads(pickle.dumps(env, protocol=pickle.HIGHEST_PROTOCOL))
    except (pickle.PicklingError, TypeError, AttributeError):
        pass

    try:
        return copy.deepcopy(env)
    except Exception as exc:
        raise CloneError(
            f"clone_env failed for {type(env).__name__}. "
            f"Implement __deepcopy__ or a custom clone() method. "
            f"Underlying error: {exc}"
        ) from exc


class CloneError(RuntimeError):
    """Raised when clone_env cannot deep-copy an environment."""


# ---------------------------------------------------------------------------
# STEP LOGGER
# ---------------------------------------------------------------------------

class StepLogger:
    """Writes JSONL step logs (one JSON object per line)."""

    def __init__(self, path: str):
        import os
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._file = open(path, "a", encoding="utf-8")
        self._frame_store: dict[str, list[list[int]]] = {}

    def log_step(
        self,
        game_id: str,
        session_id: str,
        turn: int,
        level: int,
        action: str,
        frame_before: list[list[int]] | None,
        frame_after: list[list[int]] | None,
        state_before: str,
        state_after: str,
        reward: float,
        reasoning: dict | None = None,
        extra: dict | None = None,
    ):
        h_before = frame_state_hash(frame_before) if frame_before else "none"
        h_after = frame_state_hash(frame_after) if frame_after else "none"

        if frame_before:
            self._frame_store[h_before] = frame_before
        if frame_after:
            self._frame_store[h_after] = frame_after

        record: dict[str, Any] = {
            "game_id": game_id,
            "session_id": session_id,
            "turn": turn,
            "level": level,
            "action": action,
            "reasoning": reasoning,
            "frame_before_hash": h_before,
            "frame_after_hash": h_after,
            "frame_changed": h_before != h_after,
            "state_before": state_before,
            "state_after": state_after,
            "reward": reward,
        }
        if extra:
            record.update(extra)

        self._file.write(json.dumps(record) + "\n")
        self._file.flush()

    def log_session(self, session_meta: dict):
        self._file.write(
            json.dumps({"_record_type": "session", **session_meta}) + "\n"
        )
        self._file.flush()

    def save_frame_store(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._frame_store, f)

    def close(self):
        self._file.close()


# ---------------------------------------------------------------------------
# ACTION HELPERS
# ---------------------------------------------------------------------------

def parse_click_coords(data: dict) -> tuple[int, int] | None:
    """Extract (x, y) from ACTION6 data dict."""
    if "x" in data and "y" in data:
        return int(data["x"]), int(data["y"])
    return None


def is_direction_action(action_id: int) -> bool:
    """ACTION1-4 are directional (up/down/left/right)."""
    return action_id in (1, 2, 3, 4)


# Direction deltas for ACTION1-4: (dx, dy) in game world coordinates
# ACTION1=Up(0,-1), ACTION2=Down(0,1), ACTION3=Left(-1,0), ACTION4=Right(1,0)
DIRECTION_DELTAS: dict[int, tuple[int, int]] = {
    1: (0, -1),   # ACTION1 = Up
    2: (0, 1),    # ACTION2 = Down
    3: (-1, 0),   # ACTION3 = Left
    4: (1, 0),    # ACTION4 = Right
}


def get_direction_delta(action_id: int) -> tuple[int, int]:
    """Get (dx, dy) for a directional action. Returns (0,0) for non-directional."""
    return DIRECTION_DELTAS.get(action_id, (0, 0))


# ---------------------------------------------------------------------------
# GENERAL UTILITIES
# ---------------------------------------------------------------------------

def generate_session_id(game_id: str) -> str:
    import time
    import random
    import string
    ts = int(time.time() * 1000) % 100_000
    rand = "".join(random.choices(string.ascii_lowercase, k=4))
    return f"{game_id[:8]}_{ts}_{rand}"


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


def manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def neighbors_4(
    pos: tuple[int, int], grid_size: tuple[int, int]
) -> list[tuple[int, int]]:
    r, c = pos
    rows, cols = grid_size
    return [
        (r + dr, c + dc)
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]
        if 0 <= r + dr < rows and 0 <= c + dc < cols
    ]


def neighbors_8(
    pos: tuple[int, int], grid_size: tuple[int, int]
) -> list[tuple[int, int]]:
    r, c = pos
    rows, cols = grid_size
    return [
        (r + dr, c + dc)
        for dr in [-1, 0, 1]
        for dc in [-1, 0, 1]
        if (dr, dc) != (0, 0)
        and 0 <= r + dr < rows
        and 0 <= c + dc < cols
    ]


def flood_fill(
    grid: list[list[int]],
    start: tuple[int, int],
    passable: set[int],
) -> set[tuple[int, int]]:
    from collections import deque
    rows, cols = len(grid), len(grid[0])
    visited = {start}
    queue = deque([start])
    while queue:
        r, c = queue.popleft()
        for nr, nc in neighbors_4((r, c), (rows, cols)):
            if (nr, nc) not in visited and grid[nr][nc] in passable:
                visited.add((nr, nc))
                queue.append((nr, nc))
    return visited
