from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from noxus_sdk.resources.base import BaseResource, BaseService

if TYPE_CHECKING:
    from noxus_sdk.client import Client


class ApiKey(BaseResource):
    id: str
    name: str
    tenant_admin: bool
    value: str
    permissions: list[str] | None = None


UserStatus = Literal["active", "pending", "suspended"]


class TenantUser(BaseResource):
    id: str
    email: str
    display_name: str | None = None
    tenant_admin: bool
    is_active: bool
    status: UserStatus | None = None
    tenant_role_id: str | None = None
    tenant_role: str | None = None


class Membership(BaseModel):
    workspace_id: str
    workspace_name: str
    role_id: str | None = None
    role: str | None = None


class TenantUserDetail(TenantUser):
    metadata: dict[str, str] = Field(default_factory=dict)
    memberships: list[Membership] = Field(default_factory=list)


class Workspace(BaseResource):
    id: str
    name: str
    description: str | None = None

    def delete(self) -> None:
        self.client.delete(f"/v1/admin/groups/{self.id}")

    async def adelete(self) -> None:
        await self.client.adelete(f"/v1/admin/groups/{self.id}")

    def add_api_key(self, name: str, *, is_admin: bool = False) -> ApiKey:
        api_key = self.client.post(
            f"/v1/admin/groups/{self.id}/api-keys",
            {"name": name, "tenant_admin": is_admin},
        )
        return ApiKey(client=self.client, **api_key)

    async def aadd_api_key(self, name: str, *, is_admin: bool = False) -> ApiKey:
        api_key = await self.client.apost(
            f"/v1/admin/groups/{self.id}/api-keys",
            {"name": name, "tenant_admin": is_admin},
        )
        return ApiKey(client=self.client, **api_key)


class AdminService(BaseService[Workspace]):
    def __init__(self, client: Client, *, enabled: bool = True) -> None:
        self.client = client
        self.enabled = enabled

    def get_me(self) -> ApiKey:
        response = self.client.get("/v1/admin/me")
        return ApiKey(client=self.client, **response)

    async def aget_me(self) -> ApiKey:
        response = await self.client.aget("/v1/admin/me")
        return ApiKey(client=self.client, **response)

    async def alist_workspaces(self) -> list[Workspace]:
        if not self.enabled:
            raise ValueError(
                "Admin service is disabled because client was not initialized with an admin API key",
            )
        response = await self.client.aget("/v1/admin/groups")
        return [Workspace(client=self.client, **group) for group in response]

    def list_workspaces(self) -> list[Workspace]:
        if not self.enabled:
            raise ValueError(
                "Admin service is disabled because client was not initialized with an admin API key",
            )
        response = self.client.get(
            "/v1/admin/groups",
        )
        return [Workspace(client=self.client, **group) for group in response]

    def create_workspace(self, name: str, description: str | None = None) -> Workspace:
        if not self.enabled:
            raise ValueError(
                "Admin service is disabled because client was not initialized with an admin API key",
            )
        response = self.client.post(
            "/v1/admin/groups",
            {"name": name, "description": description},
        )
        return Workspace(client=self.client, **response)

    async def acreate_workspace(
        self,
        name: str,
        description: str | None = None,
    ) -> Workspace:
        if not self.enabled:
            raise ValueError(
                "Admin service is disabled because client was not initialized with an admin API key",
            )
        response = await self.client.apost(
            "/v1/admin/groups",
            {"name": name, "description": description},
        )
        return Workspace(client=self.client, **response)

    # ── system (tenant-scoped) API keys ─────────────────────────────────
    # Minted in the tenant's hidden system workspace; the only keys allowed to
    # carry tenant-wide permissions. Requires a tenant-admin key.
    def create_system_key(
        self,
        name: str,
        *,
        permissions: list[str] | None = None,
        tenant_admin: bool = False,
    ) -> ApiKey:
        body = {
            "name": name,
            "permissions": permissions or [],
            "tenant_admin": tenant_admin,
        }
        return ApiKey(
            client=self.client, **self.client.post("/v1/admin/system-keys", body)
        )

    async def acreate_system_key(
        self,
        name: str,
        *,
        permissions: list[str] | None = None,
        tenant_admin: bool = False,
    ) -> ApiKey:
        body = {
            "name": name,
            "permissions": permissions or [],
            "tenant_admin": tenant_admin,
        }
        response = await self.client.apost("/v1/admin/system-keys", body)
        return ApiKey(client=self.client, **response)

    def list_system_keys(self) -> list[ApiKey]:
        return [
            ApiKey(client=self.client, **k)
            for k in self.client.get("/v1/admin/system-keys")
        ]

    async def alist_system_keys(self) -> list[ApiKey]:
        response = await self.client.aget("/v1/admin/system-keys")
        return [ApiKey(client=self.client, **k) for k in response]

    def delete_system_key(self, key_id: str) -> bool:
        return self.client.delete(f"/v1/admin/system-keys/{key_id}")["success"]

    async def adelete_system_key(self, key_id: str) -> bool:
        response = await self.client.adelete(f"/v1/admin/system-keys/{key_id}")
        return response["success"]

    # ── tenant users (system key: users:read / invite / edit / delete) ──
    def list_users(
        self,
        *,
        search: str | None = None,
        status: UserStatus | None = None,
        workspace_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TenantUser]:
        params = _user_filters(search, status, workspace_id, limit, offset)
        return [
            TenantUser(client=self.client, **u)
            for u in self.client.get("/v1/admin/users", params=params)
        ]

    async def alist_users(
        self,
        *,
        search: str | None = None,
        status: UserStatus | None = None,
        workspace_id: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[TenantUser]:
        params = _user_filters(search, status, workspace_id, limit, offset)
        response = await self.client.aget("/v1/admin/users", params=params)
        return [TenantUser(client=self.client, **u) for u in response]

    def get_user(self, user_id: str) -> TenantUserDetail:
        return self._user(self.client.get(f"/v1/admin/users/{user_id}"))

    async def aget_user(self, user_id: str) -> TenantUserDetail:
        return self._user(await self.client.aget(f"/v1/admin/users/{user_id}"))

    def get_user_access(self, user_id: str) -> dict:
        """The user's tenant role and permissions, and each workspace with its
        role and the permissions it gives them there."""
        return self.client.get(f"/v1/admin/users/{user_id}/access")

    async def aget_user_access(self, user_id: str) -> dict:
        return await self.client.aget(f"/v1/admin/users/{user_id}/access")

    def create_user(
        self,
        email: str,
        *,
        display_name: str | None = None,
        tenant_role: str | None = None,
        workspaces: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
        send_invite: bool = False,
    ) -> TenantUserDetail:
        """``workspaces`` maps a workspace id to a role id or name."""
        body = _create_body(
            email, display_name, tenant_role, workspaces, metadata, send_invite
        )
        return self._user(self.client.post("/v1/admin/users", body))

    async def acreate_user(
        self,
        email: str,
        *,
        display_name: str | None = None,
        tenant_role: str | None = None,
        workspaces: dict[str, str] | None = None,
        metadata: dict[str, str] | None = None,
        send_invite: bool = False,
    ) -> TenantUserDetail:
        body = _create_body(
            email, display_name, tenant_role, workspaces, metadata, send_invite
        )
        return self._user(await self.client.apost("/v1/admin/users", body))

    def update_user(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        email: str | None = None,
        metadata: dict[str, str] | None = None,
        tenant_role: str | None = None,
    ) -> TenantUserDetail:
        body = _drop_none(
            display_name=display_name,
            email=email,
            metadata=metadata,
            tenant_role=tenant_role,
        )
        return self._user(self.client.patch(f"/v1/admin/users/{user_id}", body))

    async def aupdate_user(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        email: str | None = None,
        metadata: dict[str, str] | None = None,
        tenant_role: str | None = None,
    ) -> TenantUserDetail:
        body = _drop_none(
            display_name=display_name,
            email=email,
            metadata=metadata,
            tenant_role=tenant_role,
        )
        return self._user(await self.client.apatch(f"/v1/admin/users/{user_id}", body))

    def set_tenant_role(self, user_id: str, role: str) -> TenantUserDetail:
        path = f"/v1/admin/users/{user_id}/tenant-role"
        return self._user(self.client.put(path, {"role": role}))

    async def aset_tenant_role(self, user_id: str, role: str) -> TenantUserDetail:
        path = f"/v1/admin/users/{user_id}/tenant-role"
        return self._user(await self.client.aput(path, {"role": role}))

    def suspend_user(self, user_id: str) -> TenantUserDetail:
        return self._user(self.client.post(f"/v1/admin/users/{user_id}/suspend"))

    async def asuspend_user(self, user_id: str) -> TenantUserDetail:
        return self._user(await self.client.apost(f"/v1/admin/users/{user_id}/suspend"))

    def reactivate_user(self, user_id: str) -> TenantUserDetail:
        return self._user(self.client.post(f"/v1/admin/users/{user_id}/reactivate"))

    async def areactivate_user(self, user_id: str) -> TenantUserDetail:
        path = f"/v1/admin/users/{user_id}/reactivate"
        return self._user(await self.client.apost(path))

    def delete_user(self, user_id: str, *, transfer_to: str | None = None) -> bool:
        params = {"transfer_to": transfer_to} if transfer_to else None
        return self.client.delete(f"/v1/admin/users/{user_id}", params=params)[
            "success"
        ]

    async def adelete_user(
        self, user_id: str, *, transfer_to: str | None = None
    ) -> bool:
        params = {"transfer_to": transfer_to} if transfer_to else None
        response = await self.client.adelete(
            f"/v1/admin/users/{user_id}", params=params
        )
        return response["success"]

    def list_members(self, workspace_id: str) -> list[TenantUser]:
        path = f"/v1/admin/groups/{workspace_id}/members"
        return [TenantUser(client=self.client, **u) for u in self.client.get(path)]

    async def alist_members(self, workspace_id: str) -> list[TenantUser]:
        path = f"/v1/admin/groups/{workspace_id}/members"
        response = await self.client.aget(path)
        return [TenantUser(client=self.client, **u) for u in response]

    def set_membership(
        self, workspace_id: str, user_id: str, role: str
    ) -> TenantUserDetail:
        """Add the user to the workspace with ``role``, or change their role there."""
        path = f"/v1/admin/groups/{workspace_id}/members/{user_id}"
        return self._user(self.client.put(path, {"role": role}))

    async def aset_membership(
        self, workspace_id: str, user_id: str, role: str
    ) -> TenantUserDetail:
        path = f"/v1/admin/groups/{workspace_id}/members/{user_id}"
        return self._user(await self.client.aput(path, {"role": role}))

    def remove_membership(self, workspace_id: str, user_id: str) -> TenantUserDetail:
        path = f"/v1/admin/groups/{workspace_id}/members/{user_id}"
        return self._user(self.client.delete(path))

    async def aremove_membership(
        self, workspace_id: str, user_id: str
    ) -> TenantUserDetail:
        path = f"/v1/admin/groups/{workspace_id}/members/{user_id}"
        return self._user(await self.client.adelete(path))

    def _user(self, data: dict) -> TenantUserDetail:
        return TenantUserDetail(client=self.client, **data)

    # ── tenant roles (requires a system key with org:admin) ─────────────
    def list_roles(self) -> list[dict]:
        return self.client.get("/v1/admin/roles")

    async def alist_roles(self) -> list[dict]:
        return await self.client.aget("/v1/admin/roles")

    def create_role(
        self,
        name: str,
        permissions: dict[str, bool],
        *,
        description: str | None = None,
    ) -> dict:
        body = {"name": name, "permissions": permissions, "description": description}
        return self.client.post("/v1/admin/roles", body)

    async def acreate_role(
        self,
        name: str,
        permissions: dict[str, bool],
        *,
        description: str | None = None,
    ) -> dict:
        body = {"name": name, "permissions": permissions, "description": description}
        return await self.client.apost("/v1/admin/roles", body)

    def delete_role(self, role_id: str) -> dict:
        return self.client.delete(f"/v1/admin/roles/{role_id}")

    async def adelete_role(self, role_id: str) -> dict:
        return await self.client.adelete(f"/v1/admin/roles/{role_id}")


def _drop_none(**values: str | int | dict[str, str] | None) -> dict:
    return {k: v for k, v in values.items() if v is not None}


def _user_filters(
    search: str | None,
    status: str | None,
    workspace_id: str | None,
    limit: int | None,
    offset: int,
) -> dict:
    return _drop_none(
        search=search,
        status=status,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )


def _create_body(
    email: str,
    display_name: str | None,
    tenant_role: str | None,
    workspaces: dict[str, str] | None,
    metadata: dict[str, str] | None,
    send_invite: bool,
) -> dict:
    return {
        **_drop_none(
            display_name=display_name,
            tenant_role=tenant_role,
            metadata=metadata,
        ),
        "email": email,
        "workspaces": [
            {"workspace_id": ws, "role": role}
            for ws, role in (workspaces or {}).items()
        ],
        "send_invite": send_invite,
    }
