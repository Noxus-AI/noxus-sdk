"""Base plugin class for plugin development"""

from __future__ import annotations

import inspect

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 — tomllib is 3.11+ stdlib
    import tomli as tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Generic, Literal, TypeVar, cast, get_args

from pydantic import BaseModel

if TYPE_CHECKING:
    from noxus_sdk.datasources.base import BaseDataSource
    from noxus_sdk.integrations.base import BaseIntegration
    from noxus_sdk.nodes.base import BaseNode
    from noxus_sdk.triggers.base import BasePollingTrigger

from noxus_sdk.ncl import serialize_config
from noxus_sdk.nodes.base import BaseNodeV2
from noxus_sdk.plugins.manifest import PluginManifest
from noxus_sdk.plugins.types import PluginCategory
from noxus_sdk.schemas import ValidationResult


class PluginConfiguration(BaseModel):
    """Configuration for the plugin"""

    @classmethod
    def serialize(cls) -> dict:
        """Get the serialized configuration for the plugin"""

        # serialize_config's annotation predates type[]; it takes a class.
        return serialize_config(cast(BaseModel, cls))

    # Can be overridden to specify custom validation
    def validate_config(self) -> ValidationResult:
        """Validate the configuration for the plugin"""
        return ValidationResult(valid=True)


ConfigType = TypeVar("ConfigType", bound=PluginConfiguration)


class BasePlugin(Generic[ConfigType]):
    """Base class for plugin development."""

    # Core plugin metadata
    name: str  # Unique identifier used for plugin lookup, dependencies, and database storage
    display_name: str  # Human-readable name for display purposes
    version: str  # Semantic versioning (e.g. 1.0.0)
    description: str  # Short description of the plugin
    category: PluginCategory = PluginCategory.OTHER  # Category of the plugin
    author: str  # Author of the plugin

    # Execution configuration
    execution: Literal["runtime", "docker", "remote"] = "runtime"

    # Required for execution == "docker"
    image: str | None = None

    # Required for execution == "remote"
    endpoint: str | None = None

    # Optional shell command the platform runs inside the sandbox once at
    # provision time (after the dependency install). Use it to install system
    # packages or CLI tools nodes shell out to. Must be idempotent — a
    # re-provision runs it again — and must never embed credentials.
    setup_command: str | None = None

    # Sandbox budget for the warm worker, in manager slots (1/8 CPU + 256 MiB
    # each). Raise it for plugins that crunch data in-process.
    execution_slots: int = 1

    # Internal variables (not exposed to the user)
    _config_class: type[
        ConfigType
    ]  # Used for internal purposes like getting the configuration class

    def __init_subclass__(cls) -> None:
        """Set the configuration class for the plugin when the sublcass is created"""
        # get_args(cls.__orig_bases__[0])[0] -> PluginConfiguration class defined by the user
        cls._config_class = get_args(cls.__orig_bases__[0])[0]  # type: ignore
        return super().__init_subclass__()

    @classmethod
    def get_config_class(cls) -> type[ConfigType]:
        return cls._config_class

    @classmethod
    def get_manifest(cls) -> PluginManifest:
        """Get the manifest for the plugin"""

        plugin_instance = cls()
        provided_nodes = plugin_instance.nodes()
        provided_integrations = plugin_instance.integrations()
        provided_triggers = plugin_instance.triggers()
        provided_datasources = plugin_instance.datasources()

        # Plugin must provide at least one node, integration, trigger, or datasource.
        if (
            not provided_nodes
            and not provided_integrations
            and not provided_triggers
            and not provided_datasources
        ):
            raise ValueError(
                f"Plugin '{cls.name}' must provide at least one node, "
                "integration, trigger, or datasource",
            )

        # Split V1 and V2 nodes into separate manifest lists. BaseNodeV2 is a
        # BaseNode subclass, so it must be checked first.
        v1_nodes = [n for n in provided_nodes if not issubclass(n, BaseNodeV2)]
        v2_nodes = [n for n in provided_nodes if issubclass(n, BaseNodeV2)]

        return PluginManifest(
            name=cls.name,
            display_name=cls.display_name,
            version=cls.version,
            description=cls.description,
            category=cls.category,
            author=cls.author,
            dependencies=cls._plugin_dependencies(),
            config=cls.get_config_class().serialize(),
            execution=cls.execution,
            image=cls.image,
            endpoint=cls.endpoint,
            setup_command=cls.setup_command,
            execution_slots=cls.execution_slots,
            nodes=[node.get_definition() for node in v1_nodes],
            nodes_v2=[node.get_definition() for node in v2_nodes],
            integrations=[
                integration.get_definition() for integration in provided_integrations
            ],
            triggers=[trigger.get_definition() for trigger in provided_triggers],
            datasources=[
                datasource.get_definition() for datasource in provided_datasources
            ],
        )

    @classmethod
    def _plugin_dependencies(cls) -> list[str]:
        """The plugin's declared runtime deps, read from its pyproject.toml so
        the platform can show them. Best-effort — empty if not resolvable."""
        try:
            start = Path(inspect.getfile(cls)).resolve().parent
            for directory in (start, *start.parents):
                pyproject = directory / "pyproject.toml"
                if pyproject.is_file():
                    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
                    deps = data.get("project", {}).get("dependencies", [])
                    return [str(d) for d in deps]
        except Exception:
            pass
        return []

    # Methods to override

    def nodes(self) -> list[type[BaseNode]]:
        """Return list of node classes provided by this plugin"""
        return []

    def integrations(self) -> list[type[BaseIntegration]]:
        """Return list of integration classes provided by this plugin"""
        return []

    def triggers(self) -> list[type[BasePollingTrigger]]:
        """Return list of polling trigger classes provided by this plugin"""
        return []

    def datasources(self) -> list[type[BaseDataSource]]:
        """Return list of KB datasource classes provided by this plugin"""
        return []
