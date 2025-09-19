"""Base plugin class for plugin development"""
from __future__ import annotations

from typing import TYPE_CHECKING, Generic, Literal, TypeVar, get_args

from pydantic import BaseModel

if TYPE_CHECKING:
    from noxus_sdk.integrations.base import BaseIntegration
    from noxus_sdk.nodes.base import BaseNode

from noxus_sdk.ncl import serialize_config
from noxus_sdk.plugins.manifest import PluginManifest
from noxus_sdk.plugins.types import PluginCategory
from noxus_sdk.schemas import ValidationResult


class PluginConfiguration(BaseModel):
    """Configuration for the plugin"""

    @classmethod
    def serialize(cls) -> dict:
        """Get the serialized configuration for the plugin"""

        return serialize_config(cls)

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

        # Plugin must provide at least one node OR integration
        if not provided_nodes and not provided_integrations:
            raise ValueError(
                f"Plugin '{cls.name}' must provide at least one node or integration",
            )


        return PluginManifest(
            name=cls.name,
            display_name=cls.display_name,
            version=cls.version,
            description=cls.description,
            category=cls.category,
            author=cls.author,
            config=cls.get_config_class().serialize(),
            execution=cls.execution,
            image=cls.image,
            endpoint=cls.endpoint,
            nodes=[node.get_definition() for node in provided_nodes],
            integrations=[integration.get_definition() for integration in provided_integrations],
        )

    # Methods to override

    def nodes(self) -> list[type[BaseNode]]:
        """Return list of node classes provided by this plugin"""
        return []

    def integrations(self) -> list[type[BaseIntegration]]:
        """Return list of integration classes provided by this plugin"""
        return []
