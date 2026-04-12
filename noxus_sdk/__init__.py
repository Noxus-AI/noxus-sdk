"""Noxus SDK - Software development kit to extend the Noxus platform and interact with its API."""

from noxus_sdk.__version__ import __version__
from noxus_sdk.client import Client

__all__ = ["Client", "__version__"]
