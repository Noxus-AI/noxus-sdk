"""Tests for the workflow/agent methods the public API exposed but the SDK
never wrapped: logs, export/import, duplicate/publish/restore/versions."""

from __future__ import annotations

import json

import httpx
import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources._exports import import_body, import_params

_AGENT = {
    "id": "a-1",
    "name": "Agent",
    "definition": {"model": ["gpt-4o"], "temperature": 0.5, "tools": []},
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


# ── shared export/import helpers ────────────────────────────────────────


def test_import_body_accepts_bytes_and_str() -> None:
    assert import_body(b"raw", "auto") == {"definition": "raw", "version": "auto"}
    assert import_body("txt", "v4") == {"definition": "txt", "version": "v4"}


def test_import_params_shape() -> None:
    assert import_params("replace", True, False) == {
        "mode": "replace",
        "activate": True,
        "dry_run": False,
    }


# ── workflows ───────────────────────────────────────────────────────────


def test_workflow_logs_and_columns() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/logs/columns"):
            return httpx.Response(200, json=["run_id", "status"])
        return httpx.Response(200, json={"rows": []})

    wf = _client(handler).workflows
    assert wf.get_logs("wf-1") == {"rows": []}
    assert wf.get_logs_columns("wf-1") == ["run_id", "status"]


def test_workflow_export_defaults() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, content=b"bundle")

    data = _client(handler).workflows.export("wf-1")
    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/workflows/wf-1/export"
    assert captured["params"]["version"] == "auto"
    assert captured["params"]["include_dependencies"] == "true"
    assert "version_id" not in captured["params"]
    assert data == b"bundle"


def test_workflow_export_v4_with_version_id() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, content=b"yaml")

    _client(handler).workflows.export(
        "wf-1", version="v4", version_id="v-9", include_dependencies=False
    )
    assert captured["params"]["version"] == "v4"
    assert captured["params"]["version_id"] == "v-9"
    assert captured["params"]["include_dependencies"] == "false"


def test_workflow_export_preview_omits_version_id_when_absent() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"artifacts": []})

    _client(handler).workflows.export_preview("wf-1")
    assert captured["method"] == "GET"
    assert captured["params"] == {}


def test_workflow_import_round_trips_bytes() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=[{"id": "wf-2"}])

    result = _client(handler).workflows.import_(b"bundle", dry_run=True)
    assert captured["path"] == "/v1/workflows/import"
    assert captured["body"] == {"definition": "bundle", "version": "auto"}
    assert captured["params"]["dry_run"] == "true"
    assert result == [{"id": "wf-2"}]


# ── agents ──────────────────────────────────────────────────────────────


def test_agent_duplicate_returns_agent() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json={**_AGENT, "id": "a-2"})

    agent = _client(handler).agents.duplicate("a-1")
    assert captured["path"] == "/v1/agents/a-1/duplicate"
    assert agent.id == "a-2"


def test_agent_publish_and_restore() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"status": "ok"})

    agents = _client(handler).agents
    assert agents.publish("a-1") == {"status": "ok"}
    assert agents.restore("a-1") == {"status": "ok"}
    assert calls == ["/v1/agents/a-1/publish", "/v1/agents/a-1/restore"]


def test_agent_list_versions_uses_pagination() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/agents/a-1/versions"
        return httpx.Response(200, json={"items": [{"id": "v1"}], "total": 1})

    assert _client(handler).agents.list_versions("a-1") == [{"id": "v1"}]


def test_agent_tool_schemas() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/agents/tool-schemas"
        return httpx.Response(200, json={"web_research": {"type": "object"}})

    assert "web_research" in _client(handler).agents.get_tool_schemas()


def test_agent_export_and_import() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/export"):
            captured["export_params"] = dict(request.url.params)
            return httpx.Response(200, content=b"agent-bundle")
        captured["import_body"] = _body(request)
        return httpx.Response(200, json=[{"id": "a-3"}])

    agents = _client(handler).agents
    bundle = agents.export("a-1", version="v4")
    assert captured["export_params"]["version"] == "v4"
    assert agents.import_(bundle) == [{"id": "a-3"}]
    assert captured["import_body"]["definition"] == "agent-bundle"


@pytest.mark.asyncio
async def test_async_agent_publish_and_workflow_logs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/logs" in request.url.path:
            return httpx.Response(200, json={"rows": []})
        return httpx.Response(200, json={"status": "ok"})

    client = _client(handler)
    assert await client.agents.apublish("a-1") == {"status": "ok"}
    assert await client.workflows.aget_logs("wf-1") == {"rows": []}
    await client.aclose()
