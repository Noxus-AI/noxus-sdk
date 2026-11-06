"""A V2 node that runs an existing V1 node.

Give a plugin's V1 node a V2 version without rewriting it: the V2 config
subclasses the V1 config and declares each V1 input connector as a bindable
field, and ``call`` runs the V1 node's ``call`` with that config. The V2
version then cannot drift from the V1 one.

    class ReadRecordV2Config(ReadRecordConfig):
        record_id: str = Parameter(bindable=True, display=ConfigText(label="Record ID"))

    class ReadRecordV2Outputs(NodeOutputs):
        subject: str

    class ReadRecordV2(V1BridgeNode[ReadRecordV2Config, ReadRecordV2Outputs]):
        node_name = "ReadRecordV2"
        v1_node_cls = ReadRecordNode

Everything the V2 class does not set itself (title, description, image,
integrations, timeout, ...) is copied from the V1 node.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, ClassVar, Generic

from noxus_sdk.nodes.base import BaseNode, BaseNodeV2, ConfigType, OutputsType

if TYPE_CHECKING:
    from noxus_sdk.plugins.context import RemoteExecutionContext

_INHERITED_FROM_V1 = (
    "title",
    "color",
    "description",
    "small_description",
    "category",
    "sub_category",
    "image",
    "documentation_url",
    "integrations",
    "max_timeout",
    "timeout_per_unit",
)


class V1BridgeNode(
    BaseNodeV2[ConfigType, OutputsType], Generic[ConfigType, OutputsType]
):
    parent_class = True

    v1_node_cls: ClassVar[type[BaseNode]]
    # V1 output names that cannot be a V2 output field name (`from`), mapped to
    # the field name the V2 output schema uses instead.
    output_renames: ClassVar[dict[str, str]] = {}

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        v1 = cls.__dict__.get("v1_node_cls")
        if v1 is None:
            return
        for attr in _INHERITED_FROM_V1:
            if attr not in cls.__dict__:
                setattr(cls, attr, getattr(v1, attr))  # noqa: lint-ignore - external SDK

    async def call(self, ctx: RemoteExecutionContext) -> dict:
        v1_inputs = {connector.name for connector in self.v1_node_cls.inputs}
        # Unbound optional inputs arrive as None; leave them out so the V1
        # call's own defaults apply.
        kwargs = {
            name: value
            for name, value in self.config
            if name in v1_inputs and value is not None
        }
        raw = self.v1_node_cls(self.config).call(ctx, **kwargs)
        if inspect.isawaitable(raw):
            raw = await raw
        outputs = dict(raw) if isinstance(raw, dict) else {}
        return {self.output_renames.get(k, k): v for k, v in outputs.items()}
