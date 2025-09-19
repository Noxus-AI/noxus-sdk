from __future__ import annotations

from types import NoneType, UnionType
from typing import TYPE_CHECKING, Any, Union, get_args, get_origin

from pydantic_core import PydanticUndefinedType

if TYPE_CHECKING:
    from pydantic import BaseModel


def serialize_config(config_class: BaseModel) -> dict[str, Any]:
    config_fields = {}

    for name, value in config_class.model_fields.items():
        _default = (
            value.default
            if not isinstance(value.default, PydanticUndefinedType)
            else None
        )
        optional = False
        origin = get_origin(value.annotation)
        if origin is Union or origin is UnionType:
            types = get_args(value.annotation)
            if NoneType in types or _default is not None:
                optional = True

            _type = types[0].__name__
        else:
            if _default is not None:
                optional = True
            _type = value.annotation.__name__

        attr_repr = {
            "type": _type,
            "description": value.description,
            "advanced": (value.json_schema_extra or {}).get("advanced", False),
            "tab": (value.json_schema_extra or {}).get("tab", "Configuration"),
            "accordion": (value.json_schema_extra or {}).get("accordion", None),
            "optional": optional,
            "default": _default,
            "rules": [
                rule.model_dump()
                for rule in (value.json_schema_extra or {}).get("rules", [])
            ],
            "visible": (value.json_schema_extra or {}).get("visible", True),
        }

        if display_info := (value.json_schema_extra or {}).get("display", None):
            attr_repr["display"] = display_info.model_dump()

        config_fields[name] = attr_repr
    return config_fields
