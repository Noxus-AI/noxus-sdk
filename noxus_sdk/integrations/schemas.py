from __future__ import annotations

from pydantic import BaseModel


class IntegrationDefinition(BaseModel):
    type: str
    display_name: str
    image: str
    description: str = ""
    scopes: list[str] | None = None
    properties: dict[str, str] | None = None
    config: dict
