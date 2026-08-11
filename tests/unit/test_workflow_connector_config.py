import json

from noxus_sdk.workflows.workflow import (
    NODE_TYPES,
    Node,
    load_node_catalog,
    set_node_types,
)


_INVOKE_SUBFLOW_NODE_DEF = {
    "type": "InvokeSubflowNode",
    "title": "Invoke Subflow",
    "description": "Invoke another workflow.",
    "integrations": [],
    "inputs": [],
    "outputs": [
        {
            "name": "outputs",
            "label": "Output",
            "type": "variable_type_size_connector",
            "definition": {"data_type": "str", "is_list": False},
            "choices": [{"data_type": "str", "is_list": False}],
            "type_definitions": {},
            "keys": [],
        }
    ],
    "config": {},
    "is_available": True,
    "visible": True,
    "config_endpoint": None,
}


def test_dynamic_connector_keys_do_not_leak_through_cached_catalog():
    raw_catalog = json.dumps([_INVOKE_SUBFLOW_NODE_DEF]).encode()
    _, parsed_catalog = load_node_catalog(raw_catalog)
    set_node_types(parsed_catalog)

    first = Node(type="InvokeSubflowNode", id="first")
    first.output("outputs", "result", type_definition="str")

    # A new Client reuses the parsed catalog object for an identical response.
    _, cached_catalog = load_node_catalog(raw_catalog)
    set_node_types(cached_catalog)
    second = Node(type="InvokeSubflowNode", id="second")
    second.output("outputs", "output1", type_definition="str")

    assert first.connector_config["outputs"][0]["keys"] == ["result"]
    assert second.connector_config["outputs"][0]["keys"] == ["output1"]
    assert NODE_TYPES["InvokeSubflowNode"].outputs[0]["keys"] == []
