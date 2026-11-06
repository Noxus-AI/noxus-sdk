"""Classes the SDK exported up to 0.6 and removed in 0.7 (#4768).

Kept importable so plugins written against 0.6 still load. The platform does
not render them; their fields show as text.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import ConfigDict as PydanticConfigDict
from pydantic import model_validator

from noxus_sdk.ncl.displays import BaseConfigDisplay
from noxus_sdk.ncl.rules import BaseRule


class ConfigFile(BaseConfigDisplay):
    type: Literal["file"] = "file"  # type: ignore


class ConfigPhoneNumber(BaseConfigDisplay):
    type: Literal["phone_number"] = "phone_number"  # type: ignore


class ConfigTypeSelect(BaseConfigDisplay):
    type: Literal["select_type"] = "select_type"  # type: ignore
    values: list[Any]


class ConfigConditionSelect(BaseConfigDisplay):
    type: Literal["condition_select"] = "condition_select"  # type: ignore
    connector_name: str
    values: list[Any]


class ConfigCoworkerSelect(BaseConfigDisplay):
    type: Literal["coworker_select"] = "coworker_select"  # type: ignore
    include_current_node: bool = False


class ConfigUserSelector(BaseConfigDisplay):
    type: Literal["user_selector"] = "user_selector"  # type: ignore
    label: str = ""
    placeholder: str | None = None


class ConfigColorSelect(BaseConfigDisplay):
    type: Literal["color_selector"] = "color_selector"  # type: ignore
    values: list[str]
    has_custom_color: bool | None = None
    is_big: bool | None = False
    preview: str | None = None


class ConfigModelSelect(BaseConfigDisplay):
    type: Literal["model_select"] = "model_select"  # type: ignore
    endpoint: str
    model_type: str
    show_presets: bool = True
    show_inline_presets: bool = True
    layout: Literal["stacked", "side_by_side"] = "stacked"
    hide_disabled_models: bool = True
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


class ConfigOutputSelector(BaseConfigDisplay):
    type: Literal["output_selector"] = "output_selector"  # type: ignore
    connector_name: str


class ConfigVariableInputValue(BaseConfigDisplay):
    type: Literal["variable_input_value"] = "variable_input_value"  # type: ignore
    types: list[str]
    hide_toolbar: bool = False


class ConfigDisplayDict(BaseConfigDisplay):
    type: Literal["config_dict"] = "config_dict"  # type: ignore
    key_label: str
    value_label: str


class ConfigDictList(BaseConfigDisplay):
    type: Literal["config_dict_list"] = "config_dict_list"  # type: ignore
    keys: list[str]


class ConfigSearchBar(BaseConfigDisplay):
    type: Literal["search_bar"] = "search_bar"  # type: ignore
    search_endpoint: str


class ConfigWorkflowVersion(BaseConfigDisplay):
    type: Literal["config_workflow_version"] = "config_workflow_version"  # type: ignore


class ConfigComplexCondition(BaseConfigDisplay):
    type: Literal["config_complex_condition"] = "config_complex_condition"  # type: ignore


class ConfigScrapeWebsiteList(BaseConfigDisplay):
    type: Literal["config_scrape_website_list"] = "config_scrape_website_list"  # type: ignore


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
    setIncludeFolders: bool = False


class ConfigOneDrivePicker(BaseConfigDisplay):
    model_config = PydanticConfigDict(use_enum_values=True)
    type: Literal["onedrive_picker"] = "onedrive_picker"  # type: ignore
    base_url: str | None = None
    multi_select: bool = False
    file_type: str | None = None
    set_include_folders: bool = False
    name: str = "OneDrive"


ToolSections = Literal["QuickAction", "Flows", "Knowledge", "Nodes", "MCP"]


class ConfigToolsSelect(BaseConfigDisplay):
    type: Literal["tools_select"] = "tools_select"  # type: ignore
    quick_tools: list[str] | None = None
    show_sections: list[ToolSections] = ["QuickAction", "Flows", "Knowledge"]


class ConfigBaseToolsField(BaseConfigDisplay):
    """Renders a list of quick-action toggles with per-tool config."""

    type: Literal["base_tools_field"] = "base_tools_field"  # type: ignore


class ConfigKnowledgeBasesField(BaseConfigDisplay):
    """Renders KB list with picker + per-tool NCL config."""

    type: Literal["knowledge_bases_field"] = "knowledge_bases_field"  # type: ignore


class ConfigWorkflowsField(BaseConfigDisplay):
    """Renders workflow list with picker + per-tool NCL config."""

    type: Literal["workflows_field"] = "workflows_field"  # type: ignore


class ConfigCoworkersField(BaseConfigDisplay):
    """Renders coworker list with picker + per-tool NCL config."""

    type: Literal["coworkers_field"] = "coworkers_field"  # type: ignore


class ConfigActionsField(BaseConfigDisplay):
    """Renders action list with picker + per-tool NCL config."""

    type: Literal["actions_field"] = "actions_field"  # type: ignore


class ConfigPlaybookEditor(BaseConfigDisplay):
    """Visual editor for browser automation playbooks."""

    type: Literal["playbook_editor"] = "playbook_editor"  # type: ignore
    show_recorder_button: bool = True
    show_test_button: bool = True


class KeysSetBy(BaseRule):
    type: Literal["keys_set_by"] = "keys_set_by"  # type: ignore
    config_source: str


class SetsConnectorKeys(BaseRule):
    type: Literal["sets_connector_keys"] = "sets_connector_keys"  # type: ignore
    connector: str


class SetsConnectorOrConfigVisibility(BaseRule):
    type: Literal["sets_connector_or_config_visibility"] = (  # type: ignore
        "sets_connector_or_config_visibility"
    )


HUMAN_TAB: Literal["Configuration", "Safety", "Human", "Model"] = "Human"
