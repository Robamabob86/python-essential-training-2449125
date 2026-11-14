"""Loads config.yaml and .env, filling in sensible defaults for anything missing."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict[str, Any] = {
    "channel_name": "The Beep Test",
    "driver_name": "",
    "driver_pronouns": "he/him",
    "commentator": {
        "personality": "cheeky",
        "cooldown_seconds": 8.0,
        "cooldown_bypass_priority": 70,
        "min_gap_seconds": 2.5,
        "max_line_age_seconds": 4.0,
        "memory_lines": 10,
        "quiet_period_seconds": 45.0,
    },
    "llm": {
        "model": "claude-opus-5-5",
        "effort": "low",
        "max_tokens": 1024,
        "timeout_seconds": 6.0,
        "use_fallback_lines": True,
    },
    "tts": {
        "engine": "edge",
        "edge": {
            "voice": "en-GB-RyanNeural",
            "base_rate": "+8%",
            "base_pitch": "+0Hz",
            "base_volume": "+0%",
        },
        "elevenlabs": {
            "voice_id": "JBFqnCBsd6RMkjVDRZzb",
            "model_id": "eleven_multilingual_v2",
            "stability": 0.3,
            "similarity_boost": 0.8,
            "style": 0.75,
            "use_speaker_boost": True,
            "speed": 1.08,
        },
        "dramatic_pauses": True,
        "ellipsis_pause_ms": 350,
        "dash_pause_ms": 150,
        "prosody": {
            "default": {"rate": "+0%", "pitch": "+0Hz", "volume": "+0%", "pause_before_ms": 0},
        },
    },
    "audio": {"output_device": "", "volume": 0.9, "also_play_on_default": False},
    "ducking": {"enabled": False, "duck_to": 0.35, "process_name": "iRacingSim64DX11.exe"},
    "hotkeys": {"enabled": True, "mute_toggle": "ctrl+shift+m", "force_line": "ctrl+shift+l"},
    "logging": {"folder": "logs", "save_audio_clips": False},
    "detection": {
        "poll_hz": 10,
        "battle_gap_seconds": 1.0,
        "battle_closing_seconds": 0.4,
        "battle_repeat_seconds": 40.0,
        "slow_lap_percent": 7.0,
        "position_settle_seconds": 1.2,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: str | os.PathLike | None = None) -> dict[str, Any]:
    """Read config.yaml (if present) on top of DEFAULTS, and load .env keys."""
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
        load_dotenv()  # also a .env in the current folder, if any
    except ImportError:  # pragma: no cover
        pass

    cfg_path = Path(path) if path else PROJECT_ROOT / "config.yaml"
    user_cfg: dict = {}
    if cfg_path.exists():
        with open(cfg_path, "r", encoding="utf-8") as fh:
            user_cfg = yaml.safe_load(fh) or {}
    else:
        print(f"[config] {cfg_path} not found - using built-in defaults.")
    return _deep_merge(DEFAULTS, user_cfg)
