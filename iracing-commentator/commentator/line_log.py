"""Writes every spoken line, with timestamps, to logs/ (handy for editing and Shorts)."""

from __future__ import annotations

import time
import wave
from datetime import datetime
from pathlib import Path

from .config import PROJECT_ROOT


class LineLog:
    def __init__(self, cfg: dict) -> None:
        folder = Path(cfg.get("folder", "logs"))
        self.folder = folder if folder.is_absolute() else PROJECT_ROOT / folder
        self.folder.mkdir(parents=True, exist_ok=True)
        self.save_clips = bool(cfg.get("save_audio_clips", False))
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.path = self.folder / f"commentary_{stamp}.txt"
        self.clip_dir = self.folder / f"clips_{stamp}"
        self.started = time.monotonic()
        self._n = 0
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(f"# Commentary log started {datetime.now():%Y-%m-%d %H:%M:%S}\n")
            fh.write("# wall-clock | since start | race time | event | line\n")
        print(f"[log] Writing lines to {self.path}")

    def write(self, line: str, event_type: str, session_time: float | None = None,
              status: str = "spoken", clip=None) -> None:
        self._n += 1
        since = time.monotonic() - self.started
        race = f"{int(session_time // 60):02d}:{session_time % 60:05.2f}" if session_time else "--:--"
        entry = (f"[{datetime.now():%H:%M:%S}] +{int(since // 3600):d}:{int(since % 3600 // 60):02d}:"
                 f"{since % 60:04.1f} | race {race} | {event_type:<15} | {line}")
        if status != "spoken":
            entry += f"   ({status})"
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(entry + "\n")
        if self.save_clips and clip is not None and status == "spoken":
            import numpy as np

            self.clip_dir.mkdir(exist_ok=True)
            pcm = (np.clip(clip.samples, -1, 1) * 32767).astype("<i2").tobytes()
            with wave.open(str(self.clip_dir / f"{self._n:04d}_{event_type}.wav"), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(clip.sample_rate)
                wf.writeframes(pcm)
