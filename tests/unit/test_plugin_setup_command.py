"""Manifest carries the plugin's optional install-time setup command."""

from __future__ import annotations

from typing import ClassVar

from noxus_sdk.integrations.base import BaseCredentials, BaseIntegration
from noxus_sdk.ncl import Parameter
from noxus_sdk.plugins import BasePlugin, PluginConfiguration


class _Creds(BaseCredentials):
    type: ClassVar[str] = "setup_cmd_test"
    api_key: str = Parameter(default="")

    def is_ready(self) -> bool:
        return bool(self.api_key)


class _Integration(BaseIntegration[_Creds]):
    display_name = "Setup Cmd Test"
    image = ""


class _Config(PluginConfiguration):
    pass


class _PluginWithSetup(BasePlugin[_Config]):
    name = "with-setup"
    display_name = "With Setup"
    version = "0.0.1"
    description = "d"
    author = "t"
    setup_command = "apt-get install -y -qq jq"

    def integrations(self) -> list[type[BaseIntegration]]:
        return [_Integration]


class _PluginWithoutSetup(BasePlugin[_Config]):
    name = "without-setup"
    display_name = "Without Setup"
    version = "0.0.1"
    description = "d"
    author = "t"

    def integrations(self) -> list[type[BaseIntegration]]:
        return [_Integration]


def test_setup_command_round_trips_through_manifest() -> None:
    manifest = _PluginWithSetup.get_manifest()
    assert manifest.setup_command == "apt-get install -y -qq jq"
    dumped = manifest.model_dump(mode="json")
    assert dumped["setup_command"] == "apt-get install -y -qq jq"


def test_setup_command_defaults_to_none() -> None:
    assert _PluginWithoutSetup.get_manifest().setup_command is None
