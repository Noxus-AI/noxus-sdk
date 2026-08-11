from __future__ import annotations

from pydantic import BaseModel, Field


class DatasourceDefinition(BaseModel):
    """A plugin-provided KB datasource, as declared in the manifest.

    A datasource is an external source a Knowledge Base ingests files from. The
    one-shot ``fetch`` (pull the files once, the "Add knowledge" flow) is
    supported today; incremental ``sync`` (poll for changes) is reserved via
    ``supports_sync`` for a later phase.
    """

    type: str
    title: str | None = None
    description: str | None = None
    image: str | None = None
    config: dict
    integrations: list[str] = Field(default_factory=list)
    supports_sync: bool = False
