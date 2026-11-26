from __future__ import annotations

import mimetypes
import os
import unicodedata
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
        extra="allow", arbitrary_types_allowed=True, validate_assignment=True
    )
    rel_path: Optional[str] = None
    external_id: Optional[str] = None


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
    async def from_bytes_internal_uri(
        cls,
        ctx: RemoteExecutionContext,
        data: bytes,
        name: Optional[str] = None,
        content_type: str = "text/plain",
        source_type: SourceType = SourceType.Document,
        source_metadata: Optional[SourceMetadata | dict] = None,
    ) -> File:
        """Persist raw ``bytes`` to platform storage and return a :class:`File`
        that references them by internal (``spot://``) URI.

        Alias of :meth:`from_bytes` — both upload through the host ``upload_file``
        callback, so the resulting file lives in platform storage (not the
        sandbox) and can be handed to downstream nodes. Prefer this when you want
        an explicit, self-documenting call at a persistence site (e.g. saving a
        downloaded attachment); use :meth:`from_bytes` otherwise.
        """
        return await cls.from_bytes(
            ctx,
            data,
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


_FALLBACK_NAME = "file"
_MAX_NAME_BYTES = 255
_MAX_EXTENSION_BYTES = 32
# Bidi embeddings, overrides and isolates change how a name is displayed:
# "invoice<U+202E>gpj.exe" reads as "invoiceexe.jpg".
_BIDI_CONTROLS = frozenset(
    chr(code) for code in [*range(0x202A, 0x202F), *range(0x2066, 0x206A)]
)


def _kept_in_file_name(ch: str) -> bool:
    return unicodedata.category(ch) != "Cc" and ch not in _BIDI_CONTROLS


def safe_file_name(name: str) -> str:
    """``name`` reduced to one path segment, safe to create inside a folder.

    File names come from uploads and email attachments, so a separator,
    ``..`` or an absolute path must never reach the filesystem.
    """
    base = name.replace("\\", "/").rsplit("/", 1)[-1]
    base = "".join(ch for ch in base if _kept_in_file_name(ch)).strip()
    if base in ("", ".", ".."):
        return _FALLBACK_NAME
    if len(base.encode()) <= _MAX_NAME_BYTES:
        return base
    stem, extension = os.path.splitext(base)
    if len(extension.encode()) > _MAX_EXTENSION_BYTES:
        stem, extension = base, ""
    budget = _MAX_NAME_BYTES - len(extension.encode())
    return stem.encode()[:budget].decode(errors="ignore") + extension


def _numbered_name(stem: str, extension: str, copy: int) -> str:
    if len(extension.encode()) > _MAX_EXTENSION_BYTES:
        stem, extension = stem + extension, ""
    suffix = f" ({copy}){extension}"
    head = stem.encode()[: _MAX_NAME_BYTES - len(suffix.encode())]
    return head.decode(errors="ignore") + suffix


def unique_local_path(folder: str, name: str) -> str:
    """A path in ``folder`` for ``name`` that nothing occupies yet.

    Two files whose names reduce to the same safe name get ``report.pdf`` and
    ``report (1).pdf`` rather than one overwriting the other.
    """
    root = os.path.realpath(folder)
    base = safe_file_name(name)
    stem, extension = os.path.splitext(base)
    candidate = os.path.join(root, base)
    copy = 0
    while os.path.lexists(candidate):
        copy += 1
        candidate = os.path.join(root, _numbered_name(stem, extension, copy))
    if os.path.dirname(os.path.realpath(candidate)) != root:
        raise ValueError(f"File name {name!r} resolves outside {folder}")
    return candidate


async def persist_files(
    ctx: RemoteExecutionContext, files: list[File], path: str | None = None
) -> list[str]:
    """Download ``files`` into a local directory and return each file's path.

    Each file's bytes are fetched via the host ``get_content`` callback and
    written under ``path`` (a fresh directory under ``/tmp`` when omitted) as
    :func:`safe_file_name` of its ``name``; same-named files stay distinct. The
    directory lives on the plugin's own sandbox filesystem: use this when a
    library needs real file paths on disk rather than :class:`File` references.
    """
    if not path:
        path = os.path.join("/tmp", uuid.uuid4().hex)
    os.makedirs(path, exist_ok=True)
    paths = []
    for f in files:
        local_path = unique_local_path(path, f.name)
        with open(local_path, "xb") as fp:
            fp.write(await f.get_content(ctx))
        paths.append(local_path)
    return paths


async def persist_files_locally(
    ctx: RemoteExecutionContext, files: list[File], path: str | None = None
) -> str:
    """Like :func:`persist_files`, returning the directory instead of the paths."""
    if not path:
        path = os.path.join("/tmp", uuid.uuid4().hex)
    await persist_files(ctx, files, path)
    return path
