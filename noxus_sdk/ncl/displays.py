"""Configuration display components."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

# ========================================
# BASE CLASS
# ========================================


class BaseConfigDisplay(BaseModel):
    """Base class for configuration UI components.

    Provides common layout and styling properties. Subclasses should
    override the 'type' field with their component identifier.
    """

    type: str = "base"
    label: str
    tooltip: str | None = None
    error: str | None = None
    is_subconfig: bool = False
    col_span: int = 12  # Grid column span (1-12)
    col_justify: Literal["start", "center", "end"] | None = None
    col_align: Literal["start", "center", "end"] | None = None
    is_disabled: bool | None = False


# ========================================
# BASIC INPUT COMPONENTS
# ========================================


class ConfigText(BaseConfigDisplay):
    type: Literal["text"] = "text"  # type: ignore
    placeholder: str | None = None
    number_of_lines: int = 1
    show_refresh: bool = False
    is_code: bool = False
    is_textarea: bool = False
    class_name: str | None = None


class ConfigPassword(BaseConfigDisplay):
    type: Literal["password"] = "password"  # type: ignore
    placeholder: str | None = None


class ConfigNumber(BaseConfigDisplay):
    type: Literal["number"] = "number"  # type: ignore


class ConfigNumberSlider(BaseConfigDisplay):
    type: Literal["number_slider"] = "number_slider"  # type: ignore
    min: float | int = 0
    max: float | int = 100
    step: float | int = 1
    hide_number: bool = True


class ConfigNumberRangeSlider(BaseConfigDisplay):
    type: Literal["number_range_slider"] = "number_range_slider"  # type: ignore
    min: float | int = 0
    max: float | int = 100
    step: float | int = 1
    hide_number: bool = True


class ConfigNumberRange(BaseConfigDisplay):
    type: Literal["number_range"] = "number_range"  # type: ignore
    min: float | int
    max: float | int


class ConfigToggle(BaseConfigDisplay):
    type: Literal["toggle"] = "toggle"  # type: ignore


class ConfigToggleButton(BaseConfigDisplay):
    type: Literal["toggle_button"] = "toggle_button"  # type: ignore
    icon: str
    toggledIcon: str | None = None  # noqa: N815 - Bad legacy code..


class ConfigFileArray(BaseConfigDisplay):
    type: Literal["file_array"] = "file_array"  # type: ignore
    can_select_multiple_files: bool = False
    allowed_file_types: list[str] | None = None
    variant: Literal["logo", "image", "regular"] = "regular"


class ConfigTimePicker(BaseConfigDisplay):
    type: Literal["time_picker"] = "time_picker"  # type: ignore


# ========================================
# SELECTION COMPONENTS
# ========================================


class ConfigSelect(BaseConfigDisplay):
    type: Literal["select"] = "select"  # type: ignore
    values: list[Any]
    placeholder: str | None = None
    is_clearable: bool = False
    is_horizontal: bool = False
    is_searchable: bool = True


class ConfigChipsSelect(BaseConfigDisplay):
    type: Literal["select_chips"] = "select_chips"  # type: ignore
    label: str | None = None  # type: ignore
    values: list[Any]
    can_wrap: bool = True


class ConfigMenuSelect(BaseConfigDisplay):
    type: Literal["menu_select"] = "menu_select"  # type: ignore
    values: list[Any]
    button_label: str | None = None
    button_variant: Literal[
        "default", "destructive", "outline", "secondary", "ghost", "link"
    ] = "default"
    button_size: Literal["default", "sm", "lg", "icon"] = "default"
    button_icon: str | None = None
    needs_confirmation: bool = False
    confirmation_message: str | None = None
    is_horizontal: bool = False


class ConfigMultiSelect(BaseConfigDisplay):
    type: Literal["multi_select"] = "multi_select"  # type: ignore
    values: list[Any]
    placeholder: str | None = None
    max_options: int | None = None


class ConfigEnumSlider(BaseConfigDisplay):
    type: Literal["enum_slider"] = "enum_slider"  # type: ignore
    values: list[str]
    is_horizontal: bool = False


# ========================================
# TEXT & RICH TEXT COMPONENTS
# ========================================


class ConfigChipsText(BaseConfigDisplay):
    type: Literal["chips_text"] = "chips_text"  # type: ignore
    placeholder: str | None = None
    bottom_text: str | None = None
    chips_are_closable: bool = False


class ConfigChipsListText(BaseConfigDisplay):
    type: Literal["chips_list_text"] = "chips_list_text"  # type: ignore
    placeholder: str | None = None
    max_values: int | None = None
    bottom_text: str | None = None
    chips_are_closable: bool = False
    hide_toolbar: bool = False


class ConfigTextVariables(BaseConfigDisplay):
    type: Literal["big_text_variables"] = "big_text_variables"  # type: ignore
    placeholder: str | None = None
    number_of_lines: int = 1
    connector_name: str


class ConfigBigText(BaseConfigDisplay):
    type: Literal["big_text"] = "big_text"  # type: ignore
    placeholder: str | None = None
    number_of_lines: int = 5
    hide_toolbar: bool = False


class ConfigRichTextVariables(BaseConfigDisplay):
    type: Literal["rich_text_variables"] = "rich_text_variables"  # type: ignore
    placeholder: str | None = None
    number_of_lines: int = 5
    connector_name: str
    hide_toolbar: bool = False
    is_simple_text: bool = False
    no_space_on_insert: bool = False
    hide_chip_options: bool = False


class ConfigRichTextVariablesAI(BaseConfigDisplay):
    type: Literal["rich_text_variables_ai"] = "rich_text_variables_ai"  # type: ignore
    placeholder: str | None = None
    number_of_lines: int = 5
    connector_name: str

    @classmethod
    def render(cls, template: list[dict], variables: dict[str, str]) -> str:
        """Render template by replacing ((variable)) syntax with actual values."""
        text_template = "".join(m["text"] for m in template)
        for key, value in variables.items():
            text_template = text_template.replace(f"(({key}))", value)
        return text_template


# ========================================
# DICTIONARY & COMPLEX DATA
# ========================================


class ConfigDictEntry(BaseModel):
    label: str
    placeholder: str
    has_chips: bool = False


class ConfigDictComplexList(BaseConfigDisplay):
    type: Literal["config_dict_complex_list"] = "config_dict_complex_list"  # type: ignore
    subtitle: str | None = None
    keys: list[ConfigDictEntry]
    prefix_name: str = "Output"


class ConfigDictComplexListStandalone(BaseConfigDisplay):
    type: Literal["config_dict_complex_list_standalone"] = (  # pyright: ignore[reportIncompatibleVariableOverride]
        "config_dict_complex_list_standalone"
    )
    subtitle: str | None = None
    keys: list[ConfigDictEntry]


class ConfigDictListWithoutConnector(BaseConfigDisplay):
    type: Literal["config_dict_list_without_connector"] = (  # pyright: ignore[reportIncompatibleVariableOverride]
        "config_dict_list_without_connector"
    )
    key_label: str
    value_label: str
    key_prefix: str
    value_placeholder: str
    required_keys: list[str] | None = None


class ConfigTypeDictArray(BaseConfigDisplay):
    type: Literal["type_dict_array"] = "type_dict_array"  # type: ignore
    values: list[str]
    type_map: dict[str, str]


class ConfigBindableDictRows(BaseConfigDisplay):
    """Row editor for `dict[str, str]` fields: a name and a value per row.
    `locked_rows=True` fixes the row names so users edit values only."""

    type: Literal["config_bindable_dict_rows"] = "config_bindable_dict_rows"  # type: ignore
    locked_rows: bool = False
    empty_message: str | None = None


# ========================================
# DYNAMIC & SEARCH COMPONENTS
# ========================================


class ConfigDynamicText(BaseConfigDisplay):
    type: Literal["config_dynamic_text"] = "config_dynamic_text"  # type: ignore
    placeholder: str | None = None


class ConfigDynamicSelect(BaseConfigDisplay):
    """A select whose options are derived from another config field's metadata.

    Use when the valid options depend on a choice the user made in another
    field — e.g. an embedding-dimension picker that must reflect what the
    currently-selected embedding model supports.

    Contract for frontend renderers:
    - Read `source_field` from the form state — typically a `ConfigModelSelect`
      field so its cached metadata list is available client-side.
    - Look up the currently-selected item in that cached list.
    - Read `source_attribute` on the resolved item: it must be a `list` of
      primitive values (ints, strings) to render as options.
    - If `source_field` is empty or `source_attribute` is null/empty on the
      resolved item, fall back to `fallback_values` (render nothing if that
      is empty too). This is how the UI handles models without the attribute.
    """

    type: Literal["config_dynamic_select"] = "config_dynamic_select"  # type: ignore
    source_field: str
    """Name of the other config field to read the selection from."""
    source_attribute: str
    """Attribute on the resolved source item whose list value becomes the options."""
    endpoint: str
    """Backend endpoint that returns the catalog of items for `source_field` —
    typically the same endpoint the source field's `ConfigModelSelect` uses
    (e.g. `/models/embeddings`). The renderer fetches this, matches against
    the selected source value, and reads `source_attribute` off the match."""
    fallback_values: list[Any] = []
    """Used when the source field is empty or its attribute is null/empty."""
    placeholder: str | None = None
    is_clearable: bool = True
    is_searchable: bool = False


# ========================================
# UI DISPLAY COMPONENTS (NON-INPUT)
# ========================================


class ConfigDivider(BaseConfigDisplay):
    type: Literal["divider"] = "divider"  # type: ignore
    label: str = ""


class ConfigBanner(BaseConfigDisplay):
    type: Literal["banner"] = "banner"  # type: ignore
    label: str = ""
    style: Literal["info", "warning", "error"] = "info"


class ConfigTextDisplay(BaseConfigDisplay):
    type: Literal["ui_text_display"] = "ui_text_display"  # type: ignore
    label: str = ""
    title: str | None = None
    text: str | None = None
    small_text: str | None = None


AnyConfigDisplay = Annotated[
    ConfigText
    | ConfigPassword
    | ConfigNumber
    | ConfigNumberSlider
    | ConfigNumberRangeSlider
    | ConfigNumberRange
    | ConfigToggle
    | ConfigToggleButton
    | ConfigFileArray
    | ConfigTimePicker
    | ConfigSelect
    | ConfigChipsSelect
    | ConfigMenuSelect
    | ConfigMultiSelect
    | ConfigEnumSlider
    | ConfigChipsText
    | ConfigChipsListText
    | ConfigTextVariables
    | ConfigBigText
    | ConfigRichTextVariables
    | ConfigRichTextVariablesAI
    | ConfigDictComplexList
    | ConfigDictComplexListStandalone
    | ConfigDictListWithoutConnector
    | ConfigTypeDictArray
    | ConfigBindableDictRows
    | ConfigDynamicText
    | ConfigDynamicSelect
    | ConfigDivider
    | ConfigBanner
    | ConfigTextDisplay,
    Field(discriminator="type"),
]
