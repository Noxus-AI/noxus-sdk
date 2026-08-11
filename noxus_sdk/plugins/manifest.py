from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from noxus_sdk.datasources.schemas import DatasourceDefinition
from noxus_sdk.integrations.schemas import IntegrationDefinition
from noxus_sdk.nodes.schemas import NodeDefinition
from noxus_sdk.plugins.types import PluginCategory
from noxus_sdk.triggers.schemas import TriggerDefinition

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

    # pyproject [project].dependencies, captured at manifest generation so the
    # platform can display what a plugin installs.
    dependencies: list[str] = []

    # Configuration
    config: dict

    # Execution configuration
    execution: Literal["runtime", "docker", "remote"] = "runtime"
    image: str | None = None
    endpoint: str | None = None

    # Plugin components. V1 and V2 nodes are kept as separate entities: a V1
    # node renders/wires with edge connectors, a V2 node with bindable config
    # fields — the platform backs each with a different generic executor.
    nodes: list[NodeDefinition] = []
    nodes_v2: list[NodeDefinition] = []
    integrations: list[IntegrationDefinition] = []
    triggers: list[TriggerDefinition] = []
    datasources: list[DatasourceDefinition] = []

    @classmethod
    def from_file(cls, file_path: Path) -> PluginManifest:
        """Load plugin manifest from a file"""
        with open(file_path) as f:
            return cls.model_validate_json(f.read())
