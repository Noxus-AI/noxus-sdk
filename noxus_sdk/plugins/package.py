import tarfile
from pathlib import Path


def _should_include_file(file_path: Path, plugin_root: Path) -> bool:
    """Determine if a file should be included in the package"""
    relative_path = file_path.relative_to(plugin_root)

    # Exclude common build/cache directories and files
    exclude_patterns = {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".coverage",
        "htmlcov",
        ".git",
        ".gitignore",
        ".DS_Store",
        "*.pyc",
        "*.pyo",
        "*.egg-info",
        "build",
        "dist",
        ".venv",
        "venv",
        ".env",
    }

    # Check if any part of the path matches exclude patterns
    for part in relative_path.parts:
        if part in exclude_patterns or part.startswith("."):
            return False
        # Check for glob patterns
        if part.endswith((".pyc", ".pyo")):
            return False

    return True

def package_plugin(plugin_path: Path, output_path: Path) -> Path:
    """Package a plugin into a tar.gz file"""

    # Create tar.gz archive
    with tarfile.open(output_path, "w:gz") as tar:
        # Add all files in the plugin directory, excluding common build/cache files
        for item in plugin_path.rglob("*"):
            if item.is_file() and _should_include_file(item, plugin_path):
                # Use relative path within the archive
                arcname = item.relative_to(plugin_path.parent)
                tar.add(item, arcname=arcname)

    return output_path
