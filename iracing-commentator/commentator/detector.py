"""Watches a stream of Snapshots and spots the interesting moments."""

from __future__ import annotations

import random
import statistics
from collections import deque
from typing import Optional

from . import numbers as nw
from .events import Event, EventType
from .telemetry import (FLAG_CHECKERED, FLAG_GREEN, FLAG_WHITE, STATE_CHECKERED,
                        STATE_COOL_DOWN, STATE_RACING, Snapshot)

# How iRacing scores incidents on road courses
INCIDENT_KINDS = {
    1: "off-track (all four wheels off)",
    2: "loss of control (a spin or big slide)",
    4: "contact with another car",
}


def build_context(s: Snapshot) -> dict:
    """The race state every event carries - raw numbers plus spoken versions."""
    ctx = {
        "track": s.track_name or "unknown track",
        "car": s.car_name or "unknown car",
        "driver": s.driver_name or "our driver",
        "session_type": s.session_type,
        "lap": s.lap,
        "laps_completed": s.laps_completed,
        "total_laps": s.total_laps,
        "laps_remaining": s.laps_remaining,
        "position": s.position or None,
        "position_spoken": nw.position_words(s.position),
        "total_cars": s.total_cars,
        "starting_position": s.starting_position,
        "gap_ahead_s": round(s.gap_ahead, 2) if s.gap_ahead is not None else None,
        "gap_ahead_spoken": nw.gap_words(s.gap_ahead) if s.gap_ahead is not None else None,
        "car_ahead": s.car_ahead_name or None,
        "gap_behind_s": round(s.gap_behind, 2) if s.gap_behind is not None else None,
        "gap_behind_spoken": nw.gap_words(s.gap_behind) if s.gap_behind is not None else None,
        "car_behind": s.car_behind_name or None,
        "last_lap_s": round(s.last_lap_time, 3) if s.last_lap_time else None,
        "last_lap_spoken": nw.laptime_words(s.last_lap_time) if s.last_lap_time else None,
        "best_lap_s": round(s.best_lap_time, 3) if s.best_lap_time else None,
        "best_lap_spoken": nw.laptime_words(s.best_lap_time) if s.best_lap_time else None,
        "incident_points": s.incidents,
        "in_pits": s.on_pit_road,
    }
    if s.time_remaining is not None and s.total_laps is None:
        ctx["minutes_remaining"] = round(s.time_remaining / 60, 1)
    return {k: v for k, v in ctx.items() if v is not None}


class EventDetector:
    def __init__(self, cfg: dict) -> None:
        d = cfg.get("detection", {})
        c = cfg.get("commentator", {})
        self.battle_gap = float(d.get("battle_gap_seconds", 1.0))
        self.battle_closing = float(d.get("battle_closing_seconds", 0.4))
        self.battle_repeat = float(d.get("battle_repeat_seconds", 40))
        self.slow_lap_factor = 1 + float(d.get("slow_lap_percent", 7)) / 100
        self.settle = float(d.get("position_settle_seconds", 1.2))
        self.quiet_period = float(c.get("quiet_period_seconds", 45))
        self.reset()

    def reset(self) -> None:
        self.prev: Optional[Snapshot] = None
        self.race_started = False
        self.white_called = False
        self.checkered_seen_at_lap: Optional[int] = None
        self.finished = False
        self.start_position: Optional[int] = None
        self.stable_position: Optional[int] = None
        self.pending_position: Optional[int] = None
        self.pending_since = 0.0
        self.lap_times: list[float] = []
        self.best_seen: Optional[float] = None
        self.pitted_this_lap = False
        self.gap_ahead_hist: deque = deque()
        self.gap_behind_hist: deque = deque()
        self.last_battle: dict[str, tuple[float, str]] = {}
        self.last_activity = None  # monotonic time of last event/line
        self.incidents_total = 0
        self.positions_history: list[int] = []
        self._next_quiet = self.quiet_period
        self._incident_events = 0

    # Called by the director whenever a line is spoken, so colour commentary
    # only fills genuine silence.
    def note_activity(self, now: float) -> None:
        self.last_activity = now
        self._next_quiet = self.quiet_period * random.uniform(0.8, 1.3)

    def update(self, s: Snapshot, now: float) -> list[Event]:
        events: list[Event] = []
        if self.last_activity is None:
            self.last_activity = now
        p = self.prev
        if p is None or s.track_name != p.track_name or s.session_type != p.session_type:
            # New session (or first read): learn the state, don't shout about it.
            if p is not None:
                self.reset()
                self.last_activity = now
            self.prev = s
            self.stable_position = s.position or None
            self.incidents_total = s.incidents
            self.best_seen = s.best_lap_time
            if s.is_race and s.session_state >= STATE_RACING:
                self.race_started = True  # joined mid-race
                self.start_position = s.starting_position or s.position or None
            return events

        def emit(etype: EventType, **detail) -> None:
            events.append(Event(etype, context=build_context(s), detail=detail, created_at=now))

        if s.is_race:
            self._race_flags(p, s, emit)
            self._positions(s, now, emit)
            self._battles(s, now, emit)
        self._incidents(p, s, emit)
        self._laps(p, s, emit)
        self._pits(p, s, emit)

        if events:
            self.last_activity = now
        elif now - self.last_activity >= self._next_quiet and not self.finished:
            emit(EventType.COLOUR, **self._colour_detail(s))
            self.note_activity(now)

        self.prev = s
        return events

    def force_event(self, s: Optional[Snapshot], now: float) -> Event:
        """Hotkey 'say something now'."""
        ctx = build_context(s) if s else {}
        detail = self._colour_detail(s) if s else {}
        return Event(EventType.COLOUR, context=ctx, detail=detail, created_at=now, forced=True)

    # -- individual detectors -------------------------------------------------
    def _race_flags(self, p: Snapshot, s: Snapshot, emit) -> None:
        green_now = bool(s.session_flags & FLAG_GREEN) or s.session_state == STATE_RACING
        if not self.race_started and green_now and s.session_state >= STATE_RACING:
            self.race_started = True
            self.start_position = s.starting_position or s.position or None
            emit(EventType.RACE_START, starting_position=self.start_position,
                 starting_position_spoken=nw.position_words(self.start_position or 0))

        if (self.race_started and not self.white_called and s.session_flags & FLAG_WHITE
                and s.session_state == STATE_RACING):
            self.white_called = True
            emit(EventType.FINAL_LAP)

        checkered = bool(s.session_flags & FLAG_CHECKERED) or s.session_state >= STATE_CHECKERED
        if self.race_started and checkered and self.checkered_seen_at_lap is None:
            self.checkered_seen_at_lap = p.laps_completed
        if (self.race_started and not self.finished and self.checkered_seen_at_lap is not None
                and (s.laps_completed > self.checkered_seen_at_lap or s.session_state >= STATE_COOL_DOWN)):
            self.finished = True
            start = self.start_position
            gained = (start - s.position) if (start and s.position) else None
            emit(EventType.CHEQUERED_FLAG,
                 finishing_position=s.position,
                 finishing_position_spoken=nw.position_words(s.position),
                 starting_position=start,
                 positions_gained=gained,
                 total_incidents=s.incidents,
                 race_story=self._race_story())

    def _positions(self, s: Snapshot, now: float, emit) -> None:
        if not self.race_started or self.finished or not s.position:
            return
        if self.stable_position is None:
            self.stable_position = s.position
            return
        if s.position == self.stable_position:
            self.pending_position = None
            return
        if s.position != self.pending_position:
            self.pending_position, self.pending_since = s.position, now
            return
        if now - self.pending_since < self.settle:
            return
        old, new = self.stable_position, s.position
        self.stable_position, self.pending_position = new, None
        self.positions_history.append(new)
        change = old - new
        detail = dict(old_position=old, new_position=new,
                      new_position_spoken=nw.position_words(new),
                      places=abs(change))
        if self.start_position:
            detail["net_vs_start"] = self.start_position - new
        emit(EventType.POSITION_GAINED if change > 0 else EventType.POSITION_LOST, **detail)

    def _battles(self, s: Snapshot, now: float, emit) -> None:
        if not self.race_started or self.finished or s.on_pit_road:
            self.gap_ahead_hist.clear()
            self.gap_behind_hist.clear()
            return
        for hist, gap, name, etype in (
            (self.gap_ahead_hist, s.gap_ahead, s.car_ahead_name, EventType.BATTLE_AHEAD),
            (self.gap_behind_hist, s.gap_behind, s.car_behind_name, EventType.UNDER_PRESSURE),
        ):
            if gap is None:
                hist.clear()
                continue
            if hist and hist[-1][2] != name:  # different car now - start again
                hist.clear()
            hist.append((now, gap, name))
            while hist and now - hist[0][0] > 10.0:
                hist.popleft()
            if now - hist[0][0] < 4.0:
                continue
            closed_by = max(g for _, g, _ in hist) - gap
            if gap <= self.battle_gap and closed_by >= self.battle_closing:
                last_t, last_name = self.last_battle.get(etype.value, (-1e9, ""))
                if now - last_t >= self.battle_repeat or last_name != name:
                    self.last_battle[etype.value] = (now, name)
                    emit(etype, rival=name or "the car", gap_s=round(gap, 2),
                         gap_spoken=nw.gap_words(gap), closed_by_s=round(closed_by, 2),
                         closed_by_spoken=nw.delta_words(closed_by) + " in the last few seconds")
                    hist.clear()

    def _incidents(self, p: Snapshot, s: Snapshot, emit) -> None:
        if s.incidents > self.incidents_total:
            delta = s.incidents - self.incidents_total
            self.incidents_total = s.incidents
            kind = INCIDENT_KINDS.get(delta, "a combination of off-tracks/contact")
            emit(EventType.INCIDENT, new_points=delta, kind=kind, total_points=s.incidents,
                 times_this_session=self._incident_count_bump())
        elif s.incidents < self.incidents_total:  # counter reset (new session)
            self.incidents_total = s.incidents

    def _incident_count_bump(self) -> int:
        self._incident_events += 1
        return self._incident_events

    def _laps(self, p: Snapshot, s: Snapshot, emit) -> None:
        if s.laps_completed <= p.laps_completed:
            if s.on_pit_road:
                self.pitted_this_lap = True
            return
        lap_time = s.last_lap_time
        pitted, self.pitted_this_lap = self.pitted_this_lap or s.on_pit_road, False
        if not lap_time or lap_time <= 0 or (s.laps_completed <= 1 and s.is_race):
            if s.best_lap_time and self.best_seen is None:
                self.best_seen = s.best_lap_time
            return  # standing-start lap or no valid time
        is_pb = (s.best_lap_time is not None and abs(s.best_lap_time - lap_time) < 0.001
                 and (self.best_seen is None or lap_time < self.best_seen - 0.001))
        clean = self.lap_times[-8:]
        avg = statistics.mean(clean) if len(clean) >= 2 else None
        if is_pb:
            improvement = (self.best_seen - lap_time) if self.best_seen else None
            self.best_seen = lap_time
            emit(EventType.PERSONAL_BEST, lap_time_spoken=nw.laptime_words(lap_time),
                 improvement_spoken=nw.delta_words(improvement) if improvement else "first timed lap")
        elif avg and lap_time > avg * self.slow_lap_factor and not pitted:
            emit(EventType.SLOW_LAP, lap_time_spoken=nw.laptime_words(lap_time),
                 slower_by_spoken=nw.delta_words(lap_time - avg),
                 average_spoken=nw.laptime_words(avg))
        if not pitted and (avg is None or lap_time < avg * self.slow_lap_factor):
            self.lap_times.append(lap_time)
        if s.best_lap_time and (self.best_seen is None or s.best_lap_time < self.best_seen):
            self.best_seen = s.best_lap_time

    def _pits(self, p: Snapshot, s: Snapshot, emit) -> None:
        if s.on_pit_road and not p.on_pit_road:
            self.pitted_this_lap = True
            emit(EventType.PIT_ENTRY)
        elif p.on_pit_road and not s.on_pit_road:
            emit(EventType.PIT_EXIT)

    # -- helpers ----------------------------------------------------------------
    def _colour_detail(self, s: Snapshot) -> dict:
        topics = ["the driver's progress so far", "the gap to the cars around", "lap times and consistency",
                  "the track and car", "incident count and survival", "what's needed for the rest of the race",
                  "life as an iRacing rookie", "the channel and the viewers watching"]
        detail = {"suggested_topic": random.choice(topics)}
        if self.lap_times:
            detail["average_lap_spoken"] = nw.laptime_words(statistics.mean(self.lap_times[-8:]))
        if self.start_position and s.position and s.is_race:
            detail["net_positions_vs_start"] = self.start_position - s.position
        return detail

    def _race_story(self) -> str:
        bits = []
        if self.positions_history:
            bits.append("positions held during race: " + ", ".join(map(str, self.positions_history[-12:])))
        bits.append(f"incident events: {self._incident_events}")
        return "; ".join(bits)
