"""Unit tests for the sandboxes SDK resource (OpenSandbox-shaped ergonomics)."""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from noxus_sdk.client import Client
from noxus_sdk.errors import NotFoundError
from noxus_sdk.resources.sandboxes import Sandbox

_SANDBOX = {
    "id": "sb-1",
    "label": "report",
    "status": "running",
    "created_at": "2024-01-01T00:00:00",
    "last_activity": "2024-01-01T00:00:00",
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


def _sb(handler) -> Sandbox:
    """A Sandbox bound to a mocked client, without spending a GET on it."""
    return Sandbox(client=_client(handler), **_SANDBOX)


def test_create_returns_sandbox() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        return httpx.Response(200, json=_SANDBOX)

    sb = _client(handler).sandboxes.create(label="report", persistent=True)
    assert captured["path"] == "/v1/sandboxes"
    assert captured["body"] == {"label": "report", "persistent": True}
    assert sb.id == "sb-1"
    assert sb.label == "report"
    assert "sb-1" in repr(sb)


def test_list_and_get() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/sandboxes":
            return httpx.Response(200, json=[_SANDBOX])
        return httpx.Response(200, json=_SANDBOX)

    client = _client(handler)
    assert [s.id for s in client.sandboxes.list()] == ["sb-1"]
    assert client.sandboxes.get("sb-1").status == "running"


def test_commands_run_returns_streams_and_exit_code() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        return httpx.Response(
            200,
            json={"stdout": "hi\n", "stderr": "", "exit_code": 0, "timed_out": False},
        )

    result = _sb(handler).commands.run("echo hi", timeout=30)
    assert captured["path"] == "/v1/sandboxes/sb-1/commands"
    assert captured["body"] == {"command": "echo hi", "timeout": 30}
    assert result.stdout == "hi\n"
    assert result.exit_code == 0
    assert result.ok is True


def test_command_failure_is_reported_not_raised() -> None:
    """A non-zero exit is a result, not a transport error — the caller decides."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"stdout": "", "stderr": "boom", "exit_code": 2, "timed_out": False},
        )

    result = _sb(handler).commands.run("false")
    assert result.ok is False
    assert result.stderr == "boom"


def test_timeout_omitted_when_not_given() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = _body(request)
        return httpx.Response(
            200, json={"stdout": "", "stderr": "", "exit_code": 0, "timed_out": False}
        )

    _sb(handler).commands.run("ls")
    assert captured["body"] == {"command": "ls"}


def test_files_write_text_and_bytes() -> None:
    captured: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(_body(request))
        return httpx.Response(200, json={"path": "/work/f"})

    files = _sb(handler).files
    files.write("/work/f", "hello")
    files.write("/work/f", b"\x00\x01binary")

    assert captured[0] == {"path": "/work/f", "content": "hello", "encoding": "utf-8"}
    assert captured[1]["encoding"] == "base64"
    assert base64.b64decode(captured[1]["content"]) == b"\x00\x01binary"


def test_files_read_text_and_bytes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("encoding") == "base64":
            return httpx.Response(
                200,
                json={
                    "path": "/work/f",
                    "content": base64.b64encode(b"\x00raw").decode(),
                    "encoding": "base64",
                },
            )
        return httpx.Response(
            200, json={"path": "/work/f", "content": "hello", "encoding": "utf-8"}
        )

    files = _sb(handler).files
    assert files.read("/work/f") == "hello"
    assert files.read_bytes("/work/f") == b"\x00raw"


def test_kill() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True})

    assert _client(handler).sandboxes.delete("sb-1") is True


def test_context_manager_kills_sandbox() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.method == "DELETE":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(200, json=_SANDBOX)

    client = _client(handler)
    with client.sandboxes.create(label="tmp") as sb:
        assert sb.id == "sb-1"
    assert "DELETE /v1/sandboxes/sb-1" in calls


def test_missing_sandbox_raises_typed_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Sandbox not found"})

    with pytest.raises(NotFoundError):
        _client(handler).sandboxes.get("nope")


@pytest.mark.asyncio
async def test_async_create_run_kill() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commands"):
            return httpx.Response(
                200,
                json={"stdout": "ok", "stderr": "", "exit_code": 0, "timed_out": False},
            )
        if request.method == "DELETE":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(200, json=_SANDBOX)

    client = _client(handler)
    async with await client.sandboxes.acreate(label="tmp") as sb:
        result = await sb.commands.arun("echo ok")
        assert result.stdout == "ok"
    await client.aclose()
