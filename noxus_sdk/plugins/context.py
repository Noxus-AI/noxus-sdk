"""Remote execution context for plugins"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING, Protocol
from pydantic import BaseModel

if TYPE_CHECKING:
    from noxus_sdk.files import File, SourceType, SourceMetadata


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


class CredentialsHelper(Protocol):
    async def update_integration_credentials(
        self,
        integration_name: str,
        payload: dict,
        credential_id: str | None = None,
    ) -> None: ...


class RemoteExecutionContext(BaseModel):
    plugin_config: dict = {}
    integration_credentials: dict[str, dict] = {}
    # The stored credential id each payload came from, so a plugin can write
    # an updated payload back to the exact row it was handed.
    integration_credential_ids: dict[str, str] = {}
    group_id: str | None = None
    # Opaque, single-use token minted by the host for this call. File
    # callbacks must present it; the host uses it to resolve which workspace
    # the call belongs to. Plugin code never needs to read or set it.
    call_token: str | None = None
    _file_helper: FileHelper | None = None
    _credentials_helper: CredentialsHelper | None = None

    def get_integration_credentials(self, integration_name: str) -> dict:
        return (
            self.integration_credentials.get(integration_name, {})
            if self.integration_credentials
            else {}
        )

    def get_file_helper(self) -> FileHelper:
        if self._file_helper is None:
            raise RuntimeError("File helper not initialized in context")
        return self._file_helper

    def set_file_helper(self, file_helper: FileHelper) -> None:
        self._file_helper = file_helper

    async def update_integration_credentials(
        self,
        integration_name: str,
        payload: dict,
        credential_id: str | None = None,
    ) -> None:
        """Push an updated credential payload back to the platform store.

        Scoped by the host to the calling workspace and to integrations the
        calling plugin declares. Use when the plugin refreshes a token the
        stored credential would otherwise lose (e.g. rotated OAuth state)."""
        if self._credentials_helper is None:
            raise RuntimeError("Credentials helper not initialized in context")
        await self._credentials_helper.update_integration_credentials(
            integration_name,
            payload,
            credential_id or self.integration_credential_ids.get(integration_name),
        )

    def set_credentials_helper(self, helper: CredentialsHelper) -> None:
        self._credentials_helper = helper

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

    pass
