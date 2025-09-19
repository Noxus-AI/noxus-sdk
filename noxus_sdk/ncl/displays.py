"""Configuration display components."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic import ConfigDict as PydanticConfigDict

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


class ConfigNumber(BaseConfigDisplay):
    type: Literal["number"] = "number"  # type: ignore


class ConfigNumberSlider(BaseConfigDisplay):
    type: Literal["number_slider"] = "number_slider"  # type: ignore
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


class ConfigFile(BaseConfigDisplay):
    type: Literal["file"] = "file"  # type: ignore


class ConfigFileArray(BaseConfigDisplay):
    type: Literal["file_array"] = "file_array"  # type: ignore
    can_select_multiple_files: bool = False
    allowed_file_types: list[str] | None = None


class ConfigTimePicker(BaseConfigDisplay):
    type: Literal["time_picker"] = "time_picker"  # type: ignore


class ConfigPhoneNumber(BaseConfigDisplay):
    type: Literal["phone_number"] = "phone_number"  # type: ignore


# ========================================
# SELECTION COMPONENTS
# ========================================


class ConfigSelect(BaseConfigDisplay):
    type: Literal["select"] = "select"  # type: ignore
    values: list[Any]
    placeholder: str | None = None
    is_clearable: bool = False
    is_horizontal: bool = False


class ConfigChipsSelect(BaseConfigDisplay):
    type: Literal["select_chips"] = "select_chips"  # type: ignore
    label: str | None = None  # type: ignore
    values: list[Any]
    can_wrap: bool = True


class ConfigMultiSelect(BaseConfigDisplay):
    type: Literal["multi_select"] = "multi_select"  # type: ignore
    values: list[Any]
    placeholder: str | None = None
    max_options: int | None = None


class ConfigTypeSelect(BaseConfigDisplay):
    type: Literal["select_type"] = "select_type"  # type: ignore
    values: list[Any]


class ConfigConditionSelect(BaseConfigDisplay):
    type: Literal["condition_select"] = "condition_select"  # type: ignore
    connector_name: str
    values: list[Any]


class ConfigEnumSlider(BaseConfigDisplay):
    type: Literal["enum_slider"] = "enum_slider"  # type: ignore
    values: list[str]
    is_horizontal: bool = False


class ConfigCoworkerSelect(BaseConfigDisplay):
    type: Literal["coworker_select"] = "coworker_select"  # type: ignore


class ConfigUserSelector(BaseConfigDisplay):
    type: Literal["user_selector"] = "user_selector"  # type: ignore
    label: str = ""
    placeholder: str | None = None


# ========================================
# MODEL & API COMPONENTS
# ========================================


class ConfigModelSelect(BaseConfigDisplay):
    type: Literal["model_select"] = "model_select"  # type: ignore
    endpoint: str
    model_type: str
    model_config = PydanticConfigDict(protected_namespaces=())


class ConfigModelToggle(BaseConfigDisplay):
    type: Literal["model_toggle"] = "model_toggle"  # type: ignore
    endpoint: str
    model_type: str
    model_config = PydanticConfigDict(protected_namespaces=())


class ConfigProviderModelToggle(BaseConfigDisplay):
    type: Literal["provider_model_toggle"] = "provider_model_toggle"  # type: ignore
    provider: str
    model: str
    icon: str | None = None
    icon_url: str | None = None

    @model_validator(mode="after")
    def _validate_icon(self) -> ConfigProviderModelToggle:
        if self.icon is None and self.icon_url is None:
            raise ValueError("Either icon or icon_url must be provided")
        return self


class ApiToggleState(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    REQUESTING = "requesting"


class ConfigApiToggle(BaseConfigDisplay):
    type: Literal["api_toggle"] = "api_toggle"  # type: ignore
    toggle_label: str


class ConfigProviderApiToggle(ConfigApiToggle):
    type: Literal["provider_api_toggle"] = "provider_api_toggle"  # type: ignore


class ServiceAccountField(BaseConfigDisplay):
    type: Literal["service_account"] = "service_account"  # type: ignore
    name: str
    key: str


class APIKeyField(BaseConfigDisplay):
    type: Literal["api_key"] = "api_key"  # type: ignore
    name: str
    key: str


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


class ConfigTextArray(BaseConfigDisplay):
    type: Literal["text_array"] = "text_array"  # type: ignore


class ConfigOutputSelector(BaseConfigDisplay):
    type: Literal["output_selector"] = "output_selector"  # type: ignore
    connector_name: str


class ConfigVariableInputValue(BaseConfigDisplay):
    type: Literal["variable_input_value"] = "variable_input_value"  # type: ignore
    types: list[str]
    hide_toolbar: bool = False


# ========================================
# DICTIONARY & COMPLEX DATA
# ========================================


class ConfigDisplayDict(BaseConfigDisplay):
    type: Literal["config_dict"] = "config_dict"  # type: ignore
    key_label: str
    value_label: str


class ConfigDictList(BaseConfigDisplay):
    type: Literal["config_dict_list"] = "config_dict_list"  # type: ignore
    keys: list[str]


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
    type: Literal["config_dict_complex_list_standalone"] = "config_dict_complex_list_standalone"  # type: ignore
    subtitle: str | None = None
    keys: list[ConfigDictEntry]


class ConfigDictListWithoutConnector(BaseConfigDisplay):
    type: Literal["config_dict_list_without_connector"] = "config_dict_list_without_connector"  # type: ignore
    key_label: str
    value_label: str
    key_prefix: str
    value_placeholder: str
    required_keys: list[str] | None = None


class ConfigTypeDictArray(BaseConfigDisplay):
    type: Literal["type_dict_array"] = "type_dict_array"  # type: ignore
    values: list[str]
    type_map: dict[str, str]


# ========================================
# DYNAMIC & SEARCH COMPONENTS
# ========================================


class ConfigDynamicText(BaseConfigDisplay):
    type: Literal["config_dynamic_text"] = "config_dynamic_text"  # type: ignore
    placeholder: str | None = None


class ConfigDynamicSelect(BaseConfigDisplay):
    type: Literal["config_dynamic_select"] = "config_dynamic_select"  # type: ignore


class ConfigSearchBar(BaseConfigDisplay):
    type: Literal["search_bar"] = "search_bar"  # type: ignore
    search_endpoint: str


class ConfigWorkflowVersion(BaseConfigDisplay):
    type: Literal["config_workflow_version"] = "config_workflow_version"  # type: ignore


class ConfigComplexCondition(BaseConfigDisplay):
    type: Literal["config_complex_condition"] = "config_complex_condition"  # type: ignore


class ConfigScrapeWebsiteList(BaseConfigDisplay):
    type: Literal["config_scrape_website_list"] = "config_scrape_website_list"  # type: ignore


# ========================================
# THIRD-PARTY INTEGRATIONS
# ========================================


class GdriveFileType(str, Enum):
    PDFS = "application/pdf"
    DOCUMENTS = "application/pdf,text/plain,application/vnd.google-apps.document,application/vnd.google-apps.presentation,application/json"
    GDOCUMENTS = "application/vnd.google-apps.document"
    FOLDERS = "application/vnd.google-apps.folder"
    SPREADSHEETS = "application/vnd.google-apps.spreadsheet"
    ANY = "application/pdf,text/plain,application/vnd.google-apps.document,application/vnd.google-apps.presentation,application/json,application/vnd.google-apps.folder,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation"


class ConfigGdrivePicker(BaseConfigDisplay):
    model_config = PydanticConfigDict(use_enum_values=True)
    type: Literal["gdrive_picker"] = "gdrive_picker"  # type: ignore
    multi_select: bool = False
    file_type: GdriveFileType | None = None
    setIncludeFolders: bool = False  # noqa: N815 - Bad legacy code..


class ConfigOneDrivePicker(BaseConfigDisplay):
    model_config = PydanticConfigDict(use_enum_values=True)
    type: Literal["onedrive_picker"] = "onedrive_picker"  # type: ignore
    base_url: str | None = None
    multi_select: bool = False
    file_type: str | None = None
    set_include_folders: bool = False
    name: str = "OneDrive"


# ========================================
# TOOL & WORKFLOW COMPONENTS
# ========================================

ToolSections = Literal["QuickAction", "Flows", "Knowledge", "Nodes", "MCP", "Chatflow"]


class ConfigToolsSelect(BaseConfigDisplay):
    type: Literal["tools_select"] = "tools_select"  # type: ignore
    quick_tools: list[str] | None = None
    show_sections: list[ToolSections] = ["QuickAction", "Flows", "Knowledge"]


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
    | ConfigNumber
    | ConfigNumberSlider
    | ConfigNumberRange
    | ConfigToggle
    | ConfigToggleButton
    | ConfigFile
    | ConfigFileArray
    | ConfigTimePicker
    | ConfigPhoneNumber
    | ConfigSelect
    | ConfigChipsSelect
    | ConfigMultiSelect
    | ConfigTypeSelect
    | ConfigConditionSelect
    | ConfigEnumSlider
    | ConfigCoworkerSelect
    | ConfigUserSelector
    | ConfigModelSelect
    | ConfigModelToggle
    | ConfigProviderModelToggle
    | ConfigApiToggle
    | ConfigChipsText
    | ConfigChipsListText
    | ConfigTextVariables
    | ConfigBigText
    | ConfigRichTextVariables
    | ConfigRichTextVariablesAI
    | ConfigTextArray
    | ConfigOutputSelector
    | ConfigVariableInputValue
    | ConfigDisplayDict
    | ConfigDictList
    | ConfigDictComplexList
    | ConfigDictComplexListStandalone
    | ConfigDictListWithoutConnector
    | ConfigTypeDictArray
    | ConfigDynamicText
    | ConfigDynamicSelect
    | ConfigSearchBar
    | ConfigWorkflowVersion
    | ConfigComplexCondition
    | ConfigScrapeWebsiteList
    | ConfigGdrivePicker
    | ConfigOneDrivePicker
    | ConfigToolsSelect
    | ConfigDivider
    | ConfigBanner
    | ConfigTextDisplay,
    Field(discriminator="type"),
]
