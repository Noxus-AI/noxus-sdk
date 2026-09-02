from __future__ import annotations

import enum
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from noxus_sdk.resources._exports import (
    ExportFormat,
    ImportMode,
    import_body,
    import_params,
)
from noxus_sdk.resources.base import BaseResource, BaseService
from noxus_sdk.resources.conversations import (
    ConversationSettings,
)

AgentSettings: TypeAlias = ConversationSettings


class TriggerType(str, enum.Enum):
    SLACK = "slack"
    TEAMS = "teams"


class TriggerData(BaseModel):
    trigger_type: TriggerType = Field(exclude=True)
    team_id: str
    channel: str | None = None
    keyword: str | None = None


class AssistantTrigger(BaseResource):
    id: UUID
    group_id: UUID
    definition: dict
    routing_key: str
    agent_id: UUID = Field(alias="assistant_id")

    model_config = ConfigDict(from_attributes=True)

    def delete(self) -> None:
        self.client.delete(f"/v1/triggers/{self.id}")

    async def adelete(self) -> None:
        await self.client.adelete(f"/v1/triggers/{self.id}")


class Agent(BaseResource):
    id: str
    name: str
    definition: AgentSettings
    draft_definition: AgentSettings | None = None
    model_config = ConfigDict(validate_assignment=True, extra="allow")

    def add_trigger(self, trigger_data: TriggerData) -> AssistantTrigger:
        url = f"/v1/agents/{self.id}/triggers/{trigger_data.trigger_type.value}"
        result = self.client.post(url, trigger_data.model_dump())
        return AssistantTrigger(client=self.client, **result)

    async def aadd_trigger(self, trigger_data: TriggerData) -> AssistantTrigger:
        url = f"/v1/agents/{self.id}/triggers/{trigger_data.trigger_type.value}"
        result = await self.client.apost(url, trigger_data.model_dump())
        return AssistantTrigger(client=self.client, **result)

    def triggers(self) -> list[AssistantTrigger]:
        result = self.client.get(f"/v1/agents/{self.id}/triggers")
        return [AssistantTrigger(client=self.client, **result) for result in result]

    async def atriggers(self) -> list[AssistantTrigger]:
        result = await self.client.aget(f"/v1/agents/{self.id}/triggers")
        return [AssistantTrigger(client=self.client, **result) for result in result]

    def update(
        self,
        name: str,
        settings: AgentSettings,
        *,
        preview: bool = False,
    ) -> Agent:
        result = self.client.patch(
            f"/v1/agents/{self.id}",
            {"name": name, "definition": settings.model_dump()},
            params={"preview": preview},
        )
        for key, value in result.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def delete(self) -> None:
        self.client.delete(f"/v1/agents/{self.id}")


class AgentService(BaseService[Agent]):
    async def alist(self) -> list[Agent]:
        results = await self.client.apget("/v1/agents")
        return [Agent(client=self.client, **result) for result in results]

    def list(self) -> list[Agent]:
        results = self.client.pget("/v1/agents")
        return [Agent(client=self.client, **result) for result in results]

    def create(self, name: str, settings: AgentSettings) -> Agent:
        result = self.client.post(
            "/v1/agents",
            {"name": name, "definition": settings.model_dump()},
        )
        return Agent(client=self.client, **result)

    async def acreate(self, name: str, settings: AgentSettings) -> Agent:
        result = await self.client.apost(
            "/v1/agents",
            {"name": name, "definition": settings.model_dump()},
        )
        return Agent(client=self.client, **result)

    def get(self, agent_id: str) -> Agent:
        result = self.client.get(f"/v1/agents/{agent_id}")
        return Agent(client=self.client, **result)

    async def aget(self, agent_id: str) -> Agent:
        result = await self.client.aget(f"/v1/agents/{agent_id}")
        return Agent(client=self.client, **result)

    def update(
        self,
        agent_id: str,
        name: str | None = None,
        settings: AgentSettings | None = None,
        *,
        preview: bool = False,
    ) -> Agent:
        result = self.client.patch(
            f"/v1/agents/{agent_id}",
            {"name": name, "definition": settings.model_dump() if settings else None},
            params={"preview": preview},
        )
        return Agent(client=self.client, **result)

    async def aupdate(
        self,
        agent_id: str,
        name: str | None = None,
        settings: AgentSettings | None = None,
        *,
        preview: bool = False,
    ) -> Agent:
        result = await self.client.apatch(
            f"/v1/agents/{agent_id}",
            {
                "name": name,
                "definition": settings.model_dump() if settings else None,
            },
            params={"preview": preview},
        )
        return Agent(client=self.client, **result)

    def delete(self, agent_id: str) -> None:
        self.client.delete(f"/v1/agents/{agent_id}")

    async def adelete(self, agent_id: str) -> None:
        await self.client.adelete(f"/v1/agents/{agent_id}")

    # ── lifecycle ──────────────────────────────────────────────────────
    def duplicate(self, agent_id: str) -> Agent:
        """Copy an agent into a new one."""
        return Agent(
            client=self.client, **self.client.post(f"/v1/agents/{agent_id}/duplicate")
        )

    async def aduplicate(self, agent_id: str) -> Agent:
        response = await self.client.apost(f"/v1/agents/{agent_id}/duplicate")
        return Agent(client=self.client, **response)

    def publish(self, agent_id: str) -> dict:
        """Promote the agent's draft definition to live."""
        return self.client.post(f"/v1/agents/{agent_id}/publish")

    async def apublish(self, agent_id: str) -> dict:
        return await self.client.apost(f"/v1/agents/{agent_id}/publish")

    def restore(self, agent_id: str) -> dict:
        """Discard the draft and restore the published definition."""
        return self.client.post(f"/v1/agents/{agent_id}/restore")

    async def arestore(self, agent_id: str) -> dict:
        return await self.client.apost(f"/v1/agents/{agent_id}/restore")

    def list_versions(
        self, agent_id: str, page: int = 1, page_size: int = 10
    ) -> list[dict]:
        return self.client.pget(
            f"/v1/agents/{agent_id}/versions", page=page, page_size=page_size
        )

    async def alist_versions(
        self, agent_id: str, page: int = 1, page_size: int = 10
    ) -> list[dict]:
        return await self.client.apget(
            f"/v1/agents/{agent_id}/versions", page=page, page_size=page_size
        )

    def get_tool_schemas(self) -> dict:
        """Config schemas for every tool an agent can be given."""
        return self.client.get("/v1/agents/tool-schemas")

    async def aget_tool_schemas(self) -> dict:
        return await self.client.aget("/v1/agents/tool-schemas")

    # ── export / import ────────────────────────────────────────────────
    def export_preview(self, agent_id: str, version_id: str | None = None) -> dict:
        params = {"version_id": version_id} if version_id else {}
        return self.client.get(f"/v1/agents/{agent_id}/export/preview", params=params)

    async def aexport_preview(
        self, agent_id: str, version_id: str | None = None
    ) -> dict:
        params = {"version_id": version_id} if version_id else {}
        return await self.client.aget(
            f"/v1/agents/{agent_id}/export/preview", params=params
        )

    def _export_params(
        self,
        version: ExportFormat,
        version_id: str | None,
        set_active_on_import: bool,
    ) -> dict:
        params: dict = {
            "version": version,
            "set_active_on_import": set_active_on_import,
        }
        if version_id:
            params["version_id"] = version_id
        return params

    def export(
        self,
        agent_id: str,
        *,
        version: ExportFormat = "auto",
        version_id: str | None = None,
        set_active_on_import: bool = False,
    ) -> bytes:
        """Export an agent bundle (``auto`` = legacy base64, ``v4`` = .nx YAML)."""
        response = self.client._request(
            "POST",
            f"/v1/agents/{agent_id}/export",
            params=self._export_params(version, version_id, set_active_on_import),
        )
        return response.content

    async def aexport(
        self,
        agent_id: str,
        *,
        version: ExportFormat = "auto",
        version_id: str | None = None,
        set_active_on_import: bool = False,
    ) -> bytes:
        response = await self.client._arequest(
            "POST",
            f"/v1/agents/{agent_id}/export",
            params=self._export_params(version, version_id, set_active_on_import),
        )
        return response.content

    def import_(
        self,
        definition: str | bytes,
        *,
        version: ExportFormat = "auto",
        mode: ImportMode = "clone",
        activate: bool = False,
        dry_run: bool = False,
    ) -> list[dict]:
        return self.client.post(
            "/v1/agents/import",
            import_body(definition, version),
            params=import_params(mode, activate, dry_run),
        )

    async def aimport_(
        self,
        definition: str | bytes,
        *,
        version: ExportFormat = "auto",
        mode: ImportMode = "clone",
        activate: bool = False,
        dry_run: bool = False,
    ) -> list[dict]:
        return await self.client.apost(
            "/v1/agents/import",
            import_body(definition, version),
            params=import_params(mode, activate, dry_run),
        )
