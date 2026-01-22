"""Git plugin source for downloading plugins from repositories"""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse, urlunparse

import aiofiles
import git
from loguru import logger
from pydantic import BaseModel, Field

from noxus_sdk.plugins.exceptions import (
    GitAuthenticationError,
    GitRepositoryNotFoundError,
    ManifestNotFoundError,
)
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

    # Auth option 1: Token/PAT (works with GitHub, GitLab, Bitbucket, etc.)
    token: str | None = Field(
        default=None,
        description="Access token for private repositories",
    )

    # Auth option 2: Username + Password/Token
    username: str | None = Field(
        default=None,
        description="Git username for authentication",
    )
    password: str | None = Field(
        default=None,
        description="Git password or personal access token",
    )

    def get_name(self) -> str:
        if self.path:
            return self.path.split("/")[-1]
        repo_name = self.repo_url.split("/")[-1]
        return repo_name.replace(".git", "")

    def _get_authenticated_url(self) -> str:
        """Build authenticated URL for git operations."""
        if not self.repo_url.startswith(("http://", "https://")):
            return self.repo_url

        parsed = urlparse(self.repo_url)

        if self.token:
            # Token auth: https://token@github.com/user/repo
            netloc = f"{self.token}@{parsed.hostname}"
        elif self.username and self.password:
            # Username + password/token: https://user:pass@github.com/user/repo
            netloc = f"{self.username}:{self.password}@{parsed.hostname}"
        else:
            return self.repo_url

        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"

        return urlunparse(parsed._replace(netloc=netloc))

    def _get_api_token(self) -> str | None:
        """Get token for API authentication (token takes precedence over password)."""
        return self.token or self.password

    def _handle_git_error(self, error: git.GitCommandError) -> Exception:
        """Convert git errors to user-friendly exceptions."""
        stderr = str(error.stderr).lower() if error.stderr else ""
        stdout = str(error.stdout).lower() if error.stdout else ""
        error_text = f"{stderr} {stdout}"

        # Authentication errors (private repos, invalid credentials)
        auth_patterns = [
            "authentication",
            "could not read username",
            "invalid credentials",
            "permission denied",
            "access denied",
        ]
        if any(pattern in error_text for pattern in auth_patterns):
            return GitAuthenticationError(
                "Authentication failed. This may be a private repository - "
                "please provide credentials.",
            )

        # Repository not found errors
        not_found_patterns = [
            "not found",
            "does not exist",
            "returned error: 404",
            "unable to access",
            "no such repository",
        ]
        if any(pattern in error_text for pattern in not_found_patterns):
            return GitRepositoryNotFoundError(
                f"Repository not found: {self.repo_url}. "
                "Check that the URL is correct and the repository exists.",
            )

        # Network/DNS errors
        if "could not resolve host" in error_text:
            return GitRepositoryNotFoundError(
                f"Could not resolve host for {self.repo_url}. "
                "Check your network connection.",
            )

        # Fallback with original error for debugging
        return GitRepositoryNotFoundError(
            f"Failed to clone repository {self.repo_url}: {error.stderr or error}",
        )

    async def _get_manifest_via_api(self) -> PluginManifest:
        """Fast manifest retrieval via GitHub API (avoids cloning)."""
        if not is_github_repo(self.repo_url):
            raise ValueError("GitHub API method only works with GitHub repositories")

        manifest_path = (
            f"{self.path}/{MANIFEST_FILENAME}" if self.path else MANIFEST_FILENAME
        )

        manifest_data = await get_file_content(
            self.repo_url,
            manifest_path,
            self.branch,
            github_token=self._get_api_token(),
        )
        return PluginManifest(**manifest_data)

    async def _download_subdirectory(self, temp_path: Path, target_path: Path) -> Path:
        """Use sparse checkout to download only the specified subdirectory."""
        if self.path is None:
            raise ValueError("Subdirectory path must be specified for sparse checkout")

        clone_url = self._get_authenticated_url()

        try:
            # Sparse + partial clone for bandwidth efficiency
            repo = git.Repo.clone_from(
                clone_url,
                temp_path,
                branch=self.branch,
                depth=1,
                no_checkout=True,
                multi_options=[
                    "--filter=blob:none",  # Skip blob downloads initially
                    "--sparse",  # Enable sparse checkout
                ],
            )
        except git.GitCommandError as e:
            raise self._handle_git_error(e) from e

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
        clone_url = self._get_authenticated_url()

        try:
            git.Repo.clone_from(
                clone_url,
                temp_path,
                branch=self.branch,
                depth=1,
                multi_options=["--filter=blob:none"],  # Defer blob downloads
            )
        except git.GitCommandError as e:
            raise self._handle_git_error(e) from e

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
                raise ManifestNotFoundError(
                    f"No manifest.json found in repository {self.repo_url}. "
                    "This does not appear to be a valid Noxus plugin.",
                )

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
