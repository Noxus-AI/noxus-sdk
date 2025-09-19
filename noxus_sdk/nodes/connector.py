from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any, Generic, Literal, TypeGuard, TypeVar

from loguru import logger
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    TypeAdapter,
    model_validator,
)
from pydantic.dataclasses import dataclass

from noxus_sdk.ncl import AnyRule
from noxus_sdk.nodes.types import DataType, TypeDefinition
from noxus_sdk.utils.errors import UnexpectedError

ValueType = TypeVar("ValueType", bound=Any)


@dataclass
class DataContainer(Generic[ValueType]):
    definition: TypeDefinition
    value: ValueType

    @model_validator(mode="after")
    def validate(self) -> DataContainer:
        def convert_to_type(v: object, t: type) -> object:
            if isinstance(v, list):
                return [convert_to_type(i, t) for i in v]
            if not isinstance(v, t):
                v = t.model_validate(v)
            return v

        if self.definition.data_type == DataType.File:
            from noxus_sdk.plugins.schemas import File

            self.value = convert_to_type(self.value, File)
        elif self.definition.data_type == DataType.Image:
            from noxus_sdk.plugins.schemas import Image

            self.value = convert_to_type(self.value, Image)
        elif self.definition.data_type == DataType.Audio:
            from noxus_sdk.plugins.schemas import Audio

            self.value = convert_to_type(self.value, Audio)
        return self

    def dict(self) -> dict:
        return DataContainerTypeAdapter.dump_python(self)

    def copy(self) -> DataContainer:
        return DataContainer(definition=self.definition, value=deepcopy(self.value))

    def is_list(self) -> bool:
        return (
            isinstance(self.value, list) and self.definition.data_type != DataType.list
        )

    def dim(self) -> int:
        return 1 if not self.is_list() else len(self.value)

    def flatten(self) -> DataContainer:
        _new = self.copy()
        _old_value = _new.value
        if isinstance(_old_value, list) and len(_old_value) == 1:
            _new.value = _old_value[0]
        return _new

    def expand(self, new_size: int) -> DataContainer:
        _new = self.copy()
        _old_value = _new.value
        if _new.is_list():
            if _new.dim() != 1:
                from noxus_sdk.utils.errors import UnexpectedError

                raise UnexpectedError("Can't expand a list with more than 1 element")
            _old_value = _new.value[0]

        new_value = [_old_value] * new_size
        _new.value = new_value
        return _new

    def explode(self) -> list[DataContainer]:
        """Turn N length data container into N x 1 length data containers"""
        if not self.is_list():
            return [self]

        out = []
        for i in range(self.dim()):
            it_value = self.value[i]
            out.append(DataContainer(definition=self.definition, value=it_value))

        return out


DataContainerTypeAdapter = TypeAdapter(DataContainer)


# ========= Params ==========


class ConnectorParams(BaseModel):
    definition: TypeDefinition = Field(
        validation_alias=AliasChoices("definition", "active"),
    )
    name: str = ""
    optional: bool = False


class VariableConnectorParams(ConnectorParams):
    keys: list[str]
    allow_empty: bool = False


class VariableTypeConnectorParams(ConnectorParams):
    pass


class VariableTypeSizeConnectorParams(ConnectorParams):
    keys: list[str]
    type_definitions: dict[str, TypeDefinition]


PossibleConnectorParams = (
    VariableTypeSizeConnectorParams
    | VariableConnectorParams
    | VariableTypeConnectorParams
    | ConnectorParams
)


class ConnectorConfiguration(BaseModel):
    inputs: list[PossibleConnectorParams] = []
    outputs: list[PossibleConnectorParams] = []


# ========= Connectors ==========


@dataclass
class Connector:
    name: str
    label: str
    definition: TypeDefinition
    type: Literal["connector"] = "connector"
    propagates_list: bool = True
    optional: bool = False
    rules: list[AnyRule] = Field(default=[])
    visible: bool = True
    # NOTE: exclude from openapi schema generation
    processors: list[Callable[[Any, bool], Any]] = Field(default=[], exclude=True)

    def update(self, value: PossibleConnectorParams) -> None:
        self.optional = value.optional


@dataclass
class FlowInputConnector(Connector):
    name: str
    label: str
    definition: TypeDefinition
    type: Literal["input"] = "input"  # type: ignore


@dataclass
class FlowOutputConnector(Connector):
    name: str
    label: str
    definition: TypeDefinition
    type: Literal["output"] = "output"  # type: ignore


@dataclass
class VariableConnector(Connector):
    type: Literal["variable_connector"] = "variable_connector"  # type: ignore
    keys: list[str] = Field(default=[])
    manual: bool = True
    allow_empty: bool = False

    def update(self, value: VariableConnectorParams | dict) -> None:  # type: ignore
        if isinstance(value, dict):
            value = VariableConnectorParams(**value)
        self.keys = value.keys
        super().update(value)


@dataclass
class VariableTypeConnector(Connector):
    type: Literal["variable_type_connector"] = "variable_type_connector"  # type: ignore
    choices: list[TypeDefinition] = Field(default=[])

    def update(self, value: VariableTypeConnectorParams | dict) -> None:  # type: ignore
        if isinstance(value, dict):
            value = VariableTypeConnectorParams(**value)

        _data_types = [c.data_type for c in self.choices]
        if value.definition.data_type in _data_types:
            self.definition = value.definition
        else:
            msg = "Wrong connector type provided in connector configuration"
            logger.warning(msg)
            raise UnexpectedError(
                msg,
            )
        super().update(value)


@dataclass
class VariableTypeSizeConnector(Connector):
    type: Literal["variable_type_size_connector"] = "variable_type_size_connector"  # type: ignore
    type_definitions: dict[str, TypeDefinition] = Field(default={})
    choices: list[TypeDefinition] = Field(default=[])
    keys: list[str] = Field(default=[])
    manual: bool = False

    def update(self, value: VariableTypeSizeConnectorParams | dict) -> None:  # type: ignore
        if isinstance(value, dict):
            value = VariableTypeSizeConnectorParams(**value)

        super().update(value)
        if value.keys:
            self.keys = value.keys
        if value.type_definitions:
            _data_types = [c.data_type for c in self.choices]
            for k, v in value.type_definitions.items():
                if v.data_type in _data_types and k in self.keys:
                    self.type_definitions[k] = v
                else:
                    msg = "Wrong connector type or connector key provided in connector configuration"
                    logger.warning(msg)
                    raise UnexpectedError(msg)


def is_variable_size(conn: Any) -> TypeGuard[VariableSizeConnectors]:  # noqa: ANN401 - Use of any is acceptable here
    return isinstance(conn, (VariableConnector, VariableTypeSizeConnector))


def is_flow_input(conn: Any) -> bool:  # noqa: ANN401 - Use of any is acceptable here
    return isinstance(conn, FlowInputConnector)


def is_flow_output(conn: Any) -> bool:  # noqa: ANN401 - Use of any is acceptable here
    return isinstance(conn, FlowOutputConnector)


@dataclass
class VariableTypeFlowInputConnector(FlowInputConnector, VariableTypeConnector):
    type: Literal["variable_type_input"] = "variable_type_input"  # type: ignore
    configured_by: str | None = None


@dataclass
class VariableTypeFlowOutputConnector(FlowOutputConnector, VariableTypeConnector):
    type: Literal["variable_type_output"] = "variable_type_output"  # type: ignore
    configured_by: str | None = None


VariableSizeConnectors = VariableConnector | VariableTypeSizeConnector
AnyConnector = (
    Connector
    | VariableConnector
    | VariableTypeConnector
    | VariableTypeSizeConnector
    | FlowInputConnector
    | FlowOutputConnector
    | VariableTypeFlowInputConnector
    | VariableTypeFlowOutputConnector
)


# ========= Utilities ==========


@dataclass
class ConnectorId:
    name: str
    node_id: str


@dataclass
class RelativeAddress:
    connector_name: str
    key: str | None = None
    _cache: dict = Field(default_factory=dict, init=False, repr=False, exclude=True)

    def __post_init__(self) -> None:
        self._cache["resolve"] = (
            f"{self.connector_name}::{self.key}"
            if self.key
            else f"{self.connector_name}"
        )
        self._cache["hash"] = hash(self._cache["resolve"])

    def __hash__(self) -> int:
        return self._cache["hash"]

    def __eq__(self, other: object) -> bool:
        return self._cache["resolve"] == other._cache["resolve"]

    def resolve(self) -> str:
        return self._cache["resolve"]


@dataclass
class ConnectorAddress:
    connector_name: str
    node_id: str
    key: str | None = None
    optional: bool = False

    def __hash__(self) -> int:
        return hash(self.resolve())

    def __eq__(self, other: object) -> bool:
        return self.resolve() == other.resolve()

    def resolve(self) -> str:
        if self.key:
            return f"{self.node_id}::{self.connector_name}::{self.key}"
        return f"{self.node_id}::{self.connector_name}"

    @classmethod
    def from_relative_address(
        cls,
        node_id: str,
        relative_address: RelativeAddress,
    ) -> ConnectorAddress:
        return cls(
            node_id=node_id,
            connector_name=relative_address.connector_name,
            key=relative_address.key,
        )

    def to_relative_address(self) -> RelativeAddress:
        return RelativeAddress(connector_name=self.connector_name, key=self.key)
