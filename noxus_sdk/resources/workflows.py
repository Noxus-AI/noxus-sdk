from datetime import datetime
from uuid import UUID
from builtins import list as List  # noqa
from pydantic import ConfigDict

from noxus_sdk.resources._exports import (
    ExportFormat,
    ImportMode,
    import_body,
    import_params,
)
from noxus_sdk.resources.base import BaseResource, BaseService
from noxus_sdk.workflows import WorkflowDefinition


class WorkflowVersion(BaseResource):
    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    created_by: UUID | None = None
    definition: dict


class WorkflowService(BaseService[WorkflowDefinition]):
    async def alist(
        self, page: int = 1, page_size: int = 10
    ) -> list[WorkflowDefinition]:
        workflows_data = await self.client.apget(
            f"/v1/workflows",
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
            f"/v1/workflows",
            params={"page": page, "page_size": page_size, "type": "flow"},
            page=page,
            page_size=page_size,
        )
        return [
            WorkflowDefinition.model_validate({"client": self.client, **data})
            for data in workflows_data
        ]

    def delete(self, workflow_id: str):
        self.client.delete(f"/v1/workflows/{workflow_id}")

    async def adelete(self, workflow_id: str):
        await self.client.adelete(f"/v1/workflows/{workflow_id}")

    def save(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        w = self.client.post(f"/v1/workflows", workflow.to_noxus())
        workflow.refresh_from_data(client=self.client, **w)
        return workflow

    async def asave(self, workflow: WorkflowDefinition) -> WorkflowDefinition:
        w = await self.client.apost(f"/v1/workflows", workflow.to_noxus())
        workflow.refresh_from_data(client=self.client, **w)
        return workflow

    def get(self, workflow_id: str) -> WorkflowDefinition:
        w = self.client.get(f"/v1/workflows/{workflow_id}")
        return WorkflowDefinition.model_validate({"client": self.client, **w})

    async def aget(self, workflow_id: str) -> WorkflowDefinition:
        w = await self.client.aget(f"/v1/workflows/{workflow_id}")
        return WorkflowDefinition.model_validate({"client": self.client, **w})

    def update(
        self, workflow_id: str, workflow: WorkflowDefinition, force: bool = False
    ) -> WorkflowDefinition:
        w = self.client.patch(
            f"/v1/workflows/{workflow_id}?force={force}", workflow.to_noxus()
        )
        workflow.refresh_from_data(client=self.client, **w)
        return workflow

    async def aupdate(
        self, workflow_id: str, workflow: WorkflowDefinition, force: bool = False
    ) -> WorkflowDefinition:
        w = await self.client.apatch(
            f"/v1/workflows/{workflow_id}?force={force}", workflow.to_noxus()
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

    def list_versions(self, workflow_id: str) -> List[WorkflowVersion]:
        w = self.client.get(f"/v1/workflows/{workflow_id}/versions")
        return [WorkflowVersion.model_validate({"client": self.client, **v}) for v in w]

    async def alist_versions(self, workflow_id: str) -> List[WorkflowVersion]:
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

    # ── logs ───────────────────────────────────────────────────────────
    def get_logs(self, workflow_id: str) -> dict:
        """Execution logs for a workflow."""
        return self.client.get(f"/v1/workflows/{workflow_id}/logs")

    async def aget_logs(self, workflow_id: str) -> dict:
        return await self.client.aget(f"/v1/workflows/{workflow_id}/logs")

    def get_logs_columns(self, workflow_id: str) -> List[str]:
        """The columns available in this workflow's logs."""
        return self.client.get(f"/v1/workflows/{workflow_id}/logs/columns")

    async def aget_logs_columns(self, workflow_id: str) -> List[str]:
        return await self.client.aget(f"/v1/workflows/{workflow_id}/logs/columns")

    # ── export / import ────────────────────────────────────────────────
    def export_preview(self, workflow_id: str, version_id: str | None = None) -> dict:
        """What an export would contain, without producing the bundle."""
        params = {"version_id": version_id} if version_id else {}
        return self.client.get(
            f"/v1/workflows/{workflow_id}/export/preview", params=params
        )

    async def aexport_preview(
        self, workflow_id: str, version_id: str | None = None
    ) -> dict:
        params = {"version_id": version_id} if version_id else {}
        return await self.client.aget(
            f"/v1/workflows/{workflow_id}/export/preview", params=params
        )

    def _export_params(
        self,
        version: ExportFormat,
        version_id: str | None,
        set_active_on_import: bool,
        include_dependencies: bool,
    ) -> dict:
        params: dict = {
            "version": version,
            "set_active_on_import": set_active_on_import,
            "include_dependencies": include_dependencies,
        }
        if version_id:
            params["version_id"] = version_id
        return params

    def export(
        self,
        workflow_id: str,
        *,
        version: ExportFormat = "auto",
        version_id: str | None = None,
        set_active_on_import: bool = False,
        include_dependencies: bool = True,
    ) -> bytes:
        """Export a workflow bundle.

        ``auto`` (the default) emits the legacy base64 bundle; pass ``v4`` for
        plaintext multi-doc YAML (.nx). ``include_dependencies`` bundles
        referenced sub-flows / KBs / files.
        """
        response = self.client._request(
            "POST",
            f"/v1/workflows/{workflow_id}/export",
            params=self._export_params(
                version, version_id, set_active_on_import, include_dependencies
            ),
        )
        return response.content

    async def aexport(
        self,
        workflow_id: str,
        *,
        version: ExportFormat = "auto",
        version_id: str | None = None,
        set_active_on_import: bool = False,
        include_dependencies: bool = True,
    ) -> bytes:
        response = await self.client._arequest(
            "POST",
            f"/v1/workflows/{workflow_id}/export",
            params=self._export_params(
                version, version_id, set_active_on_import, include_dependencies
            ),
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
    ) -> List[dict]:
        """Import a bundle produced by ``export``; ``dry_run`` reports without writing."""
        return self.client.post(
            "/v1/workflows/import",
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
    ) -> List[dict]:
        return await self.client.apost(
            "/v1/workflows/import",
            import_body(definition, version),
            params=import_params(mode, activate, dry_run),
        )
