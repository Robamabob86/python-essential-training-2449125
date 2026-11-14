import numpy as np

from commentator.config import load_config
from commentator.director import Director
from commentator.events import Event, EventType
from commentator.tts.base import Clip


class Clock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class FakeWriter:
    def __init__(self, clock, delay=0.5):
        self.clock, self.delay, self.history = clock, delay, []

    def write(self, event):
        self.clock.t += self.delay  # pretend the AI takes a moment
        return f"line for {event.type.value}", "ai", self.delay

    def remember(self, event, line):
        self.history.append(line)


class FakeTTS:
    name = "fake"

    def __init__(self, clock, delay=0.3):
        self.clock, self.delay = clock, delay

    def synthesize(self, text, event_type="default"):
        self.clock.t += self.delay
        return Clip(np.zeros(2400, dtype=np.float32))


class FakePlayer:
    def __init__(self, clock):
        self.clock, self.played = clock, 0

    def play(self, samples, sr):
        self.clock.t += 2.0
        self.played += 1

    def stop(self):
        pass


def make(writer_delay=0.5, tts_delay=0.3):
    clock = Clock()
    d = Director(load_config(), FakeWriter(clock, writer_delay), FakeTTS(clock, tts_delay),
                 FakePlayer(clock), clock=clock)
    return d, clock


def ev(etype, clock, **kw):
    return Event(etype, created_at=clock.t, **kw)


def test_speaks_and_remembers():
    d, clock = make()
    assert d.submit(ev(EventType.PERSONAL_BEST, clock))
    assert d.run_pending()
    assert d.writer.history == ["line for personal_best"]


def test_low_priority_dropped_during_cooldown_high_priority_allowed():
    d, clock = make()
    d.submit(ev(EventType.PIT_ENTRY, clock)); d.run_pending()
    clock.t += 3  # inside 8s cooldown, past min gap
    assert not d.submit(ev(EventType.COLOUR, clock))
    assert d.submit(ev(EventType.INCIDENT, clock))
    assert d.run_pending()


def test_higher_priority_replaces_waiting_event():
    d, clock = make()
    d.submit(ev(EventType.SLOW_LAP, clock))
    d.submit(ev(EventType.POSITION_GAINED, clock))
    assert not d.submit(ev(EventType.COLOUR, clock))
    d.run_pending()
    assert d.writer.history == ["line for position_gained"]


def test_stale_lines_are_skipped():
    d, clock = make(writer_delay=3.5, tts_delay=1.0)  # 4.5s > 4s limit
    d.submit(ev(EventType.POSITION_GAINED, clock))
    assert not d.run_pending()
    assert d.stats["stale"] == 1 and d.player.played == 0


def test_mute_drops_everything():
    d, clock = make()
    d.toggle_mute()
    assert not d.submit(ev(EventType.CHEQUERED_FLAG, clock))
