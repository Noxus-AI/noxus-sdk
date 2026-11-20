import json

import httpx
import pytest

from noxus_sdk.client import Client

TEAM = {
    "id": "team-1",
    "name": "Support",
    "members": [
        {
            "id": "user-2",
            "email": "agent@example.com",
            "display_name": None,
            "saml_only": True,
        }
    ],
}


@pytest.fixture
def client():
    requests = [
        ("GET", "/v1/admin/teams", None, [TEAM]),
        ("POST", "/v1/admin/teams", {"name": "Support", "user_ids": ["user-2"]}, TEAM),
        ("GET", "/v1/admin/teams/team-1", None, TEAM),
        ("PATCH", "/v1/admin/teams/team-1", {"name": "Help"}, {**TEAM, "name": "Help"}),
        ("PUT", "/v1/admin/teams/team-1/members/user-2", None, {"success": True}),
        ("PUT", "/v1/admin/teams/team-1/members", {"user_ids": []}, TEAM),
        ("DELETE", "/v1/admin/teams/team-1/members/user-2", None, {"success": True}),
        ("DELETE", "/v1/admin/teams/team-1", None, {"success": True}),
    ]

    def handle(request: httpx.Request) -> httpx.Response:
        method, path, body, result = requests.pop(0)
        assert (request.method, request.url.path) == (method, path)
        assert (json.loads(request.content) if request.content else None) == body
        return httpx.Response(200, json=result)

    return Client(
        api_key="test-key",
        load_me=False,
        load_nodes=False,
        transport=httpx.MockTransport(handle),
    )


def test_team_provisioning(client: Client) -> None:
    admin = client.admin
    assert [team.id for team in admin.list_teams()] == ["team-1"]
    team = admin.create_team("Support", user_ids=["user-2"])
    assert admin.get_team(team.id).members[0].email == "agent@example.com"
    assert admin.rename_team(team.id, "Help").name == "Help"
    assert admin.add_team_member(team.id, "user-2")
    assert admin.replace_team_members(team.id, []).members[0].saml_only
    assert admin.remove_team_member(team.id, "user-2")
    assert admin.delete_team(team.id)
    client.close()


@pytest.mark.asyncio
async def test_async_team_provisioning(client: Client) -> None:
    admin = client.admin
    assert [team.id for team in await admin.alist_teams()] == ["team-1"]
    team = await admin.acreate_team("Support", user_ids=["user-2"])
    assert (await admin.aget_team(team.id)).members[0].email == "agent@example.com"
    assert (await admin.arename_team(team.id, "Help")).name == "Help"
    assert await admin.aadd_team_member(team.id, "user-2")
    assert (await admin.areplace_team_members(team.id, [])).members[0].saml_only
    assert await admin.aremove_team_member(team.id, "user-2")
    assert await admin.adelete_team(team.id)
    await client.aclose()
