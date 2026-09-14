"""Unit tests for the SDK HTTP client: typed errors, rate-limit backoff,
pooling, lifecycle, pagination and SSE parsing. Uses httpx.MockTransport so
no network is touched."""

from __future__ import annotations

from typing import Callable

import httpx
import pytest

import noxus_sdk.client as client_mod
from noxus_sdk.client import Client
from noxus_sdk.errors import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    NoxusApiError,
    RateLimitedError,
    RequestFailedError,
    ServerError,
    UnauthorizedError,
    ValidationError,
)

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler, **kwargs) -> Client:
    return Client(
        api_key="test-key",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


# ── typed errors ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "exc"),
    [
        (400, BadRequestError),
        (401, UnauthorizedError),
        (403, ForbiddenError),
        (404, NotFoundError),
        (422, ValidationError),
        (429, RateLimitedError),
        (500, ServerError),
        (503, ServerError),
    ],
)
def test_status_maps_to_typed_error(status: int, exc: type[NoxusApiError]) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={"detail": "boom"})

    c = _client(handler, max_retries=0)
    with pytest.raises(exc) as info:
        c.get("/v1/thing")
    assert info.value.status_code == status
    assert isinstance(info.value, NoxusApiError)


def test_error_is_subclass_of_request_failed_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "nope"})

    c = _client(handler)
    with pytest.raises(RequestFailedError):
        c.get("/v1/thing")


def test_error_carries_body_and_request_id() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"detail": "bad input"},
            headers={"x-request-id": "req-123"},
        )

    c = _client(handler)
    with pytest.raises(NoxusApiError) as info:
        c.get("/v1/thing")
    assert info.value.request_id == "req-123"
    assert info.value.body == {"detail": "bad input"}
    assert "bad input" in str(info.value)
    assert "req-123" in str(info.value)


def test_success_returns_json() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    c = _client(handler)
    assert c.get("/v1/thing") == {"ok": True}


# ── rate-limit backoff ──────────────────────────────────────────────────


def test_retries_429_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(client_mod.time, "sleep", sleeps.append)
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(429)
        return httpx.Response(200, json={"ok": True})

    c = _client(handler)
    assert c.get("/v1/thing") == {"ok": True}
    assert calls["n"] == 3
    assert sleeps == [1.0, 2.0]  # exponential 2**0, 2**1


def test_retry_after_header_is_honored(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(client_mod.time, "sleep", sleeps.append)
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json={"ok": True})

    c = _client(handler)
    c.get("/v1/thing")
    assert sleeps == [7.0]


def test_exhausted_retries_raise_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(client_mod.time, "sleep", sleeps.append)
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429)

    c = _client(handler, max_retries=2)
    with pytest.raises(RateLimitedError):
        c.get("/v1/thing")
    assert calls["n"] == 3  # initial + 2 retries
    assert sleeps == [1.0, 2.0]


# ── pooling & lifecycle ─────────────────────────────────────────────────


def test_sync_client_is_pooled() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    c = _client(handler)
    first = c._http()
    c.get("/v1/a")
    c.get("/v1/b")
    assert c._http() is first


def test_close_disposes_client() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    c = _client(handler)
    pooled = c._http()
    c.close()
    assert c._sync_client is None
    assert c._http() is not pooled


def test_context_manager_closes() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    with _client(handler) as c:
        c.get("/v1/a")
        assert c._sync_client is not None
    assert c._sync_client is None


def test_offline_construction_touches_no_network() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be made during construction")

    # Should not raise: load_nodes/load_me are off.
    _client(handler)


# ── pagination ──────────────────────────────────────────────────────────


def test_pget_returns_items() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [{"id": 1}, {"id": 2}]})

    c = _client(handler)
    assert c.pget("/v1/list") == [{"id": 1}, {"id": 2}]


def test_pget_missing_items_returns_empty() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"total": 0})

    c = _client(handler)
    assert c.pget("/v1/list") == []


# ── SSE ─────────────────────────────────────────────────────────────────


def test_event_stream_parses_sse() -> None:
    body = "event: message\ndata: hello\n\nevent: done\ndata: bye\n\n"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=body
        )

    c = _client(handler)
    events = list(c.event_stream("/v1/stream"))
    assert [(e.event, e.data) for e in events] == [
        ("message", "hello"),
        ("done", "bye"),
    ]


def test_event_stream_retries_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client_mod.time, "sleep", lambda *_: None)
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            content="event: message\ndata: hi\n\n",
        )

    c = _client(handler)
    events = list(c.event_stream("/v1/stream"))
    assert calls["n"] == 2
    assert [(e.event, e.data) for e in events] == [("message", "hi")]


def test_event_stream_raises_typed_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "gone"})

    c = _client(handler)
    with pytest.raises(NotFoundError):
        list(c.event_stream("/v1/stream"))


# ── async ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_async_typed_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "no"})

    c = _client(handler)
    with pytest.raises(ForbiddenError):
        await c.aget("/v1/thing")
    await c.aclose()


@pytest.mark.asyncio
async def test_async_retries_429_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    c = _client(handler)
    assert await c.aget("/v1/thing") == {"ok": True}
    assert calls["n"] == 3
    await c.aclose()


@pytest.mark.asyncio
async def test_async_exhaustion_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "0"})

    c = _client(handler, max_retries=1)
    with pytest.raises(RateLimitedError):
        await c.aget("/v1/thing")
    await c.aclose()


@pytest.mark.asyncio
async def test_async_context_manager() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as c:
        assert await c.aget("/v1/thing") == {"ok": True}
        assert c._async_client is not None
    assert c._async_client is None


# ── base_url precedence ─────────────────────────────────────────────────


def test_explicit_base_url_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOXUS_BACKEND_URL", "http://from-env:8000")
    client = Client(
        api_key="k", base_url="http://explicit:9000", load_nodes=False, load_me=False
    )
    assert client.base_url == "http://explicit:9000"


def test_env_fills_default_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOXUS_BACKEND_URL", "http://from-env:8000")
    client = Client(api_key="k", load_nodes=False, load_me=False)
    assert client.base_url == "http://from-env:8000"


def test_default_base_url_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOXUS_BACKEND_URL", raising=False)
    client = Client(api_key="k", load_nodes=False, load_me=False)
    assert client.base_url == "https://backend.noxus.ai"
