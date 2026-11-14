"""A scripted pretend race, so you can hear the commentator without iRacing.

It produces the same Snapshot objects as the real telemetry, so the real event
detector, AI, voice and audio output are all exercised end to end.
"""

from __future__ import annotations

import copy
import time
from typing import Optional

from .telemetry import (FLAG_CHECKERED, FLAG_GREEN, FLAG_WHITE, STATE_CHECKERED,
                        STATE_COOL_DOWN, STATE_PARADE, STATE_RACING, Snapshot)

# (seconds from start, changes). "ramp" smoothly moves a value over N seconds.
TIMELINE: list[tuple[float, dict]] = [
    (0, dict(session_state=STATE_PARADE, position=14, starting_position=14, lap=0)),
    (4, dict(session_state=STATE_RACING, session_flags=FLAG_GREEN, lap=1)),
    (13, dict(position=12)),                                  # two places at the start
    (24, dict(incidents=1)),                                  # 1x off-track
    (32, dict(laps_completed=1, lap=2, last_lap_time=98.214, best_lap_time=98.214)),
    (35, dict(gap_ahead=1.7, ramp=dict(gap_ahead=(0.45, 7)))),  # reeling in the car ahead
    (47, dict(position=11, gap_ahead=2.1, car_ahead_name="M. Verstappen Jr", gap_behind=0.9, car_behind_name="J. Hamilton")),
    (57, dict(laps_completed=2, lap=3, last_lap_time=94.811, best_lap_time=94.811)),  # PB
    (68, dict(incidents=5, position=13, gap_behind=1.2)),     # 4x contact, lose two
    (80, dict(laps_completed=3, lap=4, last_lap_time=95.302)),
    (84, dict(laps_completed=4, lap=5, last_lap_time=95.020)),
    (96, dict(laps_completed=5, lap=6, last_lap_time=103.95)),  # slow lap
    (106, dict(on_pit_road=True)),
    (118, dict(on_pit_road=False, position=15, gap_behind=2.4)),
    (124, dict(gap_behind=2.4, ramp=dict(gap_behind=(0.5, 7)))),  # under pressure
    # ...quiet stretch here: colour commentary should fill it
    (165, dict(position=14, laps_completed=6, lap=7, last_lap_time=96.4)),
    (176, dict(session_flags=FLAG_WHITE)),
    (189, dict(position=13)),
    (200, dict(session_flags=FLAG_CHECKERED, session_state=STATE_CHECKERED)),
    (203, dict(laps_completed=7, lap=8, last_lap_time=95.88)),
    (215, dict(session_state=STATE_COOL_DOWN)),
]
DURATION = 222.0


class FakeRaceSource:
    """Drop-in replacement for IRacingSource. speed=2.0 plays twice as fast."""

    def __init__(self, driver_name: str = "", speed: float = 1.0, clock=time.monotonic) -> None:
        self.speed = max(0.1, float(speed))
        self.clock = clock
        self.start = clock()
        self.connected = True
        self.snap = Snapshot(
            track_name="Okayama International Circuit - Short",
            car_name="Mazda MX-5 Cup",
            driver_name=driver_name or "Rookie",
            session_type="Race",
            total_cars=22,
            total_laps=7,
            laps_remaining=7,
            gap_ahead=2.5,
            gap_behind=1.8,
            car_ahead_name="J. Hamilton",
            car_behind_name="D. Ricciardo-Smith",
        )
        self._next = 0
        self._ramps: dict[str, tuple[float, float, float, float]] = {}

    @property
    def elapsed(self) -> float:
        return (self.clock() - self.start) * self.speed

    @property
    def finished(self) -> bool:
        return self.elapsed > DURATION

    def read(self) -> Optional[Snapshot]:
        t = self.elapsed
        while self._next < len(TIMELINE) and TIMELINE[self._next][0] <= t:
            at, changes = TIMELINE[self._next]
            changes = dict(changes)
            for key, (target, dur) in changes.pop("ramp", {}).items():
                self._ramps[key] = (at, dur, float(changes.get(key, getattr(self.snap, key))), target)
            for key, value in changes.items():
                setattr(self.snap, key, value)
                if key in self._ramps and key not in TIMELINE[self._next][1].get("ramp", {}):
                    del self._ramps[key]
            self._next += 1
        for key, (at, dur, frm, to) in list(self._ramps.items()):
            frac = min(1.0, (t - at) / dur)
            setattr(self.snap, key, frm + (to - frm) * frac)
            if frac >= 1.0:
                del self._ramps[key]
        self.snap.session_time = t
        if self.snap.laps_remaining is not None and self.snap.total_laps:
            self.snap.laps_remaining = max(0, self.snap.total_laps - self.snap.laps_completed)
        return copy.deepcopy(self.snap)

    def close(self) -> None:
        pass
