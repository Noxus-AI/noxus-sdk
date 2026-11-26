from __future__ import annotations

import json
import uuid
from pathlib import Path

from noxus_sdk.cli.commands.plugin import generate_manifest
from noxus_sdk.plugins.validate import validate_plugin

_PLUGIN_SOURCE = """
from typing import ClassVar

from noxus_sdk.integrations.base import BaseCredentials, BaseIntegration
from noxus_sdk.ncl import Parameter
from noxus_sdk.plugins import BasePlugin, PluginConfiguration


class _Creds(BaseCredentials):
    type: ClassVar[str] = "{name}_creds"
    api_key: str = Parameter(default="")

    def is_ready(self) -> bool:
        return bool(self.api_key)


class _Integration(BaseIntegration[_Creds]):
    display_name = "Manifest JSON Test"
    image = ""


class _Config(PluginConfiguration):
    pass


class ManifestJsonPlugin(BasePlugin[_Config]):
    name = "{name}"
    display_name = "Manifest JSON"
    version = "0.0.1"
    description = "{description}"
    author = "t"
{class_settings}
    def integrations(self) -> list[type[BaseIntegration]]:
        return [_Integration]
"""


def _plugin_dir(
    tmp_path: Path, *, description: str = "d", class_settings: str = ""
) -> Path:
    name = f"manifest_json_{uuid.uuid4().hex[:8]}"
    package = tmp_path / name
    package.mkdir()
    (package / "__init__.py").write_text(
        _PLUGIN_SOURCE.format(
            name=name, description=description, class_settings=class_settings
        )
    )
    return tmp_path


def _write_manifest_json(path: Path, **settings: str | int) -> None:
    manifest, result = validate_plugin(path)
    assert manifest is not None, result.errors
    (path / "manifest.json").write_text(
        json.dumps({**manifest.model_dump(mode="json"), **settings})
    )


def test_manifest_json_wins_over_the_deprecated_class_attributes(
    tmp_path: Path,
) -> None:
    path = _plugin_dir(
        tmp_path,
        class_settings='    execution_slots = 4\n    setup_command = "echo class"\n',
    )
    _write_manifest_json(path, execution_slots=2, setup_command="echo manifest")

    manifest, result = validate_plugin(path)

    assert manifest is not None, result.errors
    assert (manifest.execution_slots, manifest.setup_command) == (2, "echo manifest")
    assert result.warnings == [
        "ManifestJsonPlugin.execution_slots is deprecated and ignored: set "
        '"execution_slots": 4 in manifest.json instead.',
        "ManifestJsonPlugin.setup_command is deprecated and ignored: set "
        '"setup_command" in manifest.json instead.',
    ]


def test_stale_manifest_json_is_reported(tmp_path: Path) -> None:
    path = _plugin_dir(tmp_path)
    _write_manifest_json(path, description="an older description")

    _, result = validate_plugin(path)

    assert result.warnings == [
        "manifest.json is out of date with the plugin code: "
        "run `noxus plugin generate-manifest`."
    ]


def test_generate_manifest_keeps_manifest_json_sandbox_settings(
    tmp_path: Path,
) -> None:
    path = _plugin_dir(tmp_path, description="new")
    _write_manifest_json(
        path, description="old", execution_slots=3, setup_command="echo hi"
    )

    generate_manifest(path=str(path))

    written = json.loads((path / "manifest.json").read_text())
    assert (
        written["description"],
        written["execution_slots"],
        written["setup_command"],
    ) == ("new", 3, "echo hi")


def test_without_manifest_json_the_defaults_apply(tmp_path: Path) -> None:
    path = _plugin_dir(tmp_path, class_settings="    execution_slots = 4\n")

    manifest, result = validate_plugin(path)

    assert manifest is not None, result.errors
    assert (manifest.execution_slots, manifest.setup_command) == (1, None)
    assert len(result.warnings) == 1


def test_an_explicit_default_on_the_class_is_still_reported(tmp_path: Path) -> None:
    path = _plugin_dir(
        tmp_path,
        class_settings="    execution_slots = 1\n    setup_command = None\n",
    )

    _, result = validate_plugin(path)

    assert result.warnings == [
        "ManifestJsonPlugin.execution_slots is deprecated and ignored: set "
        '"execution_slots": 1 in manifest.json instead.',
        "ManifestJsonPlugin.setup_command is deprecated and ignored: set "
        '"setup_command" in manifest.json instead.',
    ]


def test_generate_manifest_rewrites_a_manifest_json_from_an_older_schema(
    tmp_path: Path,
) -> None:
    path = _plugin_dir(tmp_path)
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "name": "old",
                "nodes": [{"type": "OldNode"}],
                "execution_slots": 3,
                "setup_command": "echo hi",
            }
        )
    )

    manifest, result = validate_plugin(path)
    assert result.errors == []
    assert manifest is not None
    assert (manifest.execution_slots, manifest.setup_command) == (3, "echo hi")
    assert result.warnings == [
        "manifest.json is out of date with the plugin code: "
        "run `noxus plugin generate-manifest`."
    ]

    generate_manifest(path=str(path))

    written = json.loads((path / "manifest.json").read_text())
    assert (written["nodes"], written["execution_slots"]) == ([], 3)
