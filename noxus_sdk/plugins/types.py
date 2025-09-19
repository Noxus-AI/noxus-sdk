"""Plugin-specific types and enums"""

from enum import Enum


class PluginExecutionMode(str, Enum):
    RUNTIME = "runtime"
    DOCKER = "docker"
    REMOTE = "remote"


class PluginCategory(str, Enum):
    GENERAL = "general"
    DOCUMENT = "document"
    OTHER = "other"


class PluginStatus(str, Enum):
    INSTALLING = "installing"
    MISSING_CONFIG = "missing_config"
    RUNNING = "running"
    RESTARTING = "restarting"
    UNINSTALLING = "uninstalling"
    UNINSTALLED = "uninstalled"
    ERROR = "error"


class PluginSourceType(str, Enum):
    GIT = "git"
    LOCAL = "local"
    UPLOAD = "upload"
    MARKETPLACE = "marketplace"
