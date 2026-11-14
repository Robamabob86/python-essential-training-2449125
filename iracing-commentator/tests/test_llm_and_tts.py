import json

from commentator.config import load_config
from commentator.events import Event, EventType
from commentator.llm import LineWriter, clean_line, opener
from commentator.personalities import system_prompt
from commentator.tts.base import prosody_for, split_for_pauses


def test_clean_line():
    assert clean_line('"Up to P5 - get in!"\nextra') == "Up to fifth - get in!"
    assert len(clean_line("word " * 40).split()) <= 22


def test_user_message_has_structured_context(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    w = LineWriter(load_config())
    w.remember(Event(EventType.INCIDENT), "Oh dear, the grass again!")
    msg = w.build_user_message(Event(EventType.INCIDENT, context={"lap": 3}, detail={"kind": "off-track"}))
    payload = json.loads(msg.split("\n", 1)[1].rsplit("\n\n", 1)[0])
    assert payload["race_state"]["lap"] == 3
    assert payload["recent_lines"] == ["Oh dear, the grass again!"]
    assert payload["banned_openers"] == ["oh dear"]


def test_offline_fallback(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    w = LineWriter(load_config())
    line, source, _ = w.write(Event(EventType.POSITION_GAINED, detail={"new_position_spoken": "ninth"}))
    assert source == "canned" and line


def test_both_personalities_exist():
    for p in ("pro", "cheeky"):
        assert "20 words" in system_prompt(p, "The Beep Test", "Rob")
    assert opener("Oh dear, again!") == "oh dear"


def test_pauses_and_prosody():
    segs = split_for_pauses("He's alongside... he's got the run... and he's THROUGH!", 350, 150)
    assert [p for _, p in segs] == [350, 350, 0]
    p = prosody_for(load_config()["tts"], "position_gained")
    assert p.rate == 8 + 14 and p.pitch == 8
