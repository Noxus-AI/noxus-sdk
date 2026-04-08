"""Base node classes for plugin development"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar, get_args

from pydantic import BaseModel

from noxus_sdk.ncl import serialize_config
from noxus_sdk.nodes.schemas import (
    ConfigResponse,
    NodeDefinition,
    NodeInput,
    NodeOutput,
)
from noxus_sdk.nodes.types import NodeCategory

if TYPE_CHECKING:
    from noxus_sdk.nodes.connector import Connector, NodeDetail, AnyConnector
    from noxus_sdk.plugins.context import RemoteExecutionContext
else:
    AnyConnector = object


class NodeConfiguration(BaseModel):
    """Base configuration class for nodes"""

    @classmethod
    def serialize(cls) -> dict:
        return serialize_config(cls)


ConfigType = TypeVar("ConfigType", bound=NodeConfiguration)


class BaseNode(Generic[ConfigType]):
    inputs: list[Connector]  # Will be set to an empty list if not set
    outputs: list[Connector]  # Connectable outputs only
    details: list[NodeDetail]  # Display-only details (not connectable)
    node_name = "BaseNode"
    title = "Base Node"
    color = "#D5D5DE"
    description = "No description."
    small_description: str | None = None
    category = NodeCategory.OTHER
    sub_category: str | None = None
    image: str | None = None
    documentation_url: str | None = None
    example: str | None = None
    gathers_list = False
    integrations: dict[str, list[str]]  # Will be set to an empty dict if not set

    config_class: type[ConfigType]
    # how much each node can take at maximum
    max_timeout = 240.0
    parent_class: bool = False

    def __init_subclass__(cls) -> None:
        cls.config_class = get_args(cls.__orig_bases__[0])[0]  # type: ignore
        # Set default values
        if not hasattr(cls, "integrations"):
            cls.integrations = {}

        if not hasattr(cls, "inputs"):
            cls.inputs = []

        if not hasattr(cls, "outputs"):
            cls.outputs = []

        if not hasattr(cls, "details"):
            cls.details = []

        # Validate no key name conflicts between outputs and details
        output_names = {conn.name for conn in cls.outputs}
        detail_names = {detail.name for detail in cls.details}
        conflicts = output_names & detail_names
        if conflicts:
            raise ValueError(
                f"Node {cls.__name__} has conflicting names between outputs and details: {', '.join(conflicts)}. "
                "Output connector names and detail names must be unique."
            )

        return super().__init_subclass__()

    def __init__(self, node_config: ConfigType) -> None:
        self.config = node_config

    @classmethod
    async def get_config(
        cls,
        ctx: RemoteExecutionContext,  # noqa: ARG003 - Here for documentation purposes
        config_response: ConfigResponse,
        *,
        skip_cache: bool = False,  # noqa: ARG003 - Here for documentation purposes
    ) -> ConfigResponse:
        return config_response

    @classmethod
    def get_config_class(cls) -> type[ConfigType]:
        return cls.config_class

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        """Convert node class to NodeDefinition for plugin manifest"""

        # Convert connectors to inputs/outputs
        inputs = []
        for connector in cls.inputs:
            inputs.append(
                NodeInput(
                    name=connector.name,
                    label=connector.label,
                    definition=connector.definition.__dict__,
                    optional=connector.optional,
                ),
            )

        outputs = []
        for connector in cls.outputs:
            outputs.append(
                NodeOutput(
                    name=connector.name,
                    label=connector.label,
                    definition=connector.definition.__dict__,
                    optional=connector.optional,
                ),
            )

        # Serialize details
        details = [
            {
                "name": detail.name,
                "label": detail.label,
                "display": detail.display.model_dump(),
            }
            for detail in cls.details
        ]

        config = cls.get_config_class()
        config_dict = config.serialize()

        return NodeDefinition(
            inputs=inputs,
            outputs=outputs,
            details=details,
            config=config_dict,
            type=cls.node_name,
            color=cls.color,
            image=cls.image,
            title=cls.title,
            description=cls.description,
            small_description=cls.small_description,
            documentation_url=cls.documentation_url,
            category=cls.category.value
            if hasattr(cls.category, "value")
            else str(cls.category),
            sub_category=cls.sub_category,
            example=cls.example,
            integrations=list(cls.integrations.keys()),
            config_endpoint=f"/nodes/{cls.node_name}/config",
        )

    async def call(
        self,
        ctx: RemoteExecutionContext,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        raise NotImplementedError
