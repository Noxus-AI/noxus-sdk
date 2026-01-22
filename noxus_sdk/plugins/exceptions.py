"""Plugins domain exceptions."""


class PluginValidationError(Exception):
    pass


class PluginSourceError(Exception):
    """Base exception for plugin source errors."""


class GitAuthenticationError(PluginSourceError):
    """Raised when git authentication fails (private repo without credentials)."""


class GitRepositoryNotFoundError(PluginSourceError):
    """Raised when git repository is not found or inaccessible."""


class ManifestNotFoundError(PluginSourceError):
    """Raised when manifest.json is not found in the plugin."""
