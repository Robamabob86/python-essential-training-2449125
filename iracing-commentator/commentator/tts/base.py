"""Shared text-to-speech pieces: the Clip type, prosody maths, pauses and decoding."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

SAMPLE_RATE = 24000  # everything is decoded to 24 kHz mono float32


@dataclass
class Clip:
    samples: np.ndarray            # mono float32, -1..1
    sample_rate: int = SAMPLE_RATE
    encoded: list[bytes] = field(default_factory=list)  # original mp3 bytes (for saving clips)

    @property
    def seconds(self) -> float:
        return len(self.samples) / float(self.sample_rate)


@dataclass
class Prosody:
    rate: int = 0          # percent
    pitch: int = 0         # Hz
    volume: int = 0        # percent
    pause_before_ms: int = 0

    def edge_args(self) -> dict:
        return {"rate": f"{self.rate:+d}%", "pitch": f"{self.pitch:+d}Hz", "volume": f"{self.volume:+d}%"}


def _num(value, default: int = 0) -> int:
    m = re.search(r"[-+]?\d+", str(value or ""))
    return int(m.group()) if m else default


def prosody_for(tts_cfg: dict, event_type: str) -> Prosody:
    """Base voice settings + the per-event tweak from config.yaml."""
    table = tts_cfg.get("prosody", {}) or {}
    ev = table.get(event_type) or table.get("default") or {}
    base = tts_cfg.get("edge", {}) or {}
    return Prosody(
        rate=_num(base.get("base_rate")) + _num(ev.get("rate")),
        pitch=_num(base.get("base_pitch")) + _num(ev.get("pitch")),
        volume=_num(base.get("base_volume")) + _num(ev.get("volume")),
        pause_before_ms=_num(ev.get("pause_before_ms")),
    )


def split_for_pauses(text: str, ellipsis_ms: int, dash_ms: int) -> list[tuple[str, int]]:
    """Split a line at '...' and ' - ' into (segment, pause_after_ms) pairs.

    "He's alongside... and he's THROUGH!" -> [("He's alongside...", 350), ("and he's THROUGH!", 0)]
    Tiny fragments are glued to their neighbour so the voice doesn't sound choppy.
    """
    parts = re.split(r"(\.\.\.|…|\s[-–—]\s)", text)
    segments: list[tuple[str, int]] = []
    buf = ""
    for piece in parts:
        if piece in ("...", "…"):
            buf += "..."
            segments.append((buf.strip(), ellipsis_ms))
            buf = ""
        elif piece and re.fullmatch(r"\s[-–—]\s", piece):
            buf += ","
            segments.append((buf.strip(), dash_ms))
            buf = ""
        else:
            buf += piece
    if buf.strip():
        segments.append((buf.strip(), 0))
    # merge fragments with fewer than 2 real words into the next segment
    merged: list[tuple[str, int]] = []
    carry = ""
    for seg, pause in segments:
        seg = (carry + " " + seg).strip() if carry else seg
        if len(re.findall(r"[A-Za-z']+", seg)) < 2 and pause:
            carry = seg
            continue
        carry = ""
        merged.append((seg, pause))
    if carry:
        if merged:
            last, p = merged[-1]
            merged[-1] = (last + " " + carry, p)
        else:
            merged.append((carry, 0))
    return [(s, p) for s, p in merged if re.search(r"[A-Za-z]", s)] or [(text, 0)]


def decode_mp3(data: bytes) -> np.ndarray:
    import miniaudio

    decoded = miniaudio.decode(data, output_format=miniaudio.SampleFormat.FLOAT32,
                               nchannels=1, sample_rate=SAMPLE_RATE)
    return np.asarray(decoded.samples, dtype=np.float32)


def trim_silence(samples: np.ndarray, threshold: float = 0.01, keep_ms: int = 30) -> np.ndarray:
    loud = np.flatnonzero(np.abs(samples) > threshold)
    if loud.size == 0:
        return samples[:0]
    keep = int(SAMPLE_RATE * keep_ms / 1000)
    return samples[max(0, loud[0] - keep): min(len(samples), loud[-1] + keep)]


def silence(ms: int) -> np.ndarray:
    return np.zeros(int(SAMPLE_RATE * max(0, ms) / 1000), dtype=np.float32)


def join(pieces: list[tuple[np.ndarray, int]], pause_before_ms: int = 0) -> np.ndarray:
    out = [silence(pause_before_ms)] if pause_before_ms else []
    for samples, pause_after in pieces:
        out.append(samples)
        if pause_after:
            out.append(silence(pause_after))
    out.append(silence(60))  # tiny tail so the last word isn't clipped
    return np.concatenate(out) if out else silence(0)


class TTSEngine:
    name = "base"

    def synthesize(self, text: str, event_type: str = "default") -> Clip:  # pragma: no cover
        raise NotImplementedError
