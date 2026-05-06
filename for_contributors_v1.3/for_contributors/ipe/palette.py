"""
palette.py — 16-color palette
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# PALETTE — 16 colours (indices 0–15)
# ---------------------------------------------------------------------------

PALETTE_RGB: dict[int, tuple[int, int, int]] = {
    0:  (0,   0,   0),     # Black      — background / empty
    1:  (0,   116, 217),   # Blue       — agent / moveable / state B
    2:  (228, 26,  28),    # Red        — danger / blocker / state A
    3:  (77,  175, 74),    # Green      — goal / success / correct
    4:  (255, 225, 25),    # Yellow     — key / collectible / trigger
    5:  (128, 128, 128),   # Gray       — walls / impassable
    6:  (207, 62,  150),   # Magenta    — transformer / modifier
    7:  (255, 127, 14),    # Orange     — resource / energy / carried-state
    8:  (148, 202, 255),   # Light Blue — portal / teleport / link
    9:  (139, 90,  43),    # Brown      — terrain / ground
    10: (128, 0,   0),     # Maroon     — state C / secondary
    11: (0,   128, 128),   # Teal       — state D / tertiary
    12: (127, 255, 0),     # Light Green— secondary success / partial
    13: (211, 211, 211),   # Light Gray — floor / neutral / UI border
    14: (255, 175, 200),   # Pink       — life / status
    15: (255, 255, 255),   # White      — bright / highlight / text
}

PALETTE_HEX: dict[int, str] = {
    0: "#000000", 1: "#0074D9", 2: "#E41A1C", 3: "#4DAF4A",
    4: "#FFE119", 5: "#808080", 6: "#CF3E96", 7: "#FF7F0E",
    8: "#94CAFF", 9: "#8B5A2B", 10: "#800000", 11: "#008080",
    12: "#7FFF00", 13: "#D3D3D3", 14: "#FFAFC8", 15: "#FFFFFF",
}

COLOR_NAMES: dict[int, str] = {
    0: "black", 1: "blue", 2: "red", 3: "green",
    4: "yellow", 5: "gray", 6: "magenta", 7: "orange",
    8: "light_blue", 9: "brown", 10: "maroon", 11: "teal",
    12: "light_green", 13: "light_gray", 14: "pink", 15: "white",
}

COLOR_CHARS: dict[int, str] = {
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

CHAR_TO_COLOR: dict[str, int] = {v: k for k, v in COLOR_CHARS.items()}
