"""V2 plugin nodes are two schemas, not connectors.

A `BaseNodeV2` declares a **config schema** whose `bindable=True` fields are the
node's inputs, and a single **output schema** (`NodeOutputs`) listing every
output field. On the wire the bindable fields split into the manifest's
`inputs` and the rest into `config`, so the platform executor and a V1 plugin
node stay compatible.
"""

from __future__ import annotations

from typing import Any

from noxus_sdk.nodes.base import (
    BaseNode,
    BaseNodeV2,
    NodeConfiguration,
    NodeOutputs,
)
from noxus_sdk.nodes.connector import Connector
from noxus_sdk.nodes.types import DataType, TypeDefinition
from noxus_sdk.ncl import Parameter
from noxus_sdk.plugins import BasePlugin, PluginConfiguration
from noxus_sdk.plugins.types import PluginCategory


class _V2Config(NodeConfiguration):
    text: str = Parameter(default="", bindable=True)  # bindable input
    items: list = Parameter(default_factory=list, bindable=True)  # list input
    suffix: str = Parameter(default="!")  # plain config


class _V2Outputs(NodeOutputs):
    echo: str
    tags: list[str]


class _V2Node(BaseNodeV2[_V2Config, _V2Outputs]):
    node_name = "SpecV2Node"
    title = "Spec V2"
    description = "config schema + output schema, no connectors"

    async def call(self, ctx: Any) -> dict[str, Any]:
        return {"echo": f"{self.config.text}{self.config.suffix}", "tags": []}


class _V1Node(BaseNode[_V2Config]):
    node_name = "SpecV1Node"
    title = "Spec V1"
    description = "connectors"
    inputs = [
        Connector(
            name="text",
            label="text",
            definition=TypeDefinition(data_type=DataType.str),
        )
    ]
    outputs = [
        Connector(
            name="echo",
            label="echo",
            definition=TypeDefinition(data_type=DataType.str),
        )
    ]

    async def call(self, ctx: Any, text: str) -> dict[str, Any]:
        return {"echo": text}


def test_bindable_config_fields_become_inputs() -> None:
    d = _V2Node.get_definition()
    assert [(i.name, i.definition) for i in d.inputs] == [
        ("text", {"data_type": "str", "is_list": False}),
        ("items", {"data_type": "list", "is_list": False}),
    ]
    # Non-bindable fields stay in config; bindable ones are NOT duplicated there.
    assert set(d.config) == {"suffix"}


def test_output_schema_declares_every_field() -> None:
    d = _V2Node.get_definition()
    assert [(o.name, o.definition) for o in d.outputs] == [
        ("echo", {"data_type": "str", "is_list": False}),
        ("tags", {"data_type": "str", "is_list": True}),  # list[str] -> str + is_list
    ]


def test_data_type_serializes_to_plain_string() -> None:
    d = _V2Node.get_definition()
    assert d.inputs[0].definition["data_type"] == "str"
    assert isinstance(d.inputs[0].definition["data_type"], str)


def test_node_with_no_bindable_fields_has_empty_inputs() -> None:
    class _Cfg(NodeConfiguration):
        only_setting: str = Parameter(default="x")

    class _Out(NodeOutputs):
        result: str

    class _Bare(BaseNodeV2[_Cfg, _Out]):
        node_name = "BareV2"
        title = "Bare"
        description = "no inputs"

        async def call(self, ctx: Any) -> dict[str, Any]:
            return {"result": "ok"}

    d = _Bare.get_definition()
    assert d.inputs == []
    assert set(d.config) == {"only_setting"}
    assert [o.name for o in d.outputs] == ["result"]


def test_plugin_splits_v1_and_v2_nodes() -> None:
    class _Plugin(BasePlugin[PluginConfiguration]):
        name = "spec-plugin"
        display_name = "Spec Plugin"
        version = "0.0.1"
        description = "mixed"
        category = PluginCategory.OTHER
        author = "spec-test"

        def nodes(self) -> list[type[BaseNode]]:
            return [_V1Node, _V2Node]

    m = _Plugin.get_manifest()
    assert [n.type for n in m.nodes] == ["SpecV1Node"]
    assert [n.type for n in m.nodes_v2] == ["SpecV2Node"]


def test_visible_reaches_the_manifest() -> None:
    class _Hidden(BaseNode[_V2Config]):
        node_name = "HiddenV1"
        title = "Hidden"
        description = "retired, still runnable"
        outputs = [
            Connector(
                name="out",
                label="Out",
                definition=TypeDefinition(data_type=DataType.str),
            )
        ]
        visible = False

        async def call(self, ctx: Any) -> dict[str, Any]:
            return {"out": ""}

    assert _Hidden.get_definition().visible is False
    assert _V1Node.get_definition().visible is True
