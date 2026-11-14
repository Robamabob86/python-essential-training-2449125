"""Global hotkeys: mute/unmute and 'say something now'. Work while iRacing has focus."""

from __future__ import annotations

from typing import Callable


def register_hotkeys(cfg: dict, on_mute: Callable[[], None], on_force: Callable[[], None]) -> bool:
    if not cfg.get("enabled", True):
        return False
    try:
        import keyboard
    except Exception as exc:
        print(f"[hotkeys] Hotkeys unavailable ({exc}). Install with: pip install keyboard")
        return False
    try:
        keyboard.add_hotkey(cfg.get("mute_toggle", "ctrl+shift+m"), on_mute)
        keyboard.add_hotkey(cfg.get("force_line", "ctrl+shift+l"), on_force)
    except Exception as exc:
        print(f"[hotkeys] Couldn't register hotkeys ({exc}). Try running as administrator.")
        return False
    print(f"[hotkeys] Mute/unmute: {cfg.get('mute_toggle')}   Force a line: {cfg.get('force_line')}")
    return True
