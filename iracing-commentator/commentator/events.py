"""Race events and their priorities."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    RACE_START = "race_start"
    FINAL_LAP = "final_lap"
    POSITION_GAINED = "position_gained"
    POSITION_LOST = "position_lost"
    BATTLE_AHEAD = "battle_ahead"        # closing on the car in front
    UNDER_PRESSURE = "under_pressure"    # car behind closing on us
    INCIDENT = "incident"
    PERSONAL_BEST = "personal_best"
    SLOW_LAP = "slow_lap"
    PIT_ENTRY = "pit_entry"
    PIT_EXIT = "pit_exit"
    CHEQUERED_FLAG = "chequered_flag"
    COLOUR = "colour"                    # quiet-period colour commentary


# Higher number = more important. Incidents, overtakes and the finish win.
PRIORITY: dict[EventType, int] = {
    EventType.CHEQUERED_FLAG: 100,
    EventType.INCIDENT: 90,
    EventType.POSITION_GAINED: 80,
    EventType.POSITION_LOST: 80,
    EventType.RACE_START: 75,
    EventType.FINAL_LAP: 70,
    EventType.BATTLE_AHEAD: 60,
    EventType.UNDER_PRESSURE: 60,
    EventType.PIT_ENTRY: 50,
    EventType.PIT_EXIT: 50,
    EventType.PERSONAL_BEST: 45,
    EventType.SLOW_LAP: 40,
    EventType.COLOUR: 10,
}

# What the event means, in plain words, for the AI.
DESCRIPTION: dict[EventType, str] = {
    EventType.RACE_START: "The green flag is out - the race has started.",
    EventType.FINAL_LAP: "White flag - the driver has started the final lap.",
    EventType.POSITION_GAINED: "The driver has just gained a position (overtake or someone else's mistake).",
    EventType.POSITION_LOST: "The driver has just lost a position.",
    EventType.BATTLE_AHEAD: "The driver is closing quickly on the car ahead - a battle is building.",
    EventType.UNDER_PRESSURE: "The car behind is closing quickly on the driver - they're under pressure.",
    EventType.INCIDENT: "The driver just picked up incident points.",
    EventType.PERSONAL_BEST: "The driver just set a new personal best lap.",
    EventType.SLOW_LAP: "The driver just completed a lap much slower than their average.",
    EventType.PIT_ENTRY: "The driver is entering the pit lane.",
    EventType.PIT_EXIT: "The driver is leaving the pit lane and rejoining.",
    EventType.CHEQUERED_FLAG: "Chequered flag - the driver has finished the race.",
    EventType.COLOUR: "Nothing much is happening. Give a bit of colour commentary on the current state of play.",
}


@dataclass
class Event:
    type: EventType
    context: dict[str, Any] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.monotonic)
    forced: bool = False  # created by the "force a line" hotkey

    @property
    def priority(self) -> int:
        return PRIORITY[self.type]

    def age(self, now: float | None = None) -> float:
        return (now if now is not None else time.monotonic()) - self.created_at

    def __str__(self) -> str:
        bits = ", ".join(f"{k}={v}" for k, v in self.detail.items())
        return f"{self.type.value}({bits})" if bits else self.type.value
