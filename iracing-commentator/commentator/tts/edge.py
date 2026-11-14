"""Free Microsoft neural voices via edge-tts (needs an internet connection)."""

from __future__ import annotations

import asyncio
import os

from .base import Clip, TTSEngine, decode_mp3, join, prosody_for, split_for_pauses, trim_silence


class EdgeTTS(TTSEngine):
    name = "edge"

    def __init__(self, tts_cfg: dict) -> None:
        import edge_tts  # noqa: F401  (fail early if missing)

        self.cfg = tts_cfg
        self.voice = tts_cfg.get("edge", {}).get("voice", "en-GB-RyanNeural")

    async def _one(self, text: str, args: dict) -> bytes:
        import edge_tts

        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or None
        comm = edge_tts.Communicate(text, self.voice, connect_timeout=5, receive_timeout=10,
                                    proxy=proxy, **args)
        audio = bytearray()
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        if not audio:
            raise RuntimeError("edge-tts returned no audio")
        return bytes(audio)

    async def _all(self, segments: list[tuple[str, int]], args: dict) -> list[bytes]:
        # all segments are synthesised at the same time to keep latency low
        return await asyncio.gather(*(self._one(seg, args) for seg, _ in segments))

    def synthesize(self, text: str, event_type: str = "default") -> Clip:
        pros = prosody_for(self.cfg, event_type)
        if self.cfg.get("dramatic_pauses", True):
            segments = split_for_pauses(text, int(self.cfg.get("ellipsis_pause_ms", 350)),
                                        int(self.cfg.get("dash_pause_ms", 150)))
        else:
            segments = [(text, 0)]
        mp3s = asyncio.run(self._all(segments, pros.edge_args()))
        pieces = []
        for (seg, pause), data in zip(segments, mp3s):
            samples = decode_mp3(data)
            if len(segments) > 1:
                samples = trim_silence(samples)
            pieces.append((samples, pause))
        return Clip(join(pieces, pros.pause_before_ms), encoded=list(mp3s))
