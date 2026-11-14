"""Writes each commentary line with Claude (falls back to canned lines if offline)."""

from __future__ import annotations

import json
import os
import re
import time
from collections import deque
from typing import Optional

from .events import DESCRIPTION, Event
from .fallback_lines import fallback_line
from .numbers import speakify
from .personalities import system_prompt

MAX_WORDS = 22


def opener(line: str) -> str:
    """First two words, lower-cased, punctuation stripped - used to ban repeat openers."""
    words = re.findall(r"[a-zA-Z']+", line.lower())
    return " ".join(words[:2])


def clean_line(text: str) -> str:
    """Make the model's reply safe to speak: one line, no quotes, no digits, <= ~22 words."""
    text = (text or "").strip()
    text = text.splitlines()[0].strip() if text else ""
    text = re.sub(r"^\s*(line|commentary|commentator)\s*:\s*", "", text, flags=re.IGNORECASE)
    text = text.strip(" \"'“”‘’*`")
    text = re.sub(r"[#*_`]", "", text)
    words = text.split()
    if len(words) > MAX_WORDS:
        text = " ".join(words[:MAX_WORDS]).rstrip(",;:-") + "!"
    return speakify(text)


class LineWriter:
    """Keeps the commentary memory and turns Events into spoken lines."""

    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        llm = cfg["llm"]
        self.model = llm.get("model", "claude-opus-5-5")
        self.effort = llm.get("effort", "low")
        self.max_tokens = int(llm.get("max_tokens", 1024))
        self.timeout = float(llm.get("timeout_seconds", 6))
        self.use_fallback = bool(llm.get("use_fallback_lines", True))
        self.history: deque[dict] = deque(maxlen=int(cfg["commentator"].get("memory_lines", 10)))
        self.personality = cfg["commentator"].get("personality", "cheeky")
        self.driver = cfg.get("driver_name") or ""
        self._server_fallbacks = True  # Anthropic server-side refusal fallback
        self.client = None
        if os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-ant-") and "your-key" not in os.environ.get("ANTHROPIC_API_KEY", ""):
            try:
                import anthropic

                self._anthropic = anthropic
                self.client = anthropic.Anthropic(timeout=self.timeout, max_retries=0)
            except Exception as exc:
                print(f"[ai] Could not start the Anthropic client: {exc}")
        else:
            print("[ai] No ANTHROPIC_API_KEY in .env - using built-in canned lines.")

    @property
    def ai_enabled(self) -> bool:
        return self.client is not None

    def set_driver(self, name: str) -> None:
        if name and not self.cfg.get("driver_name"):
            self.driver = name

    # ---------------------------------------------------------------------
    def build_user_message(self, event: Event) -> str:
        recent = [h["line"] for h in self.history]
        payload = {
            "event": event.type.value,
            "what_happened": DESCRIPTION[event.type],
            "details": event.detail,
            "race_state": event.context,
            "forced": event.forced,
            "recent_lines": recent,
            "recent_events": [h["event"] for h in self.history],
            "banned_openers": sorted({opener(l) for l in recent[-4:] if opener(l)}),
        }
        return ("Race moment (JSON):\n" + json.dumps(payload, ensure_ascii=False, indent=1)
                + "\n\nYour one spoken line:")

    def _call_claude(self, event: Event) -> Optional[str]:
        a = self._anthropic
        kwargs = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system_prompt(self.personality, self.cfg.get("channel_name", "The Beep Test"),
                                 self.driver, self.cfg.get("driver_pronouns", "he/him")),
            messages=[{"role": "user", "content": self.build_user_message(event)}],
            output_config={"effort": self.effort},
        )
        try:
            if self._server_fallbacks:
                try:
                    resp = self.client.beta.messages.create(
                        betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
                except a.BadRequestError:
                    # Model/account doesn't support server-side fallbacks: use plain calls.
                    self._server_fallbacks = False
                    resp = self.client.messages.create(**kwargs)
            else:
                resp = self.client.messages.create(**kwargs)
        except a.AuthenticationError:
            print("[ai] API key rejected - check ANTHROPIC_API_KEY in .env. Using canned lines.")
            self.client = None
            return None
        except a.RateLimitError:
            print("[ai] Rate limited by the API - using a canned line this time.")
            return None
        except a.APITimeoutError:
            print("[ai] The AI took too long - using a canned line.")
            return None
        except a.APIStatusError as exc:
            print(f"[ai] API error {exc.status_code}: {getattr(exc, 'message', exc)}")
            return None
        except a.APIConnectionError:
            print("[ai] Can't reach the AI (internet?) - using a canned line.")
            return None

        if resp.stop_reason == "refusal":
            return None
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return text or None

    def write(self, event: Event) -> tuple[Optional[str], str, float]:
        """Returns (line, source, seconds_taken). source is 'ai' or 'canned'."""
        t0 = time.monotonic()
        line, source = None, "ai"
        if self.client is not None:
            raw = self._call_claude(event)
            line = clean_line(raw) if raw else None
        if not line and self.use_fallback:
            last = opener(self.history[-1]["line"]) if self.history else ""
            for _ in range(5):  # don't open the same way twice in a row
                line, source = clean_line(fallback_line(event)), "canned"
                if opener(line) != last:
                    break
        return line, source, time.monotonic() - t0

    def remember(self, event: Event, line: str) -> None:
        self.history.append({"event": event.type.value, "line": line})
