from noxus_sdk.ncl import ConfigSelect, Parameter
from noxus_sdk.nodes import (
    BaseNode,
    Connector,
    DataType,
    NodeCategory,
    NodeConfiguration,
    TypeDefinition,
)
from noxus_sdk.plugins import RemoteExecutionContext


class ExampleNodeConfiguration(NodeConfiguration):
    """Configuration for the Example node that sums two numbers."""

    operation: str = Parameter(default="", display=ConfigSelect(label="Operation", values=["Add", "Subtract", "Multiply", "Divide"]))


class ExampleNode(BaseNode[ExampleNodeConfiguration]):
    """{{ cookiecutter.description }}"""

    inputs = [
        Connector(name="a", label="A", definition=TypeDefinition(data_type=DataType.str)),
        Connector(name="b", label="B", definition=TypeDefinition(data_type=DataType.str)),
    ]
    outputs = [
        Connector(name="result", label="Sum", definition=TypeDefinition(data_type=DataType.str)),
    ]

    node_name = "ExampleNode"
    title = "Example node"
    description = "An example node that performs an operation on two numbers."
    category = NodeCategory.OTHER

    async def call(self, ctx: RemoteExecutionContext, a: str, b: str):
        """Return the sum of configuration values a and b as a string."""
        a_int, b_int = int(a), int(b)

        if self.config.operation == "Add":
            total = a_int + b_int
        elif self.config.operation == "Subtract":
            total = a_int - b_int
        elif self.config.operation == "Multiply":
            total = a_int * b_int
        elif self.config.operation == "Divide":
            total = a_int / b_int
        else:
            total = 0

        return {"result": str(total)}
