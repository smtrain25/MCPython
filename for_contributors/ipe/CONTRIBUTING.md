# Building Games — Contributor Guide

## Overview

This framework builds turn-based puzzle games on a 64x64 pixel grid with 16 colours. Games are played by humans in a browser and solved by LLM agents. Your job is to create games that test reasoning — not reflexes or domain knowledge.

---

## Hard Rules

These are non-negotiable. The engine enforces most of them.

| Rule | Enforced by |
|------|-------------|
| **Turn-based only.** No real-time, no clocks, no timers. The game only advances when an action is taken. | Engine design |
| **64x64 pixel output.** All games render to exactly 64x64. The camera auto-scales your grid. | Camera class |
| **16 colours (0-15).** No custom colours. Use the palette. | Palette + validation |
| **7 actions max.** RESET + ACTION1-7. No custom action types. | GameAction enum |
| **Reward on level completion only.** No per-step rewards, no partial credit, no shaped rewards. Score increments by 1 per level beaten. | BaseGame.next_level() |
| **100% solvable.** Every level, every seed, must be completable. Verify with the BFS solver. | Your testing |
| **No language/trivia/domain knowledge.** Games must be solvable using spatial reasoning, pattern recognition, basic logic. | Your design |
| **No hidden rules that can't be discovered.** The player must be able to infer every rule from gameplay. | Your design |

### What about lives / turn limits?

- **Turn limits**: Allowed. Implement in your `step()` — count actions, call `self.lose()` when budget exhausted. The agent sees the frame (which can include a visual budget bar) but gets no explicit "turns remaining" metadata. They must read it from the grid, just like a human.
- **Lives**: Not recommended. The framework has no lives system. If you want retry-like mechanics, use `self.lose()` to trigger a reset.
- **Time limits**: **Not allowed.** The game must never advance without player input.

---

## Core Concepts

### What is a Sprite?

A **sprite** is a rectangular block of coloured pixels placed on the game grid. Everything visible in the game is a sprite — the player, walls, goals, items, enemies, UI indicators.

```python
# A 1x1 blue dot
player = Sprite(pixels=[[1]], name="player", x=5, y=5)

# A 3x3 green square
goal = Sprite(pixels=[[3,3,3],[3,3,3],[3,3,3]], name="goal", x=10, y=10)

# A 2x2 shape with transparency
arrow = Sprite(pixels=[[-1, 1], [1, -1]], name="arrow", x=0, y=0)
```

Pixel values:
- `0-15` — palette colours (visible, rendered)
- `-1` — fully transparent (not rendered, not collidable)
- `-2` — invisible but collidable (invisible walls, hitboxes)

Sprites can be scaled (`set_scale`), rotated (0/90/180/270), mirrored, recoloured (`color_remap`), and cloned. They support pixel-perfect collision detection.

### What is a Level?

A **level** is a collection of sprites on a grid. Games have 3-10 levels. Each level defines a `grid_size` (the actual gameplay area) which the camera auto-scales to fit 64x64.

```python
levels = [
    Level(sprites=[], grid_size=(8, 8), name="Tutorial"),    # 8x upscale
    Level(sprites=[], grid_size=(16, 16), name="Easy"),       # 4x upscale
    Level(sprites=[], grid_size=(32, 32), name="Medium"),     # 2x upscale
    Level(sprites=[], grid_size=(64, 64), name="Hard"),       # 1:1
]
```

Sprites are added in `on_set_level()`, not the Level constructor. This lets you use seeded randomness for procedural generation.

### Increasing Difficulty

Difficulty should increase across levels by introducing complexity, not just scale:

1. **Level 1-2**: Introduce core mechanic in isolation. Force the player to interact with it to proceed.
2. **Level 3-4**: Combine mechanics. Add obstacles. Increase grid size.
3. **Level 5+**: Full complexity. Multiple interacting systems. Longer optimal solutions.

**Key principle**: When you introduce a new mechanic (e.g., a breakable block), design a level where the player MUST interact with it to progress. Don't let them bypass new elements.

---

## The Palette

| Index | Colour | Typical Use |
|-------|--------|-------------|
| 0 | Black | Background / empty |
| 1 | Blue | Agent / player |
| 2 | Red | Danger / blocker |
| 3 | Green | Goal / success |
| 4 | Yellow | Key / collectible / trigger |
| 5 | Gray | Walls / impassable |
| 6 | Magenta | Modifier / transformer |
| 7 | Orange | Resource / energy |
| 8 | Light Blue | Portal / teleport |
| 9 | Brown | Terrain / ground |
| 10 | Maroon | Secondary state |
| 11 | Teal | Tertiary state |
| 12 | Light Green | Partial success |
| 13 | Light Gray | Floor / UI border / padding |
| 14 | Pink | Life / status |
| 15 | White | Highlight / text |
| -1 | Transparent | Not rendered, not collidable |
| -2 | Invisible | Not rendered, IS collidable (invisible walls, hitboxes) |

---

## Actions

| ID | Name | Human Key | Use for |
|----|------|-----------|---------|
| 0 | RESET | R | Restart level (or full game if at start) |
| 1 | ACTION1 | W / Up | Movement up |
| 2 | ACTION2 | S / Down | Movement down |
| 3 | ACTION3 | A / Left | Movement left |
| 4 | ACTION4 | D / Right | Movement right |
| 5 | ACTION5 | Space | Interact / confirm / execute |
| 6 | ACTION6 | Click | Click at (x,y) on the 64x64 display |
| 7 | ACTION7 | Z | Undo |

Only declare the actions your game actually uses:
```python
available_actions=[1, 2, 3, 4]     # movement only
available_actions=[6]               # click only
available_actions=[1, 2, 3, 4, 5]  # movement + interact
```

### Click Games (ACTION6)

The player clicks on the 64x64 display. Your game receives display coordinates (0-63). Convert to grid coordinates:

```python
coords = self.camera.display_to_grid(self.action.get_x(), self.action.get_y())
if coords:
    grid_x, grid_y = coords
    sprite = self.current_level.get_sprite_at(grid_x, grid_y)
```

Tag clickable sprites with `"sys_click"`:
```python
Sprite(pixels=[[4]], name="button", tags=["sys_click"])
```

---

## What You Receive

You'll get a template folder to copy. Place it next to the `ipe/` engine directory:

```
project_root/
├── ipe/                  # engine — DO NOT EDIT anything in here
└── my_game/              # your game (copied from ipe/game_template/)
    ├── my_game.py        # YOUR GAME — edit this
    ├── run.py            # starts the browser gameplay server
    ├── verify.py         # checks solvability across seeds
    ├── requirements.txt  # dependencies
    ├── README.md         # quick reference
    └── __init__.py
```

**Important:** Do not modify any files inside `ipe/`. The engine is shared infrastructure — your game code lives entirely in your own game folder. If you need to change engine behaviour, override methods in your `BaseGame` subclass.

## Quick Start

```bash
# 1. Copy the template next to ipe/
cp -r ipe/game_template my_game

# 2. Install dependencies
pip install -r my_game/requirements.txt

# 3. Edit my_game/my_game.py — subclass BaseGame, override step() and on_set_level()

# 4. Run the game server
cd my_game
python run.py
# Open http://127.0.0.1:5000

# 5. Verify solvability
python verify.py
```

The `run.py` and `verify.py` scripts handle path setup automatically — they find the `ipe/` engine in the parent directory.

---

## Game Types & Examples

### Agentic (movement games)

Player has a position on the grid and navigates through space.

| Game idea | Mechanics | Actions |
|-----------|-----------|---------|
| **Maze** | Find path from start to goal avoiding walls | 1-4 |
| **Sokoban** | Push blocks onto target positions | 1-4 |
| **Snake** | Grow by collecting items, avoid self-collision | 1-4 |
| **Symbol transport** | Carry state through transformers to unlock goal | 1-4 |
| **Escape room** | Find keys, unlock doors, reach exit | 1-5 |
| **Fog explorer** | Navigate with limited visibility radius | 1-4 |
| **Ice slider** | Move on ice (slide until hitting wall) | 1-4 |
| **Gravity maze** | Swap gravity direction, navigate to goal | 1-5 |

### Non-Agentic (click/pattern games)

No player position. Entire grid is the puzzle.

| Game idea | Mechanics | Actions |
|-----------|-----------|---------|
| **Click-to-remove** | Click sprites to remove them, clear board | 6 |
| **Pattern completion** | Fill missing cells to complete a pattern rule | 6 |
| **Colour sorting** | Click to swap/cycle colours into groups | 6 |
| **Memory** | Briefly shown pattern, reproduce from memory | 6 |
| **Overlay decomposition** | Two patterns combined, separate them | 6 |
| **Jigsaw** | Click to rotate/place tiles | 5, 6 |
| **Nonogram** | Fill cells to satisfy row/column clues | 6 |

### Orchestration (system manipulation)

Challenge is manipulating coupled systems.

| Game idea | Mechanics | Actions |
|-----------|-----------|---------|
| **Lights-out** | Toggle cells, neighbours flip too | 1-5 or 6 |
| **Volume matching** | Adjust column heights to match target | 1-5 |
| **Gear puzzle** | Rotate connected gears to align markers | 1-5 |
| **Circuit routing** | Connect inputs to outputs without crossing | 6 |
| **Gravity sandbox** | Remove supports, blocks fall to target layout | 6 |
| **Conveyor belts** | Place/rotate belts to route items to targets | 5, 6 |

### Discovery (rule inference)

Player doesn't know the rules and must discover them.

| Game idea | Mechanics | Actions |
|-----------|-----------|---------|
| **Rule inference** | Objects follow hidden rules — discover by experiment | 1-5 |
| **State machine** | Elements cycle through states — find the pattern | 5, 6 |

---

## Collision & Tags

```python
# Move with collision checking
collisions = self.try_move("player", dx, dy)  # [] = success

# Check position
sprite = self.current_level.get_sprite_at(x, y)

# Find sprites by tag
enemies = self.current_level.get_sprites_by_tag("enemy")
items = self.current_level.get_sprites_by_any_tag(["key", "coin"])
all_tags = self.current_level.get_all_tags()
```

### System Tags

| Tag | Meaning |
|-----|---------|
| `sys_click` | Valid click target for ACTION6 |
| `sys_every_pixel` | Every non-transparent pixel is a separate click target |
| `sys_static` | Merged at level init for performance |
| `sys_place` | Placeable area for drag-and-drop |

---

## Rewards & Scoring

- `reward = 0` during play. Always. No exceptions.
- Score increments by 1 when `self.next_level()` is called.
- `self.win()` is called automatically when the last level is completed.
- The agent/human sees score as `levels_completed / win_levels`.
- There is no partial credit, no efficiency bonus, no per-step signal.

---

## Optional Mixins

### Fog of War

```python
from ipe.mixins import FogMixin, VisibilityMode

class MyGame(FogMixin, BaseGame):
    visibility_mode = VisibilityMode.RADIUS_FOG  # CHAMBERS, FLASHLIGHT
    fog_radius = 5
```

### Symbol Transport

```python
from ipe.mixins import SymbolCarrierMixin, Transformer, Blocker

class MyGame(SymbolCarrierMixin, BaseGame):
    def on_set_level(self, level):
        self._init_symbol_state("blue", "green", transformers=[...])
```

---

## Testing

All commands run from inside your game directory (e.g. `my_game/`).

### 1. Browser play
```bash
python run.py
# Open http://127.0.0.1:5000
```

### 2. Verify solvability
```bash
python verify.py
```
This tests 10 seeds. All must pass. If any fail, fix your `_generate_level()`.

### 3. Terminal play (optional)
```python
import sys; from pathlib import Path; sys.path.insert(0, str(Path('.').resolve().parent))
from my_game import MyGame
from ipe.runner import run_human
run_human(MyGame(seed=0))
```

### 4. Human play recording
Terminal play automatically logs to JSONL:
```python
session = run_human(MyGame(), log_dir="runs")
# Creates: runs/{session_id}.jsonl
```

---

## Play Logs

When you run your game with `python run.py`, every action you take in the browser is automatically recorded to the `play_logs/` directory (created next to `run.py`).

```
my_game/
├── play_logs/
│   └── my_game_12345678_abc123.jsonl   # one file per session
├── my_game.py
├── run.py
└── ...
```

Each `.jsonl` file contains one JSON object per line: a session start record, one record per action (with turn number, level, action, and game state), and a session summary when the game is completed.

**You must play through your game at least once and complete all levels.** The play logs are required when you submit your game — they confirm the game is playable and record how many turns it took a human to finish.

---

## Checklist

- [ ] 3-10 levels
- [ ] All levels solvable across 20+ seeds
- [ ] `game_name` and `description` set
- [ ] `category` reflects game type
- [ ] `available_actions` only includes used actions
- [ ] `self.complete_action()` in every code path of `step()`
- [ ] New mechanics introduced with forced-interaction levels
- [ ] Difficulty increases across levels
- [ ] Seeded randomness for all random choices
- [ ] No language, trivia, or domain knowledge required
- [ ] Turn-based only (no timers)
- [ ] Played through all levels in browser (play logs in `play_logs/`)
- [ ] Submit `play_logs/` directory with your game
