"""Remote execution context for plugins"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from noxus_sdk.files import File, SourceMetadata, SourceType


class FileHelper(Protocol):
    async def get_content(self, file: File) -> bytes: ...

    async def upload_file(
        self,
        file_name: str,
        content: bytes,
        content_type: str = "text/plain",
        source_type: SourceType | str = "Document",
        source_metadata: SourceMetadata | dict | None = None,
        group_id: str | None = None,
    ) -> Any: ...


class RemoteExecutionContext(BaseModel):
    plugin_config: dict = {}
    integration_credentials: dict[str, dict] = {}
    group_id: str | None = None
    _file_helper: FileHelper | None = None

    def get_integration_credentials(self, integration_name: str) -> dict:
        return (
            self.integration_credentials[integration_name]
            if self.integration_credentials
            else {}
        )

    def get_file_helper(self) -> FileHelper:
        if self._file_helper is None:
            raise RuntimeError("File helper not initialized in context")
        return self._file_helper

    def set_file_helper(self, file_helper: FileHelper) -> None:
        self._file_helper = file_helper

    def get_group(self) -> Any:
        class Group:
            def __init__(self, group_id: str | None):
                self.group_id = group_id

            def get_id(self) -> str:
                return self.group_id or "00000000-0000-0000-0000-000000000000"

            def get_name(self) -> str:
                return "Plugin Group"

        return Group(self.group_id)


class RunExecutionContext(RemoteExecutionContext):
    """Alias for RemoteExecutionContext in plugin context"""
