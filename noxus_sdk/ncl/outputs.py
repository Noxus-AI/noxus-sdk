"""Output type definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from noxus_sdk.ncl.parameters import Parameter

# ========================================
# BASE CLASS
# ========================================


class OutputTypeBase(BaseModel):
    """Base class for output type definitions."""

    name: str
    required: bool = True


# ========================================
# OUTPUT TYPE IMPLEMENTATIONS
# ========================================


class BoolOutputType(OutputTypeBase):
    type: Literal["checkbox"] = "checkbox"
    initial_value: dict | str | bool | None = None

    true_label: str = Parameter(default="Accept", advanced=True)
    false_label: str = Parameter(default="Reject", advanced=True)


class SelectOutputType(OutputTypeBase):
    type: Literal["select"] = "select"
    initial_value: str | None = None
    options: list[str] = []


class StringOutputType(OutputTypeBase):
    type: Literal["text"] = "text"
    initial_value: dict | str | None = None


class FileOutputType(OutputTypeBase):
    type: Literal["file"] = "file"
    initial_value: dict | str | None = None


# ========================================
# UNION TYPE FOR ALL OUTPUTS
# ========================================

OutputType = BoolOutputType | StringOutputType | FileOutputType | SelectOutputType
