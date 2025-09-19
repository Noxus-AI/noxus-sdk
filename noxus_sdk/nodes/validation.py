"""Node validation utilities"""

from __future__ import annotations

from typing import TYPE_CHECKING

from noxus_sdk.schemas import ValidationResult

if TYPE_CHECKING:
    from noxus_sdk.nodes import BaseNode


def validate_node(node_class: type[BaseNode]) -> ValidationResult | None:
    """Validate a node class definition"""
    errors = []
    warnings = []

    # Basic validation checks
    if not hasattr(node_class, "title"):
        errors.append("Node must have a title")

    if not hasattr(node_class, "description"):
        warnings.append("Node should have a description")

    if not hasattr(node_class, "call"):
        errors.append("Node must implement call method")

    return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
