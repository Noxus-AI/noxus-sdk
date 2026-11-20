"""This module implements the configuration language used to extend the Noxus platform."""

import importlib
import warnings

from noxus_sdk.ncl.displays import (
    AnyConfigDisplay,
    BaseConfigDisplay,
    ConfigBanner,
    ConfigBigText,
    ConfigBindableDictRows,
    ConfigChipsListText,
    ConfigChipsSelect,
    ConfigChipsText,
    ConfigDictComplexList,
    ConfigDictComplexListStandalone,
    ConfigDictEntry,
    ConfigDictListWithoutConnector,
    ConfigDivider,
    ConfigDynamicSelect,
    ConfigDynamicText,
    ConfigEnumSlider,
    ConfigFileArray,
    ConfigMenuSelect,
    ConfigMultiSelect,
    ConfigNumber,
    ConfigNumberRange,
    ConfigNumberRangeSlider,
    ConfigNumberSlider,
    ConfigPassword,
    ConfigRichTextVariables,
    ConfigRichTextVariablesAI,
    ConfigSelect,
    ConfigText,
    ConfigTextDisplay,
    ConfigTextVariables,
    ConfigTimePicker,
    ConfigToggle,
    ConfigToggleButton,
    ConfigTypeDictArray,
)
from noxus_sdk.ncl.outputs import (
    BoolOutputType,
    FileOutputType,
    OutputType,
    OutputTypeBase,
    SelectOutputType,
    StringOutputType,
)
from noxus_sdk.ncl.parameters import (
    ADVANCED_ACCORDION,
    CONFIGURATION_TAB,
    MODEL_TAB,
    SAFETY_TAB,
    Parameter,
)
from noxus_sdk.ncl.rules import (
    AnyRule,
    BaseRule,
    DisabledIf,
    SetsConnectorType,
    SetsConnectorTypeAndKeys,
    TypeAndKeysSetBy,
    TypeSetBy,
    VisibleIf,
    VisibleIfGroup,
)
from noxus_sdk.ncl.utils import serialize_config

__all__ = [
    # parameters
    "ADVANCED_ACCORDION",
    "CONFIGURATION_TAB",
    "MODEL_TAB",
    "SAFETY_TAB",
    "Parameter",
    # displays
    "BaseConfigDisplay",
    "ConfigText",
    "ConfigNumber",
    "ConfigNumberSlider",
    "ConfigNumberRangeSlider",
    "ConfigNumberRange",
    "ConfigToggle",
    "ConfigToggleButton",
    "ConfigFileArray",
    "ConfigTimePicker",
    "ConfigSelect",
    "ConfigMenuSelect",
    "ConfigChipsSelect",
    "ConfigMultiSelect",
    "ConfigEnumSlider",
    "ConfigChipsText",
    "ConfigChipsListText",
    "ConfigTextVariables",
    "ConfigBigText",
    "ConfigRichTextVariables",
    "ConfigRichTextVariablesAI",
    "ConfigPassword",
    "ConfigDictEntry",
    "ConfigDictComplexList",
    "ConfigDictComplexListStandalone",
    "ConfigDictListWithoutConnector",
    "ConfigTypeDictArray",
    "ConfigBindableDictRows",
    "ConfigDynamicText",
    "ConfigDynamicSelect",
    "ConfigDivider",
    "ConfigBanner",
    "ConfigTextDisplay",
    "AnyConfigDisplay",
    # rules
    "BaseRule",
    "TypeSetBy",
    "VisibleIfGroup",
    "VisibleIf",
    "DisabledIf",
    "SetsConnectorType",
    "SetsConnectorTypeAndKeys",
    "TypeAndKeysSetBy",
    "AnyRule",
    # outputs
    "OutputTypeBase",
    "BoolOutputType",
    "SelectOutputType",
    "StringOutputType",
    "FileOutputType",
    "OutputType",
    # utils
    "serialize_config",
]

_REMOVED = frozenset(
    {
        "APIKeyField",
        "ApiToggleState",
        "ConfigActionsField",
        "ConfigApiToggle",
        "ConfigBaseToolsField",
        "ConfigColorSelect",
        "ConfigComplexCondition",
        "ConfigConditionSelect",
        "ConfigCoworkerSelect",
        "ConfigCoworkersField",
        "ConfigDictList",
        "ConfigDisplayDict",
        "ConfigFile",
        "ConfigGdrivePicker",
        "ConfigKnowledgeBasesField",
        "ConfigModelSelect",
        "ConfigModelToggle",
        "ConfigOneDrivePicker",
        "ConfigOutputSelector",
        "ConfigPhoneNumber",
        "ConfigPlaybookEditor",
        "ConfigProviderApiToggle",
        "ConfigProviderModelToggle",
        "ConfigScrapeWebsiteList",
        "ConfigSearchBar",
        "ConfigToolsSelect",
        "ConfigTypeSelect",
        "ConfigUserSelector",
        "ConfigVariableInputValue",
        "ConfigWorkflowVersion",
        "ConfigWorkflowsField",
        "GdriveFileType",
        "HUMAN_TAB",
        "KeysSetBy",
        "ServiceAccountField",
        "SetsConnectorKeys",
        "SetsConnectorOrConfigVisibility",
        "ToolSections",
    }
)


def __getattr__(name: str):  # noqa: ANN202
    if name not in _REMOVED:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    warnings.warn(
        f"noxus_sdk.ncl.{name} was removed in SDK 0.7 and renders as a text field",
        DeprecationWarning,
        stacklevel=2,
    )
    return getattr(
        importlib.import_module("noxus_sdk.ncl._removed"), name
    )  # lint-ignore: no-getattr
