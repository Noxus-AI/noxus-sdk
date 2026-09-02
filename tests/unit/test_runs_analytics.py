"""Tests for the run methods that were missing from the SDK (stop/data/search/
sync) and the new analytics resource."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources.runs import Run

_RUN = {
    "id": "r-1",
    "group_id": "g-1",
    "workflow_id": "wf-1",
    "input": {},
    "status": "running",
    "progress": 0,
    "created_at": "2024-01-01T00:00:00",
}


def _client(handler) -> Client:
    return Client(
        api_key="k",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
    )


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content.decode())


def test_stop_run() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={**_RUN, "status": "stopped"})

    run = _client(handler).runs.stop("r-1")
    assert captured["path"] == "/v1/runs/r-1/stop"
    assert run.status == "stopped"


def test_run_instance_stop_and_data() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/stop"):
            return httpx.Response(200, json={**_RUN, "status": "stopped"})
        return httpx.Response(200, json={"nodes": []})

    client = _client(handler)
    run = Run(client=client, **_RUN)
    assert run.stop().status == "stopped"
    assert run.data() == {"nodes": []}


def test_get_data_passes_fetch_structured_flag() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"nodes": []})

    _client(handler).runs.get_data("r-1", fetch_structured_data=False)
    assert captured["params"]["fetch_structured_data"] == "false"


def test_search_returns_items() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        return httpx.Response(200, json={"items": [{"id": "r-1"}], "total": 1})

    items = _client(handler).runs.search("hello", limit=5, search_in=["output"])
    assert captured["path"] == "/v1/runs/search"
    assert captured["body"] == {
        "query": "hello",
        "limit": 5,
        "offset": 0,
        "exact": True,
        "search_in": ["output"],
    }
    assert items == [{"id": "r-1"}]


def test_search_omits_search_in_when_not_given() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = _body(request)
        return httpx.Response(200, json={"items": []})

    _client(handler).runs.search("q")
    assert "search_in" not in captured["body"]


def test_search_handles_missing_items_key() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total": 0})

    assert _client(handler).runs.search("q") == []


def test_run_sync_posts_input() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"output": "done"})

    result = _client(handler).runs.run_sync("wf-1", {"a": 1}, output_only=True)
    assert captured["path"] == "/v1/workflows/wf-1/runs/sync"
    assert captured["body"] == {"input": {"a": 1}}
    assert captured["params"]["output_only"] == "true"
    assert result == {"output": "done"}


# ── analytics ───────────────────────────────────────────────────────────


def test_analytics_get_sends_iso_range() -> None:
    captured: dict = {}
    end = datetime(2024, 1, 8, tzinfo=timezone.utc)
    start = end - timedelta(days=7)

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"type": "simple", "value": {"count": 3}})

    result = _client(handler).analytics.get("flow_runs", start, end)
    assert captured["path"] == "/analytics/flow_runs"
    assert captured["params"]["time_start"] == start.isoformat()
    assert captured["params"]["time_end"] == end.isoformat()
    assert result.type == "simple"
    assert result.value == {"count": 3}


def test_analytics_rejects_naive_datetimes() -> None:
    """The API only accepts tz-aware bounds; fail in the SDK with a clear
    message rather than sending something the backend will 422."""

    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not reach the network")

    with pytest.raises(ValueError, match="timezone-aware"):
        _client(handler).analytics.get(
            "flow_runs", datetime(2024, 1, 1), datetime(2024, 1, 2)
        )


def test_analytics_pagination_is_optional() -> None:
    captured: dict = {}
    end = datetime(2024, 1, 8, tzinfo=timezone.utc)

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"type": "table", "value": {"rows": []}})

    client = _client(handler)
    client.analytics.get("flow_runs", end - timedelta(days=1), end)
    assert "page" not in captured["params"]

    client.analytics.get(
        "flow_runs", end - timedelta(days=1), end, page=2, page_size=50
    )
    assert captured["params"]["page"] == "2"
    assert captured["params"]["page_size"] == "50"


@pytest.mark.asyncio
async def test_async_analytics_and_stop() -> None:
    end = datetime(2024, 1, 8, tzinfo=timezone.utc)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/analytics/"):
            return httpx.Response(200, json={"type": "simple", "value": 1})
        return httpx.Response(200, json={**_RUN, "status": "stopped"})

    client = _client(handler)
    assert (
        await client.analytics.aget("flow_runs", end - timedelta(days=1), end)
    ).value == 1
    assert (await client.runs.astop("r-1")).status == "stopped"
    await client.aclose()
