"""The V1 SDK Node model must not crash when it deserializes a V2 workflow.

The proxy ``workflows_get`` / ``workflows_list`` tools fetch every workflow —
including V2 flows the genie builds — and parse them through the V1 ``Node``
model. V2 node schemas have NO connectors: their output specs are
``{name, label, data_type, is_list}`` with no ``type`` key (V1 connectors carry a
``ConnectorType`` under ``type``). Reading ``output["type"]`` unconditionally
raised ``KeyError('type')`` and surfaced to the agent as
``MCP server error: 'type'``.
"""

from noxus_sdk.workflows.workflow import Edge, Node, load_node_types

# A V2 node as the backend serializes it in /v1/nodes: empty connector inputs,
# outputs as bare NodeOutputV2 specs (data_type at top level, no "type").
_V2_NODE_DEF = {
    "type": "GenerateTextV2",
    "title": "Generate Text",
    "description": "Generate text with an LLM.",
    "small_description": None,
    "category": "ai_text",
    "integrations": [],
    "inputs": [],
    "outputs": [
        {"name": "output", "label": "Output", "data_type": "str", "is_list": False}
    ],
    "config": {},
    "is_available": True,
    "visible": True,
    "config_endpoint": None,
}


def test_v2_node_deserializes_without_type_key():
    load_node_types([_V2_NODE_DEF])

    node = Node(type="GenerateTextV2", id="11111111-1111-1111-1111-111111111111")

    assert [o.name for o in node.outputs] == ["output"]
    assert node.inputs == []


def test_v2_edge_with_source_target_maps_onto_from_to():
    # V2 flow edges: {id, source, target, source_handle, target_handle} — the V1
    # model needs from_id/to_id EdgePoints. Parsing must map, not crash.
    edge = Edge.model_validate(
        {
            "id": "e1",
            "source": "node-a",
            "target": "node-b",
            "source_handle": None,
            "target_handle": None,
        }
    )

    assert edge.from_id.node_id == "node-a"
    assert edge.to_id.node_id == "node-b"
