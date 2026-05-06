# SKILL: Turn-Based Puzzle Game Framework
## Design Specification v3

Read this file completely before writing any game code. Every design decision is here.

---

## 1. CORE PHILOSOPHY

- **Turn-based only.** No real-time, no clocks. The environment only advances when an action is taken.
- **Reasoning over reaction.** Intelligence = action *efficiency* relative to an optimal solution, not just whether the puzzle is solved.
- **Core priors only.** Games must be solvable using innate cognitive priors: objectness, agentness, spatial reasoning, basic arithmetic/geometry, elementary logic and topology. No language knowledge, trivia, or domain expertise required.
- **100% solvable.** Every level must be completable by at least 2 naïve human testers.
- **Novelty required.** No memorization pathway should exist. Unseen games must be genuinely novel.
- **Completion reward only.** Score increments by 1 per level beaten. `reward = 0` on every step during play. There is no shaped reward, no per-step signal, no partial credit during play.

---

## 2. THE PLAYER-RELATIONSHIP AXIS

This is the most important structural decision for any new game. It determines the action vocabulary, the rendering contract, what counts as difficulty, and how the LLM reasons. Every game must declare one of three categories:

### 2a. Agentic
There is a **spatial agent** with a position on the grid. Navigation is part of the problem. The frame is a map with a "you are here." The LLM must track its own position, plan routes, and reason about reachability.

- Actions are primarily directional (ACTION1-4 for movement)
- State includes agent coordinates
- Difficulty is controlled by map topology, visibility, carried-state, and obstacle layout
- Examples: maze navigation, Sokoban-style pushing, symbol transport

### 2b. Non-Agentic
There is **no spatial agent**. The entire frame is the puzzle state. The LLM acts on the puzzle as a whole, not from within it. There is no position to track.

- Actions are operations on the puzzle structure (ACTION6 click, ACTION5 interact)
- The LLM reasons about pattern structure, rule inference, constraint satisfaction
- Difficulty is controlled by the number of simultaneous constraints, ambiguity, and the opacity of the combining rule
- Examples: overlay/superimposition inference, pattern completion, constraint satisfaction

### 2c. Orchestration
A **cursor or selection state** exists, but the challenge is manipulating a system to match a target configuration. Navigation is trivial or absent; the puzzle is in the *effect* of actions on the global state.

- Actions are object-level operations: ACTION5 (select/apply), ACTION6 (click)
- Difficulty is controlled by action coupling (does changing A affect B?), reversibility, and target complexity
- Examples: volume/height matching, lights-out variants, state machine configuration

```python
CATEGORY = Literal["agentic", "non_agentic", "orchestration"]
```

---

## 3. THE ENGINE CONTRACT

Every game subclasses `BaseGame` from the `ipe` package. The engine provides the game loop, rendering, level management, and reset logic. You override two methods: `step()` and `on_set_level()`.

### 3a. Core Classes

```python
from ipe import BaseGame, Camera, Level, Sprite, GameAction

class MyGame(BaseGame):
    # ── Required metadata ──
    game_name = "My Puzzle"
    description = "A puzzle game."
    category = "agentic"              # "agentic" | "non_agentic" | "orchestration"
    primitive_tags = ["navigation"]   # reasoning primitives (see §14)
    feedback_tier = 1                 # 0-3 (see §15)

    def __init__(self, seed=0):
        self._rng = random.Random(seed)

        levels = [
            Level(sprites=[], grid_size=(16, 16), name="Level 1"),
            Level(sprites=[], grid_size=(16, 16), name="Level 2"),
            Level(sprites=[], grid_size=(16, 16), name="Level 3"),
        ]
        camera = Camera(
            width=16, height=16,      # viewport size (auto-scales to 64x64)
            background=0,             # palette index for empty cells
            letter_box=5,             # palette index for letterbox padding
        )
        super().__init__(
            game_id="my_puzzle",
            levels=levels,
            camera=camera,
            available_actions=[1, 2, 3, 4],  # ACTION1-4 (movement)
            seed=seed,
        )

    def on_set_level(self, level: Level) -> None:
        """Called when a level starts. Build sprites and populate the level here.
        Receives the Level object (not an index). Called on init and level change."""
        self._generate_level(level)

    def step(self) -> None:
        """Game logic — called on every action.
        MUST call self.complete_action() in every code path."""
        action = self.action.id
        # ... handle action ...
        self.complete_action()
```

### 3b. Action System

Actions use the `GameAction` enum with integer IDs (0-7). Games declare which actions they use:

```python
available_actions=[1, 2, 3, 4]     # movement only (ACTION1-4)
available_actions=[6]               # click only (ACTION6)
available_actions=[1, 2, 3, 4, 5]  # movement + interact
```

| ID | Name    | Key       | Description                    |
|----|---------|-----------|--------------------------------|
| 0  | RESET   | R         | Restart level / game (always available) |
| 1  | ACTION1 | W / Up    | Up                             |
| 2  | ACTION2 | S / Down  | Down                           |
| 3  | ACTION3 | A / Left  | Left                           |
| 4  | ACTION4 | D / Right | Right                          |
| 5  | ACTION5 | Space / F | Interact / execute             |
| 6  | ACTION6 | Click     | Click at (x,y) in 64x64 space |
| 7  | ACTION7 | Z         | Undo                           |

ACTION6 (click) carries x,y coordinates (0-63) via `ComplexAction`. All others are `SimpleAction`.

### 3c. Frame Output

The engine always outputs a 64x64 pixel frame. `FrameData` (Pydantic-validated) contains:

```python
FrameData:
    game_id: str
    frame: list[list[list[int]]]    # 64x64 grid of color indices
    state: GameState                 # NOT_PLAYED | NOT_FINISHED | WIN | GAME_OVER
    levels_completed: int
    win_levels: int
    action_input: ActionInput
    full_reset: bool
    available_actions: list[int]
    text_observation: str            # ASCII rendering
    image_observation: bytes         # PNG bytes
```

### 3d. Sprites

Everything visible is a `Sprite` — a rectangular block of coloured pixels:

```python
player = Sprite(pixels=[[1]], name="player", x=5, y=5)       # 1x1 blue dot
goal = Sprite(pixels=[[3,3,3],[3,3,3],[3,3,3]], name="goal")  # 3x3 green square
wall = Sprite(pixels=[[5]], name="wall", x=3, y=3, tags=["wall"])
```

**Pixel values:**
- `0–15` — palette colours (visible)
- `-1` — transparent (not rendered, not collidable)
- `-2` — invisible but collidable (collision detection only)

**Sprite features:**
- Scaling: `set_scale(n)` — positive = upscale, negative = downscale
- Rotation: `set_rotation(0|90|180|270)`, `rotate(delta)`
- Mirroring: `set_mirror_ud(bool)`, `set_mirror_lr(bool)`
- Recolouring: `color_remap(old_color, new_color)` — `None` remaps all non-transparent
- Cloning: `clone(new_name=None)`
- Collision: `collides_with(other)` — pixel-perfect by default
- Merging: `merge(other)` — combine two sprites into one
- Tags: `tags=["wall", "sys_click"]` — for querying and system behaviour
- Layers: `layer=0` — higher layers render on top
- Interaction modes: `TANGIBLE`, `INTANGIBLE` (visible, no collision), `INVISIBLE` (collision only), `REMOVED`
- Blocking modes: `PIXEL_PERFECT` (default), `BOUNDING_BOX`, `NOT_BLOCKED`

### 3e. Levels & Camera

A `Level` is a collection of sprites on a grid. The `Camera` auto-scales any grid size to 64x64 output with letterboxing:

```python
levels = [
    Level(sprites=[], grid_size=(8, 8), name="Tutorial"),    # 8x upscale
    Level(sprites=[], grid_size=(16, 16), name="Easy"),       # 4x upscale
    Level(sprites=[], grid_size=(32, 32), name="Medium"),     # 2x upscale
    Level(sprites=[], grid_size=(64, 64), name="Hard"),       # 1:1
]
camera = Camera(width=16, height=16)  # match your grid size
```

**Level methods:**
```python
level.add_sprite(sprite)                    # add a sprite
level.remove_sprite(sprite)                 # remove a sprite
level.remove_all_sprites()                  # clear all sprites
level.get_sprites()                         # list all sprites
level.get_sprites_by_name("player")         # find by name
level.get_sprites_by_tag("wall")            # find by tag
level.get_sprites_by_tags(["a", "b"])       # find by ALL tags
level.get_sprites_by_any_tag(["a", "b"])    # find by ANY tag
level.get_sprite_at(x, y)                   # topmost sprite at position
level.get_sprite_at(x, y, tag="sys_click")  # filtered by tag
level.collides_with(sprite)                 # all sprites colliding with sprite
```

**Camera methods:**
```python
camera.display_to_grid(x, y)   # convert 64x64 display coords → grid coords (or None)
camera.resize(width, height)   # change viewport size
camera.move(dx, dy)            # pan the camera
```

### 3f. Key Engine Methods

```python
# In your step() method:
self.action                    # current ActionInput (id, data, reasoning)
self.action.id                 # GameAction enum value
self.action.get_x()            # x coordinate for ACTION6 clicks (0-63)
self.action.get_y()            # y coordinate for ACTION6 clicks (0-63)
self.complete_action()         # MUST be called in every step() code path
self.next_level()              # advance to next level (score += 1)
self.win()                     # game complete (called auto on last level)
self.lose()                    # trigger GAME_OVER, auto-reset current level

# Level/state:
self.current_level             # the current Level object
self.level_index               # current level index (0-based)
self.num_levels                # total number of levels
self.is_last_level()           # True if on the final level
self.score                     # current score (levels completed)
self.state                     # current GameState

# Movement:
self.try_move("player", dx, dy)   # move named sprite with collision detection
                                   # returns list of collided sprites (empty = moved ok)

# Click coordinate conversion:
grid_coords = self.camera.display_to_grid(self.action.get_x(), self.action.get_y())
if grid_coords:
    gx, gy = grid_coords
    sprite = self.current_level.get_sprite_at(gx, gy)
```

---

## 4. GRID SPECIFICATION

The camera always outputs 64x64 pixels. Game grids can be any size up to 64x64 — the camera auto-scales:

```python
# Grid sizes and their upscale factors:
# 8x8   → 8x upscale
# 16x16 → 4x upscale
# 32x32 → 2x upscale
# 64x64 → 1:1 (no scaling)
```

Grid size as a difficulty lever:
- **8–16**: Small state space, fast exploration, suits non-agentic inference games
- **16–32**: Default navigation and orchestration games
- **32–64**: Spatial reasoning challenges, large maps, fog-of-war games

---

## 5. COLOR PALETTE

**16 fixed semantic colors.** Every game uses the same palette. Never invent new colors.

| Index | Name       | Hex       | RGB             | Semantic Role                        | ASCII |
|-------|------------|-----------|-----------------|--------------------------------------|-------|
| 0     | Black      | `#000000` | (0, 0, 0)       | Background / empty / unrevealed      | `.`   |
| 1     | Blue       | `#0074D9` | (0, 116, 217)   | Agent / moveable / player            | `@`   |
| 2     | Red        | `#E41A1C` | (228, 26, 28)   | Danger / blocker / state A           | `X`   |
| 3     | Green      | `#4DAF4A` | (77, 175, 74)   | Goal / success / correct             | `G`   |
| 4     | Yellow     | `#FFE119` | (255, 225, 25)  | Key / collectible / trigger          | `K`   |
| 5     | Gray       | `#808080` | (128, 128, 128) | Walls / impassable terrain           | `#`   |
| 6     | Magenta    | `#CF3E96` | (207, 62, 150)  | Transformer / modifier               | `M`   |
| 7     | Orange     | `#FF7F0E` | (255, 127, 14)  | Resource / energy / carried-state    | `R`   |
| 8     | Light Blue | `#94CAFF` | (148, 202, 255) | Portal / teleport / link             | `~`   |
| 9     | Brown      | `#8B5A2B` | (139, 90, 43)   | Terrain / ground / passable          | `B`   |
| 10    | Maroon     | `#800000` | (128, 0, 0)     | State C / secondary modifier         | `V`   |
| 11    | Teal       | `#008080` | (0, 128, 128)   | State D / tertiary modifier          | `T`   |
| 12    | Light Green| `#7FFF00` | (127, 255, 0)   | Partial success / intermediate goal  | `g`   |
| 13    | Light Gray | `#D3D3D3` | (211, 211, 211) | Floor / neutral / UI border          | `_`   |
| 14    | Pink       | `#FFAFC8` | (255, 175, 200) | Life / health / status               | `P`   |
| 15    | White      | `#FFFFFF` | (255, 255, 255) | Highlight / emphasis / text          | `W`   |

**Palette rules:**
- No game requires distinguishing more than **6 colors simultaneously**.
- If you need more than 8 active colors at once, you are testing perception — redesign.
- Colors 10-14 exist for games needing additional state variables.

---

## 6. ACTION MAPPING

All actions use the `GameAction` enum. Games declare only the subset they use via `available_actions`.

### Action-to-Category Mapping

| Action | Agentic | Non-Agentic | Orchestration |
|---|---|---|---|
| RESET (0) | Always | Always | Always |
| ACTION1-4 (movement) | **Primary** | No | No |
| ACTION5 (interact) | Common | Common | **Primary** |
| ACTION6 (click x,y) | No | **Primary** | Common |
| ACTION7 (undo) | Optional | Optional | Optional |

### Action Rules

- `available_actions` declares which actions the game uses. RESET is always available.
- Every declared action must have an observable effect in at least one game state.
- Context-dependent no-ops are fine (e.g., ACTION1 against a wall does nothing but still counts as an action).
- ACTION7 (undo) depth is **1 step only**. Consecutive undos are no-ops. Undos **count** as actions.
- RESET during level 1 restarts the entire game. During level N > 1, restarts current level only. Counts as 1 action.

---

## 7. RENDERING

The engine provides both ASCII and PNG renderers. Both are always provided to the agent.

### 7a. ASCII Renderer

`render_ascii_64()` converts the 64x64 frame to text using `COLOR_CHARS`:

```python
COLOR_CHARS = {
    0: ".",   # black / background
    1: "@",   # blue / agent
    2: "X",   # red / danger
    3: "G",   # green / goal
    4: "K",   # yellow / key
    5: "#",   # gray / wall
    6: "M",   # magenta / modifier
    7: "R",   # orange / resource
    8: "~",   # light blue / portal
    9: "B",   # brown / terrain
    10: "V",  # maroon / state-C
    11: "T",  # teal / state-D
    12: "g",  # light green / partial
    13: "_",  # light gray / floor
    14: "P",  # pink / life
    15: "W",  # white / highlight
}
```

### 7b. PNG Renderer

`render_png_64()` renders the frame as a scaled PNG image (default 256x256 at 4x scale).

### 7c. UI Stamp Helpers

The engine provides in-frame UI rendering utilities:

```python
from ipe import (
    stamp_target_box,    # bordered sub-grid showing target configuration
    stamp_state_box,     # bordered sub-grid showing current state
    stamp_step_bar,      # row of colored cells showing step budget
    stamp_progress_bar,  # bar showing level progress
    stamp_label_row,     # text label rendered as colored cells
    stamp_mini_grid,     # small grid embedded in the frame
    stamp_separator,     # visual separator line
)
```

### 7d. Frame Utilities

```python
from ipe import (
    frame_hash,          # SHA-256 hash of a frame (for deduplication)
    frames_equal,        # compare two frames for equality
    frame_diff,          # list of (row, col, old, new) differences
    ascii_to_frame,      # parse ASCII text back to frame data
    validate_frame,      # check frame dimensions and color indices
    make_empty_frame,    # create a blank 64x64 frame
    clone_frame,         # deep copy a frame
)
```

**Rendering rules:**
- All UI elements are rendered using the same cell/color system as gameplay
- The agent must learn to segment UI from gameplay elements
- The ASCII observation should be identical in information content to the PNG

---

## 8. REWARD

```python
# Reward is ONLY issued on level completion. Zero during all play.
# Score increments by 1 when self.next_level() is called.
# self.win() is called automatically when the last level is completed.
# The agent/human sees score as levels_completed / win_levels.
# There is no partial credit, no efficiency bonus, no per-step signal.

# GAME_OVER (step budget exhausted or failed condition met):
# Game auto-resets to beginning of current level.
# state = GAME_OVER briefly, then resets. Agent continues play.
```

---

## 9. GAME STYLE TAXONOMY

Every game has one **primary style** and may have one **secondary style**. Tag both.

### 9a. Agentic Styles

**Agent Navigation (NVX)**
The agent moves through a spatial environment to reach a goal. Core challenge is pathfinding, obstacle avoidance, and route planning.
- Actions: ACTION1-4 (movement)
- Difficulty levers: map topology, corridor width, organic vs. rectilinear rooms, dead ends, one-way passages

**Symbol Transport (STX)**
The agent navigates while carrying a stateful symbol. The symbol's state changes as the agent passes through modifier objects. The goal is only reachable when the symbol is in the correct state.
- Actions: ACTION1-4 (movement), ACTION5 (interact)
- Key property: the agent must reason *backward* from goal state to construct the required transformation chain, then *forward* to plan the route

**Multi-Room / Chamber Navigation (MRN)**
The map is partitioned into rooms connected by gates or narrow passages. The agent cannot see into adjacent rooms from within the current one.
- Actions: ACTION1-4 (movement), ACTION5 (interact)
- Visibility: current room is fully visible; adjacent rooms are black (color 0)

### 9b. Non-Agentic Styles

**Overlay Inference (OVI)**
The visible frame is the result of superimposing two or more base patterns. The agent must decompose the observed pattern back into its constituent layers.
- Actions: ACTION6 (click)
- Key property: the agent must form and test hypotheses about the combining rule

**Pattern Completion (PCR)**
A partial grid is shown. Some cells are hidden or unset. The agent must infer the underlying rule and complete the pattern.
- Actions: ACTION6 (click)

**Constraint Satisfaction (CST)**
Place N objects on the grid such that a set of visible constraints is satisfied. Visual Sudoku/nonogram family.
- Actions: ACTION6 (click)

**Inverse Inference (IVI)**
The agent is shown the *output* of a transformation and must determine what input produced it.
- Actions: ACTION6 (click)

### 9c. Orchestration Styles

**Volume / Height Orchestration (VOC)**
A set of columns or stacks. Actions change the height/volume of individual stacks. Goal: match a target height profile.
- Actions: ACTION1-4 (cursor), ACTION5 (apply)

**State Machine Configuration (SMC)**
Toggle or cycle elements across the grid to achieve a target global state. Lights-out family.
- Actions: ACTION6 (click) or ACTION1-5

**Object Arrangement / Sorting (OBA)**
Move or reorder objects to satisfy a target arrangement.
- Actions: ACTION6 (click), ACTION1-4 (move)

---

## 10. VISIBILITY & VIEWPORT MECHANICS

Visibility restriction is one of the cleanest difficulty levers. It converts a planning problem into a memory + planning problem.

### 10a. Full Visibility (default)
The entire grid is always visible. All object states are displayed.

### 10b. Chamber / Room Visibility
The map is divided into rooms. The agent sees its current room fully. Adjacent rooms are rendered as black (color 0).

### 10c. Radius Fog-of-War
Cells within Manhattan distance R of the agent are visible. All others are color 0.

### 10d. Directional Flashlight
Only cells in a cone in the agent's current facing direction are revealed.

### Implementation

Use the `FogMixin` from `ipe.mixins`:

```python
from ipe.mixins import FogMixin, VisibilityMode

class MyGame(FogMixin, BaseGame):
    visibility_mode = VisibilityMode.RADIUS_FOG  # FULL, CHAMBERS, FLASHLIGHT
    fog_radius = 5          # for RADIUS_FOG
    fog_cone_depth = 8      # for FLASHLIGHT
    fog_cone_width = 3      # for FLASHLIGHT

    def on_set_level(self, level: Level) -> None:
        grid_w, grid_h = level.grid_size or (16, 16)
        self._init_fog((grid_h, grid_w))       # initialize fog memory
        # For CHAMBERS mode, also call:
        # self._build_room_map_from_frame(raw_frame)

    def step(self) -> None:
        action = self.action.id
        self._track_facing(action.value)       # update facing for flashlight
        # ... movement logic ...
        # After rendering the raw frame, apply fog:
        # fogged_frame = self._apply_fog(raw_frame)
        self.complete_action()
```

**FogMixin methods:**
```python
self._init_fog(grid_size)                    # initialize fog memory grid
self._build_room_map_from_frame(frame)       # auto-detect rooms via flood-fill
self._apply_fog(raw_frame)                   # apply visibility to a frame
self._track_facing(action_id)                # update facing from ACTION1-4
```

**Standalone functions (for custom fog logic):**
```python
from ipe.mixins import apply_visibility, build_room_map, make_fog_memory, VisibilityMode
```

**Note on rendering:** When fog is active, the ASCII rendering shows:
- `@` for the agent
- Current visible cells using their normal characters
- `.` for all unrevealed cells (fog)

---

## 11. SYMBOL TRANSPORT MECHANIC

For games where the agent carries a stateful symbol through transformers, use `SymbolCarrierMixin`:

```python
from ipe.mixins import SymbolCarrierMixin, Transformer, Blocker, SymbolGoal

class MyGame(SymbolCarrierMixin, BaseGame):
    def on_set_level(self, level: Level) -> None:
        self._init_symbol_state(
            initial_state="neutral",
            goal_state="green",
            transformers=[
                Transformer(pos=(5, 5), input_state="neutral", output_state="red", color=6),
                Transformer(pos=(10, 5), input_state="red", output_state="green", color=6),
            ],
            blockers=[
                Blocker(pos=(8, 0), required_state="red", size=(1, 16)),
            ],
            symbol_goal=SymbolGoal(pos=(14, 14), required_state="green"),
        )

    def step(self) -> None:
        # After moving agent:
        blocked = self._apply_symbol_logic(new_agent_pos)
        if blocked:
            # revert movement
            pass
        if self._check_symbol_win(agent_pos):
            self.next_level()
        self.complete_action()
```

**SymbolCarrierMixin methods:**
```python
self._init_symbol_state(initial, goal, transformers, blockers, symbol_goal)
self._apply_symbol_logic(agent_pos)      # returns True if move is blocked
self._check_symbol_win(agent_pos)        # True if at goal with correct state
self._render_symbol_ui(frame)            # stamp carried/target icons on frame
self._render_transformers_on_grid(frame) # render transformer sprites
self._render_blockers_on_grid(frame)     # render blocker sprites
self._snapshot_symbol()                  # save state (for undo)
self._restore_symbol(snapshot)           # restore state (for undo)
self.get_required_transform_chain()      # BFS to find minimum transform sequence
self.symbol_state_summary()              # "Symbol: red | Goal: green | mismatch"
```

**Transformer** — grid object that changes the carried symbol state:
- `pos`, `input_state`, `output_state`, `color`, `size`, `uses` (-1 = unlimited), `is_decoy`

**Blocker** — impassable wall that opens when symbol matches:
- `pos`, `required_state`, `size`, `color_locked`, `color_unlocked`

**SymbolGoal** — win condition when agent arrives with correct state:
- `pos`, `required_state`, `size`, `color`

---

## 12. DATA-DRIVEN MECHANICS SYSTEM

For complex games with multiple interacting mechanics, use the data-driven system:

```python
from ipe import (
    BlockRole, MechanicType, Rule, RulePhase, RuleCategory,
    MechanicSpec, GameMechanics,
)
from ipe.mixins import MechanicsRuleMixin

# Define mechanic types
portal = MechanicType("portal", BlockRole.PORTAL, color=8, size=(2, 2))
key = MechanicType("key", BlockRole.KEY, color=4, paired_with="door", collectible=True)
door = MechanicType("door", BlockRole.DOOR, color=5, paired_with="key")

# Define rules
portal_spec = MechanicSpec(
    mechanic_type=portal,
    rules=[
        Rule(RuleCategory.PLACEMENT_COUNT, RulePhase.PLACEMENT, "portal",
             params={"min": 2, "max": 2}),
        Rule(RuleCategory.PLACEMENT_PAIRING, RulePhase.PLACEMENT, "portal",
             params={"paired_with": "portal"}),
    ],
    introduction_level=0,
)

mechanics = GameMechanics(specs=[portal_spec])

class MyGame(MechanicsRuleMixin, BaseGame):
    def __init__(self, seed=0):
        super().__init__(...)
        self._init_mechanics(mechanics)

    def on_set_level(self, level: Level) -> None:
        self._setup_level_mechanics(self.level_index)
        result = self._validate_current_level(level, self.level_index)

    def step(self) -> None:
        self._record_mechanic_interaction("portal")
        expired = self._tick_mechanics()
        if at_goal and self._check_mechanics_win():
            self.next_level()
        self.complete_action()
```

**BlockRole** values: `AGENT`, `GOAL`, `WALL`, `HAZARD`, `PORTAL`, `KEY`, `DOOR`, `TRANSFORMER`, `RESOURCE`, `SWITCH`, `GATE`, `DECORATION`, `CUSTOM`

**RulePhase** values: `PLACEMENT`, `INTRODUCTION`, `RUNTIME`, `VALIDATION`

**RuleCategory** values: `PLACEMENT_COUNT`, `PLACEMENT_POSITION`, `PLACEMENT_PROXIMITY`, `PLACEMENT_PAIRING`, `PLACEMENT_REGION`, `PLACEMENT_SYMMETRY`, `FORCED_INTERACTION`, `CONFINED_CELL`, `RELATED_PLACEMENT`, `INTERACTION_REQUIRED`, `INTERACTION_SEQUENCE`, `INTERACTION_CAPACITY`, `TIMER_DECAY`, `DELAYED_EFFECT`, `COOLDOWN`, `VISIBILITY_HIDDEN`, `MEMORY_REQUIRED`, `PATTERN_MATCH`, `TRIGGER_EFFECT`, `CHAIN_REACTION`

---

## 13. CAMERA UI INTERFACES

For persistent UI overlays rendered on top of the 64x64 frame (after sprite rendering and scaling), use camera interfaces:

```python
from ipe import RenderableUserDisplay, ToggleableUserDisplay, Camera
import numpy as np

class ScoreDisplay(RenderableUserDisplay):
    """Custom UI overlay rendered on top of the frame."""
    def render_interface(self, frame: np.ndarray) -> np.ndarray:
        # frame is 64x64 numpy array of palette indices
        frame[0, 0:5] = 15  # white pixels in top-left
        return frame

camera = Camera(width=16, height=16, interfaces=[ScoreDisplay()])
```

**ToggleableUserDisplay** — manages sprite pairs (enabled/disabled visual states) for buttons and toggles:

```python
toggle = ToggleableUserDisplay(sprite_pairs=[
    (enabled_sprite, disabled_sprite),  # pair 0
])
toggle.enable(0)
toggle.disable(0)
toggle.is_enabled(0)
toggle.enable_all_by_tag("button")
toggle.disable_all_by_tag("button")
```

---

## 14. OBJECTS & INTERACTABLES

| Object Class         | Max Per Level | Role |
|---------------------|---------------|------|
| Agent               | 1–2           | Player-controlled entity |
| Goal                | 1–3           | Target state or position |
| Key/Trigger         | 1–4           | Must be activated to unlock progress |
| Blocker/Obstacle    | 2–6           | Constrains movement or state |
| Modifier/Transformer| 1–3           | Changes properties of agent, carried state, or other objects |
| Resource            | 0–3           | Consumable (budget, energy, uses) |
| UI Indicator        | 0–3           | Renders visible state (step bar, target box, current-state box) |

**Object rendering:** Simple geometric forms — rectangles, L-shapes, T-shapes, crosses. Never single-pixel objects except for UI step indicators.

### System Tags

| Tag | Meaning |
|-----|---------|
| `sys_click` | Valid click target for ACTION6 |
| `sys_every_pixel` | Every non-transparent pixel is a separate click target |
| `sys_static` | Merged at level init for performance |
| `sys_place` | Placeable area for drag-and-drop |

### Placeable Areas

For games with drag-and-drop placement (e.g., placing pieces on a board):

```python
from ipe import PlaceableArea

area = PlaceableArea(x=2, y=2, width=12, height=12, x_scale=2, y_scale=2)
level = Level(sprites=[], grid_size=(16, 16), placeable_areas=[area])
```

---

## 15. UI RENDERING CONVENTIONS

These are how game state indicators are rendered *inside the grid frame* — not as overlaid text.

### Target Box
A bordered sub-grid in a corner of the main frame (typically top-center or top-right). Shows the target configuration the agent must achieve. Use `stamp_target_box()`.

### Current State Box
A bordered sub-grid (typically bottom-left). Shows the *current* state of the relevant system. Use `stamp_state_box()`.

### Step Budget Bar
A row of colored cells along the bottom edge of the grid. Yellow cells = remaining steps. Red cells = penalty/cost indicators. Use `stamp_step_bar()`.

### Progress Indicator
A single-row or single-column bar along the top or left edge. Use `stamp_progress_bar()`.

**Rule:** All UI elements are rendered using the same cell/color system as gameplay. The agent must learn to segment UI from gameplay elements — this is itself a reasoning challenge.

---

## 16. DIFFICULTY LEVERS

These are orthogonal dials. Mix them to tune difficulty without changing game type.

### Navigation / Spatial Difficulty
- **Map topology**: linear corridor → branching maze → irregular organic blob shape
- **Corridor width**: wide rooms vs. single-cell passages
- **Dead ends**: ratio of dead ends to through-routes
- **Room count**: 1 room → multi-room chamber system
- **Organic rooms**: non-rectilinear boundaries test reachability reasoning in irregular spaces

### Visibility Difficulty
- **Fog radius**: full visibility → radius 10 → radius 4 → flashlight only
- **Memory requirement**: with fog, does the agent need to remember previously seen areas?
- **Observation delay**: frame shown is N steps old (tests predictive planning)
- **Partial target revelation**: in non-agentic games, the target pattern is revealed incrementally as sub-tasks are completed

### State/Transformation Difficulty
- **Transformation chain length**: how many modifier steps are required (1 → 5+)
- **Decoy transformers**: modifiers that look correct but produce wrong output
- **Non-commutativity**: applying modifier A then B gives different result than B then A
- **Irreversible actions**: a subset of actions cannot be undone, raising decision stakes
- **State aliasing**: two configurations look identical visually but have different hidden states

### Constraint Difficulty
- **Indirection depth**: how many reasoning hops from cause to effect (1-hop = direct; 5-hop = complex chain)
- **Action coupling**: in orchestration games, does action on object A affect object B?
- **Hidden constraints**: some rules are not displayed and must be inferred from violations
- **Multi-objective**: two or more sub-goals that must be achieved, possibly in a specific order
- **Budget asymmetry**: different regions/rooms have different step budgets, forcing prioritization

### Inference Difficulty (Non-Agentic)
- **Layer count**: number of superimposed patterns (2 → 4)
- **Combining rule opacity**: is the combining rule (XOR, additive, etc.) stated, hinted, or fully hidden?
- **Pattern similarity**: how similar are the base patterns to each other?
- **Red herrings**: extra objects that look interactable but have no effect; discovering their inactivity costs actions

### Temporal Difficulty
- **Time-locked objects**: some objects cycle through states every N steps; they are only accessible in the right state
- **Delayed effects**: an action has its effect N steps after it is taken
- **Action side effects**: every action has a secondary effect the agent must discover and disentangle from the intended effect

---

## 17. REASONING PRIMITIVES

Tag each game with its primitive composition: e.g., `["pathfinding", "state_transform", "sequence", "non_commutative"]`

**Spatial:** `pathfinding`, `sliding`, `rotation`, `mirroring`, `adjacency`, `topology`, `irregular_boundary`

**Logic:** `boolean_gates`, `conditional`, `sequence`, `parity`, `exclusion`, `non_commutative`

**State:** `toggle`, `cycle`, `accumulation`, `decay`, `transfer`, `state_transform`, `aliased_state`

**Pattern:** `matching`, `completion`, `sorting`, `grouping`, `mapping`, `overlay_inference`, `decomposition`

**Causal:** `chain_reaction`, `delayed_effect`, `reversibility`, `dependencies`, `side_effects`, `action_coupling`

**Memory:** `fog_of_war`, `chamber_exploration`, `cross_turn_memory`, `observation_delay`

---

## 18. FEEDBACK TIERS

Each game chooses one tier. Higher tier = more information = tests exploitation. Lower tier = harder = tests exploration and hypothesis formation.

| Tier | Name       | What's Revealed                                                          | % of Games |
|------|------------|--------------------------------------------------------------------------|------------|
| 0    | Silent     | New frame only. No score, no progress, no win/lose. Agent infers all.   | 20%        |
| 1    | Progress   | Frame + step counter visible in grid UI.                                 | 40%        |
| 2    | Outcome    | Frame + progress + clear WIN/GAME_OVER signal per level.                | 30%        |
| 3    | Diagnostic | Frame + progress + win/lose + partial "what went wrong" indicator.       | 10%        |

**Rule:** The frame is always returned after every action — that is the irreducible minimum.

---

## 19. UNDO & RESET

```python
# UNDO (ACTION7)
# - Reverts to state before the last action
# - Depth: 1 step only. Consecutive undos are no-ops.
# - Counts as 1 action toward the step budget.

# RESET (ACTION0)
# - Level 1: restarts entire game
# - Level N > 1: restarts current level; prior levels' completion preserved
# - Counts as 1 action.

# GAME_OVER (step budget exhausted or failed condition met)
# - Game auto-resets to beginning of current level.
# - Agent continues play.
```

---

## 20. STEP BUDGETS

Step budgets are implemented in your game's `step()` method. Count actions and call `self.lose()` when exhausted.

The budget can be rendered on the grid as a bottom-bar UI element using `stamp_step_bar()`. The agent reads the budget from the visual frame — it is never provided as metadata.

---

## 21. SOLVABILITY

- Every level must be verified solvable before being shipped.
- Use the built-in `BFSSolver` from `ipe.solver`:

```python
from ipe.solver import BFSSolver

solver = BFSSolver(max_depth=2000)
result = solver.solve(game)
print(result)  # SolverResult with solvable, optimal_steps, solution_path
```

- `BFSSolver` also provides:
  - `solve_all_levels(game)` — solve every level sequentially
  - `verify_and_report(game)` — full verification report (JSON-friendly dict)

- For click-based games where BFS is impractical, use programmatic verification in `verify.py`.
- Run `python verify.py` from your game directory to test across 10 seeds.

- `GreedySolver` is also available for games where BFS is too expensive:

```python
from ipe.solver import GreedySolver

solver = GreedySolver(heuristic_fn=my_heuristic, max_steps=2000)
result = solver.solve(game)
```

---

## 22. GAME FILE STRUCTURE

Every game lives in its own directory. Use the template at `ipe/game_template/`:

```
my_game/
├── my_game.py        # Your game class (subclasses BaseGame)
├── run.py            # Start the game server
├── verify.py         # Solvability verification across seeds
├── requirements.txt  # Dependencies (usually just ipe's deps)
└── play_logs/        # Auto-created when you play in the browser
    └── *.jsonl       # One file per play session
```

**run.py** — starts the Flask server:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from my_game import MyGame
from ipe.server import run_server

if __name__ == "__main__":
    game = MyGame(seed=0)
    run_server(game, port=5000)
```

**verify.py** — tests solvability:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from my_game import MyGame
from ipe.solver import BFSSolver

print("Verifying solvability across 10 seeds...")
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
```

---

## 23. LOGGING

The server automatically logs gameplay to JSONL files in `play_logs/`:

```
my_game/
├── play_logs/
│   └── my_game_12345678_abc123.jsonl   # one file per session
```

Each `.jsonl` file contains one JSON object per line: a session start record, one record per action (with turn number, level, action, and game state), and a session summary when the game is completed.

---

## 24. LLM AGENT INTEGRATION

The browser UI includes built-in LLM agent support:

- **LiteLLM Proxy**: base URL + model selection
- **Direct API**: provider (OpenAI/Anthropic/Google) + key + model
- **Test Connection**: validates connectivity, lists available models
- **Modality Check**: probes text and vision capabilities
- **Send Image**: toggle whether the PNG frame is sent to the model

The agent receives:
1. A system prompt with the game description and color legend
2. The ASCII text observation (and optionally the PNG image)
3. The list of available actions

The agent responds with a JSON object containing the chosen action and reasoning.

Server-side `.env` configuration:
```
LITELLM_BASE_URL=https://your-proxy.example.com
LITELLM_API_KEY=sk-...
model_name=gpt-4o
```

API keys configured in `.env` stay server-side and are never exposed to the browser.

---

## 25. COMPLETE MINIMAL GAME EXAMPLE

This is the actual game template. Copy `ipe/game_template/` and edit:

```python
"""my_game.py — A complete working game."""
from __future__ import annotations
import random
from ipe import BaseGame, Camera, GameAction, Level, Sprite

LEVELS = [
    Level(sprites=[], grid_size=(16, 16), name="Level 1"),
    Level(sprites=[], grid_size=(16, 16), name="Level 2"),
    Level(sprites=[], grid_size=(16, 16), name="Level 3"),
]

class MyGame(BaseGame):
    game_name = "My Puzzle Game"
    description = "Navigate to the green goal."
    category = "agentic"
    primitive_tags = ["navigation"]
    feedback_tier = 1

    def __init__(self, seed: int = 0) -> None:
        self._rng = random.Random(seed)
        camera = Camera(background=0, letter_box=5, width=16, height=16)
        super().__init__(
            game_id="my_game",
            levels=LEVELS,
            camera=camera,
            available_actions=[1, 2, 3, 4],  # Up, Down, Left, Right
            seed=seed,
        )

    def on_set_level(self, level: Level) -> None:
        """Called when a level starts. Build your level content here."""
        grid_w, grid_h = level.grid_size or (16, 16)

        # Player (blue, 1x1)
        player = Sprite(pixels=[[1]], name="player", x=1, y=1, tags=["player"])
        level.add_sprite(player)

        # Goal (green, 2x2)
        goal = Sprite(
            pixels=[[3, 3], [3, 3]], name="goal",
            x=grid_w - 4, y=grid_h - 4, tags=["goal"],
        )
        level.add_sprite(goal)

        # Random walls (gray)
        for _ in range(3 + self._rng.randint(0, 3)):
            wx = self._rng.randint(2, grid_w - 3)
            wy = self._rng.randint(2, grid_h - 3)
            wall = Sprite(pixels=[[5]], name=f"wall_{wx}_{wy}", x=wx, y=wy, tags=["wall"])
            level.add_sprite(wall)

    def step(self) -> None:
        """Game logic — called on every action."""
        action = self.action.id

        if action in (GameAction.ACTION1, GameAction.ACTION2,
                      GameAction.ACTION3, GameAction.ACTION4):
            dx, dy = {
                GameAction.ACTION1: (0, -1),   # Up
                GameAction.ACTION2: (0, 1),    # Down
                GameAction.ACTION3: (-1, 0),   # Left
                GameAction.ACTION4: (1, 0),    # Right
            }[action]

            collisions = self.try_move("player", dx, dy)
            if not collisions:
                player = self.current_level.get_sprites_by_name("player")[0]
                goal = self.current_level.get_sprites_by_name("goal")[0]
                if (player.x >= goal.x and player.x < goal.x + goal.width and
                        player.y >= goal.y and player.y < goal.y + goal.height):
                    self.next_level()

        self.complete_action()
```

---

## 26. DESIGN RULES — QUICK REFERENCE

| Dimension | Rule |
|-----------|------|
| Grid | Any size up to 64x64; camera auto-scales to 64x64 output |
| Colors | 16 total; max 6 active simultaneously per level |
| Objects | Max 12 total per level; max 7 logical per decision point |
| Object size | Minimum 2×2 cells |
| Levels | 3–10 per game |
| Action interface | GameAction enum (0-7); declare used subset via `available_actions` |
| Undo depth | 1 step only; costs 1 action |
| Reward | Zero during play; score += 1 on level completion only |
| Feedback | Choose tier 0–3; visual state always returned as both ASCII and PNG |
| Solvability | 100% required; verify with BFS solver or programmatic check |
| Play mode | Turn-based only; no real-time |
| LLM interface | ASCII frame + available_actions → JSON action response |
| Visibility | Full / chamber / radius-fog / flashlight — pick one per game |
| Category | Every game is agentic, non_agentic, or orchestration — declare explicitly |
| UI elements | Rendered as colored cells inside the grid, never as overlaid metadata |
| Logging | JSONL per step; automatic in browser play |
| Mixins | FogMixin, SymbolCarrierMixin, MechanicsRuleMixin — composable |
| File structure | my_game.py + run.py + verify.py + requirements.txt |
