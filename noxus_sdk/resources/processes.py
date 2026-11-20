"""Process export.

    bundle = client.processes.export(process_id, version="v4")
    alone = client.processes.export(process_id, include_dependencies=False)

``include_dependencies`` (default true) bundles the process's flows and the
tables they use; without it the bundle holds the process alone.
"""

from __future__ import annotations

from noxus_sdk.resources._exports import ExportFormat
from noxus_sdk.resources.base import BaseService


class ProcessService(BaseService[dict]):
    def export_preview(
        self, process_id: str, *, include_dependencies: bool = True
    ) -> dict:
        """What an export would contain, without producing the bundle."""
        return self.client.get(
            f"/v1/processes/{process_id}/export/preview",
            params={"include_dependencies": include_dependencies},
        )

    async def aexport_preview(
        self, process_id: str, *, include_dependencies: bool = True
    ) -> dict:
        return await self.client.aget(
            f"/v1/processes/{process_id}/export/preview",
            params={"include_dependencies": include_dependencies},
        )

    def export(
        self,
        process_id: str,
        *,
        version: ExportFormat = "auto",
        set_active_on_import: bool = False,
        include_dependencies: bool = True,
    ) -> bytes:
        """Export a process bundle (``auto`` = legacy base64, ``v4`` = .nx YAML)."""
        response = self.client._request(
            "POST",
            f"/v1/processes/{process_id}/export",
            params={
                "version": version,
                "set_active_on_import": set_active_on_import,
                "include_dependencies": include_dependencies,
            },
        )
        return response.content

    async def aexport(
        self,
        process_id: str,
        *,
        version: ExportFormat = "auto",
        set_active_on_import: bool = False,
        include_dependencies: bool = True,
    ) -> bytes:
        response = await self.client._arequest(
            "POST",
            f"/v1/processes/{process_id}/export",
            params={
                "version": version,
                "set_active_on_import": set_active_on_import,
                "include_dependencies": include_dependencies,
            },
        )
        return response.content
