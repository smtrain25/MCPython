"""
run.py — Start the game server.

Usage:
    python run.py
    Then open http://127.0.0.1:5000
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from my_game import MyGame
from ipe.server import run_server

if __name__ == "__main__":
    _here = Path(__file__).resolve().parent
    game = MyGame(seed=0)
    run_server(game, port=5000, log_dir=str(_here / "play_logs"))
