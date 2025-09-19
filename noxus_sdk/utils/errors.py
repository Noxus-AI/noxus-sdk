"""Common error classes for noxus-sdk"""


class NoxusError(Exception):
    """Base exception for all noxus-sdk errors"""


class NodeDefinitionError(NoxusError):
    """Error in node definition"""


class UnexpectedError(NoxusError):
    """Unexpected error during execution"""


class PluginValidationError(NoxusError):
    """Plugin validation failed"""
