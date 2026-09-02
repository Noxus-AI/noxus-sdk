"""Unit tests for the triggers SDK resource (read + delete)."""

from __future__ import annotations

import httpx
import pytest

from noxus_sdk.client import Client


def _client(handler) -> Client:
    return Client(
        api_key="k",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
    )


def test_list_triggers() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={"items": [{"id": "t-1"}], "total": 1})

    triggers = _client(handler).triggers.list("wf-1")
    assert captured["path"] == "/v1/workflows/wf-1/triggers"
    assert triggers == [{"id": "t-1"}]


def test_list_events_passes_search() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"items": [{"id": "e-1"}]})

    events = _client(handler).triggers.list_events("wf-1", "t-1", search="failed")
    assert captured["path"] == "/v1/workflows/wf-1/triggers/t-1/events"
    assert captured["params"]["search"] == "failed"
    assert events == [{"id": "e-1"}]


def test_list_events_omits_search_when_absent() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"items": []})

    _client(handler).triggers.list_events("wf-1", "t-1")
    assert "search" not in captured["params"]


def test_iter_events_paginates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        size = int(request.url.params.get("size", "100"))
        if page == 1:
            items = [{"id": i} for i in range(size)]  # full page
        elif page == 2:
            items = [{"id": "last"}]  # partial → stop
        else:
            items = []
        return httpx.Response(200, json={"items": items})

    events = list(_client(handler).triggers.iter_events("wf-1", "t-1", page_size=50))
    assert len(events) == 51


def test_all_events_filters() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"items": [{"id": "e-1"}]})

    _client(handler).triggers.events(
        event_type="webhook", workflow_id="wf-1", started_run=True
    )
    assert captured["path"] == "/v1/triggers/events"
    assert captured["params"]["event_type"] == "webhook"
    assert captured["params"]["workflow_id"] == "wf-1"
    assert captured["params"]["started_run"] == "true"


def test_all_events_omits_unset_filters() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"items": []})

    _client(handler).triggers.events()
    for key in ("search", "event_type", "workflow_id", "started_run"):
        assert key not in captured["params"]


def test_create_trigger() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = __import__("json").loads(request.content.decode())
        return httpx.Response(200, json={"id": "t-1"})

    result = _client(handler).triggers.create(
        "wf-1", {"type": "schedule"}, workflow_version_id="v-1"
    )
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/workflows/wf-1/triggers"
    assert captured["body"] == {
        "definition": {"type": "schedule"},
        "workflow_version_id": "v-1",
    }
    assert result == {"id": "t-1"}


def test_update_trigger_omits_version_when_absent() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["body"] = __import__("json").loads(request.content.decode())
        return httpx.Response(200, json={"id": "t-1"})

    _client(handler).triggers.update("wf-1", "t-1", {"type": "webhook"})
    assert captured["method"] == "PATCH"
    assert "workflow_version_id" not in captured["body"]


def test_delete_trigger() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        return httpx.Response(200, json={"success": True})

    assert _client(handler).triggers.delete("t-1") is True
    assert captured["method"] == "DELETE"
    assert captured["path"] == "/v1/triggers/t-1"


@pytest.mark.asyncio
async def test_async_list_and_events() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [{"id": "x"}]})

    client = _client(handler)
    assert await client.triggers.alist("wf-1") == [{"id": "x"}]
    assert await client.triggers.aevents() == [{"id": "x"}]
    await client.aclose()
