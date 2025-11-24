from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from noxus_sdk.resources.base import BaseResource, BaseService
from noxus_sdk.workflows import WorkflowDefinition

if TYPE_CHECKING:
    import builtins


class WorkflowVersion(BaseResource):
    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    created_by: UUID | None = None
    definition: dict


class WorkflowService(BaseService[WorkflowDefinition]):
    async def alist(
        self,
        page: int = 1,
        page_size: int = 10,
    ) -> list[WorkflowDefinition]:
        workflows_data = await self.client.apget(
            "/v1/workflows",
            params={"page": page, "page_size": page_size, "type": "flow"},
            page=page,
            page_size=page_size,
        )
        return [
            WorkflowDefinition.model_validate({"client": self.client, **data})
            for data in workflows_data
        ]

    def list(self, page: int = 1, page_size: int = 10) -> list[WorkflowDefinition]:
        workflows_data = self.client.pget(
            "/v1/workflows",
            params={"page": page, "page_size": page_size, "type": "flow"},
            page=page,
            page_size=page_size,
        )
        return [
            WorkflowDefinition.model_validate({"client": self.client, **data})
            for data in workflows_data
        ]

    def delete(self, workflow_id: str) -> None:
        self.client.delete(f"/v1/workflows/{workflow_id}")

    async def adelete(self, workflow_id: str) -> None:
        await self.client.adelete(f"/v1/workflows/{workflow_id}")

    def save(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        w = self.client.post("/v1/workflows", workflow.to_noxus())
        workflow.refresh_from_data(client=self.client, **w)
        return workflow

    async def asave(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        w = await self.client.apost("/v1/workflows", workflow.to_noxus())
        workflow.refresh_from_data(client=self.client, **w)
        return workflow

    def get(self, workflow_id: str) -> WorkflowDefinition:
        w = self.client.get(f"/v1/workflows/{workflow_id}")
        return WorkflowDefinition.model_validate({"client": self.client, **w})

    async def aget(self, workflow_id: str) -> WorkflowDefinition:
        w = await self.client.aget(f"/v1/workflows/{workflow_id}")
        return WorkflowDefinition.model_validate({"client": self.client, **w})

    def update(
        self,
        workflow_id: str,
        workflow: WorkflowDefinition,
        *,
        force: bool = False,
    ) -> WorkflowDefinition:
        w = self.client.patch(
            f"/v1/workflows/{workflow_id}?force={force}",
            workflow.to_noxus(),
        )
        workflow.refresh_from_data(client=self.client, **w)
        return workflow

    async def aupdate(
        self,
        workflow_id: str,
        workflow: WorkflowDefinition,
        *,
        force: bool = False,
    ) -> WorkflowDefinition:
        w = await self.client.apatch(
            f"/v1/workflows/{workflow_id}?force={force}",
            workflow.to_noxus(),
        )
        workflow.refresh_from_data(client=self.client, **w)
        return workflow

    def save_version(
        self,
        workflow_id: str,
        workflow: WorkflowDefinition,
        name: str,
        description: str | None,
    ) -> WorkflowVersion:
        body = {
            "name": name,
            "description": description,
            "definition": workflow.to_noxus()["definition"],
        }
        w = self.client.post(
            f"/v1/workflows/{workflow_id}/versions",
            body,
        )
        return WorkflowVersion.model_validate({"client": self.client, **w})

    async def asave_version(
        self,
        workflow_id: str,
        workflow: WorkflowDefinition,
        name: str,
        description: str | None,
    ) -> WorkflowVersion:
        body = {
            "name": name,
            "description": description,
            "definition": workflow.to_noxus()["definition"],
        }
        w = await self.client.apost(
            f"/v1/workflows/{workflow_id}/versions",
            body,
        )
        return WorkflowVersion.model_validate({"client": self.client, **w})

    def list_versions(self, workflow_id: str) -> builtins.list[WorkflowVersion]:
        w = self.client.get(f"/v1/workflows/{workflow_id}/versions")
        return [WorkflowVersion.model_validate({"client": self.client, **v}) for v in w]

    async def alist_versions(self, workflow_id: str) -> builtins.list[WorkflowVersion]:
        w = await self.client.aget(f"/v1/workflows/{workflow_id}/versions")
        return [WorkflowVersion.model_validate({"client": self.client, **v}) for v in w]

    def update_version(
        self,
        workflow_id: str,
        version_id: str,
        name: str,
        description: str | None,
        definition: WorkflowDefinition,
    ) -> WorkflowVersion:
        w = self.client.patch(
            f"/v1/workflows/{workflow_id}/versions/{version_id}",
            {
                "name": name,
                "description": description,
                "definition": definition.to_noxus()["definition"],
            },
        )
        return WorkflowVersion.model_validate({"client": self.client, **w})

    async def aupdate_version(
        self,
        workflow_id: str,
        version_id: str,
        name: str,
        description: str | None,
        definition: WorkflowDefinition,
    ) -> WorkflowVersion:
        w = await self.client.apatch(
            f"/v1/workflows/{workflow_id}/versions/{version_id}",
            {
                "name": name,
                "description": description,
                "definition": definition.to_noxus()["definition"],
            },
        )
        return WorkflowVersion.model_validate({"client": self.client, **w})
