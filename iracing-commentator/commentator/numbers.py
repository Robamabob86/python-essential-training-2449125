"""Turn race numbers into words a commentator would actually say.

"P5" -> "fifth", 0.48 s -> "half a second", 92.456 s -> "one thirty-two point five".
Used twice: to give the AI ready-made spoken phrases, and as a safety net that
cleans up any digits the AI still writes before the line reaches the voice.
"""

from __future__ import annotations

import re

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]

_ORD_IRREGULAR = {"one": "first", "two": "second", "three": "third", "five": "fifth",
                  "eight": "eighth", "nine": "ninth", "twelve": "twelfth"}


def number_words(n: int) -> str:
    """Cardinal number in words (0-999)."""
    n = int(n)
    if n < 0:
        return "minus " + number_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + ("-" + _ONES[ones] if ones else "")
    if n < 1000:
        hundreds, rest = divmod(n, 100)
        return _ONES[hundreds] + " hundred" + (" and " + number_words(rest) if rest else "")
    return str(n)


def ordinal_words(n: int) -> str:
    """5 -> 'fifth', 21 -> 'twenty-first'."""
    words = number_words(n)
    head, sep, last = words.rpartition("-") if "-" in words else ("", "", words)
    if last in _ORD_IRREGULAR:
        last = _ORD_IRREGULAR[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last = last + "th"
    return f"{head}{sep}{last}"


def position_words(pos: int | None) -> str:
    if not pos or pos <= 0:
        return "unknown"
    if pos == 1:
        return "first - leading the race"
    return ordinal_words(pos)


def gap_words(seconds: float | None) -> str:
    """Round a gap the way a commentator would."""
    if seconds is None or seconds < 0:
        return "unknown"
    s = float(seconds)
    if s < 0.15:
        return "nothing at all - right on the gearbox"
    if s < 0.35:
        return "a couple of tenths"
    if s < 0.65:
        return "half a second"
    if s < 0.85:
        return "three quarters of a second"
    if s < 1.25:
        return "about a second"
    if s < 1.75:
        return "a second and a half"
    if s < 10:
        whole = round(s)
        return f"about {number_words(whole)} seconds"
    if s < 60:
        return f"about {number_words(int(round(s / 5) * 5))} seconds"
    return "over a minute"


def laptime_words(seconds: float | None) -> str:
    """92.456 -> 'one thirty-two point five' (how lap times are spoken on TV)."""
    if not seconds or seconds <= 0:
        return "no time yet"
    total_tenths = int(round(float(seconds) * 10))
    minutes, rem_tenths = divmod(total_tenths, 600)
    secs, tenth = divmod(rem_tenths, 10)
    if minutes == 0:
        return f"{number_words(secs)} point {number_words(tenth)} seconds"
    sec_part = number_words(secs) if secs >= 10 else f"oh {number_words(secs)}"
    return f"{number_words(minutes)} {sec_part} point {number_words(tenth)}"


def delta_words(seconds: float) -> str:
    """Lap delta: 1.8 -> 'nearly two seconds', 0.3 -> 'three tenths'."""
    s = abs(float(seconds))
    if s < 0.1:
        return "a hair"
    if s < 1.0:
        tenths = max(1, int(round(s * 10)))
        return "a tenth" if tenths == 1 else f"{number_words(tenths)} tenths"
    return gap_words(s).replace("about ", "") if s < 1.75 else f"{number_words(round(s))} seconds"


# --------------------------------------------------------------------------
# Safety net: rewrite digits the AI might still produce
# --------------------------------------------------------------------------

_P_RE = re.compile(r"\bP(\d{1,2})\b")
_LAPTIME_RE = re.compile(r"\b(\d):(\d{2})(?:\.(\d{1,3}))?\b")
_GAP_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s?(?:s|sec|secs|seconds)\b", re.IGNORECASE)
_ORD_RE = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE)
_DEC_RE = re.compile(r"\b(\d+)\.(\d+)\b")
_INT_RE = re.compile(r"\b(\d{1,3})\b")
_INC_RE = re.compile(r"\b(\d{1,2})x\b", re.IGNORECASE)


def speakify(text: str) -> str:
    """Rewrite numbers in a line so TTS says them naturally."""
    text = _P_RE.sub(lambda m: ordinal_words(int(m.group(1))), text)
    text = _LAPTIME_RE.sub(
        lambda m: laptime_words(int(m.group(1)) * 60 + int(m.group(2)) + float("0." + (m.group(3) or "0"))),
        text,
    )
    text = _GAP_RE.sub(lambda m: gap_words(float(m.group(1))), text)
    text = _ORD_RE.sub(lambda m: ordinal_words(int(m.group(1))), text)
    text = _INC_RE.sub(lambda m: f"{number_words(int(m.group(1)))} x", text)
    text = _DEC_RE.sub(lambda m: f"{number_words(int(m.group(1)))} point "
                       + " ".join(number_words(int(d)) for d in m.group(2)[:2]), text)
    text = _INT_RE.sub(lambda m: number_words(int(m.group(1))), text)
    return text
