"""
verify.py — Check that your game is solvable across multiple seeds.

Usage:
    python verify.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from my_game import MyGame
from ipe.solver import BFSSolver

print("Verifying solvability across 10 seeds...")
print()

all_ok = True
for seed in range(10):
    game = MyGame(seed=seed)
    report = BFSSolver(max_depth=300, verbose=False).verify_and_report(game)
    status = "OK" if report["all_solvable"] else "FAIL"
    levels = report["optimal_steps_by_level"]
    print(f"  Seed {seed:2d}: [{status}]  optimal steps per level: {levels}")
    if not report["all_solvable"]:
        all_ok = False

print()
if all_ok:
    print("All seeds solvable!")
else:
    print("SOME SEEDS FAILED — fix your level generation.")
