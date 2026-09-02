"""Shared export/import wire helpers.

Knowledge bases, workflows and agents all export and import the same way, so the
format literals and the request shaping live here rather than three times over.
"""

from __future__ import annotations

from typing import Any, Literal

# "auto" exports the legacy base64 bundle (back-compat with existing pipelines)
# and, on import, detects the format from the payload. "v4" is plaintext
# multi-doc YAML (.nx); "v3" is base64 explicitly.
ExportFormat = Literal["auto", "v3", "v4"]

ImportMode = Literal["clone", "version", "replace"]


def import_body(definition: str | bytes, version: ExportFormat) -> dict[str, Any]:
    """Bundles come back from ``export`` as bytes; accept them without ceremony."""
    return {
        "definition": definition.decode()
        if isinstance(definition, bytes)
        else definition,
        "version": version,
    }


def import_params(mode: ImportMode, activate: bool, dry_run: bool) -> dict[str, Any]:
    return {"mode": mode, "activate": activate, "dry_run": dry_run}
