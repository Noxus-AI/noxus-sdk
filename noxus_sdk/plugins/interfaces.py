"""Plugin interfaces and abstract base classes"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from noxus_sdk.plugins.manifest import PluginManifest


class PluginSource(ABC):
    """Abstract base class for plugin sources"""

    @abstractmethod
    def get_name(self) -> str:
        """Get the name/identifier of the plugin"""

    @abstractmethod
    async def download_plugin(self, output_dir: str | Path | None = None) -> Path:
        """Download or copy the plugin to the output directory"""

    @abstractmethod
    async def get_manifest(self) -> PluginManifest:
        """Get the manifest of the plugin"""
