"""Plays commentary to one chosen output device (e.g. VB-Audio Virtual Cable)."""

from __future__ import annotations

import threading
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
except Exception as _exc:  # PortAudio missing etc.
    sd = None
    _SD_ERROR = _exc
else:
    _SD_ERROR = None

# Preferred Windows host APIs: MME resamples for us and is the most forgiving.
_HOSTAPI_PREFERENCE = ["MME", "Windows DirectSound", "Windows WASAPI"]


def output_devices() -> list[dict]:
    if sd is None:
        return []
    hostapis = sd.query_hostapis()
    devices = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev.get("max_output_channels", 0) > 0:
            devices.append({
                "index": idx,
                "name": dev["name"],
                "hostapi": hostapis[dev["hostapi"]]["name"],
                "samplerate": int(dev.get("default_samplerate", 48000)),
                "channels": dev["max_output_channels"],
            })
    return devices


def print_output_devices(selected: Optional[int] = None) -> None:
    if sd is None:
        print(f"[audio] Audio library not available: {_SD_ERROR}")
        return
    default_out = sd.default.device[1] if sd.default.device else None
    print("\nAvailable audio OUTPUT devices (put part of a name in config.yaml > audio > output_device):")
    for d in output_devices():
        tags = []
        if d["index"] == default_out:
            tags.append("system default")
        if d["index"] == selected:
            tags.append("<-- COMMENTATOR")
        tag = f"  [{', '.join(tags)}]" if tags else ""
        print(f"  {d['index']:>3}: {d['name']}  ({d['hostapi']}){tag}")
    print()


def find_device(name_or_index) -> Optional[int]:
    """Match a config value (name fragment or number) to a device index."""
    if sd is None or name_or_index in (None, ""):
        return None
    if isinstance(name_or_index, int) or str(name_or_index).strip().isdigit():
        return int(name_or_index)
    wanted = str(name_or_index).lower()
    matches = [d for d in output_devices() if wanted in d["name"].lower()]
    if not matches:
        return None
    matches.sort(key=lambda d: _HOSTAPI_PREFERENCE.index(d["hostapi"])
                 if d["hostapi"] in _HOSTAPI_PREFERENCE else 99)
    return matches[0]["index"]


def _resample(samples: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst or len(samples) == 0:
        return samples
    n = int(round(len(samples) * dst / src))
    x_old = np.linspace(0, 1, len(samples), endpoint=False)
    x_new = np.linspace(0, 1, n, endpoint=False)
    return np.interp(x_new, x_old, samples).astype(np.float32)


class AudioPlayer:
    """Blocking playback to the commentator device (and optionally your speakers)."""

    def __init__(self, audio_cfg: dict) -> None:
        self.volume = float(audio_cfg.get("volume", 0.9))
        self.device = find_device(audio_cfg.get("output_device"))
        self.also_default = bool(audio_cfg.get("also_play_on_default", False))
        self._stop = threading.Event()
        wanted = audio_cfg.get("output_device")
        if sd is None:
            print(f"[audio] No audio output available ({_SD_ERROR}). Lines will be shown but not played.")
        elif wanted and self.device is None:
            print(f"[audio] WARNING: no output device matching '{wanted}'. Using the system default "
                  "instead - is VB-Audio Virtual Cable installed? (see README)")
        print_output_devices(self.device)

    @property
    def available(self) -> bool:
        return sd is not None

    def stop(self) -> None:
        self._stop.set()

    def _play_on(self, samples: np.ndarray, sr: int, device: Optional[int]) -> None:
        dev_sr = sr
        try:
            sd.check_output_settings(device=device, samplerate=sr, channels=1, dtype="float32")
        except Exception:
            info = sd.query_devices(device if device is not None else sd.default.device[1])
            dev_sr = int(info.get("default_samplerate", 48000))
            samples = _resample(samples, sr, dev_sr)
        block = 1024
        with sd.OutputStream(samplerate=dev_sr, device=device, channels=1, dtype="float32") as stream:
            for i in range(0, len(samples), block):
                if self._stop.is_set():
                    break
                stream.write(samples[i:i + block].reshape(-1, 1))

    def play(self, samples: np.ndarray, sample_rate: int) -> None:
        if sd is None:
            return
        self._stop.clear()
        samples = np.clip(samples * self.volume, -1.0, 1.0).astype(np.float32)
        threads = []
        if self.also_default and self.device is not None:
            t = threading.Thread(target=self._safe_play, args=(samples, sample_rate, None), daemon=True)
            t.start()
            threads.append(t)
        self._safe_play(samples, sample_rate, self.device)
        for t in threads:
            t.join(timeout=10)

    def _safe_play(self, samples, sr, device) -> None:
        try:
            self._play_on(samples, sr, device)
        except Exception as exc:
            print(f"[audio] Playback failed on device {device}: {exc}")
