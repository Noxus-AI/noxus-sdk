"""Connector inputs must reach node code as real objects, not raw JSON.

Inputs cross the transport as plain JSON, so a File arrives as a dict and a
datetime as an ISO string. `_coerce_inputs` rebuilds them — without it, node
authors would silently receive strings/dicts where they declared rich types.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from noxus_sdk.files import File
from noxus_sdk.nodes.base import BaseNode, NodeConfiguration
from noxus_sdk.nodes.connector import Connector
from noxus_sdk.nodes.types import DataType, TypeDefinition
from noxus_sdk.plugins.dispatch import _coerce_inputs


def _c(name: str, data_type: DataType, *, is_list: bool = False) -> Connector:
    return Connector(
        name=name,
        label=name,
        definition=TypeDefinition(data_type=data_type, is_list=is_list),
    )


class Cfg(NodeConfiguration):
    pass


class Node(BaseNode[Cfg]):
    node_name = "CoercionNode"
    inputs = [
        _c("when", DataType.datetime),
        _c("whens", DataType.datetime, is_list=True),
        _c("doc", DataType.File),
        _c("docs", DataType.File, is_list=True),
        _c("text", DataType.str),
        _c("n", DataType.number),
        _c("flag", DataType.bool),
    ]
    outputs = []

    async def call(self, ctx, **kwargs) -> dict[str, Any]:
        return kwargs


def _node() -> Node:
    return Node(Cfg())


def test_datetime_input_is_parsed_from_iso():
    out = _coerce_inputs(_node(), {"when": "2026-07-12T09:30:00+00:00"})
    assert isinstance(out["when"], datetime)
    assert out["when"].year == 2026 and out["when"].day == 12


def test_datetime_list_is_parsed_elementwise():
    out = _coerce_inputs(
        _node(), {"whens": ["2026-01-02T00:00:00", "2026-03-04T00:00:00"]}
    )
    assert all(isinstance(v, datetime) for v in out["whens"])
    assert [v.month for v in out["whens"]] == [1, 3]


def test_unparseable_datetime_passes_through_rather_than_exploding():
    # One malformed field shouldn't fail the whole node execution.
    out = _coerce_inputs(_node(), {"when": "not-a-timestamp"})
    assert out["when"] == "not-a-timestamp"


def test_file_input_is_rebuilt_into_a_model():
    out = _coerce_inputs(
        _node(), {"doc": {"id": "f1", "name": "a.txt", "uri": "spot://f1"}}
    )
    assert isinstance(out["doc"], File)
    assert out["doc"].name == "a.txt"


def test_file_list_is_rebuilt_elementwise():
    out = _coerce_inputs(
        _node(),
        {
            "docs": [
                {"id": "f1", "name": "a.txt", "uri": "spot://f1"},
                {"id": "f2", "name": "b.txt", "uri": "spot://f2"},
            ]
        },
    )
    assert all(isinstance(v, File) for v in out["docs"])
    assert [v.name for v in out["docs"]] == ["a.txt", "b.txt"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("text", "hello"), ("n", 42), ("flag", True)],
)
def test_scalar_inputs_pass_through_untouched(field, value):
    assert _coerce_inputs(_node(), {field: value})[field] == value


def test_inputs_without_a_connector_are_forwarded_verbatim():
    assert _coerce_inputs(_node(), {"extra": {"raw": 1}})["extra"] == {"raw": 1}


def test_datetime_number_and_bool_are_declarable_types():
    # The platform has always supported these; the SDK could not express them,
    # so a plugin could not declare a datetime/number/bool connector at all.
    values = {d.value for d in DataType}
    assert {"datetime", "number", "bool"} <= values
