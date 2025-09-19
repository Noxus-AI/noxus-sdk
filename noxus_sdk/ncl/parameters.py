"""Parameter definition utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

if TYPE_CHECKING:
    from noxus_sdk.ncl.displays import BaseConfigDisplay
    from noxus_sdk.ncl.rules import BaseRule

# Constants
ADVANCED_ACCORDION = "Advanced options"
CONFIGURATION_TAB: Literal["Configuration", "Safety", "Human", "Model"] = "Configuration"
MODEL_TAB: Literal["Configuration", "Safety", "Human", "Model"] = "Model"
SAFETY_TAB: Literal["Configuration", "Safety", "Human", "Model"] = "Safety"
HUMAN_TAB: Literal["Configuration", "Safety", "Human", "Model"] = "Human"


def Parameter(  # noqa: N802 - Syntax sugar
    *args,
    display: BaseConfigDisplay | None = None,
    visible: bool = True,
    rules: list[BaseRule] | None = None,
    advanced: bool = False,
    tab: Literal["Configuration", "Safety", "Human", "Model"] = "Configuration",
    accordion: str | None = None,
    optional: bool = False,
    tooltip: str | None = None,
    placeholder: Any | None = None,  # noqa: ANN401 - No way around this for now
    col_span: int | None = None,
    col_justify: Literal["start", "center", "end"] | None = None,
    col_align: Literal["start", "center", "end"] | None = None,
    **kwargs,
) -> Field:
    """Create a configuration parameter with UI metadata."""
    js_field: dict[str, Any] = {}
    if display:
        js_field["display"] = display
    if not visible:
        js_field["visible"] = False
    if rules:
        js_field["rules"] = rules
    if advanced:
        js_field["advanced"] = True
    if optional:
        js_field["optional"] = True
    if tab:
        js_field["tab"] = tab
    if accordion:
        js_field["accordion"] = accordion
    if tooltip:
        js_field["tooltip"] = tooltip
    if placeholder:
        js_field["placeholder"] = placeholder
    if col_span:
        js_field["col_span"] = col_span
    if col_justify:
        js_field["col_justify"] = col_justify
    if col_align:
        js_field["col_align"] = col_align
    return Field(
        *args,
        json_schema_extra=js_field,
        **kwargs,
    )
