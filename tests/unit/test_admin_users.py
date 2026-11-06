"""Unit tests for user administration in the SDK."""

from __future__ import annotations

import json

import httpx

from noxus_sdk.client import Client

_USER = {
    "id": "u-1",
    "email": "ada@example.com",
    "display_name": "Ada",
    "tenant_admin": False,
    "is_active": True,
    "status": "pending",
    "tenant_role": "Base",
    "memberships": [
        {
            "workspace_id": "w-1",
            "workspace_name": "Engineering",
            "role_id": "r-1",
            "role": "Editor",
        }
    ],
}


def _client(handler) -> Client:
    return Client(
        api_key="k",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
    )


def _recorder(response: dict | list) -> tuple[list[httpx.Request], Client]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=response)

    return seen, _client(handler)


def test_create_user_sends_workspaces_and_parses_memberships() -> None:
    seen, client = _recorder(_USER)
    user = client.admin.create_user(
        "ada@example.com", tenant_role="Base", workspaces={"w-1": "Editor"}
    )
    assert seen[0].method == "POST" and seen[0].url.path == "/v1/admin/users"
    assert json.loads(seen[0].content) == {
        "email": "ada@example.com",
        "tenant_role": "Base",
        "workspaces": [{"workspace_id": "w-1", "role": "Editor"}],
        "send_invite": False,
    }
    assert user.memberships[0].role == "Editor"
    assert user.status == "pending"


def test_list_users_sends_filters() -> None:
    seen, client = _recorder([_USER])
    users = client.admin.list_users(search="ada", status="pending", workspace_id="w-1")
    params = dict(seen[0].url.params)
    assert params == {
        "search": "ada",
        "status": "pending",
        "workspace_id": "w-1",
        "offset": "0",
    }
    assert users[0].tenant_role == "Base"


def test_membership_and_delete_with_transfer() -> None:
    seen, client = _recorder(_USER)
    client.admin.set_membership("w-1", "u-1", "Editor")
    assert seen[0].method == "PUT"
    assert seen[0].url.path == "/v1/admin/groups/w-1/members/u-1"
    assert json.loads(seen[0].content) == {"role": "Editor"}

    seen, client = _recorder({"success": True})
    assert client.admin.delete_user("u-1", transfer_to="u-2") is True
    assert seen[0].method == "DELETE"
    assert seen[0].url.params["transfer_to"] == "u-2"


def test_list_members() -> None:
    seen, client = _recorder([_USER])
    members = client.admin.list_members("w-1")
    assert seen[0].url.path == "/v1/admin/groups/w-1/members"
    assert [m.email for m in members] == ["ada@example.com"]
