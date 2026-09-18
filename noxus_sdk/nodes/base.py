"""Base node classes for plugin development"""

from __future__ import annotations

from types import NoneType, UnionType
from typing import TYPE_CHECKING, Any, Generic, TypeVar, Union, get_args, get_origin

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
    # False keeps the node executable for flows that already use it while dropping
    # it from the node picker — how a superseded node is retired.
    visible = True
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
    def _definition_inputs(cls) -> list[NodeInput]:
        """The manifest input list. V1 nodes derive it from their connectors;
        V2 nodes override this to build it from their connector-free specs."""
        return [
            NodeInput(
                name=connector.name,
                label=connector.label,
                definition=connector.definition.__dict__,
                optional=connector.optional,
            )
            for connector in cls.inputs
        ]

    @classmethod
    def _definition_outputs(cls) -> list[NodeOutput]:
        return [
            NodeOutput(
                name=connector.name,
                label=connector.label,
                definition=connector.definition.__dict__,
                optional=connector.optional,
            )
            for connector in cls.outputs
        ]

    @classmethod
    def _definition_config(cls) -> dict:
        """The manifest config dict. V1 serializes the whole config class; V2
        overrides this to drop the bindable fields it routes to ``inputs``."""
        return cls.get_config_class().serialize()

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        """Convert node class to NodeDefinition for plugin manifest"""

        inputs = cls._definition_inputs()
        outputs = cls._definition_outputs()
        config_dict = cls._definition_config()

        # Serialize details
        details = [
            {
                "name": detail.name,
                "label": detail.label,
                "display": detail.display.model_dump(),
            }
            for detail in cls.details
        ]

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
            max_timeout=cls.max_timeout,
            visible=cls.visible,
        )

    async def call(
        self,
        ctx: RemoteExecutionContext,
        *args,
        **kwargs,
    ) -> dict[str, Any]:
        raise NotImplementedError


_PY_TO_DATA_TYPE = {
    "str": "str",
    "int": "number",
    "float": "number",
    "bool": "bool",
    "dict": "dict",
    "list": "list",
    "datetime": "datetime",
    "File": "File",
    "Image": "Image",
    "Audio": "Audio",
    "Chat": "Chat",
}


def _annotation_to_type(annotation: Any) -> tuple[str, bool]:
    """Map a Python annotation to a ``(data_type, is_list)`` pair. ``list[X]``
    becomes the element type flagged as a list; ``Optional[X]`` unwraps to X."""
    origin = get_origin(annotation)
    if origin is list:
        args = get_args(annotation)
        inner, _ = _annotation_to_type(args[0]) if args else ("str", False)
        return inner, True
    if origin is Union or origin is UnionType:
        for arg in get_args(annotation):
            if arg is not NoneType:
                return _annotation_to_type(arg)
        return "str", False
    name = getattr(annotation, "__name__", str(annotation))
    return _PY_TO_DATA_TYPE.get(name, name), False


class NodeOutputs(BaseModel):
    """Output schema for a V2 plugin node: **one class declaring every output**
    as a field. The field's annotation gives the output type (``list[X]`` → a
    list output); ``call`` returns a dict keyed by these field names.

        class MyOutputs(NodeOutputs):
            text: str
            tags: list[str]
    """

    @classmethod
    def to_outputs(cls) -> list[NodeOutput]:
        outputs: list[NodeOutput] = []
        for name, field in cls.model_fields.items():
            data_type, is_list = _annotation_to_type(field.annotation)
            outputs.append(
                NodeOutput(
                    name=name,
                    label=name,
                    definition={"data_type": data_type, "is_list": is_list},
                    optional=False,
                )
            )
        return outputs


OutputsType = TypeVar("OutputsType", bound=NodeOutputs)


class BaseNodeV2(BaseNode[ConfigType], Generic[ConfigType, OutputsType]):
    """Base for a **V2** plugin node — modelled on the platform's native V2
    nodes, which have **no connectors**. A V2 node is two schemas:

    - a **config schema** (its ``ConfigType``) whose fields are the node's
      settings; a field marked ``Parameter(bindable=True)`` is a bindable
      **input** — in the editor it takes a literal or a ``:var[...]`` reference
      to an upstream output;
    - an **output schema** (``NodeOutputs`` subclass) that declares every output
      field in one place.

    ``BaseNodeV2[MyConfig, MyOutputs]``. Every config value (bindable inputs
    included) arrives on ``self.config``; ``call(ctx)`` returns a dict keyed by
    the output field names.

    On the wire the bindable fields are split into the manifest's ``inputs`` and
    the rest into ``config`` — so a plugin can ship V1 and V2 nodes side by side
    and each surfaces in the matching editor's picker.
    """

    parent_class = True

    # V2 has no connectors; inputs come from bindable config fields, outputs
    # from the output schema.
    inputs: list = []  # type: ignore[assignment]
    outputs: list = []  # type: ignore[assignment]
    outputs_class: type[NodeOutputs] = NodeOutputs

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        if cls.__dict__.get("parent_class"):
            return
        args = get_args(cls.__orig_bases__[0])  # type: ignore
        if len(args) >= 2 and isinstance(args[1], type):
            cls.outputs_class = args[1]

    @classmethod
    def _bindable_fields(cls) -> dict[str, Any]:
        """Config fields the author marked ``bindable=True`` — the node's
        inputs, keyed by field name."""
        fields = {}
        for name, field in cls.get_config_class().model_fields.items():
            if (field.json_schema_extra or {}).get("bindable"):
                fields[name] = field
        return fields

    @classmethod
    def _definition_inputs(cls) -> list[NodeInput]:
        serialized = cls.get_config_class().serialize()
        inputs: list[NodeInput] = []
        for name, field in cls._bindable_fields().items():
            data_type, is_list = _annotation_to_type(field.annotation)
            entry = serialized.get(name, {})
            label = (entry.get("display") or {}).get("label") or name
            inputs.append(
                NodeInput(
                    name=name,
                    label=label,
                    definition={"data_type": data_type, "is_list": is_list},
                    optional=bool(entry.get("optional", False)),
                )
            )
        return inputs

    @classmethod
    def _definition_outputs(cls) -> list[NodeOutput]:
        return cls.outputs_class.to_outputs()

    @classmethod
    def _definition_config(cls) -> dict:
        # Bindable fields are routed to `inputs`; everything else is config.
        bindable = set(cls._bindable_fields())
        return {
            name: field
            for name, field in cls.get_config_class().serialize().items()
            if name not in bindable
        }
