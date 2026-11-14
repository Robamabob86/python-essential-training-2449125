"""The Director decides what gets said, and when.

Rules (all configurable in config.yaml > commentator):
- One line at a time. While a line is being written/spoken, only the single most
  important waiting event is kept; anything less important is dropped.
- Cooldown after each line. During it, low-priority events are dropped; big ones
  (incidents, overtakes, finish) may still get through after a short minimum gap.
- Never stale: if a line isn't ready to play within max_line_age_seconds of the
  moment it describes, it is thrown away instead of being played late.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from .events import Event
from .llm import LineWriter


class Director:
    def __init__(self, cfg: dict, writer: LineWriter, tts, player, ducker=None, log=None,
                 on_spoken: Optional[Callable[[float], None]] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        c = cfg["commentator"]
        self.cooldown = float(c.get("cooldown_seconds", 8))
        self.bypass = int(c.get("cooldown_bypass_priority", 80))
        self.min_gap = float(c.get("min_gap_seconds", 2.5))
        self.max_age = float(c.get("max_line_age_seconds", 4.0))
        self.writer, self.tts, self.player = writer, tts, player
        self.ducker, self.log, self.on_spoken = ducker, log, on_spoken
        self.clock = clock
        self.muted = False
        self.busy = False
        self.last_end = -1e9
        self.pending: Optional[Event] = None
        self.session_time: Optional[float] = None
        self._cv = threading.Condition()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self.stats = {"spoken": 0, "dropped": 0, "stale": 0}

    # -- public API -------------------------------------------------------------
    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="director", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        with self._cv:
            self._running = False
            self._cv.notify_all()
        self.player.stop()
        if self._thread:
            self._thread.join(timeout=3)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self.muted:
            self.player.stop()
            with self._cv:
                self.pending = None
        print(f"\n[director] Commentator {'MUTED' if self.muted else 'LIVE'}\n")
        return self.muted

    def in_cooldown(self, now: Optional[float] = None) -> bool:
        now = self.clock() if now is None else now
        return now < self.last_end + self.cooldown

    def submit(self, event: Event) -> bool:
        """Offer an event. Returns True if it was accepted (it may still be dropped later)."""
        now = self.clock()
        if self.muted:
            return False
        with self._cv:
            if not self._allowed(event, now):
                self._drop(event, "cooldown")
                return False
            if self.pending is not None:
                if event.priority < self.pending.priority:
                    self._drop(event, f"lower priority than waiting {self.pending.type.value}")
                    return False
                self._drop(self.pending, f"replaced by {event.type.value}")
            self.pending = event
            self._cv.notify_all()
        return True

    # -- internals --------------------------------------------------------------
    def _allowed(self, event: Event, now: float) -> bool:
        if event.forced:
            return True
        if event.age(now) > self.max_age:
            return False
        if not self.in_cooldown(now):
            return True
        return event.priority >= self.bypass

    def _drop(self, event: Event, why: str) -> None:
        self.stats["dropped"] += 1
        print(f"[director] dropped {event} - {why}")

    def _take(self) -> Optional[Event]:
        """Pop the waiting event once it may be spoken, or None (and drop it) if it went stale."""
        with self._cv:
            event = self.pending
            if event is None:
                return None
            now = self.clock()
            if event.age(now) > self.max_age:
                self.pending = None
                self.stats["stale"] += 1
                print(f"[director] skipped {event} - stale before we could start")
                return None
            if not event.forced and now < self.last_end + self.min_gap:
                return None  # wait for the minimum gap
            if not self._allowed(event, now):
                self.pending = None
                self._drop(event, "cooldown")
                return None
            self.pending = None
            self.busy = True
            return event

    def run_pending(self) -> bool:
        """Process the waiting event (if any) right now. Returns True if a line was spoken."""
        event = self._take()
        if event is None:
            return False
        try:
            return self._handle(event)
        finally:
            self.busy = False

    def _superseded(self, event: Event) -> bool:
        p = self.pending
        return p is not None and p.priority > event.priority

    def _handle(self, event: Event) -> bool:
        line, source, took = self.writer.write(event)
        if not line:
            return False
        if self._superseded(event):
            print(f"[director] binned line for {event} - something bigger happened")
            return False
        try:
            clip = self.tts.synthesize(line, event.type.value)
        except Exception as exc:
            print(f"[tts] Speech failed: {exc}")
            if self.log:
                self.log.write(line, event.type.value, self.session_time, status=f"tts failed: {exc}")
            return False
        age = event.age(self.clock())
        if age > self.max_age and not event.forced:
            self.stats["stale"] += 1
            print(f"[director] skipped (stale, {age:.1f}s old): {line}")
            if self.log:
                self.log.write(line, event.type.value, self.session_time, status=f"skipped: stale {age:.1f}s")
            return False
        if self.muted or self._superseded(event):
            return False

        print(f"\n  >> [{event.type.value}] {line}    ({source}, ready in {age:.1f}s)\n")
        if self.ducker:
            self.ducker.duck()
        try:
            self.player.play(clip.samples, clip.sample_rate)
        finally:
            if self.ducker:
                self.ducker.restore()
        self.last_end = self.clock()
        self.writer.remember(event, line)
        self.stats["spoken"] += 1
        if self.log:
            self.log.write(line, event.type.value, self.session_time, clip=clip)
        if self.on_spoken:
            self.on_spoken(self.last_end)
        return True

    def _loop(self) -> None:
        while True:
            with self._cv:
                while self._running and self.pending is None:
                    self._cv.wait(timeout=0.5)
                if not self._running:
                    return
            try:
                if not self.run_pending():
                    time.sleep(0.05)
            except Exception as exc:  # never let one bad line kill the commentator
                print(f"[director] error: {exc}")
                self.busy = False
