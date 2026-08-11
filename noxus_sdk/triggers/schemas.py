from __future__ import annotations

from pydantic import BaseModel, Field


class TriggerDefinition(BaseModel):
    """A plugin-provided polling trigger, as declared in the manifest."""

    type: str
    title: str | None = None
    description: str | None = None
    image: str | None = None
    config: dict
    integrations: list[str] = Field(default_factory=list)
    polling_interval: float = 300.0
    # Event field name -> human-readable type label, used by the editor to
    # wire trigger outputs into workflow inputs.
    outputs: dict[str, str] = Field(default_factory=dict)
