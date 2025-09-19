"""GitHub API utilities for plugin operations"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx
from async_lru import alru_cache
from loguru import logger

from noxus_sdk.plugins import PluginManifest


def is_github_repo(repo_url: str) -> bool:
    """Check if this is a GitHub repository"""
    return "github.com" in repo_url.lower()


def parse_github_url(repo_url: str) -> tuple[str, str]:
    """Parse GitHub URL to get owner and repo name"""
    # Handle both https://github.com/owner/repo and git@github.com:owner/repo formats
    if repo_url.startswith("git@"):
        # git@github.com:owner/repo.git -> owner/repo
        parts = repo_url.split(":")[-1].replace(".git", "").split("/")
    else:
        # https://github.com/owner/repo -> owner/repo
        parts = (
            repo_url.replace("https://github.com/", "").replace(".git", "").split("/")
        )

    if len(parts) >= 2:
        return parts[0], parts[1]
    raise ValueError(f"Could not parse GitHub URL: {repo_url}")


async def get_file_content(
    repo_url: str,
    file_path: str,
    branch: str = "main",
    github_token: str | None = None,
) -> dict[str, Any]:
    """Get file content from GitHub repository via API"""
    if not is_github_repo(repo_url):
        raise ValueError("This function only works with GitHub repositories")

    logger.info("Getting file via GitHub API")

    owner, repo = parse_github_url(repo_url)

    # Construct GitHub API URL
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_path}"
    if branch != "main":
        api_url += f"?ref={branch}"

    headers = {}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    async with httpx.AsyncClient() as client:
        response = await client.get(api_url, headers=headers)

        if response.status_code == 404:
            raise FileNotFoundError(f"{file_path} not found in {repo_url}")

        response.raise_for_status()

        data = response.json()

        # GitHub API returns base64 encoded content
        file_content = base64.b64decode(data["content"]).decode("utf-8")

        logger.info("GitHub API file fetch completed")

        return json.loads(file_content)


@alru_cache(maxsize=100, ttl=60 * 30)  # 30 minutes
async def get_all_plugin_manifests(
    github_repo_url: str,
    branch: str = "main",
    github_token: str | None = None,
) -> list[PluginManifest]:
    """Return (plugin_name, manifest) for all plugins in the root folder of a git repo.

    Only look at root level, so expecting root/plugin-1 root/plugin-2 etc.
    """
    if not is_github_repo(github_repo_url):
        raise ValueError("This function only works with GitHub repositories")

    logger.info("Getting all plugin manifests via GitHub API")

    owner, repo = parse_github_url(github_repo_url)
    api = f"https://api.github.com/repos/{owner}/{repo}/contents"
    params = {"ref": branch}

    headers = {}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    async with httpx.AsyncClient() as client:
        resp = await client.get(api, params=params, headers=headers, timeout=30)
        resp.raise_for_status()

        manifests = []
        for item in resp.json():
            if item["type"] != "dir":
                continue

            url = f"{api}/{item['name']}/manifest.json"
            r = await client.get(url, params=params, headers=headers, timeout=30)
            if r.status_code != 200:  # Skip if no manifest found
                continue

            data = r.json()
            raw = base64.b64decode(data["content"]).decode()
            try:
                manifest = PluginManifest.model_validate(json.loads(raw))
                manifests.append(manifest)
            except json.JSONDecodeError:
                continue

        return manifests
