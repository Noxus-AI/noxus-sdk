"""Node-related data models and schemas"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from noxus_sdk.nodes.connector import AnyConnector


class SubflowConfig(BaseModel):
    workflow_id: str
    workflow_name: str
    workflow_nodes: list[str]


class NodeInput(BaseModel):
    name: str
    label: str
    definition: dict
    optional: bool


class NodeOutput(BaseModel):
    name: str
    label: str
    definition: dict
    optional: bool


class NodeDefinition(BaseModel):
    inputs: list[NodeInput]
    outputs: list[NodeOutput]
    config: dict
    type: str
    color: str
    image: str | None = None
    title: str | None = None
    description: str | None = None
    small_description: str | None = None
    documentation_url: str | None = None
    category: str | None = None
    sub_category: str | None = None
    example: str | None = None
    integrations: list[str] | None = None
    providers: list[str] | None = None
    knowledge_base_support: list[str] | None = None
    config_endpoint: str | None = None
    subflow_config: SubflowConfig | None = None
    is_valid: bool | None = None
    visible: bool = True
    is_available: bool = True
    show_to_user: bool = True
    paywalled: bool = False


class ConfigResponse(BaseModel):
    config: dict[str, dict]
    inputs: list[AnyConnector]
    outputs: list[AnyConnector]
    title: str | None = None
    ready: bool = False
    config_values: dict[str, Any] = {}

    def find_input(self, name: str) -> AnyConnector | None:
        for i in self.inputs:
            if i.name == name:
                return i
        return None


class ExecutionResponse(BaseModel):
    success: bool
    outputs: dict[str, Any]
