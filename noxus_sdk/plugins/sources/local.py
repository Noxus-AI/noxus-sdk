"""Local plugin source for copying plugins from local directories"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Literal

import aiofiles
from loguru import logger
from pydantic import BaseModel, Field

from noxus_sdk.plugins.interfaces import PluginSource
from noxus_sdk.plugins.manifest import PluginManifest


class LocalPluginSource(PluginSource, BaseModel):
    """Local plugin source"""

    type: Literal["local"] = "local"
    path: str = Field(..., description="Local path to the plugin directory")

    def get_name(self) -> str:
        """Get the name of the plugin"""
        return Path(self.path).name

    async def download_plugin(self, output_dir: str | Path | None = None) -> Path:
        """Copy the plugin from local directory"""
        if output_dir is None:
            raise ValueError("Output directory must be specified")

        source_path = Path(self.path)
        if not source_path.exists():
            raise FileNotFoundError(f"Plugin directory {self.path} does not exist")

        if not source_path.is_dir():
            raise ValueError(f"Plugin path {self.path} is not a directory")

        target_name = source_path.name
        target_path = Path(output_dir) / target_name

        if target_path.exists():
            raise FileExistsError(f"Destination {target_path} already exists")

        logger.info(f"Copying plugin from {source_path} to {target_path}")

        shutil.copytree(source_path, target_path)

        return target_path

    async def get_manifest(self) -> PluginManifest:
        """Get the manifest of the plugin by copying to temp dir"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Use download_plugin to get the plugin files
            plugin_path = await self.download_plugin(temp_dir)

            # Read manifest.json from copied plugin
            manifest_file = plugin_path / "manifest.json"
            if not manifest_file.exists():
                raise FileNotFoundError(f"manifest.json not found in {plugin_path}")

            # Load and parse manifest
            async with aiofiles.open(manifest_file) as f:
                content = await f.read()
                manifest_data = json.loads(content)

            return PluginManifest(**manifest_data)
