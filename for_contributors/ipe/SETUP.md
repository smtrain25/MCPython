# Setup & Usage Guide

## Requirements

- Python 3.11+
- numpy, Pillow, pydantic, flask, httpx, python-dotenv

```bash
pip install numpy pillow pydantic flask httpx python-dotenv
```

## File Structure

```
ipe/
├── __init__.py              # Package exports
├── enums.py                 # Pydantic-validated enums + data models
├── palette.py               # 16-color palette
├── sprites.py               # Sprite (transforms, collision, merge)
├── level.py                 # Level (sprite collection, PlaceableArea)
├── camera.py                # Camera (64x64 output, UI interfaces)
├── interfaces.py            # RenderableUserDisplay, ToggleableUserDisplay
├── base_game.py             # BaseGame (game loop, @final, valid actions)
├── rendering.py             # ASCII + PNG rendering, frame utils, UI stamps
├── mixins.py                # FogMixin, SymbolCarrierMixin, MechanicsRuleMixin
├── mechanics.py             # MechanicType, BlockRole, Rule, MechanicSpec, GameMechanics
├── rules.py                 # RuleValidator, RuntimeRuleTracker, verify_level_with_mechanics
├── runner.py                # Human + LLM play loops (terminal)
├── utils.py                 # JSON parsing, cloning, logging
├── solver.py                # BFS + greedy solvers
├── server.py                # Flask web server + LLM proxy + play logger
├── requirements.txt         # Engine dependencies
├── templates/gameplay.html  # Browser gameplay UI
├── CONTRIBUTING.md          # Game building guide
├── SKILL.md                 # Design specification
└── game_template/           # Starter template for contributors
    ├── __init__.py
    ├── my_game.py           # Edit this to create a new game
    ├── run.py               # Starts the browser gameplay server
    ├── verify.py            # Checks solvability across seeds
    ├── requirements.txt
    └── README.md
```

## Core Concepts

- **64x64 output**: All games render to a fixed 64x64 pixel grid
- **16-color palette**: Indices 0-15 (defined in `palette.py`)
- **7 standard actions**: ACTION1-7 + RESET (Pydantic-validated via `GameAction` enum)
- **Sprite-based rendering**: Sprites with transforms, pixel-perfect collision
- **Camera with auto-scaling**: Small grids upscaled to 64x64 with letterboxing
- **Level progression**: Games have multiple levels, advance on completion
- **UI overlay interfaces**: RenderableUserDisplay pipeline on Camera

## Quickstart: Browser Play

```bash
python -m ipe.server --port 5000
# Open http://127.0.0.1:5000
```

The browser UI includes:
- 1024x1024 canvas rendering the 64x64 grid
- WASD + click controls for human play
- Agent mode with LLM integration (LiteLLM / direct API)
- Settings modal with model search, connection test, modality check

## Quickstart: Terminal Play

```python
import sys; from pathlib import Path; sys.path.insert(0, str(Path('.').resolve().parent))
from games.CST_01.game import ClickToClear
from ipe.runner import run_human

game = ClickToClear(seed=42)
run_human(game)
```

## Building a New Game

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide. Summary:

1. Copy `ipe/game_template/` to a new folder next to `ipe/`
2. Subclass `BaseGame` from `ipe`
3. Define levels as `Level` objects with grid sizes
4. Create a `Camera` with appropriate viewport
5. Set `available_actions` (which of ACTION1-7 your game uses)
6. Override `step()` with game logic (call `self.complete_action()` when done)
7. Override `on_set_level()` for level-specific setup
8. Call `self.next_level()` on level completion
9. Run `BFSSolver` to verify solvability

## Action Reference

| ID | Name    | Key       | Description                    |
|----|---------|-----------|--------------------------------|
| 0  | RESET   | R         | Restart level / game           |
| 1  | ACTION1 | W / Up    | Up                             |
| 2  | ACTION2 | S / Down  | Down                           |
| 3  | ACTION3 | A / Left  | Left                           |
| 4  | ACTION4 | D / Right | Right                          |
| 5  | ACTION5 | Space / F | Interact / execute             |
| 6  | ACTION6 | Click     | Click at (x,y) in 64x64 space |
| 7  | ACTION7 | Z         | Undo                           |

## Agent Settings (Browser)

The gear icon opens the agent settings modal:

- **LiteLLM Proxy**: base URL + searchable model dropdown
- **Direct API**: provider (OpenAI/Anthropic/Google) + key + model
- **Test Connection**: validates connectivity, lists available models
- **Modality Check**: probes text and vision capabilities
- **Send Image**: toggle whether 1024x1024 PNG is sent to model
- **System Prompt**: custom or default
- **Max Tokens / Action Delay**: agent tuning

Settings persist in browser localStorage.
