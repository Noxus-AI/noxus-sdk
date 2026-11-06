"""``V1BridgeNode`` gives a V1 plugin node a V2 version that runs the V1 code.

The platform's V2 plugin node sends one merged config (settings plus bound
inputs) and no connector inputs; the bridge hands the V1 inputs to the V1
``call`` as kwargs and the rest stays on the config the V1 node reads.
"""

from __future__ import annotations

import asyncio
from typing import Any

from noxus_sdk.ncl import ConfigText, Parameter
from noxus_sdk.nodes import V1BridgeNode
from noxus_sdk.nodes.base import BaseNode, NodeConfiguration, NodeOutputs
from noxus_sdk.nodes.connector import Connector
from noxus_sdk.nodes.schemas import TimeoutPerUnit
from noxus_sdk.nodes.types import DataType, NodeCategory, TypeDefinition
from noxus_sdk.plugins import BasePlugin, PluginConfiguration
from noxus_sdk.plugins.context import RemoteExecutionContext
from noxus_sdk.plugins.dispatch import PluginDispatcher
from noxus_sdk.plugins.types import PluginCategory


class GreetConfig(NodeConfiguration):
    greeting: str = Parameter(default="Hello")
    max_people: int = Parameter(default=3)


class GreetNode(BaseNode[GreetConfig]):
    node_name = "GreetNode"
    title = "Greet"
    description = "Greets someone."
    image = "https://example.com/greet.png"
    category = NodeCategory.INTEGRATIONS
    integrations = {"crm": []}
    max_timeout = 600
    timeout_per_unit = TimeoutPerUnit(field="max_people", seconds=5.0)
    inputs = [
        Connector(
            name="name", label="Name", definition=TypeDefinition(data_type=DataType.str)
        ),
        Connector(
            name="title",
            label="Title",
            definition=TypeDefinition(data_type=DataType.str),
            optional=True,
        ),
    ]
    outputs = [
        Connector(
            name="from",
            label="From",
            definition=TypeDefinition(data_type=DataType.str),
        ),
        Connector(
            name="text",
            label="Text",
            definition=TypeDefinition(data_type=DataType.str),
        ),
    ]

    async def call(
        self, ctx: RemoteExecutionContext, name: str, title: str = "friend"
    ) -> dict[str, Any]:
        return {"from": "crm", "text": f"{self.config.greeting}, {title} {name}"}


class GreetV2Config(GreetConfig):
    name: str = Parameter(bindable=True, display=ConfigText(label="Name"))
    title: str | None = Parameter(
        default=None, bindable=True, display=ConfigText(label="Title")
    )


class GreetV2Outputs(NodeOutputs):
    sender: str
    text: str


class GreetV2(V1BridgeNode[GreetV2Config, GreetV2Outputs]):
    node_name = "GreetV2"
    v1_node_cls = GreetNode
    output_renames = {"from": "sender"}


class _Plugin(BasePlugin[PluginConfiguration]):
    name = "bridge-plugin"
    display_name = "Bridge"
    version = "0.0.1"
    description = "a V1 node and its V2 bridge"
    category = PluginCategory.OTHER
    author = "test"

    def nodes(self) -> list[type[BaseNode]]:
        return [GreetNode, GreetV2]


def _execute(config: dict) -> dict:
    dispatcher = PluginDispatcher(_Plugin, "bridge-plugin")
    result = asyncio.run(
        dispatcher.execute_node("GreetV2", RemoteExecutionContext(), {}, config)
    )
    return result.outputs


def test_runs_the_v1_call_with_inputs_from_the_config() -> None:
    outputs = _execute({"greeting": "Olá", "name": "Maria", "title": "Dr."})
    assert outputs == {"sender": "crm", "text": "Olá, Dr. Maria"}


def test_unbound_optional_input_falls_back_to_the_v1_default() -> None:
    assert _execute({"name": "Maria"})["text"] == "Hello, friend Maria"


def test_v2_manifest_takes_inputs_from_v1_connectors_and_metadata_from_v1() -> None:
    manifest = _Plugin.get_manifest()
    assert [n.type for n in manifest.nodes] == ["GreetNode"]
    [v2] = manifest.nodes_v2
    assert [(i.name, i.optional) for i in v2.inputs] == [
        ("name", False),
        ("title", True),
    ]
    assert set(v2.config) == {"greeting", "max_people"}
    assert [o.name for o in v2.outputs] == ["sender", "text"]
    assert v2.title == "Greet"
    assert v2.image == "https://example.com/greet.png"
    assert v2.integrations == ["crm"]
    assert v2.max_timeout == 600
    assert v2.timeout_per_unit == TimeoutPerUnit(field="max_people", seconds=5.0)
    assert manifest.nodes[0].timeout_per_unit == v2.timeout_per_unit
