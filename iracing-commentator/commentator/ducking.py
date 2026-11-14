"""Optional: turn the iRacing game volume down while the commentator speaks (Windows only)."""

from __future__ import annotations

import sys


class Ducker:
    def __init__(self, cfg: dict) -> None:
        self.enabled = bool(cfg.get("enabled", False))
        self.level = float(cfg.get("duck_to", 0.35))
        self.process = str(cfg.get("process_name", "iRacingSim64DX11.exe")).lower()
        self._saved: list[tuple[object, float]] = []
        if self.enabled and sys.platform != "win32":
            print("[ducking] Only works on Windows - disabled.")
            self.enabled = False
        if self.enabled:
            try:
                import pycaw.pycaw  # noqa: F401
            except Exception as exc:
                print(f"[ducking] pycaw not installed ({exc}) - disabled. Run: pip install pycaw")
                self.enabled = False

    def _sessions(self):
        from pycaw.pycaw import AudioUtilities

        for session in AudioUtilities.GetAllSessions():
            proc = session.Process
            if proc and proc.name().lower() == self.process:
                yield session.SimpleAudioVolume

    def duck(self) -> None:
        if not self.enabled:
            return
        try:
            import comtypes

            comtypes.CoInitialize()
            self._saved = []
            for vol in self._sessions():
                self._saved.append((vol, vol.GetMasterVolume()))
                vol.SetMasterVolume(self.level, None)
        except Exception as exc:
            print(f"[ducking] Couldn't lower game volume: {exc}")

    def restore(self) -> None:
        if not self.enabled or not self._saved:
            return
        try:
            for vol, level in self._saved:
                vol.SetMasterVolume(level, None)
        except Exception as exc:
            print(f"[ducking] Couldn't restore game volume: {exc}")
        self._saved = []
