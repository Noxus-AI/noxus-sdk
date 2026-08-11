"""Errors a plugin can raise from node/trigger/integration code.

These are plain exceptions (the SDK runs inside the sandbox, with no FastAPI /
HTTPException available). When raised inside a node's ``call()`` the message
crosses the JSON-RPC boundary and the platform surfaces it to the user as the
node's failure reason. The exception *type* does not survive the boundary today
— only the message — so keep messages actionable.
"""

from __future__ import annotations


class NoxusPluginError(Exception):
    """Base class for errors raised by plugin code."""


class IntegrationFailedError(NoxusPluginError):
    """An integration/API call failed — bad credentials, connectivity, or an
    error returned by the upstream service. Use this (not a bare Exception) so
    the message reads as a user-actionable integration problem."""


class UnexpectedError(NoxusPluginError):
    """An unexpected failure inside plugin code that the author did not
    anticipate."""
