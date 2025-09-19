"""Marketplace plugin source for downloading plugins from the official marketplace"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from noxus_sdk.plugins.interfaces import PluginSource
from noxus_sdk.plugins.sources.git import GitPluginSource

if TYPE_CHECKING:
    from pathlib import Path

    from noxus_sdk.plugins.manifest import PluginManifest


class MarketplacePluginSource(PluginSource, BaseModel):
    """Marketplace plugin source that downloads plugins from the official marketplace repository"""

    type: Literal["marketplace"] = "marketplace"
    name: str = Field(..., description="Plugin name in the marketplace")
    version: str = Field(..., description="Plugin version to download")

    def get_name(self) -> str:
        return self.name

    def _get_git_source(self) -> GitPluginSource:
        """Create a GitPluginSource configured for the marketplace repository"""
        # Marketplace repository configuration
        marketplace_repo = "https://github.com/Noxus-AI/noxus-plugins.git"
        plugin_path = f"{self.name}"

        return GitPluginSource(
            repo_url=marketplace_repo,
            branch="main",
            path=plugin_path,
        )

    async def get_manifest(self) -> PluginManifest:
        """Get plugin manifest from the marketplace repository"""
        git_source = self._get_git_source()
        return await git_source.get_manifest()

    async def download_plugin(self, output_dir: str | Path | None = None) -> Path:
        """Download plugin from the marketplace repository"""
        git_source = self._get_git_source()
        return await git_source.download_plugin(output_dir)
