"""Node-specific types and enums"""

import builtins
from dataclasses import dataclass
from enum import Enum


class NodeCategory(str, Enum):
    IO = "io"
    SOURCES = "sources"
    DATA = "data"
    LOGIC = "logic"
    AI_SOUND = "ai_sound"
    AI_IMAGE = "ai_image"
    AI_TEXT = "ai_text"
    INTEGRATIONS = "integrations"
    AGENTS = "agents"
    OTHER = "other"
    ADMIN = "admin"
    CHAT = "agent_flow"


class DataType(str, Enum):
    dict = "dict"
    str = "str"
    list = "list"
    Image = "Image"
    Audio = "Audio"
    File = "File"
    Quote = "Quote"
    Custom = "Custom"
    Chat = "Chat"

    @staticmethod
    def map_value(val: builtins.str) -> "DataType":
        _map = {
            "text": DataType.str,
            "str": DataType.str,
            "dict": DataType.dict,
            "file": DataType.File,
            "audio": DataType.Audio,
            "image": DataType.Image,
            "custom": DataType.Custom,
            "quote": DataType.Quote,
            "chat": DataType.Chat,
        }
        return _map[val.lower()]


@dataclass
class TypeDefinition:
    data_type: DataType
    is_list: bool = False
