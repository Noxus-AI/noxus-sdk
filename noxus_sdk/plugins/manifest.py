from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from noxus_sdk.integrations.schemas import IntegrationDefinition
from noxus_sdk.nodes.schemas import NodeDefinition
from noxus_sdk.plugins.types import PluginCategory

if TYPE_CHECKING:
    from pathlib import Path


class PluginManifest(BaseModel):
    """Complete plugin specification combining manifest and spec"""

    # Core plugin metadata
    name: str
    display_name: str
    version: str
    description: str
    category: PluginCategory = PluginCategory.OTHER
    author: str

    # Configuration
    config: dict

    # Execution configuration
    execution: Literal["runtime", "docker", "remote"] = "runtime"
    image: str | None = None
    endpoint: str | None = None

    # Plugin components
    nodes: list[NodeDefinition] = []
    integrations: list[IntegrationDefinition] = []

    @classmethod
    def from_file(cls, file_path: Path) -> PluginManifest:
        """Load plugin manifest from a file"""
        with open(file_path) as f:
            return cls.model_validate_json(f.read())
