"""Workspace variables and secrets.

    client.variables.create("OPENAI_KEY", value="sk-...", kind="secret")
    for var in client.variables.list():
        print(var["name"], var["kind"])

Secret values are write-only: they are never returned by ``list`` (you get
``has_value: true`` instead), only set.
"""

from __future__ import annotations

import builtins
from typing import Any, Literal

from noxus_sdk.resources.base import BaseService

VariableKind = Literal["variable", "secret"]
VariableSource = Literal["inline", "vault", "environment"]
ValueType = Literal["string", "number", "boolean", "json", "datetime", "file"]


class VariableService(BaseService[dict]):
    def list(self) -> builtins.list[dict]:
        """List variables; secret values are never included."""
        return self.client.get("/v1/variables")["variables"]

    async def alist(self) -> builtins.list[dict]:
        response = await self.client.aget("/v1/variables")
        return response["variables"]

    def create(
        self,
        name: str,
        *,
        value: str | None = None,
        kind: VariableKind = "variable",
        value_type: ValueType = "string",
        source: VariableSource = "inline",
    ) -> dict:
        """Create a variable or secret.

        For inline values pass ``value``; vault/environment sources are
        configured with their own fields via ``create_raw``.
        """
        body: dict[str, Any] = {
            "name": name,
            "kind": kind,
            "value_type": value_type,
            "source": source,
        }
        if value is not None:
            body["inline_value"] = value
        return self.client.post("/v1/variables", body)

    async def acreate(
        self,
        name: str,
        *,
        value: str | None = None,
        kind: VariableKind = "variable",
        value_type: ValueType = "string",
        source: VariableSource = "inline",
    ) -> dict:
        body: dict[str, Any] = {
            "name": name,
            "kind": kind,
            "value_type": value_type,
            "source": source,
        }
        if value is not None:
            body["inline_value"] = value
        return await self.client.apost("/v1/variables", body)

    def create_raw(self, body: dict[str, Any]) -> dict:
        """Create with the full upsert payload (vault/environment sources)."""
        return self.client.post("/v1/variables", body)

    async def acreate_raw(self, body: dict[str, Any]) -> dict:
        return await self.client.apost("/v1/variables", body)

    def update(self, variable_id: str, body: dict[str, Any]) -> dict:
        """Update a variable with a partial payload (only sent fields change)."""
        return self.client.patch(f"/v1/variables/{variable_id}", body)

    async def aupdate(self, variable_id: str, body: dict[str, Any]) -> dict:
        return await self.client.apatch(f"/v1/variables/{variable_id}", body)

    def delete(self, variable_id: str) -> bool:
        return self.client.delete(f"/v1/variables/{variable_id}")["ok"]

    async def adelete(self, variable_id: str) -> bool:
        return (await self.client.adelete(f"/v1/variables/{variable_id}"))["ok"]
