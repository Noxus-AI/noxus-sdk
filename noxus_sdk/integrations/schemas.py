from __future__ import annotations

from pydantic import BaseModel

from noxus_sdk.integrations.types import IntegrationType


class IntegrationDefinition(BaseModel):
    """Definition schema for integrations in plugin manifests"""

    name: str
    type: IntegrationType
    display_name: str
    description: str | None = None
    image: str
    scopes: list[str] | None = None

    properties: dict = {}  # Used to add extra properties to the integration definition
