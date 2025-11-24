"""Upload plugin source for handling uploaded plugin files"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Literal

import aiofiles
import httpx
from loguru import logger
from pydantic import BaseModel, Field

from noxus_sdk.plugins.interfaces import PluginSource
from noxus_sdk.plugins.manifest import PluginManifest


def _is_safe_path(base_path: Path, member_path: str) -> bool:
    """Check if the member path is safe to extract (no path traversal)"""
    # Normalize the member path and resolve any .. components
    try:
        full_path = (base_path / member_path).resolve()
        base_path_resolved = base_path.resolve()

        # Check if the resolved path is within the base directory
        return (
            str(full_path).startswith(str(base_path_resolved) + os.sep)
            or full_path == base_path_resolved
        )
    except (OSError, ValueError):
        # If path resolution fails, consider it unsafe
        return False


def _validate_member_name(name: str) -> bool:
    """Validate archive member name for security"""
    # Normalize path to catch sneaky sequences
    normalized = os.path.normpath(name)

    return not (
        normalized.startswith(("/", "\\", "~", "..", "\\\\"))
        or normalized in (".", "")
        or (":" in normalized and os.name == "nt")  # Windows drive letters
        or ".." in normalized.replace("\\", "/")  # Catch traversal
    )


class UploadPluginSource(PluginSource, BaseModel):
    """Upload plugin source for uploaded files"""

    type: Literal["upload"] = "upload"
    file_id: str = Field(..., description="File ID to download from platform")
    filename: str = Field(..., description="Original filename of the uploaded plugin")

    def get_name(self) -> str:
        """Get the name of the plugin from the filename (will be replaced by manifest name)"""
        # Remove .zip extension and any version info
        return Path(self.filename).stem

    async def download_plugin(self, output_dir: str | Path | None = None) -> Path:
        """Download and extract the uploaded plugin file to the output directory"""
        if output_dir is None:
            raise ValueError("Output directory must be specified")

        output_dir = Path(output_dir)

        # Download file from platform API
        temp_file_path = await self._download_file_from_platform()

        try:
            logger.info(f"Extracting plugin code to {output_dir}")

            # Determine file type and extract accordingly
            if self.filename.lower().endswith(".zip"):
                await self._extract_archive(temp_file_path, output_dir, "zip")
            elif self.filename.lower().endswith((".tar.gz", ".tgz", ".tar")):
                await self._extract_archive(temp_file_path, output_dir, "tar")
            else:
                raise ValueError(f"Unsupported file format: {self.filename}")

            return output_dir

        finally:
            # Clean up downloaded temp file
            if temp_file_path.exists():
                temp_file_path.unlink()

    async def _download_file_from_platform(self) -> Path:
        """Download file from platform API using file ID"""
        platform_url = os.getenv("NOXUS_PLATFORM_URL", "http://localhost:8000")
        api_key = os.getenv("PLUGIN_SERVER_PLATFORM_KEY", None)

        if not api_key:
            raise ValueError(
                "PLUGIN_SERVER_PLATFORM_KEY environment variable is required",
            )

        url = f"{platform_url}/plugin-server/files/{self.file_id}"
        headers = {"X-API-Key": api_key}

        logger.info(f"Downloading file {self.file_id} from platform: {url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=60.0)

            if response.status_code == 404:
                raise FileNotFoundError(
                    f"File with ID {self.file_id} not found on platform",
                )
            if response.status_code == 401:
                raise ValueError("Invalid API key for platform access")

            response.raise_for_status()

            # Create temporary file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=f"_{self.filename}",
                delete=False,
            )
            temp_file.write(response.content)
            temp_file.close()

            logger.info(f"Downloaded file to temporary location: {temp_file.name}")
            return Path(temp_file.name)

    async def _extract_archive(
        self,
        source_path: Path,
        target_path: Path,
        archive_type: str,
    ) -> None:
        """Extract an archive file (zip or tar), handling single-folder archives correctly"""
        try:
            # Get file names from archive
            if archive_type == "zip":
                await self._extract_zip_archive(source_path, target_path)
            elif archive_type == "tar":
                await self._extract_tar_archive(source_path, target_path)
            else:
                raise ValueError(f"Unsupported archive type: {archive_type}")

        except (zipfile.BadZipFile, tarfile.TarError) as e:
            raise ValueError(f"Invalid {archive_type} file: {source_path}") from e

    async def _extract_zip_archive(self, source_path: Path, target_path: Path) -> None:
        """Securely extract ZIP archive with path validation"""

        def _sync_extract_zip() -> None:
            with zipfile.ZipFile(source_path, "r") as archive_ref:
                names = archive_ref.namelist()
                self._secure_extract_archive(archive_ref, names, target_path, "ZIP")

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_extract_zip)

    async def _extract_tar_archive(self, source_path: Path, target_path: Path) -> None:
        """Securely extract TAR archive with path validation"""

        def _sync_extract_tar() -> None:
            with tarfile.open(source_path, "r:*") as archive_ref:
                names = archive_ref.getnames()
                self._secure_extract_archive(archive_ref, names, target_path, "TAR")

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _sync_extract_tar)

    def _secure_extract_archive(
        self,
        archive_ref: zipfile.ZipFile | tarfile.TarFile,
        names: list[str],
        target_path: Path,
        archive_type: str,
    ) -> None:
        """Common secure extraction logic for both ZIP and TAR archives"""
        if not names:
            return

        # Filter out unsafe names
        safe_names = []
        for name in names:
            if _validate_member_name(name) and _is_safe_path(target_path, name):
                safe_names.append(name)
            else:
                logger.warning(f"Skipping unsafe path in {archive_type}: {name}")

        if not safe_names:
            logger.warning(f"No safe files found in {archive_type} archive")
            return

        # Handle single folder extraction
        self._handle_single_folder_extraction(archive_ref, safe_names, target_path)

    def _handle_single_folder_extraction(
        self,
        archive_ref: zipfile.ZipFile | tarfile.TarFile,
        safe_names: list[str],
        target_path: Path,
    ) -> None:
        """Handle single folder extraction logic for both ZIP and TAR files"""
        # Get top-level entries (excluding system files)
        top_level_entries = []
        for name in safe_names:
            top_part = name.split("/")[0] if "/" in name else name
            if (
                not top_part.startswith(("__", "."))
                and top_part not in top_level_entries
            ):
                top_level_entries.append(top_part)

        # Ensure target directory exists
        target_path.mkdir(parents=True, exist_ok=True)

        # If there's exactly one top-level directory, extract its contents
        if len(top_level_entries) == 1 and any(
            name.startswith(f"{top_level_entries[0]}/") for name in safe_names
        ):
            root_dir = top_level_entries[0]
            # Extract to temp dir first, then copy contents
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_target = Path(temp_dir)
                # Extract only safe members
                self._extract_members(archive_ref, safe_names, temp_target)

                extracted_root = temp_target / root_dir
                if extracted_root.exists() and any(extracted_root.iterdir()):
                    # Copy contents of the extracted directory to target
                    for item in extracted_root.iterdir():
                        if item.is_dir():
                            shutil.copytree(
                                item,
                                target_path / item.name,
                                dirs_exist_ok=True,
                            )
                        else:
                            shutil.copy2(item, target_path / item.name)
                else:
                    # Fallback: extract directly to target
                    self._extract_members(archive_ref, safe_names, target_path)
        else:
            # Multiple top-level entries or files, extract directly
            self._extract_members(archive_ref, safe_names, target_path)

    def _extract_members(
        self,
        archive_ref: zipfile.ZipFile | tarfile.TarFile,
        safe_names: list[str],
        target_path: Path,
    ) -> None:
        """Extract members from archive, handling both ZIP and TAR formats"""
        if isinstance(archive_ref, zipfile.ZipFile):
            for name in safe_names:
                archive_ref.extract(name, target_path)
        elif isinstance(archive_ref, tarfile.TarFile):
            for name in safe_names:
                member = archive_ref.getmember(name)
                archive_ref.extract(member, target_path)

    async def get_manifest(self) -> PluginManifest:
        """Get the manifest by extracting to a temp directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract the plugin to temp directory
            plugin_path = await self.download_plugin(temp_dir)

            # Read manifest.json from extracted plugin
            manifest_file = plugin_path / "manifest.json"
            if not manifest_file.exists():
                # Show all files and directories for better debugging
                available_items = []
                for item in plugin_path.glob("*"):
                    if item.is_dir():
                        available_items.append(f"{item.name}/")
                    else:
                        available_items.append(item.name)

                logger.error(
                    f"manifest.json not found in {plugin_path}. Available items: {available_items}",
                )

                # Also check if manifest.json exists in any subdirectories
                for subdir in plugin_path.glob("*/"):
                    sub_manifest = subdir / "manifest.json"
                    if sub_manifest.exists():
                        logger.error(f"Found manifest.json in subdirectory: {subdir}")

                raise FileNotFoundError("manifest.json not found in plugin")

            # Load and parse manifest
            async with aiofiles.open(manifest_file, encoding="utf-8") as f:
                content = await f.read()
                manifest_data = json.loads(content)

            return PluginManifest(**manifest_data)
