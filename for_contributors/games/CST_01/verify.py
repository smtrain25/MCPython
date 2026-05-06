"""Verify solvability. Run: python verify.py"""

import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent.parent)
sys.path.insert(0, _root)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from game import ClickToClear
from ipe.enums import ActionInput, GameAction

print("CST_01 — Click to Clear")
print("Verifying all levels are clearable across 10 seeds...")
print()

# For click games, BFS can't enumerate clicks.
# Instead, verify that every target is reachable (clickable) by
# programmatically clicking each one.

all_ok = True
for seed in range(10):
    g = ClickToClear(seed=seed)
    g.perform_action(ActionInput(id=GameAction.RESET))

    levels_cleared = 0
    for level_idx in range(g.num_levels):
        # Click every target until cleared
        max_clicks = 200
        for _ in range(max_clicks):
            targets = g.current_level.get_sprites_by_tag("target")
            if not targets:
                levels_cleared += 1
                break
            # Click the first target's display position
            t = targets[0]
            scale, xo, yo = g.camera._calculate_scale_and_offset()
            dx = t.x * scale + xo
            dy = t.y * scale + yo
            r = g.perform_action(ActionInput(id=GameAction.ACTION6, data={"x": dx, "y": dy}))
            if r.state.value == "WIN":
                levels_cleared += 1
                break
            if r.state.value == "GAME_OVER":
                break

        if r.state.value == "WIN" and level_idx < g.num_levels - 1:
            # Engine auto-advanced; continue to next level
            pass

    status = "OK" if levels_cleared == g.num_levels else "FAIL"
    print(f"  Seed {seed:2d}: [{status}] {levels_cleared}/{g.num_levels} levels cleared")
    if levels_cleared != g.num_levels:
        all_ok = False

print()
if all_ok:
    print("All seeds solvable!")
else:
    print("SOME SEEDS FAILED — check target placement.")
