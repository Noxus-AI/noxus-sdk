from __future__ import annotations

from typing import TYPE_CHECKING

from noxus_sdk.resources.base import BaseResource, BaseService

if TYPE_CHECKING:
    from noxus_sdk.client import Client


class ApiKey(BaseResource):
    id: str
    name: str
    tenant_admin: bool
    value: str
    permissions: list[str] | None = None


class TenantUser(BaseResource):
    id: str
    email: str
    display_name: str | None = None
    tenant_admin: bool
    is_active: bool


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
        response = await self.client.apget(
            "/v1/admin/groups",
        )
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

    # ── tenant users (read; requires a system key with users:read) ──────
    def list_users(self) -> list[TenantUser]:
        return [
            TenantUser(client=self.client, **u)
            for u in self.client.get("/v1/admin/users")
        ]

    async def alist_users(self) -> list[TenantUser]:
        response = await self.client.aget("/v1/admin/users")
        return [TenantUser(client=self.client, **u) for u in response]

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
