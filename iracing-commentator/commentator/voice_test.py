"""Speaks a sample line for every event type so you can tune voice, speed and pitch."""

from __future__ import annotations

import time

from .events import Event, EventType
from .tts.base import prosody_for

SAMPLES: dict[EventType, str] = {
    EventType.RACE_START: "Lights out... and away we go! Deep breaths, rookie - don't hit anybody!",
    EventType.FINAL_LAP: "White flag! One more lap... just keep it on the black stuff!",
    EventType.POSITION_GAINED: "He's alongside... he's got the run... and he's THROUGH! Up to ninth!",
    EventType.POSITION_LOST: "Oh, that's gone. Mugged into turn one - down to twelfth.",
    EventType.BATTLE_AHEAD: "The gap's tumbling - half a second now... this is getting tasty!",
    EventType.UNDER_PRESSURE: "Mirrors full of car! Hold your nerve - stay tidy!",
    EventType.INCIDENT: "Oh dear. The grass is NOT a racing line... that's twice now!",
    EventType.PERSONAL_BEST: "Purple! A personal best - one thirty-four point eight! Where did THAT come from?",
    EventType.SLOW_LAP: "Hmm. That lap was... scenic. Nearly nine seconds off.",
    EventType.PIT_ENTRY: "In we come... mind the speed limiter, please.",
    EventType.PIT_EXIT: "Back out we go - cold tyres, so gently does it.",
    EventType.CHEQUERED_FLAG: "Chequered flag! Home in eleventh - three places gained... GET IN!",
    EventType.COLOUR: "Lovely and quiet out there. Smooth is fast, as they say... allegedly.",
}

DEMO_CONTEXT = {
    "track": "Okayama International Circuit - Short", "car": "Mazda MX-5 Cup",
    "driver": "our driver", "session_type": "Race", "lap": 5, "total_laps": 10,
    "position": 9, "position_spoken": "ninth", "total_cars": 20,
    "gap_ahead_s": 0.6, "gap_ahead_spoken": "half a second",
    "last_lap_s": 94.8, "last_lap_spoken": "one thirty-four point eight",
    "best_lap_s": 94.8, "best_lap_spoken": "one thirty-four point eight", "incident_points": 4,
}


def run_voice_test(cfg: dict, tts, player, writer=None, only: str | None = None) -> None:
    voice = cfg["tts"].get("edge", {}).get("voice") if cfg["tts"].get("engine") == "edge" else "ElevenLabs"
    print(f"\n=== Voice test: {tts.name} / {voice} ===")
    if writer is not None:
        print(f"    Lines written live by AI ({cfg['commentator'].get('personality')} personality)\n")
    for etype, sample in SAMPLES.items():
        if only and only not in etype.value:
            continue
        line = sample
        if writer is not None:
            ev = Event(etype, context=DEMO_CONTEXT, detail={"demo": True})
            line, source, took = writer.write(ev)
            writer.remember(ev, line)
            print(f"    (AI took {took:.1f}s, {source})")
        p = prosody_for(cfg["tts"], etype.value)
        t0 = time.monotonic()
        try:
            clip = tts.synthesize(line, etype.value)
        except Exception as exc:
            print(f"[tts] Failed: {exc}")
            continue
        print(f"{etype.value:<16} rate {p.rate:+d}% pitch {p.pitch:+d}Hz  "
              f"(speech ready in {time.monotonic() - t0:.1f}s)\n    \"{line}\"")
        player.play(clip.samples, clip.sample_rate)
        time.sleep(0.6)
    print("\nDone. Tweak tts settings in config.yaml and run the voice test again.\n")
