"""Optional upgrade: ElevenLabs voices - the most natural, excitable delivery.

Set tts.engine to "elevenlabs" in config.yaml and put ELEVENLABS_API_KEY in .env.
Low stability + high style gives the most expressive "commentator" read.
"""

from __future__ import annotations

import os

import httpx

from .base import Clip, TTSEngine, decode_mp3, join, prosody_for

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class ElevenLabsTTS(TTSEngine):
    name = "elevenlabs"

    def __init__(self, tts_cfg: dict) -> None:
        self.cfg = tts_cfg
        self.el = tts_cfg.get("elevenlabs", {})
        self.key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
        if not self.key:
            raise RuntimeError("ELEVENLABS_API_KEY is missing from .env")
        self.http = httpx.Client(timeout=10.0)

    def synthesize(self, text: str, event_type: str = "default") -> Clip:
        pros = prosody_for(self.cfg, event_type)
        # ElevenLabs has no pitch control; use the per-event rate as a speed tweak.
        speed = float(self.el.get("speed", 1.0)) * (1 + (pros.rate - prosody_for(self.cfg, "default").rate) / 100)
        speed = max(0.7, min(1.2, speed))
        body = {
            "text": text,
            "model_id": self.el.get("model_id", "eleven_multilingual_v2"),
            "voice_settings": {
                "stability": float(self.el.get("stability", 0.3)),
                "similarity_boost": float(self.el.get("similarity_boost", 0.8)),
                "style": float(self.el.get("style", 0.75)),
                "use_speaker_boost": bool(self.el.get("use_speaker_boost", True)),
                "speed": round(speed, 2),
            },
        }
        resp = self.http.post(
            API.format(voice_id=self.el.get("voice_id")),
            params={"output_format": "mp3_44100_128", "optimize_streaming_latency": 2},
            headers={"xi-api-key": self.key, "accept": "audio/mpeg"},
            json=body,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"ElevenLabs error {resp.status_code}: {resp.text[:200]}")
        samples = decode_mp3(resp.content)
        return Clip(join([(samples, 0)], pros.pause_before_ms), encoded=[resp.content])
