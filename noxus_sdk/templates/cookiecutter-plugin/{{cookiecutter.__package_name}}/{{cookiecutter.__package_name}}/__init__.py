"""{{ cookiecutter.description }}"""

from typing import Type

from noxus_sdk.plugins import BasePlugin, PluginConfiguration
from noxus_sdk.nodes import BaseNode
{% if cookiecutter.include_integration == 'yes' %}from noxus_sdk.integrations import BaseIntegration
{% endif %}
from {{ cookiecutter.__package_name }}.nodes import ExampleNode
{% if cookiecutter.include_integration == 'yes' %}from {{ cookiecutter.__package_name }}.integration import {{ cookiecutter.__package_name.replace('-', ' ').title().replace(' ', '') }}Integration
{% endif %}

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
{% if cookiecutter.include_integration == 'yes' %}
    def integrations(self) -> list[Type[BaseIntegration]]:
        """Return the integrations provided by this plugin"""
        return [{{ cookiecutter.__package_name.replace('-', ' ').title().replace(' ', '') }}Integration]
{% endif %}
