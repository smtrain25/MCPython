# Game Template

This is a starter template for building a puzzle game.

## Setup

```bash
pip install -r requirements.txt
```

Make sure the `ipe` package is on your Python path. If you received this template alongside the `ipe/` directory, both should be in the same parent folder:

```
your_project/
├── ipe/              # the engine — DO NOT EDIT anything in here
├── my_game/          # your game (edit this)
│   ├── my_game.py    # your game logic
│   ├── run.py        # start the server
│   ├── verify.py     # check solvability
│   └── requirements.txt
```

**Do not modify files inside `ipe/`.** All your game code goes in this folder.

## Quick start

```bash
# 1. Edit my_game.py — see the comments for what to change

# 2. Run the game server
python run.py

# 3. Open in browser
open http://127.0.0.1:5000

# 4. Verify your game is solvable
python verify.py
```

## What to edit in my_game.py

1. **Class attributes** — `game_name`, `description`, `category`, `available_actions`
2. **Camera** — `width`/`height` set your grid size (auto-scales to 64x64)
3. **Levels** — define how many levels and their grid sizes
4. **`_generate_level()`** — add sprites (player, goals, walls, items)
5. **`step()`** — handle actions, check win conditions, call `self.next_level()`

## Controls

| Key | Action |
|-----|--------|
| W / Up | ACTION1 (Up) |
| S / Down | ACTION2 (Down) |
| A / Left | ACTION3 (Left) |
| D / Right | ACTION4 (Right) |
| Space | ACTION5 (Interact) |
| Click | ACTION6 (Click x,y) |
| Z | ACTION7 (Undo) |
| R | RESET |

## Play logs

When you run `python run.py`, every action is logged to `play_logs/` (created automatically). You must play through all levels at least once. Submit the `play_logs/` directory with your game.

## Rules

- Turn-based only. No timers.
- 64x64 pixel output, 16 colours (0-15).
- Reward only on level completion. No per-step rewards.
- Every level must be solvable.
- Call `self.complete_action()` at the end of every `step()`.

See CONTRIBUTING.md in the `ipe/` package for the full guide.
