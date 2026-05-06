"""Start the game server. Run: python run.py"""

import sys
from pathlib import Path

# Add project root (where ipe/ lives) and this directory to path
_root = str(Path(__file__).resolve().parent.parent.parent)
sys.path.insert(0, _root)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from game import ClickToClear
from ipe.server import run_server

if __name__ == "__main__":
    _here = Path(__file__).resolve().parent
    run_server(ClickToClear(seed=0), port=5000, log_dir=str(_here / "play_logs"))
