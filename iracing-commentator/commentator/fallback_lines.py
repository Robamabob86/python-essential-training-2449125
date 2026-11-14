"""Canned lines used when the AI can't be reached (no internet / no API key).

{pos} = spoken position, {rival} = rival name. Kept deliberately varied.
"""

from __future__ import annotations

import random
import re

from .events import Event, EventType

LINES: dict[EventType, list[str]] = {
    EventType.RACE_START: [
        "Lights out... and away we go!",
        "Green flag! Here we go - deep breaths, and don't hit anybody!",
        "And we're racing! Starting {start}... let's see what we've got.",
    ],
    EventType.FINAL_LAP: [
        "White flag! One lap left - bring it home!",
        "Final lap! Keep it on the black stuff now...",
        "Last time round! No heroics... well, maybe a few.",
    ],
    EventType.POSITION_GAINED: [
        "Get IN! Up to {pos}!",
        "Oh, that's lovely! Into {pos} now!",
        "And that's a MOVE! {pos} - brilliant!",
        "Cheeky! That's {pos} - who taught you that?",
    ],
    EventType.POSITION_LOST: [
        "Oh dear... down to {pos}.",
        "Ah, that one's gone. {pos} now - regroup.",
        "Mugged! Dropped to {pos}... we go again.",
    ],
    EventType.BATTLE_AHEAD: [
        "Ooh, the gap's tumbling... this is getting interesting!",
        "Reeling them in! {rival} has seen you in the mirrors...",
        "Closing, closing... here comes the pressure!",
    ],
    EventType.UNDER_PRESSURE: [
        "Eyes in the mirrors - {rival} is coming!",
        "Pressure from behind now... stay calm, stay tidy.",
        "Somebody's filling those mirrors... hold your nerve!",
    ],
    EventType.INCIDENT: [
        "Oh dear. The grass is not a racing line!",
        "Well... that's one way to take a corner.",
        "Steady on! iRacing will be sending a strongly worded letter.",
        "Blimey! The incident counter's ticking... that's {inc} on the board now.",
    ],
    EventType.PERSONAL_BEST: [
        "Purple patch! A new personal best - {lap}!",
        "Now THAT is a lap! Best of the day!",
        "Look at that - a personal best! It's all clicking!",
    ],
    EventType.SLOW_LAP: [
        "Hmm, that lap was... scenic.",
        "Bit of a Sunday drive, that one.",
        "That's a slow one - shake it off and go again.",
    ],
    EventType.PIT_ENTRY: [
        "In we come to the pits... mind that speed limiter!",
        "Pit lane! Let's hope the crew's awake.",
    ],
    EventType.PIT_EXIT: [
        "Back out we go! Watch the cold tyres...",
        "Out of the pits and back in the fight!",
    ],
    EventType.CHEQUERED_FLAG: [
        "Chequered flag! Home in {pos} - what a ride!",
        "And that's the flag! {pos} - we'll take that!",
        "It's over! Finishing {pos}... and in one piece, mostly!",
    ],
    EventType.COLOUR: [
        "Quiet out there... just how the safety rating likes it.",
        "Lovely rhythm now. Smooth is fast, as they say.",
        "Settling in nicely. Running {pos} for now.",
        "Hello to everyone watching The Beep Test - it's going surprisingly well!",
    ],
}

_last: dict[EventType, str] = {}


def fallback_line(event: Event) -> str:
    ctx, det = event.context, event.detail
    options = [l for l in LINES.get(event.type, LINES[EventType.COLOUR]) if l != _last.get(event.type)]
    line = random.choice(options)
    _last[event.type] = line
    pos = det.get("finishing_position_spoken") or det.get("new_position_spoken") or ctx.get("position_spoken", "the pack")
    pos = pos.split(" - ")[0]
    text = line.format(
        pos=pos,
        start=det.get("starting_position_spoken", "from the grid").split(" - ")[0],
        rival=(det.get("rival") or "the car behind").split(" ")[-1],
        inc=det.get("total_points", ctx.get("incident_points", "a few")),
        lap=det.get("lap_time_spoken", "a cracker"),
    )
    return re.sub(r"(^|[!?]\s+|(?<!\.)\.\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)
