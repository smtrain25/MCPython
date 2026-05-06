"""
runner.py — Game runner for human terminal play and LLM agent loops.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Callable

from .base_game import BaseGame
from .enums import ActionInput, FrameData, GameAction, GameState
from .palette import COLOR_CHARS, COLOR_NAMES
from .utils import (
    parse_json_response,
    generate_session_id,
    StepLogger,
    frame_state_hash,
)


# ---------------------------------------------------------------------------
# HUMAN KEYBINDINGS
# ---------------------------------------------------------------------------

# Map keyboard input strings to GameAction
KEYBINDINGS: dict[str, GameAction] = {
    # WASD scheme
    "w": GameAction.ACTION1,       # Up
    "s": GameAction.ACTION2,       # Down
    "a": GameAction.ACTION3,       # Left
    "d": GameAction.ACTION4,       # Right
    "space": GameAction.ACTION5,   # Interact
    "f": GameAction.ACTION5,       # Interact (alt)
    "z": GameAction.ACTION7,       # Undo
    "r": GameAction.RESET,         # Reset

    # Arrow keys (terminal may send these differently)
    "up": GameAction.ACTION1,
    "down": GameAction.ACTION2,
    "left": GameAction.ACTION3,
    "right": GameAction.ACTION4,

    # Numeric / direct action IDs
    "1": GameAction.ACTION1,
    "2": GameAction.ACTION2,
    "3": GameAction.ACTION3,
    "4": GameAction.ACTION4,
    "5": GameAction.ACTION5,
    "6": GameAction.ACTION6,
    "7": GameAction.ACTION7,
    "0": GameAction.RESET,
    "reset": GameAction.RESET,
    "undo": GameAction.ACTION7,
}

# Reverse: action → human-readable label
ACTION_LABELS: dict[GameAction, str] = {
    GameAction.RESET:   "RESET (R/0)",
    GameAction.ACTION1: "UP (W/1)",
    GameAction.ACTION2: "DOWN (S/2)",
    GameAction.ACTION3: "LEFT (A/3)",
    GameAction.ACTION4: "RIGHT (D/4)",
    GameAction.ACTION5: "INTERACT (Space/F/5)",
    GameAction.ACTION6: "CLICK (6 x y)",
    GameAction.ACTION7: "UNDO (Z/7)",
}

# LLM action string mapping
LLM_ACTION_MAP: dict[str, GameAction] = {
    "reset": GameAction.RESET,
    "up": GameAction.ACTION1,
    "down": GameAction.ACTION2,
    "left": GameAction.ACTION3,
    "right": GameAction.ACTION4,
    "interact": GameAction.ACTION5,
    "click": GameAction.ACTION6,
    "undo": GameAction.ACTION7,
    "action1": GameAction.ACTION1,
    "action2": GameAction.ACTION2,
    "action3": GameAction.ACTION3,
    "action4": GameAction.ACTION4,
    "action5": GameAction.ACTION5,
    "action6": GameAction.ACTION6,
    "action7": GameAction.ACTION7,
}


# ---------------------------------------------------------------------------
# HUMAN PLAY LOOP
# ---------------------------------------------------------------------------

def run_human(env: BaseGame, log_dir: str = "runs") -> dict:
    """
    Run an interactive human play session in the terminal.

    Controls:
      W/1 = Up, S/2 = Down, A/3 = Left, D/4 = Right
      Space/F/5 = Interact, 6 x y = Click at (x,y)
      Z/7 = Undo, R/0 = Reset, Q = Quit
    """
    session_id = generate_session_id(env.game_id)
    logger = StepLogger(os.path.join(log_dir, f"{session_id}.jsonl"))

    print(f"\n{'='*60}")
    print(f"  {env.game_name}")
    print(f"  {env.description}")
    print(f"  Session: {session_id}")
    print(f"{'='*60}")
    print(f"\nControls:")
    for action_id in env._available_actions:
        ga = GameAction.from_id(action_id)
        print(f"  {ACTION_LABELS.get(ga, str(ga))}")
    print(f"  RESET (R/0)")
    print(f"  QUIT (Q)")
    print()

    # Initial reset
    result = env.perform_action(ActionInput(id=GameAction.RESET))
    _print_frame_data(result, env)

    total_actions = 0
    start_time = time.time()

    while True:
        raw = input(">>> ").strip().lower()

        if not raw:
            continue
        if raw in ("q", "quit", "exit"):
            print("Quitting.")
            break

        # Parse input to ActionInput
        action_input = _parse_human_input(raw, env._available_actions)
        if action_input is None:
            print(f"  Invalid input '{raw}'. Try: w/a/s/d/space/z/r or 1-7")
            continue

        # Perform action
        frame_before = result.frame[-1] if result.frame else None
        result = env.perform_action(action_input)
        total_actions += 1

        frame_after = result.frame[-1] if result.frame else None

        logger.log_step(
            game_id=env.game_id,
            session_id=session_id,
            turn=total_actions,
            level=env.level_index + 1,
            action=f"{action_input.id.name}",
            frame_before=frame_before,
            frame_after=frame_after,
            state_before="NOT_FINISHED",
            state_after=result.state.value,
            reward=0.0,
        )

        _print_frame_data(result, env)

        if result.state == GameState.WIN:
            print(f"\n  Game complete! Score: {result.levels_completed}/{result.win_levels}")
            break
        if result.state == GameState.GAME_OVER:
            print(f"\n  Game over! Score: {result.levels_completed}/{result.win_levels}")
            break

    elapsed = int((time.time() - start_time) * 1000)
    session_meta = {
        "session_id": session_id,
        "game_id": env.game_id,
        "agent_type": "human",
        "total_actions": total_actions,
        "levels_completed": env.score,
        "game_completed": result.state == GameState.WIN,
        "wall_clock_ms": elapsed,
    }
    logger.log_session(session_meta)
    logger.close()

    print(f"\nSession saved to {log_dir}/{session_id}.jsonl")
    return session_meta


def _parse_human_input(raw: str, available_actions: list[int]) -> ActionInput | None:
    """Parse human keyboard input into an ActionInput."""
    parts = raw.split()
    key = parts[0]

    # Check for click: "6 x y" or "click x y"
    if key in ("6", "click") and len(parts) == 3:
        try:
            x = int(parts[1])
            y = int(parts[2])
            if 0 <= x <= 63 and 0 <= y <= 63:
                return ActionInput(id=GameAction.ACTION6, data={"x": x, "y": y})
        except ValueError:
            pass
        return None

    # Look up in keybindings
    ga = KEYBINDINGS.get(key)
    if ga is None:
        return None

    # Check availability (RESET always allowed)
    if ga != GameAction.RESET and ga.value not in available_actions:
        return None

    return ActionInput(id=ga)


def _print_frame_data(fd: FrameData, env: BaseGame) -> None:
    """Print frame data for human terminal play."""
    print(f"\n--- Level {env.level_index + 1}/{env.num_levels} | "
          f"Score {fd.levels_completed}/{fd.win_levels} | "
          f"{fd.state.value} ---")
    if fd.text_observation:
        # Print abbreviated ASCII (skip showing full 64x64 in terminal)
        lines = fd.text_observation.split("\n")
        # Show first and last few lines if too many
        if len(lines) > 20:
            for line in lines[:8]:
                print(line)
            print(f"  ... ({len(lines) - 16} more rows) ...")
            for line in lines[-8:]:
                print(line)
        else:
            print(fd.text_observation)


# ---------------------------------------------------------------------------
# LLM AGENT LOOP
# ---------------------------------------------------------------------------

def run_llm_agent(
    env: BaseGame,
    llm_fn: Callable[[str, str], str],
    max_turns: int = 1000,
    log_dir: str = "runs",
    history_window: int = 6,
    verbose: bool = True,
) -> dict:
    """
    Run an LLM agent on a game.

    llm_fn        : callable(system_prompt, user_message) -> str
    max_turns     : hard cap on total actions
    log_dir       : directory for JSONL logs
    history_window: number of recent turns in LLM context
    verbose       : print state each turn
    """
    session_id = generate_session_id(env.game_id)
    logger = StepLogger(os.path.join(log_dir, f"{session_id}.jsonl"))

    system_prompt = _build_system_prompt(env)

    # Initial reset
    result = env.perform_action(ActionInput(id=GameAction.RESET))

    history: list[dict] = []
    total_turns = 0
    start_time = time.time()

    if verbose:
        print(f"\n{'='*60}")
        print(f"  LLM AGENT: {env.game_name}  [{session_id}]")
        print(f"{'='*60}\n")

    while total_turns < max_turns:
        user_message = _build_user_message(result, env, history, history_window)

        # Call LLM
        try:
            raw_response = llm_fn(system_prompt, user_message)
        except Exception as exc:
            if verbose:
                print(f"  LLM call failed: {exc}. Using reset.")
            raw_response = '{"action": 0, "thought": "LLM error"}'

        parsed = parse_json_response(raw_response)
        raw_action = parsed.get("action", 0)

        # Parse LLM action to ActionInput (accepts int or string)
        action_input = _parse_llm_action(raw_action, parsed, env._available_actions)

        reasoning = {
            "thought": parsed.get("thought", ""),
            "hypothesis": parsed.get("hypothesis", ""),
            "plan": parsed.get("plan", []),
        }

        if verbose:
            print(f"\nTurn {total_turns+1} | Level {env.level_index+1}")
            print(f"  Action : {action_input.id.value} {action_input.data or ''}")
            print(f"  Thought: {reasoning['thought'][:120]}")

        frame_before = result.frame[-1] if result.frame else None

        # Step
        result = env.perform_action(action_input)
        total_turns += 1

        frame_after = result.frame[-1] if result.frame else None

        logger.log_step(
            game_id=env.game_id,
            session_id=session_id,
            turn=total_turns,
            level=env.level_index + 1,
            action=f"{action_input.id.value}",
            frame_before=frame_before,
            frame_after=frame_after,
            state_before="NOT_FINISHED",
            state_after=result.state.value,
            reward=0.0,
            reasoning=reasoning,
        )

        history.append({
            "turn": total_turns,
            "action": action_input.id.value,
            "thought": reasoning["thought"],
        })

        if result.state == GameState.WIN:
            if verbose:
                print(f"\n  Game complete! Score: {result.levels_completed}/{result.win_levels}")
            break
        if result.state == GameState.GAME_OVER:
            if verbose:
                print(f"\n  Game over! Score: {result.levels_completed}/{result.win_levels}")
            break

    elapsed = int((time.time() - start_time) * 1000)
    session_meta = {
        "session_id": session_id,
        "game_id": env.game_id,
        "agent_type": "llm",
        "total_turns": total_turns,
        "levels_completed": env.score,
        "game_completed": result.state == GameState.WIN,
        "wall_clock_ms": elapsed,
    }
    logger.log_session(session_meta)
    logger.close()

    if verbose:
        print(f"\nSession: {log_dir}/{session_id}.jsonl")

    return session_meta


def _parse_llm_action(
    raw_action,
    parsed: dict,
    available_actions: list[int],
) -> ActionInput:
    """Parse LLM action (int or string) to ActionInput."""
    ga = None

    # Try integer first
    try:
        action_id = int(raw_action)
        ga = GameAction.from_id(action_id)
    except (ValueError, TypeError, KeyError):
        pass

    # Fallback: try string mapping
    if ga is None and isinstance(raw_action, str):
        action_str = raw_action.lower().strip()
        ga = LLM_ACTION_MAP.get(action_str)

    if ga is None:
        ga = GameAction.RESET

    # Handle ACTION6 click data
    if ga == GameAction.ACTION6:
        x = parsed.get("x", parsed.get("click_x", 0))
        y = parsed.get("y", parsed.get("click_y", 0))
        return ActionInput(id=ga, data={"x": int(x), "y": int(y)})

    return ActionInput(id=ga)


# ---------------------------------------------------------------------------
# PROMPT BUILDERS
# ---------------------------------------------------------------------------

def _build_system_prompt(env: BaseGame) -> str:
    actions_list = sorted(env._available_actions) + [0]

    return f"""Available actions: {actions_list}
For action 6, also provide "x" and "y" fields (0-63).
Action 0 restarts the current level.

The environment only advances when you take an action.

Respond with a JSON object ONLY:
{{
  "action": <action id>,
  "thought": "<your reasoning>",
  "hypothesis": "<your belief about rules or goal>",
  "plan": ["<next steps>"],
  "x": <only for action 6>,
  "y": <only for action 6>
}}"""


def _build_user_message(
    fd: FrameData,
    env: BaseGame,
    history: list[dict],
    window: int,
) -> str:
    last_frame = fd.frame[-1] if fd.frame else [[0] * 64 for _ in range(64)]

    recent = history[-window:] if len(history) > window else history
    history_lines = []
    for h in recent:
        line = f"  Turn {h['turn']}: action={h['action']}"
        if h.get("thought"):
            line += f" — {h['thought'][:80]}"
        history_lines.append(line)
    history_str = "\n".join(history_lines) if history_lines else "  (none yet)"

    return f"""{json.dumps(last_frame)}

State: {fd.state.value} | Level: {env.level_index + 1}/{env.num_levels} | Score: {fd.levels_completed}/{fd.win_levels}

Recent history:
{history_str}
"""


# ---------------------------------------------------------------------------
# CLI ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("ipe_runner.py: No game configured.")
    print("Edit the __main__ block and replace with your game class.")
    print("")
    print("Example:")
    print("  from my_game import MyGame")
    print("  env = MyGame()")
    print("  run_human(env)")
    sys.exit(0)
