from __future__ import annotations

from pydantic import BaseModel


class IntegrationDefinition(BaseModel):
    """Definition schema for integrations in plugin manifests"""

    type: str
    display_name: str
    image: str
    scopes: list[str] | None = None
    properties: dict[str, str] | None = None
    config: dict
