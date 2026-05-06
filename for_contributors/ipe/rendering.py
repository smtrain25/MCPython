"""
rendering.py — Rendering utilities.
ASCII + PNG rendering, frame utilities, and in-frame UI helpers.
"""

from __future__ import annotations

import hashlib
import io
import json

from PIL import Image

from .palette import PALETTE_RGB, COLOR_CHARS, COLOR_NAMES, CHAR_TO_COLOR


def render_ascii_64(frame: list[list[int]], extra_lines: list[str] | None = None) -> str:
    """Render a 64×64 frame as ASCII text."""
    rows = ["".join(COLOR_CHARS.get(cell, "?") for cell in row) for row in frame]
    legend = "  ".join(f"{COLOR_CHARS[k]}={COLOR_NAMES[k]}" for k in range(16))
    parts = rows + [f"Legend: {legend}"]
    if extra_lines:
        parts.extend(extra_lines)
    return "\n".join(parts)


def render_png_64(frame: list[list[int]], scale: int = 4) -> bytes:
    """Render a 64×64 frame as PNG bytes (default 256×256 image)."""
    size = len(frame)
    img = Image.new("RGB", (size * scale, size * scale), (0, 0, 0))
    pixels = img.load()
    for r in range(size):
        for c in range(size):
            color = PALETTE_RGB.get(frame[r][c], (0, 0, 0))
            for dy in range(scale):
                for dx in range(scale):
                    pixels[c * scale + dx, r * scale + dy] = color
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def frame_hash(frame: list[list[int]]) -> str:
    raw = json.dumps(frame, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:16]


def frames_equal(a: list[list[int]], b: list[list[int]]) -> bool:
    return a == b


def frame_diff(before: list[list[int]], after: list[list[int]]) -> list[tuple[int, int, int, int]]:
    diffs = []
    for r in range(len(before)):
        for c in range(len(before[r])):
            if before[r][c] != after[r][c]:
                diffs.append((r, c, before[r][c], after[r][c]))
    return diffs


def ascii_to_frame(ascii_str: str) -> list[list[int]]:
    frame = []
    for line in ascii_str.splitlines():
        if not line or not all(ch in CHAR_TO_COLOR for ch in line):
            break
        frame.append([CHAR_TO_COLOR[ch] for ch in line])
    return frame


def validate_frame(frame: list[list[int]], expected_size: int = 64) -> list[str]:
    errors = []
    if len(frame) != expected_size:
        errors.append(f"Frame has {len(frame)} rows, expected {expected_size}")
    for r, row in enumerate(frame):
        if len(row) != expected_size:
            errors.append(f"Row {r} has {len(row)} cols, expected {expected_size}")
        for c, val in enumerate(row):
            if not (0 <= val <= 15):
                errors.append(f"Cell ({r},{c}) has invalid colour index {val}")
    return errors


def make_empty_frame(size: int = 64, fill: int = 0) -> list[list[int]]:
    return [[fill] * size for _ in range(size)]


def clone_frame(frame: list[list[int]]) -> list[list[int]]:
    return [row[:] for row in frame]


# ---------------------------------------------------------------------------
# IN-FRAME UI HELPERS
# All UI elements are rendered as coloured cells inside the 64x64 grid.
# ---------------------------------------------------------------------------

def stamp_target_box(
    frame: list[list[int]],
    target_frame: list[list[int]],
    top_left: tuple[int, int],
    box_size: int,
    border_color: int = 13,
    background_color: int = 0,
) -> None:
    """Stamp a bordered target configuration panel into the frame.

    Panel is box_size x box_size cells total with a 1-cell border.
    The target_frame is sampled to fill the interior.
    """
    if box_size < 4:
        raise ValueError("box_size must be at least 4")

    tr, tc = top_left
    interior = box_size - 2
    rows = len(frame)
    cols = len(frame[0]) if rows > 0 else 0

    for dr in range(box_size):
        for dc in range(box_size):
            r, c = tr + dr, tc + dc
            if not (0 <= r < rows and 0 <= c < cols):
                continue
            is_border = dr == 0 or dr == box_size - 1 or dc == 0 or dc == box_size - 1
            frame[r][c] = border_color if is_border else background_color

    t_rows = len(target_frame)
    t_cols = len(target_frame[0]) if t_rows > 0 else 0
    if t_rows == 0 or t_cols == 0:
        return

    for dr in range(interior):
        for dc in range(interior):
            r, c = tr + 1 + dr, tc + 1 + dc
            if not (0 <= r < rows and 0 <= c < cols):
                continue
            src_r = min(int(dr / interior * t_rows), t_rows - 1)
            src_c = min(int(dc / interior * t_cols), t_cols - 1)
            frame[r][c] = target_frame[src_r][src_c]


def stamp_state_box(
    frame: list[list[int]],
    state_frame: list[list[int]],
    top_left: tuple[int, int],
    box_size: int,
    border_color: int = 5,
    background_color: int = 0,
) -> None:
    """Stamp a bordered current-state panel (mirrors target_box layout)."""
    stamp_target_box(
        frame, state_frame, top_left, box_size,
        border_color=border_color, background_color=background_color,
    )


def stamp_step_bar(
    frame: list[list[int]],
    steps_used: int,
    budget: int,
    row: int,
    col_start: int,
    col_end: int,
    fill_color: int = 4,
    empty_color: int = 0,
    penalty_color: int = 2,
    penalty_fraction: float = 0.0,
) -> None:
    """Render a horizontal step-budget bar into a single frame row."""
    if budget <= 0:
        return
    bar_width = max(0, col_end - col_start)
    remaining = max(0, budget - steps_used)
    fill_cells = int((remaining / budget) * bar_width)
    penalty_start = col_end - int(penalty_fraction * bar_width)
    rows = len(frame)
    cols = len(frame[0]) if rows > 0 else 0
    if not (0 <= row < rows):
        return
    for i in range(bar_width):
        c = col_start + i
        if not (0 <= c < cols):
            continue
        if penalty_fraction > 0 and c >= penalty_start:
            frame[row][c] = penalty_color
        elif i < fill_cells:
            frame[row][c] = fill_color
        else:
            frame[row][c] = empty_color


def stamp_progress_bar(
    frame: list[list[int]],
    value: int | float,
    maximum: int | float,
    position: int,
    axis: str = "horizontal",
    start: int = 0,
    end: int | None = None,
    fill_color: int = 14,
    empty_color: int = 0,
) -> None:
    """Render a proportional progress bar (horizontal or vertical)."""
    if maximum <= 0:
        return
    rows = len(frame)
    cols = len(frame[0]) if rows > 0 else 0

    if axis == "horizontal":
        end = end if end is not None else cols
        bar_len = max(0, end - start)
        fill_cells = int((value / maximum) * bar_len)
        if not (0 <= position < rows):
            return
        for i in range(bar_len):
            c = start + i
            if 0 <= c < cols:
                frame[position][c] = fill_color if i < fill_cells else empty_color
    elif axis == "vertical":
        end = end if end is not None else rows
        bar_len = max(0, end - start)
        fill_cells = int((value / maximum) * bar_len)
        if not (0 <= position < cols):
            return
        for i in range(bar_len):
            r = start + i
            if 0 <= r < rows:
                frame[r][position] = fill_color if i < fill_cells else empty_color


def stamp_label_row(
    frame: list[list[int]], cells: list[tuple[int, int]], row: int,
) -> None:
    """Stamp a list of (col, color_index) pairs into a single row."""
    rows = len(frame)
    cols = len(frame[0]) if rows > 0 else 0
    if not (0 <= row < rows):
        return
    for col, color in cells:
        if 0 <= col < cols:
            frame[row][col] = color


def stamp_mini_grid(
    frame: list[list[int]], pattern: list[list[int]], top_left: tuple[int, int],
) -> None:
    """Stamp a small pattern directly into the frame (no border)."""
    tr, tc = top_left
    rows = len(frame)
    cols = len(frame[0]) if rows > 0 else 0
    for dr, row in enumerate(pattern):
        for dc, val in enumerate(row):
            r, c = tr + dr, tc + dc
            if 0 <= r < rows and 0 <= c < cols:
                frame[r][c] = val


def stamp_separator(
    frame: list[list[int]],
    position: int,
    axis: str = "horizontal",
    color: int = 5,
    start: int = 0,
    end: int | None = None,
) -> None:
    """Draw a horizontal or vertical separator line."""
    rows = len(frame)
    cols = len(frame[0]) if rows > 0 else 0
    if axis == "horizontal":
        end = end if end is not None else cols
        if 0 <= position < rows:
            for c in range(start, min(end, cols)):
                frame[position][c] = color
    elif axis == "vertical":
        end = end if end is not None else rows
        if 0 <= position < cols:
            for r in range(start, min(end, rows)):
                frame[r][position] = color
