"""Configuration validation and behavior rules."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class BaseRule(BaseModel):
    """Base class for configuration rules."""

    type: Literal["base_rule"]


class TypeSetBy(BaseRule):
    type: Literal["type_set_by"] = "type_set_by"  # type: ignore
    config_source: str


class KeysSetBy(BaseRule):
    type: Literal["keys_set_by"] = "keys_set_by"  # type: ignore
    config_source: str


class VisibleIfGroup(BaseRule):
    type: Literal["visible_if_group"] = "visible_if_group"  # type: ignore
    conds: list[VisibleIf | VisibleIfGroup]
    mode: Literal["and", "or"] = "and"


class VisibleIf(BaseRule):
    type: Literal["visible_if"] = "visible_if"  # type: ignore
    config_source: str
    value: Any


class DisabledIf(BaseRule):
    type: Literal["disabled_if"] = "disabled_if"  # type: ignore
    config_source: str
    value: Any


class SetsConnectorType(BaseRule):
    type: Literal["sets_connector_type"] = "sets_connector_type"  # type: ignore
    connector: str


class SetsConnectorKeys(BaseRule):
    type: Literal["sets_connector_keys"] = "sets_connector_keys"  # type: ignore
    connector: str


class SetsConnectorTypeAndKeys(BaseRule):
    type: Literal["sets_connector_type_and_keys"] = "sets_connector_type_and_keys"  # type: ignore
    connector: str


class SetsConnectorOrConfigVisibility(BaseRule):
    type: Literal["sets_connector_or_config_visibility"] = (
        "sets_connector_or_config_visibility"  # type: ignore
    )


class TypeAndKeysSetBy(BaseRule):
    type: Literal["type_and_keys_set_by"] = "type_and_keys_set_by"  # type: ignore
    config_source: str


# Union type for all rules
AnyRule = (
    TypeSetBy
    | VisibleIf
    | VisibleIfGroup
    | DisabledIf
    | SetsConnectorType
    | SetsConnectorKeys
    | SetsConnectorTypeAndKeys
    | TypeAndKeysSetBy
    | SetsConnectorOrConfigVisibility
)
