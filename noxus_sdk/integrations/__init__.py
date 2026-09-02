"""Integrations domain - everything related to integrations"""

from noxus_sdk.integrations.base import BaseIntegration, BaseCredentials
from noxus_sdk.integrations.schemas import (
    IntegrationDefinition,
    IntegrationProviderDefinition,
    OAuth2ProviderDefinition,
    OAuth2RefreshDefinition,
    OAuth2TokenResponseDefinition,
)

__all__ = [
    "BaseIntegration",
    "IntegrationDefinition",
    "IntegrationProviderDefinition",
    "OAuth2ProviderDefinition",
    "OAuth2RefreshDefinition",
    "OAuth2TokenResponseDefinition",
    "BaseCredentials",
]
