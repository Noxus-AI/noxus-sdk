from __future__ import annotations

import mimetypes
import os
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, model_validator

if TYPE_CHECKING:
    from noxus_sdk.plugins.context import RemoteExecutionContext


class SourceType(str, Enum):
    Document = "Document"
    GoogleDrive = "Google Drive"
    Notion = "Notion"
    Website = "Website"
    OneDrive = "OneDrive"
    Slack = "Slack"
    Linear = "Linear"
    Github = "Github"
    Teams = "Teams"
    Sharepoint = "Sharepoint"
    ServiceNow = "ServiceNow"
    Custom = "Custom"

    @classmethod
    def get_by_value(cls, value: str) -> SourceType:
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"No enum member with value {value} in {cls}")


class SourceMetadata(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        arbitrary_types_allowed=True,
        validate_assignment=True,
    )
    rel_path: Optional[str] = None


class File(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: Optional[str] = None
    uri: str
    name: str
    content_type: str = "text/plain"
    source_type: SourceType = SourceType.Document
    source_metadata: Optional[SourceMetadata | dict] = None

    @classmethod
    async def from_bytes(
        cls,
        ctx: RemoteExecutionContext,
        data: bytes,
        name: Optional[str] = None,
        content_type: str = "text/plain",
        source_type: SourceType = SourceType.Document,
        source_metadata: Optional[SourceMetadata | dict] = None,
    ) -> File:
        if not name:
            name = uuid.uuid4().hex

        # This will call the bridged FileHelper in the plugin context
        out = await ctx.get_file_helper().upload_file(
            name,
            data,
            content_type=content_type,
            source_type=source_type,
            source_metadata=source_metadata,
            group_id=getattr(ctx, "group_id", None),
        )

        return cls(
            id=str(out.id) if hasattr(out, "id") else out.get("id"),
            uri=out.uri if hasattr(out, "uri") else out.get("uri"),
            name=name,
            content_type=content_type,
            source_type=source_type,
            source_metadata=source_metadata,
        )

    @classmethod
    def from_spot_uri(cls, uri: str, name: Optional[str] = None) -> File:
        """Retro-compatibility helper to create a File object from a spot:// URI"""
        if not uri.startswith("spot://"):
            raise ValueError(f"Invalid spot URI: {uri}")

        file_id = uri.replace("spot://", "").split("/")[0]
        return cls(
            id=file_id,
            uri=uri,
            name=name or f"file_{file_id}",
        )

    async def get_content(self, ctx: RemoteExecutionContext) -> bytes:
        return await ctx.get_file_helper().get_content(self)

    @model_validator(mode="before")
    @classmethod
    def set_name_and_content_type(cls, values: Any) -> Any:
        if isinstance(values, dict) and not values.get("name") and "uri" in values:
            parsed_uri = urlparse(values["uri"])
            basename = os.path.basename(parsed_uri.path)
            if basename:
                values["name"] = basename
            else:
                values["name"] = f"unknown_{uuid.uuid4().hex}"

        if (
            isinstance(values, dict)
            and not values.get("content_type")
            and "uri" in values
        ):
            derived_type, _ = mimetypes.guess_type(values["uri"])
            values["content_type"] = derived_type or "application/octet-stream"

        if isinstance(values, dict):
            if "id" not in values or values["id"] is None:
                if "spot://" in values.get("uri", ""):
                    values["id"] = values["uri"].split("/")[-1]
        return values


class EmptyFile(File):
    uri: str = "spot://empty"
    name: str = "empty.txt"

    async def get_content(self, ctx: RemoteExecutionContext) -> bytes:
        return b" "
