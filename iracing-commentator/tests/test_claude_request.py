"""Checks the real Anthropic SDK request we send, against a fake API server."""

import json

import anthropic

try:  # anthropic 2.x is built on httpx2; older SDKs on httpx
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx

from commentator.config import load_config
from commentator.events import Event, EventType
from commentator.llm import LineWriter


def _writer_with_fake_api(monkeypatch, handler):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    w = LineWriter(load_config())
    w.client = anthropic.Anthropic(api_key="sk-ant-test", max_retries=0,
                                   http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    return w


def _message(text, stop="end_turn"):
    return {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
            "content": [{"type": "text", "text": text}], "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5}}


def test_request_shape_and_line(monkeypatch):
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta", "")
        return httpx.Response(200, json=_message('"Up to P5 - GET IN!"'))

    w = _writer_with_fake_api(monkeypatch, handler)
    line, source, _ = w.write(Event(EventType.POSITION_GAINED, context={"lap": 4}))
    assert (line, source) == ("Up to fifth - GET IN!", "ai")
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["output_config"] == {"effort": "low"}
    assert body["fallbacks"] == "default" and "server-side-fallback" in seen["beta"]
    assert "Cheeky" in body["system"] or "cheeky" in body["system"].lower()
    assert '"lap": 4' in body["messages"][0]["content"]


def test_falls_back_when_api_rejects_fallbacks_then_on_errors(monkeypatch):
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append("fallbacks" in body)
        if "fallbacks" in body:
            return httpx.Response(400, json={"type": "error", "error": {"type": "invalid_request_error", "message": "no"}})
        return httpx.Response(200, json=_message("Lovely stuff!"))

    w = _writer_with_fake_api(monkeypatch, handler)
    assert w.write(Event(EventType.COLOUR))[0] == "Lovely stuff!"
    assert calls == [True, False]


def test_api_outage_uses_canned_line(monkeypatch):
    w = _writer_with_fake_api(monkeypatch, lambda r: httpx.Response(529, json={
        "type": "error", "error": {"type": "overloaded_error", "message": "busy"}}))
    line, source, _ = w.write(Event(EventType.INCIDENT))
    assert source == "canned" and line
