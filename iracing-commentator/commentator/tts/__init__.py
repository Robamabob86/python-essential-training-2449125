"""Text-to-speech engines. Add a new engine by subclassing TTSEngine."""

from __future__ import annotations

from .base import Clip, TTSEngine


def make_tts(cfg: dict) -> TTSEngine:
    tts_cfg = cfg["tts"]
    engine = str(tts_cfg.get("engine", "edge")).lower()
    if engine == "elevenlabs":
        try:
            from .elevenlabs import ElevenLabsTTS

            return ElevenLabsTTS(tts_cfg)
        except Exception as exc:
            print(f"[tts] ElevenLabs unavailable ({exc}) - falling back to edge-tts.")
    from .edge import EdgeTTS

    return EdgeTTS(tts_cfg)


__all__ = ["Clip", "TTSEngine", "make_tts"]
