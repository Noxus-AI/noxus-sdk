"""Unit tests for the variables SDK resource."""

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


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content.decode())


def test_list_unwraps_variables_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/variables"
        return httpx.Response(
            200,
            json={"variables": [{"name": "A", "kind": "secret", "has_value": True}]},
        )

    out = _client(handler).variables.list()
    assert out == [{"name": "A", "kind": "secret", "has_value": True}]


def test_create_inline_secret() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        return httpx.Response(200, json={"id": "v-1", "name": "OPENAI_KEY"})

    result = _client(handler).variables.create(
        "OPENAI_KEY", value="sk-123", kind="secret"
    )
    assert captured["path"] == "/v1/variables"
    assert captured["body"] == {
        "name": "OPENAI_KEY",
        "kind": "secret",
        "value_type": "string",
        "source": "inline",
        "inline_value": "sk-123",
    }
    assert result["id"] == "v-1"


def test_create_without_value_omits_inline_value() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = _body(request)
        return httpx.Response(200, json={"id": "v-2"})

    _client(handler).variables.create("FLAG", value_type="boolean")
    assert "inline_value" not in captured["body"]
    assert captured["body"]["value_type"] == "boolean"


def test_update_sends_partial_body() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        return httpx.Response(200, json={"id": "v-1", "name": "renamed"})

    _client(handler).variables.update("v-1", {"name": "renamed"})
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/v1/variables/v-1"
    assert captured["body"] == {"name": "renamed"}


def test_delete_reads_ok_flag() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        return httpx.Response(200, json={"ok": True})

    assert _client(handler).variables.delete("v-1") is True


@pytest.mark.asyncio
async def test_async_create_and_delete() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json={"id": "v-9"})

    client = _client(handler)
    assert (await client.variables.acreate("X", value="1"))["id"] == "v-9"
    assert await client.variables.adelete("v-9") is True
    await client.aclose()
