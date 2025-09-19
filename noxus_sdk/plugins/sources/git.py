"""Git plugin source for downloading plugins from repositories"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Literal

import aiofiles
import git
from loguru import logger
from pydantic import BaseModel, Field

from noxus_sdk.plugins.interfaces import PluginSource
from noxus_sdk.plugins.manifest import PluginManifest
from noxus_sdk.utils.github import get_file_content, is_github_repo

# Constants
MANIFEST_FILENAME = "manifest.json"
DEFAULT_BRANCH = "main"


class GitPluginSource(PluginSource, BaseModel):
    """Git plugin source with GitHub API optimization and sparse checkout."""

    type: Literal["git"] = "git"
    repo_url: str = Field(..., description="Git repository URL (HTTPS or SSH)")
    branch: str = Field(default=DEFAULT_BRANCH, description="Git branch to checkout")
    commit: str | None = Field(
        default=None,
        description="Specific commit hash (optional)",
    )
    path: str | None = Field(
        default=None,
        description="Subdirectory path within the repository",
    )

    def get_name(self) -> str:
        if self.path:
            return self.path.split("/")[-1]
        repo_name = self.repo_url.split("/")[-1]
        return repo_name.replace(".git", "")

    async def _get_manifest_via_api(self) -> PluginManifest:
        """Fast manifest retrieval via GitHub API (avoids cloning)."""
        if not is_github_repo(self.repo_url):
            raise ValueError("GitHub API method only works with GitHub repositories")

        manifest_path = f"{self.path}/{MANIFEST_FILENAME}" if self.path else MANIFEST_FILENAME

        manifest_data = await get_file_content(
            self.repo_url,
            manifest_path,
            self.branch,
        )
        return PluginManifest(**manifest_data)

    async def _download_subdirectory(self, temp_path: Path, target_path: Path) -> Path:
        """Use sparse checkout to download only the specified subdirectory."""
        if self.path is None:
            raise ValueError("Subdirectory path must be specified for sparse checkout")

        # Sparse + partial clone for bandwidth efficiency
        repo = git.Repo.clone_from(
            self.repo_url,
            temp_path,
            branch=self.branch,
            depth=1,
            no_checkout=True,
            multi_options=[
                "--filter=blob:none",  # Skip blob downloads initially
                "--sparse",  # Enable sparse checkout
            ],
        )

        repo.git.sparse_checkout("init", "--cone")
        repo.git.sparse_checkout("set", self.path)
        repo.git.checkout("-B", self.branch, f"origin/{self.branch}")

        source = temp_path / self.path
        if not source.exists():
            raise FileNotFoundError(
                f"Subdirectory '{self.path}' not found in repository {self.repo_url}",
            )

        shutil.copytree(source, target_path)
        return target_path

    async def _download_full_repository(
        self,
        temp_path: Path,
        target_path: Path,
    ) -> Path:
        """Download full repository with partial clone for bandwidth optimization."""
        git.Repo.clone_from(
            self.repo_url,
            temp_path,
            branch=self.branch,
            depth=1,
            multi_options=["--filter=blob:none"],  # Defer blob downloads
        )

        shutil.copytree(temp_path, target_path, ignore=shutil.ignore_patterns(".git"))
        return target_path

    async def download_plugin(self, output_dir: str | Path | None = None) -> Path:
        """Download plugin with sparse checkout optimization for subdirectories."""
        start_time = time.time()
        logger.debug(f"Downloading plugin from {self.repo_url}")

        if output_dir is None:
            raise ValueError("Output directory must be specified")

        output_dir = Path(output_dir)
        target_path = output_dir / self.get_name()

        if target_path.exists():
            raise FileExistsError(f"Destination {target_path} already exists")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            if self.path:
                target_path = await self._download_subdirectory(temp_path, target_path)
            else:
                target_path = await self._download_full_repository(
                    temp_path,
                    target_path,
                )

            total_time = time.time() - start_time
            logger.debug(f"Plugin download completed in {total_time:.2f}s total")
            return target_path

    async def _get_manifest_via_clone(self) -> PluginManifest:
        """Fallback: get manifest by cloning the repository."""
        start_time = time.time()
        logger.debug("Getting manifest via git clone (fallback method)")

        with tempfile.TemporaryDirectory() as temp_dir:
            plugin_path = await self.download_plugin(temp_dir)
            manifest_file = plugin_path / MANIFEST_FILENAME

            if not manifest_file.exists():
                available_files = [f.name for f in plugin_path.glob("*")]
                logger.error(
                    f"{MANIFEST_FILENAME} not found. Available files: {available_files}",
                )
                raise FileNotFoundError(f"{MANIFEST_FILENAME} not found in plugin")

            async with aiofiles.open(manifest_file, encoding="utf-8") as f:
                content = await f.read()
                manifest_data = json.loads(content)

            total_time = time.time() - start_time
            logger.debug(f"Manifest via clone completed in {total_time:.2f}s")
            return PluginManifest(**manifest_data)

    async def get_manifest(self) -> PluginManifest:
        """Get manifest via GitHub API first, fallback to git clone."""
        logger.debug(f"Getting manifest for {self.repo_url}")

        # Try GitHub API first for GitHub repos (much faster)
        if is_github_repo(self.repo_url):
            try:
                return await self._get_manifest_via_api()
            except Exception as e:  # noqa: BLE001 - If the GitHub API fails, we want to fall back to git clone. This should be better handled in the future.
                logger.warning(f"GitHub API failed: {e}, falling back to git clone")

        return await self._get_manifest_via_clone()
