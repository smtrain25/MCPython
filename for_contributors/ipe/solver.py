"""
solver.py — BFS and greedy solvers for level verification.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any

from .base_game import BaseGame
from .enums import ActionInput, GameAction, GameState, FrameData
from .utils import state_hash, clone_env


# ---------------------------------------------------------------------------
# RESULT
# ---------------------------------------------------------------------------

@dataclass
class SolverResult:
    """Result of a single BFS solve attempt."""
    solvable: bool
    optimal_steps: int              # -1 if not solvable
    solution_path: list[int]        # sequence of action IDs
    states_explored: int
    elapsed_ms: float
    level: int = 1
    notes: str = ""

    def __str__(self) -> str:
        if self.solvable:
            actions = [GameAction.from_id(a).name for a in self.solution_path]
            return (
                f"[SOLVABLE] Level {self.level} | "
                f"Optimal: {self.optimal_steps} steps | "
                f"Path: {actions} | "
                f"Explored: {self.states_explored} states | "
                f"{self.elapsed_ms:.1f}ms"
            )
        return (
            f"[UNSOLVABLE] Level {self.level} | "
            f"Explored: {self.states_explored} states | "
            f"{self.notes} | "
            f"{self.elapsed_ms:.1f}ms"
        )


# ---------------------------------------------------------------------------
# SOLVER
# ---------------------------------------------------------------------------

class BFSSolver:
    """
    BFS solver for BaseGame instances.

    Parameters
    ----------
    max_depth    : Maximum search depth.
    max_states   : Maximum states to explore.
    verbose      : Print progress.
    exclude_actions : Action IDs to exclude (default: [0, 7] = RESET, UNDO).
    """

    def __init__(
        self,
        max_depth: int = 500,
        max_states: int = 100_000,
        verbose: bool = False,
        exclude_actions: list[int] | None = None,
    ):
        self.max_depth = max_depth
        self.max_states = max_states
        self.verbose = verbose
        self.exclude_actions = set(
            exclude_actions if exclude_actions is not None
            else [0, 7]  # RESET and UNDO
        )

    def solve(self, env: BaseGame, level: int | None = None) -> SolverResult:
        """Solve the current level. Returns SolverResult."""
        t0 = time.monotonic()

        # Reset
        env.perform_action(ActionInput(id=GameAction.RESET))
        initial_hash = self._get_state_hash(env)

        queue: deque[tuple[BaseGame, list[int]]] = deque()
        queue.append((clone_env(env), []))
        visited: set[str] = {initial_hash}

        states_explored = 0
        current_level = env.level_index + 1

        while queue:
            current_env, path = queue.popleft()
            states_explored += 1

            if states_explored > self.max_states:
                elapsed = (time.monotonic() - t0) * 1000
                result = SolverResult(
                    solvable=False, optimal_steps=-1, solution_path=[],
                    states_explored=states_explored, elapsed_ms=elapsed,
                    level=current_level,
                    notes=f"max_states ({self.max_states}) exceeded",
                )
                if self.verbose:
                    print(result)
                return result

            if len(path) > self.max_depth:
                continue

            # Try each available action
            for action_id in current_env._available_actions:
                if action_id in self.exclude_actions:
                    continue

                next_env = clone_env(current_env)
                ga = GameAction.from_id(action_id)

                # Skip complex actions (ACTION6 click) in BFS
                if ga.is_complex():
                    continue

                result_fd = next_env.perform_action(ActionInput(id=ga))
                next_path = path + [action_id]

                # WIN or level advance
                if result_fd.state == GameState.WIN or (
                    result_fd.levels_completed > current_env.score
                ):
                    elapsed = (time.monotonic() - t0) * 1000
                    sol = SolverResult(
                        solvable=True, optimal_steps=len(next_path),
                        solution_path=next_path,
                        states_explored=states_explored, elapsed_ms=elapsed,
                        level=current_level,
                    )
                    if self.verbose:
                        print(sol)
                    return sol

                if result_fd.state == GameState.GAME_OVER:
                    continue

                next_hash = self._get_state_hash(next_env, result_fd)
                if next_hash in visited:
                    continue

                visited.add(next_hash)
                queue.append((next_env, next_path))

        elapsed = (time.monotonic() - t0) * 1000
        result = SolverResult(
            solvable=False, optimal_steps=-1, solution_path=[],
            states_explored=states_explored, elapsed_ms=elapsed,
            level=current_level,
            notes="BFS exhausted all reachable states",
        )
        if self.verbose:
            print(result)
        return result

    def solve_all_levels(self, env: BaseGame) -> dict[int, SolverResult]:
        """Solve every level sequentially."""
        results: dict[int, SolverResult] = {}
        working_env = clone_env(env)
        working_env.perform_action(ActionInput(id=GameAction.RESET))

        for level_num in range(1, env.num_levels + 1):
            if self.verbose:
                print(f"\n--- Solving level {level_num} / {env.num_levels} ---")

            result = self.solve(working_env, level=level_num)
            results[level_num] = result

            if not result.solvable:
                if self.verbose:
                    print(f"Level {level_num} is UNSOLVABLE. Stopping.")
                break

            # Advance by replaying solution
            for action_id in result.solution_path:
                ga = GameAction.from_id(action_id)
                fd = working_env.perform_action(ActionInput(id=ga))
                if fd.state == GameState.WIN:
                    break

        return results

    def verify_and_report(self, env: BaseGame) -> dict:
        """Solve all levels and return verification report."""
        results = self.solve_all_levels(env)
        all_solvable = all(r.solvable for r in results.values())
        optimal_by_level = {
            lvl: r.optimal_steps for lvl, r in results.items() if r.solvable
        }

        report = {
            "game_id": env.game_id,
            "num_levels": env.num_levels,
            "all_solvable": all_solvable,
            "levels": {
                lvl: {
                    "solvable": r.solvable,
                    "optimal_steps": r.optimal_steps,
                    "states_explored": r.states_explored,
                    "elapsed_ms": round(r.elapsed_ms, 1),
                    "notes": r.notes,
                }
                for lvl, r in results.items()
            },
            "optimal_steps_by_level": optimal_by_level,
            "total_optimal_steps": sum(optimal_by_level.values()),
        }

        if self.verbose:
            print(f"\n=== Verification: {env.game_id} ===")
            print(f"All solvable: {all_solvable}")
            for lvl, data in report["levels"].items():
                status = "OK" if data["solvable"] else "FAIL"
                print(f"  [{status}] Level {lvl}: optimal={data['optimal_steps']} steps")

        return report

    def _get_state_hash(self, env: BaseGame, fd: FrameData | None = None) -> str:
        if fd and fd.text_observation:
            return state_hash({"obs": fd.text_observation})
        frame = env.camera.render(env.current_level.get_sprites())
        return state_hash({"frame": frame.tolist()})


# ---------------------------------------------------------------------------
# GREEDY SOLVER
# ---------------------------------------------------------------------------

class GreedySolver:
    """Greedy best-first solver. NOT optimal — finds A solution."""

    def __init__(self, heuristic_fn, max_steps: int = 2000, verbose: bool = False):
        self.heuristic_fn = heuristic_fn
        self.max_steps = max_steps
        self.verbose = verbose

    def solve(self, env: BaseGame) -> SolverResult:
        t0 = time.monotonic()
        env_clone = clone_env(env)
        env_clone.perform_action(ActionInput(id=GameAction.RESET))
        path: list[int] = []
        steps = 0

        while steps < self.max_steps:
            actions = [a for a in env_clone._available_actions if a not in {0, 7}]
            if not actions:
                break

            best_action = None
            best_score = float("inf")
            best_env = None

            for action_id in actions:
                ga = GameAction.from_id(action_id)
                if ga.is_complex():
                    continue

                candidate = clone_env(env_clone)
                fd = candidate.perform_action(ActionInput(id=ga))

                if fd.state == GameState.WIN:
                    path.append(action_id)
                    elapsed = (time.monotonic() - t0) * 1000
                    return SolverResult(
                        solvable=True, optimal_steps=len(path),
                        solution_path=path, states_explored=steps,
                        elapsed_ms=elapsed,
                    )

                score = self.heuristic_fn(candidate)
                if score < best_score:
                    best_score = score
                    best_action = action_id
                    best_env = candidate

            if best_action is None or best_env is None:
                break

            path.append(best_action)
            env_clone = best_env
            steps += 1

        elapsed = (time.monotonic() - t0) * 1000
        return SolverResult(
            solvable=False, optimal_steps=-1, solution_path=[],
            states_explored=steps, elapsed_ms=elapsed,
            notes="GreedySolver: max_steps reached",
        )
