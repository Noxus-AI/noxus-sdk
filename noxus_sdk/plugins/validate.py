from __future__ import annotations

import sys
from contextlib import contextmanager
from importlib import import_module
from inspect import getmembers, isclass
from typing import TYPE_CHECKING

from loguru import logger

from noxus_sdk.plugins import BasePlugin, PluginManifest
from noxus_sdk.schemas import ValidationResult

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path
    from types import ModuleType


@contextmanager
def _prepend_sys_path(path: Path) -> Iterable[None]:
    """Temporarily prepend a path to sys.path."""
    inserted = False
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
        inserted = True
    try:
        yield
    finally:
        if inserted and path_str in sys.path:
            sys.path.remove(path_str)


def _iter_plugin_classes(module: ModuleType) -> list[type[BasePlugin]]:
    """Return BasePlugin subclasses defined in the given module."""
    plugin_classes: list[type[BasePlugin]] = []
    for _, obj in getmembers(module, isclass):
        if (
            issubclass(obj, BasePlugin)
            and obj is not BasePlugin
            and obj.__module__ == module.__name__
        ):
            plugin_classes.append(obj)
    return plugin_classes


def _is_valid_python_module_name(name: str) -> bool:
    """Check if a name is a valid Python module name"""
    if not name or not name.isidentifier():
        return False
    # Additional check for reserved keywords
    import keyword

    return not keyword.iskeyword(name)


def _find_plugin_package(path: Path) -> Path | None:
    """Find the actual plugin package directory (with __init__.py)"""
    # Convert to absolute path to ensure consistent behavior
    path = path.resolve()
    logger.debug(f"Finding plugin package in {path}")

    # First, scan for any subdirectory that contains __init__.py with a valid module name
    try:
        for item in path.iterdir():
            if (
                item.is_dir()
                and (item / "__init__.py").exists()
                and _is_valid_python_module_name(item.name)
                and item.name != "tests"
            ):
                # Found a valid Python package directory
                return item
    except (OSError, PermissionError):
        # Handle cases where we can't read the directory
        pass

    # Then, check the traditional structure where package has same name as parent
    nested_dir = path / path.name
    if (nested_dir / "__init__.py").exists() and _is_valid_python_module_name(
        path.name,
    ):
        return nested_dir

    # Finally, check if the path itself is a Python package with a valid name
    if (path / "__init__.py").exists() and _is_valid_python_module_name(path.name):
        return path

    return None


def _import_and_find_plugin(
    package_dir: Path,
    root_dir: Path,
) -> type[BasePlugin] | None:
    """Import package and find the BasePlugin subclass."""
    package_name = package_dir.name

    with _prepend_sys_path(root_dir):
        # Import the package using standard import semantics
        module = import_module(package_name)

        plugin_classes = _iter_plugin_classes(module)

        if not plugin_classes:
            return None
        if len(plugin_classes) == 1:
            return plugin_classes[0]
        if len(plugin_classes) > 1:
            class_names = ", ".join(cls.__name__ for cls in plugin_classes)
            raise ValueError(
                f"Multiple plugin classes found in __init__.py: {class_names}. Use only one plugin class.",
            )

        return None


def discover_and_load_plugin(
    path: Path,
) -> tuple[type[BasePlugin] | None, ValidationResult]:
    """Discover plugin class in a plugin package"""
    errors = []
    warnings = []

    plugin_package_dir = _find_plugin_package(path)
    logger.debug(f"Found plugin package in {plugin_package_dir}")

    if not plugin_package_dir:
        errors.append(
            f"No valid Python package found. Expected __init__.py in {path}, {path / path.name}, or any subdirectory",
        )
        return None, ValidationResult(valid=False, errors=errors, warnings=warnings)

    # Import the package and find BasePlugin subclasses
    plugin_class = _import_and_find_plugin(plugin_package_dir, path)
    if not plugin_class:
        errors.append(
            "No BasePlugin subclasses found in package. Define your plugin class that inherits from BasePlugin.",
        )
        return None, ValidationResult(valid=False, errors=errors, warnings=warnings)

    return plugin_class, ValidationResult(valid=True, errors=errors, warnings=warnings)


def validate_plugin(path: Path) -> tuple[PluginManifest | None, ValidationResult]:
    """Validate everything in the plugin to ensure it properly implements the plugin interface"""

    # First discover and load the plugin class
    plugin_class, discovery_result = discover_and_load_plugin(path)

    if discovery_result.errors or plugin_class is None:
        return None, discovery_result

    # Generate manifest from class
    manifest = None
    validation_errors = []

    try:
        manifest = plugin_class.get_manifest()
    except Exception as e:  # noqa: BLE001 - If the plugin manifest generation code fails, we want to return a validation result with the error. We dont control the code so need to catch all exceptions.
        validation_errors.append(f"Failed to generate manifest: {e}")

    # Combine results
    all_errors = (discovery_result.errors or []) + validation_errors
    all_warnings = discovery_result.warnings or []

    return manifest, ValidationResult(
        valid=True,
        errors=all_errors,
        warnings=all_warnings,
    )
