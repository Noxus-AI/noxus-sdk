"""Unit tests for the SDK admin surface: system keys + tenant users."""

from __future__ import annotations

import json

import httpx
import pytest

from noxus_sdk.client import Client
from noxus_sdk.errors import ForbiddenError


def _client(handler) -> Client:
    return Client(
        api_key="k",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
    )


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content.decode())


_KEY = {
    "id": "sk-1",
    "name": "ci",
    "tenant_admin": False,
    "value": "secret",
    "permissions": ["providers:manage"],
}


def test_create_system_key_sends_permissions() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        return httpx.Response(200, json=_KEY)

    key = _client(handler).admin.create_system_key(
        "ci", permissions=["providers:manage"]
    )
    assert captured["path"] == "/v1/admin/system-keys"
    assert captured["body"] == {
        "name": "ci",
        "permissions": ["providers:manage"],
        "tenant_admin": False,
    }
    assert key.value == "secret"
    assert key.permissions == ["providers:manage"]


def test_create_system_key_defaults_empty_permissions() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = _body(request)
        return httpx.Response(200, json=_KEY)

    _client(handler).admin.create_system_key("full", tenant_admin=True)
    assert captured["body"] == {
        "name": "full",
        "permissions": [],
        "tenant_admin": True,
    }


def test_list_and_delete_system_keys() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            return httpx.Response(200, json={"success": True})
        return httpx.Response(200, json=[_KEY])

    admin = _client(handler).admin
    assert [k.id for k in admin.list_system_keys()] == ["sk-1"]
    assert admin.delete_system_key("sk-1") is True


def test_list_and_create_and_delete_roles() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.setdefault("calls", []).append(f"{request.method} {request.url.path}")
        if request.method == "POST":
            captured["body"] = _body(request)
            return httpx.Response(200, json={"id": "r-1", "name": "Ops"})
        if request.method == "DELETE":
            return httpx.Response(200, json={"message": "Role deleted successfully"})
        return httpx.Response(200, json=[{"id": "r-1", "name": "Admin"}])

    admin = _client(handler).admin
    assert admin.list_roles() == [{"id": "r-1", "name": "Admin"}]
    role = admin.create_role("Ops", {"resource:run": True}, description="ops")
    assert captured["body"] == {
        "name": "Ops",
        "permissions": {"resource:run": True},
        "description": "ops",
    }
    assert role["id"] == "r-1"
    admin.delete_role("r-1")
    assert "GET /v1/admin/roles" in captured["calls"]
    assert "POST /v1/admin/roles" in captured["calls"]
    assert "DELETE /v1/admin/roles/r-1" in captured["calls"]


def test_list_users() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/admin/users"
        return httpx.Response(
            200,
            json=[
                {
                    "id": "u-1",
                    "email": "a@b.com",
                    "display_name": "A",
                    "tenant_admin": True,
                    "is_active": True,
                }
            ],
        )

    users = _client(handler).admin.list_users()
    assert users[0].email == "a@b.com"
    assert users[0].tenant_admin is True


def test_apikey_permissions_optional_for_back_compat() -> None:
    """/v1/admin/me returns no permissions field — must still construct."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id": "k", "name": "me", "tenant_admin": True, "value": "v"},
        )

    me = _client(handler).admin.get_me()
    assert me.permissions is None


def test_get_me_propagates_auth_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "forbidden"})

    with pytest.raises(ForbiddenError):
        _client(handler).admin.get_me()


@pytest.mark.asyncio
async def test_aget_me_propagates_auth_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"detail": "forbidden"})

    client = _client(handler)
    with pytest.raises(ForbiddenError):
        await client.admin.aget_me()
    await client.aclose()


@pytest.mark.asyncio
async def test_async_system_key_lifecycle() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            return httpx.Response(200, json={"success": True})
        if request.method == "POST":
            return httpx.Response(200, json=_KEY)
        return httpx.Response(200, json=[_KEY])

    admin = _client(handler).admin
    created = await admin.acreate_system_key("ci", permissions=["users:read"])
    assert created.id == "sk-1"
    assert [k.id for k in await admin.alist_system_keys()] == ["sk-1"]
    assert await admin.adelete_system_key("sk-1") is True
    await admin.client.aclose()
