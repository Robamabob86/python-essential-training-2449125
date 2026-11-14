from commentator.config import load_config
from commentator.detector import EventDetector
from commentator.events import EventType
from commentator.fake_race import FakeRaceSource
from commentator.telemetry import STATE_RACING, Snapshot


def run_fake_race():
    cfg = load_config()
    cfg["commentator"]["quiet_period_seconds"] = 20
    t = [0.0]
    src, det = FakeRaceSource(clock=lambda: t[0]), EventDetector(cfg)
    events = []
    while not src.finished:
        events += det.update(src.read(), t[0])
        t[0] += 0.1
    return events


def test_fake_race_produces_every_event_type():
    types = {e.type for e in run_fake_race()}
    assert types == set(EventType)


def test_events_carry_context():
    for e in run_fake_race():
        for key in ("track", "car", "lap", "position_spoken", "total_cars", "incident_points"):
            assert key in e.context, (e, key)


def test_finish_reports_positions_gained():
    finish = [e for e in run_fake_race() if e.type == EventType.CHEQUERED_FLAG]
    assert len(finish) == 1
    assert finish[0].detail["starting_position"] == 14
    assert finish[0].detail["finishing_position"] == 13
    assert finish[0].detail["positions_gained"] == 1


def test_position_flicker_is_ignored():
    det = EventDetector(load_config())
    base = dict(track_name="T", session_state=STATE_RACING, position=10, total_cars=20)
    det.update(Snapshot(**base), 0.0)
    assert det.update(Snapshot(**{**base, "position": 9}), 0.1) == []
    assert det.update(Snapshot(**base), 0.2) == []            # flicked back: nothing
    assert det.update(Snapshot(**{**base, "position": 9}), 0.3) == []
    events = det.update(Snapshot(**{**base, "position": 9}), 2.0)
    assert [e.type for e in events] == [EventType.POSITION_GAINED]


def test_incident_kinds():
    det = EventDetector(load_config())
    det.update(Snapshot(track_name="T", incidents=0), 0)
    ev = det.update(Snapshot(track_name="T", incidents=4), 1)
    assert ev[0].type == EventType.INCIDENT and "contact" in ev[0].detail["kind"]
