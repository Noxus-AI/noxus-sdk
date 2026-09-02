"""Unit tests for the deployments SDK resource."""

from __future__ import annotations

import json

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


def test_list_and_channels() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json=[{"id": "d-1"}])

    client = _client(handler)
    assert client.deployments.list("a-1") == [{"id": "d-1"}]
    assert seen["path"] == "/v1/agents/a-1/deployments"
    client.deployments.list_channels()
    assert seen["path"] == "/v1/channels"


def test_create_builds_minimal_body() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(201, json={"id": "d-1"})

    result = _client(handler).deployments.create(
        "a-1", channel_type="embed_widget", name="Widget"
    )
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/agents/a-1/deployments"
    # Unset optionals (alias, version) are omitted; config defaults to {}.
    assert captured["body"] == {
        "channel_type": "embed_widget",
        "config": {},
        "name": "Widget",
    }
    assert result == {"id": "d-1"}


def test_create_includes_alias_and_version() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(201, json={"id": "d-1"})

    _client(handler).deployments.create(
        "a-1",
        channel_type="form",
        alias="my-form",
        config={"title": "Hi"},
        assistant_version_id="v-1",
    )
    assert captured["body"]["alias"] == "my-form"
    assert captured["body"]["config"] == {"title": "Hi"}
    assert captured["body"]["assistant_version_id"] == "v-1"


def test_activate_deactivate_and_delete() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        return httpx.Response(200, json={"success": True, "id": "d-1"})

    client = _client(handler)
    client.deployments.activate("a-1", "d-1")
    assert captured["path"] == "/v1/agents/a-1/deployments/d-1/activate"
    client.deployments.deactivate("a-1", "d-1")
    assert captured["path"] == "/v1/agents/a-1/deployments/d-1/deactivate"
    assert client.deployments.delete("a-1", "d-1") is True
    assert captured["method"] == "DELETE"


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

    events = list(_client(handler).deployments.iter_events("a-1", "d-1", page_size=50))
    assert len(events) == 51


@pytest.mark.asyncio
async def test_async_get_and_update() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        return httpx.Response(200, json={"id": "d-1"})

    client = _client(handler)
    assert await client.deployments.aget("a-1", "d-1") == {"id": "d-1"}
    await client.deployments.aupdate("a-1", "d-1", {"name": "New"})
    assert captured["method"] == "PATCH"
    await client.aclose()
