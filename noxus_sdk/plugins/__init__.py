"""Plugin domain - everything related to plugin management"""

from noxus_sdk.plugins.base import BasePlugin, PluginConfiguration
from noxus_sdk.plugins.context import RemoteExecutionContext
from noxus_sdk.plugins.exceptions import (
    GitAuthenticationError,
    GitRepositoryNotFoundError,
    ManifestNotFoundError,
    PluginSourceError,
)
from noxus_sdk.plugins.manifest import PluginManifest
from noxus_sdk.plugins.sources import (
    AnyPluginSource,
    GitPluginSource,
    LocalPluginSource,
    UploadPluginSource,
)
from noxus_sdk.plugins.types import PluginCategory, PluginSourceType, PluginStatus

__all__ = [
    "AnyPluginSource",
    "BasePlugin",
    "GitAuthenticationError",
    "GitPluginSource",
    "GitRepositoryNotFoundError",
    "LocalPluginSource",
    "ManifestNotFoundError",
    "PluginCategory",
    "PluginConfiguration",
    "PluginManifest",
    "PluginSourceError",
    "PluginSourceType",
    "PluginStatus",
    "RemoteExecutionContext",
    "UploadPluginSource",
]
