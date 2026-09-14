"""Unit tests for the insights SDK resource."""

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


def test_csat_score_path_and_default_window() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"score": 0.9})

    result = _client(handler).insights.csat_score("a-1")
    assert captured["path"] == "/v1/agents/a-1/insights/csat-score"
    assert captured["params"]["days"] == "7"
    assert result == {"score": 0.9}


def test_optional_window_params_are_omitted() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={})

    _client(handler).insights.top_topics("a-1")
    assert "deployment_id" not in captured["params"]
    assert "message_length" not in captured["params"]
    assert captured["params"]["limit"] == "10"


def test_window_params_passed_through() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={})

    _client(handler).insights.rating_drivers(
        "a-1", days=30, limit=5, deployment_id="dep-1", message_length="short"
    )
    assert captured["params"] == {
        "days": "30",
        "limit": "5",
        "deployment_id": "dep-1",
        "message_length": "short",
    }


def test_sub_topics_omits_parent_when_absent() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={})

    _client(handler).insights.sub_topics("a-1")
    assert "parent" not in captured["params"]
    _client(handler).insights.sub_topics("a-1", parent="billing")


def test_conversations_drilldown_sends_kind_and_key() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"items": []})

    _client(handler).insights.conversations("a-1", kind="cx", key="5")
    assert captured["path"] == "/v1/agents/a-1/insights/conversations"
    assert captured["params"]["kind"] == "cx"
    assert captured["params"]["key"] == "5"


def test_noticed_and_bootstrap() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/bootstrap"):
            return httpx.Response(200, json={"ready": True})
        return httpx.Response(200, json={"items": []})

    ins = _client(handler).insights
    assert ins.noticed("a-1", limit=5) == {"items": []}
    assert ins.bootstrap_status("a-1") == {"ready": True}


@pytest.mark.asyncio
async def test_async_dashboards() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    client = _client(handler)
    assert (await client.insights.acsat_score("a-1")) == {"ok": True}
    assert (await client.insights.atop_topics("a-1", days=14)) == {"ok": True}
    assert (await client.insights.abootstrap_status("a-1")) == {"ok": True}
    await client.aclose()
