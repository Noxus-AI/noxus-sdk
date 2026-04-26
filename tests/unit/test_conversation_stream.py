"""Unit tests for Conversation.stream() / astream() and the envelope helper."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterator
from typing import Any
from unittest.mock import create_autospec
from uuid import uuid4

import pytest
from httpx_sse import ServerSentEvent

from noxus_sdk.client import Client
from noxus_sdk.resources.conversations import (
    Conversation,
    MessageRequest,
    StreamEvent,
    _sse_to_stream_event,
)


def _sse(event: str = "", data: str = "") -> ServerSentEvent:
    return ServerSentEvent(event=event, data=data)


def _client() -> Any:
    return create_autospec(Client, instance=True)


def _minimal_conversation(**overrides) -> dict:
    return {
        "id": str(uuid4()),
        "name": "Conv",
        "created_at": "2024-01-01T00:00:00",
        "last_updated_at": "2024-01-01T00:00:00",
        "status": "idle",
        "settings": {"model": ["gpt-4o"], "temperature": 0.7, "tools": []},
        **overrides,
    }


# ════════════════════════════════════════════════════════════════════
#  _sse_to_stream_event — pure helper
# ════════════════════════════════════════════════════════════════════


class TestSseToStreamEvent:
    def test_json_envelope_is_unwrapped(self):
        envelope = {"event": "text-delta", "data": {"delta": "hi"}}
        sse = _sse(event="message", data=json.dumps(envelope))
        result = _sse_to_stream_event(sse, "json")
        assert result == StreamEvent(event="text-delta", data={"delta": "hi"})

    def test_json_with_invalid_payload_falls_back(self):
        sse = _sse(event="message", data="not json at all")
        result = _sse_to_stream_event(sse, "json")
        assert result.event == "message"
        # Empty envelope dict trips the fallback to the raw payload
        assert result.data == "not json at all"

    def test_vercel_data_is_parsed_when_json(self):
        sse = _sse(event="text-delta", data='{"delta": "hello"}')
        result = _sse_to_stream_event(sse, "vercel")
        assert result == StreamEvent(event="text-delta", data={"delta": "hello"})

    def test_vercel_keeps_raw_string_when_not_json(self):
        sse = _sse(event="error", data="oops")
        result = _sse_to_stream_event(sse, "vercel")
        assert result == StreamEvent(event="error", data="oops")

    def test_vercel_defaults_event_name_when_blank(self):
        sse = _sse(event="", data='{"x": 1}')
        result = _sse_to_stream_event(sse, "vercel")
        assert result.event == "message"


# ════════════════════════════════════════════════════════════════════
#  Conversation.stream() / astream()
# ════════════════════════════════════════════════════════════════════


class TestConversationStream:
    def test_stream_yields_envelopes_and_stops_on_done(self):
        client = _client()
        events = [
            _sse(
                event="message",
                data=json.dumps({"event": "text-delta", "data": {"delta": "he"}}),
            ),
            _sse(
                event="message",
                data=json.dumps({"event": "text-delta", "data": {"delta": "llo"}}),
            ),
            _sse(event="done", data="{}"),
            _sse(
                event="message",
                data=json.dumps({"event": "text-delta", "data": {"delta": "!"}}),
            ),
        ]

        def fake_event_stream(url: str, **kwargs) -> Iterator[ServerSentEvent]:
            assert url.endswith("/stream")
            assert kwargs["method"] == "POST"
            assert kwargs["params"] == {"format": "json"}
            assert kwargs["json"] == {
                "content": "hi",
                "tool": None,
                "kb_id": None,
                "workflow_id": None,
                "files": None,
                "model_selection": None,
            }
            yield from events

        client.event_stream.side_effect = fake_event_stream

        conv = Conversation(client=client, **_minimal_conversation())
        out = list(conv.stream(MessageRequest(content="hi")))

        assert out == [
            StreamEvent(event="text-delta", data={"delta": "he"}),
            StreamEvent(event="text-delta", data={"delta": "llo"}),
        ]

    def test_stream_surfaces_timeout_event_then_stops(self):
        client = _client()
        events = [
            _sse(
                event="message",
                data=json.dumps({"event": "text-delta", "data": {"delta": "hi"}}),
            ),
            _sse(event="timeout", data="{}"),
            _sse(
                event="message",
                data=json.dumps({"event": "text-delta", "data": {"delta": "ignored"}}),
            ),
        ]

        def fake_event_stream(url: str, **kwargs) -> Iterator[ServerSentEvent]:
            yield from events

        client.event_stream.side_effect = fake_event_stream

        conv = Conversation(client=client, **_minimal_conversation())
        out = list(conv.stream(MessageRequest(content="hi")))

        # First the real event, then the surfaced timeout, then loop terminates
        assert out == [
            StreamEvent(event="text-delta", data={"delta": "hi"}),
            StreamEvent(event="timeout", data=None),
        ]

    def test_stream_passes_format_query_param(self):
        client = _client()
        captured: dict[str, Any] = {}

        def fake_event_stream(url: str, **kwargs) -> Iterator[ServerSentEvent]:
            captured.update(kwargs)
            yield _sse(event="done", data="{}")

        client.event_stream.side_effect = fake_event_stream

        conv = Conversation(client=client, **_minimal_conversation())
        list(conv.stream(MessageRequest(content="hi"), format="vercel"))

        assert captured["params"] == {"format": "vercel"}
        assert captured["method"] == "POST"

    @pytest.mark.anyio
    async def test_astream_yields_envelopes(self):
        client = _client()
        events = [
            _sse(
                event="message",
                data=json.dumps({"event": "text-delta", "data": {"delta": "hi"}}),
            ),
            _sse(event="done", data="{}"),
        ]

        async def fake_aevent_stream(
            url: str, **kwargs
        ) -> AsyncIterator[ServerSentEvent]:
            assert kwargs["method"] == "POST"
            for e in events:
                yield e

        client.aevent_stream.side_effect = fake_aevent_stream

        conv = Conversation(client=client, **_minimal_conversation())
        out = [e async for e in conv.astream(MessageRequest(content="hi"))]

        assert out == [StreamEvent(event="text-delta", data={"delta": "hi"})]


@pytest.fixture
def anyio_backend():
    return "asyncio"
