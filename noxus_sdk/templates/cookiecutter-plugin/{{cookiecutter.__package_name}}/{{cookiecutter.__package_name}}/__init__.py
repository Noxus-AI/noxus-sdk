"""{{ cookiecutter.description }}"""

from typing import Type

from noxus_sdk.plugins import BasePlugin, PluginConfiguration
from noxus_sdk.nodes import BaseNode

from {{ cookiecutter.__package_name }}.nodes import ExampleNode


class {{ cookiecutter.__package_name.replace('-', ' ').title().replace(' ', '') }}Configuration(PluginConfiguration):
    """Configuration for {{ cookiecutter.__package_name }}"""
    pass


class {{ cookiecutter.__package_name.replace('-', ' ').title().replace(' ', '') }}Plugin(BasePlugin[{{ cookiecutter.__package_name.replace('-', ' ').title().replace(' ', '') }}Configuration]):
    """{{ cookiecutter.description }}"""

    # Plugin metadata (auto-detected from package if not set)
    name = "{{ cookiecutter.__package_name }}"
    display_name = "{{ cookiecutter.plugin_name }}"
    version = "0.1.0"
    description = "{{ cookiecutter.description }}"
    author = "{{ cookiecutter.author_name }}"

    def nodes(self) -> list[Type[BaseNode]]:
        """Return the nodes provided by this plugin"""
        return [ExampleNode]
