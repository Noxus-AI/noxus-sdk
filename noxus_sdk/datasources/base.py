"""Authoring base for plugin-provided KB datasources.

A datasource is an external source a Knowledge Base ingests files from. The
platform owns the KB, ingestion (chunking/embedding), and — later — sync
scheduling; a plugin datasource only answers ``fetch``: given its config,
produce the files to ingest. It runs inside the plugin's warm sandboxed worker,
invoked over JSON-RPC (``datasource.fetch``).

Only one-shot ``fetch`` is supported today (the "Add knowledge" flow).
Incremental sync (list/get/download driven by the platform SyncEngine) is a
later phase; ``supports_sync`` is reserved for it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Generic, TypeVar, get_args

from noxus_sdk.datasources.schemas import DatasourceDefinition
from noxus_sdk.nodes.base import NodeConfiguration

if TYPE_CHECKING:
    from noxus_sdk.files import File
    from noxus_sdk.plugins.context import RemoteExecutionContext


class DatasourceConfiguration(NodeConfiguration):
    """Base configuration class for plugin datasources."""


DatasourceConfigType = TypeVar("DatasourceConfigType", bound=DatasourceConfiguration)


class BaseDataSource(Generic[DatasourceConfigType]):
    datasource_name: ClassVar[str] = "BaseDataSource"
    title: ClassVar[str] = ""
    description: ClassVar[str] = ""
    image: ClassVar[str | None] = None
    integrations: ClassVar[list[str]] = []
    # Incremental sync is a later phase — one-shot fetch only for now.
    supports_sync: ClassVar[bool] = False

    config_class: type[DatasourceConfigType]

    def __init_subclass__(cls) -> None:
        cls.config_class = get_args(cls.__orig_bases__[0])[0]  # type: ignore

    def __init__(self, config: DatasourceConfigType) -> None:
        self.config = config

    @classmethod
    def get_config_class(cls) -> type[DatasourceConfigType]:
        return cls.config_class

    @classmethod
    def get_definition(cls) -> DatasourceDefinition:
        return DatasourceDefinition(
            type=cls.datasource_name,
            title=cls.title or cls.datasource_name,
            description=cls.description,
            image=cls.image,
            config=cls.get_config_class().serialize(),
            integrations=list(cls.integrations),
            supports_sync=cls.supports_sync,
        )

    async def fetch(self, ctx: RemoteExecutionContext) -> list[File]:
        """One-shot ingestion: return the files to add to the KB.

        Fetch each file's bytes and persist it with
        ``ctx.get_file_helper().upload_file(...)`` (which stores it on the
        platform and returns a descriptor); return the resulting files. The
        content is uploaded over the host callback, not returned inline.
        """
        raise NotImplementedError
