"""
server.py — Flask server for browser-based game play + LLM agent integration.

Usage:
    python -m ipe.server                                    # default game
    python -m ipe.server --game my_game:MyGame              # single game

Serves:
    /              — gameplay HTML template
    /api/config    — game metadata
    /api/action    — perform game action (RESET, ACTION1-7)
    /api/agent-step — LLM agent: send observation, get action
    /api/test-connection — test LLM provider connectivity
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import importlib
import json
import os
import random
import re
import string
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from .enums import ActionInput, GameAction, GameState
from .base_game import BaseGame

app = Flask(__name__, static_folder=None)


# ---------------------------------------------------------------------------
# Play Session Logger — records every browser action to JSONL for verification
# ---------------------------------------------------------------------------

def _make_session_id(game_id: str) -> str:
    ts = int(time.time() * 1000) % 100_000_000
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{game_id[:12]}_{ts}_{rand}"


def _frame_hash(frame: list) -> str:
    raw = json.dumps(frame, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()[:16]


class PlaySessionLogger:
    """Append-only JSONL logger for browser play sessions."""

    def __init__(self, log_dir: str = "play_logs"):
        self._log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._session_id: str = ""
        self._game_id: str = ""
        self._file = None
        self._turn: int = 0
        self._start_time: float = 0.0

    def start_session(self, game_id: str) -> str:
        self.close()
        self._session_id = _make_session_id(game_id)
        self._game_id = game_id
        self._turn = 0
        self._start_time = time.time()
        path = os.path.join(self._log_dir, f"{self._session_id}.jsonl")
        self._file = open(path, "a", encoding="utf-8")
        self._write({"_type": "session_start", "session_id": self._session_id,
                      "game_id": game_id,
                      "timestamp": datetime.datetime.utcnow().isoformat() + "Z"})
        return self._session_id

    def log_action(self, action_id: int, action_data: dict,
                   state_after: str, level: int,
                   frame: list | None = None) -> None:
        if not self._file:
            return
        if action_id == 0:
            self._turn = 0
        else:
            self._turn += 1
        record = {
            "_type": "action",
            "session_id": self._session_id,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "turn": self._turn,
            "level": level,
            "action_id": action_id,
            "action_data": action_data or {},
            "state_after": state_after,
            "frame_hash": _frame_hash(frame) if frame else None,
        }
        self._write(record)

        if state_after == "WIN":
            self._write_completion()

    def _write_completion(self) -> None:
        elapsed = int((time.time() - self._start_time) * 1000)
        self._write({
            "_type": "session_complete",
            "session_id": self._session_id,
            "game_id": self._game_id,
            "game_completed": True,
            "total_turns": self._turn,
            "wall_clock_ms": elapsed,
        })

    def _write(self, record: dict) -> None:
        if self._file:
            self._file.write(json.dumps(record) + "\n")
            self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None

    @property
    def session_id(self) -> str:
        return self._session_id


# Global game instance (set by run_server)
_game: BaseGame | None = None
_action_count: int = 0
_play_logger: PlaySessionLogger | None = None


def run_server(game: BaseGame, host: str = "127.0.0.1", port: int = 5000,
               debug: bool = True, log_dir: str = "play_logs"):
    """Start the game server (single-game mode)."""
    global _game, _play_logger
    _game = game
    _play_logger = PlaySessionLogger(log_dir=log_dir)
    _play_logger.start_session(game.game_id)
    _game.perform_action(ActionInput(id=GameAction.RESET))
    print(f"Server starting: http://{host}:{port}")
    print(f"Game: {game.game_name} ({game.game_id})")
    print(f"Play logs: {os.path.abspath(log_dir)}/")
    app.run(host=host, port=port, debug=debug)


# ── Static / Template ───────────────────────────────────────────────

TEMPLATE_DIR = Path(__file__).parent / "templates"

@app.route("/")
def index():
    return send_from_directory(str(TEMPLATE_DIR), "gameplay.html")


# ── Game API ────────────────────────────────────────────────────────

@app.route("/api/config")
def api_config():
    if not _game:
        return jsonify({"error": "No game loaded"}), 500
    return jsonify({
        "game_id": _game.game_id,
        "game_name": _game.game_name,
        "description": _game.description,
        "num_levels": _game.num_levels,
        "available_actions": _game._available_actions,
        "category": _game.category,
    })


@app.route("/api/set-level", methods=["POST"])
def api_set_level():
    """Jump to a specific level by index (0-based)."""
    global _action_count
    if not _game:
        return jsonify({"error": "No game loaded"}), 500

    data = request.get_json(force=True)
    level_index = data.get("level", 0)

    try:
        # Reset the level from the clean copy, then jump to it
        _game._levels[level_index] = _game._clean_levels[level_index].clone()
        _game._state = GameState.NOT_FINISHED
        _game._action_count = 1  # prevent handle_reset from calling full_reset
        _game.set_level(level_index)
        _action_count = 0
    except (IndexError, ValueError) as e:
        return jsonify({"error": str(e)}), 400

    # Render the frame directly (no RESET which would jump back to level 0)
    frame = _game.camera.render(_game.current_level.get_sprites()).tolist()

    return jsonify({
        "frame": [frame],
        "state": _game._state.value,
        "levels_completed": _game._score,
        "win_levels": _game._win_score,
        "action_count": 0,
        "available_actions": _game._available_actions,
        "full_reset": False,
        "level": level_index,
    })


@app.route("/api/action", methods=["POST"])
def api_action():
    global _action_count
    if not _game:
        return jsonify({"error": "No game loaded"}), 500

    data = request.get_json(force=True)
    action_id = data.get("action_id", 0)

    try:
        ga = GameAction.from_id(action_id)
    except ValueError:
        return jsonify({"error": f"Invalid action_id: {action_id}"}), 400

    action_data = {}
    if ga == GameAction.ACTION6:
        action_data = {"x": data.get("x", 0), "y": data.get("y", 0)}

    action_input = ActionInput(id=ga, data=action_data)
    fd = _game.perform_action(action_input)

    if ga != GameAction.RESET:
        _action_count += 1
    else:
        _action_count = 0

    if _play_logger:
        last_frame = fd.frame[-1] if fd.frame else None
        _play_logger.log_action(
            action_id=action_id,
            action_data=action_data,
            state_after=fd.state.value,
            level=_game.level_index,
            frame=last_frame,
        )

    return jsonify({
        "frame": fd.frame,
        "state": fd.state.value,
        "levels_completed": fd.levels_completed,
        "win_levels": fd.win_levels,
        "action_count": _action_count,
        "available_actions": fd.available_actions,
        "full_reset": fd.full_reset,
    })


# ── LLM Agent Step ─────────────────────────────────────────────────

@app.route("/api/agent-step", methods=["POST"])
def api_agent_step():
    """Send observation to LLM, parse response, return action."""
    data = request.get_json(force=True)
    system = data.get("system", "")
    prompt = data.get("prompt", "")
    image_b64 = data.get("image_b64")
    max_tokens = data.get("max_tokens", 512)

    conn = _extract_conn(data)
    t0 = time.time()

    try:
        text = _call_llm(conn, system, prompt, image_b64, max_tokens)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

    latency = time.time() - t0

    # Parse action from LLM response
    action_id, action_data, thought = _parse_agent_response(text)

    return jsonify({
        "ok": True,
        "action_id": action_id,
        "action_data": action_data,
        "thought": thought,
        "raw_text": text[:500],
        "latency": latency,
    })


# ── Modality Check ──────────────────────────────────────────────────

@app.route("/api/modality-check", methods=["POST"])
def api_modality_check():
    """Probe text and vision capabilities of the configured model."""
    data = request.get_json(force=True)
    conn = _extract_conn(data)

    text_ok = False
    vision_ok = False
    latencies = []

    # Test text
    try:
        t0 = time.time()
        resp = _call_llm(conn, "", "Reply with exactly: OK", None, 10)
        latencies.append(time.time() - t0)
        text_ok = "ok" in resp.lower()
    except Exception:
        text_ok = False

    # Test vision (tiny 2x2 red PNG)
    try:
        import struct, zlib
        # Minimal 2x2 red PNG
        def _mini_png():
            raw = b""
            for _ in range(2):
                raw += b"\x00" + b"\xff\x00\x00" * 2
            compressed = zlib.compress(raw)
            def chunk(ctype, data):
                c = ctype + data
                return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
            return (b"\x89PNG\r\n\x1a\n"
                    + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", compressed)
                    + chunk(b"IEND", b""))
        img_bytes = _mini_png()
        img_b64 = base64.b64encode(img_bytes).decode()

        t0 = time.time()
        resp = _call_llm(conn, "", "What color is this image? Reply with one word.", img_b64, 20)
        latencies.append(time.time() - t0)
        vision_ok = len(resp.strip()) > 0
    except Exception:
        vision_ok = False

    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    return jsonify({
        "text_ok": text_ok,
        "vision_ok": vision_ok,
        "avg_latency": round(avg_latency, 2),
    })


# ── Test Connection ─────────────────────────────────────────────────

@app.route("/api/test-connection", methods=["POST"])
def api_test_connection():
    data = request.get_json(force=True)
    conn = _extract_conn(data)

    try:
        if conn["type"] == "litellm":
            return _test_litellm(conn)
        else:
            return _test_direct(conn)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ── LLM calling ────────────────────────────────────────────────────

def _extract_conn(data: dict) -> dict:
    """Extract connection config from request data."""
    return {
        "type": data.get("type", "litellm"),
        "base_url": data.get("base_url", ""),
        "api_key": data.get("api_key", ""),
        "model": data.get("model", ""),
        "provider": data.get("provider", "openai"),
    }


def _call_llm(conn: dict, system: str, prompt: str, image_b64: str | None, max_tokens: int) -> str:
    """Call LLM via OpenAI-compatible API (works with LiteLLM, OpenAI, etc.)."""
    import httpx

    base_url = conn["base_url"].rstrip("/")
    api_key = conn["api_key"]
    model = conn["model"]

    if conn["type"] == "direct" and conn["provider"] == "anthropic":
        return _call_anthropic(conn, system, prompt, image_b64, max_tokens)

    # OpenAI-compatible format (LiteLLM, OpenAI, Google via proxy)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})

    user_content = []
    if image_b64:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_b64}"}
        })
    user_content.append({"type": "text", "text": prompt})
    messages.append({"role": "user", "content": user_content})

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": messages, "max_tokens": max_tokens}

    r = httpx.post(f"{base_url}/chat/completions", json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def _call_anthropic(conn: dict, system: str, prompt: str, image_b64: str | None, max_tokens: int) -> str:
    """Direct Anthropic API call."""
    import httpx

    api_key = conn["api_key"]
    model = conn["model"]
    base_url = conn.get("base_url", "").rstrip("/") or "https://api.anthropic.com"

    user_content = []
    if image_b64:
        user_content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": image_b64}
        })
    user_content.append({"type": "text", "text": prompt})

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user_content}],
    }
    if system:
        payload["system"] = system

    r = httpx.post(f"{base_url}/v1/messages", json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json()["content"][0]["text"]


def _test_litellm(conn: dict):
    """Test LiteLLM proxy connection and fetch model list."""
    import httpx

    base_url = conn["base_url"].rstrip("/")
    api_key = conn["api_key"]
    headers = {"Authorization": f"Bearer {api_key}"}

    # Try to list models
    models = []
    try:
        r = httpx.get(f"{base_url}/models", headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json().get("data", [])
        models = sorted([m["id"] for m in data if "id" in m])
    except Exception:
        pass

    # Quick completions test
    test_model = conn["model"] or (models[0] if models else "")
    if not test_model:
        return jsonify({"ok": True, "models": models, "provider": "litellm"})

    try:
        r = httpx.post(
            f"{base_url}/chat/completions",
            json={"model": test_model, "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
            headers={**headers, "Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        return jsonify({"ok": True, "models": models, "model": test_model, "provider": "litellm"})
    except Exception as e:
        return jsonify({"ok": False, "error": f"Model test failed: {e}", "models": models})


def _test_direct(conn: dict):
    """Test direct API connection."""
    import httpx

    provider = conn["provider"]
    api_key = conn["api_key"]
    model = conn["model"]

    if provider == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
        base_url = conn.get("base_url", "").rstrip("/") or "https://api.anthropic.com"
        r = httpx.post(
            f"{base_url}/v1/messages",
            json={"model": model, "max_tokens": 5, "messages": [{"role": "user", "content": "Say ok"}]},
            headers=headers, timeout=15,
        )
        r.raise_for_status()
        return jsonify({"ok": True, "provider": "anthropic", "model": model})

    # OpenAI / Google / compatible
    base_url = conn.get("base_url", "").rstrip("/") or "https://api.openai.com/v1"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    r = httpx.post(
        f"{base_url}/chat/completions",
        json={"model": model, "messages": [{"role": "user", "content": "Say ok"}], "max_tokens": 5},
        headers=headers, timeout=15,
    )
    r.raise_for_status()
    detected = "openai"
    if "google" in base_url.lower() or "gemini" in model.lower():
        detected = "google"
    return jsonify({"ok": True, "provider": detected, "model": model})


# ── Response parsing ────────────────────────────────────────────────

def _parse_agent_response(text: str) -> tuple[int, dict, str]:
    """Parse LLM response into (action_id, action_data, thought)."""
    thought = ""
    action_id = 0  # default to RESET

    # Try JSON parse first
    try:
        # Find JSON in response
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            candidate = match.group(0)
            candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
            parsed = json.loads(candidate)
            action_id = int(parsed.get("action", parsed.get("action_id", 0)))
            thought = parsed.get("thought", parsed.get("reasoning", ""))
            action_data = {}
            if action_id == 6:
                action_data = {"x": int(parsed.get("x", 0)), "y": int(parsed.get("y", 0))}
            return action_id, action_data, thought
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    # Fallback: look for direction words
    words = text.lower().strip().split()
    direction_map = {"up": 1, "down": 2, "left": 3, "right": 4, "interact": 5, "undo": 7, "reset": 0}
    for word in reversed(words):
        clean = re.sub(r'[^a-z]', '', word)
        if clean in direction_map:
            return direction_map[clean], {}, text[:200]

    # Fallback: look for numbers
    for word in reversed(words):
        try:
            n = int(re.sub(r'[^0-9]', '', word))
            if 0 <= n <= 7:
                return n, {}, text[:200]
        except ValueError:
            continue

    return action_id, {}, text[:200]


# ── CLI entry point ─────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Game server")
    parser.add_argument("--game", default=None,
                        help="module:ClassName for a single game")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    game_spec = args.game or "ipe.template_non_agentic:ClickRemoveGame"
    module_path, class_name = game_spec.rsplit(":", 1)
    mod = importlib.import_module(module_path)
    GameClass = getattr(mod, class_name)
    game = GameClass(seed=args.seed) if "seed" in GameClass.__init__.__code__.co_varnames else GameClass()
    run_server(game, host=args.host, port=args.port)
