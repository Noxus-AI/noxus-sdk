from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal

import httpx
from loguru import logger
from pydantic import BaseModel

from noxus_sdk.integrations.base import BaseIntegration

if TYPE_CHECKING:
    from uuid import UUID

    from noxus_sdk.plugins.context import RemoteExecutionContext


class NangoProviderCredentials(BaseModel):
    """Configuration for Nango provider credentials."""


class NangoProviderOAuthCredentials(NangoProviderCredentials):
    """Configuration for Nango OAuth credentials.

    Reference:
    https://docs.nango.dev/reference/api/integration/create#option-1
    """

    type: Literal["OAUTH1", "OAUTH2", "TBA"]
    client_id: str
    client_secret: str
    scopes: str = ""
    webhook_secret: str | None = None


class NangoIntegration(BaseIntegration, ABC):
    """Integration created using Nango"""

    type = "nango"

    provider: str
    window_height: int = 600
    window_width: int = 600

    def __init_subclass__(cls) -> None:
        """Set the configuration class for the plugin when the sublcass is created"""

        if not hasattr(cls, "provider"):
            raise ValueError("Provider must be set for Nango integration")

        cls.properties = {
            "provider": cls.provider,
            "window_height": cls.window_height,
            "window_width": cls.window_width,
        }

    @classmethod
    def get_trigger_endpoint(cls, group_id: UUID) -> str | None:
        """Get the trigger endpoint of the integration"""
        return f"/groups/{group_id}/integrations/nango/{cls.provider}"

    @classmethod
    def get_delete_endpoint(cls, group_id: UUID) -> str | None:
        """Get the delete endpoint of the integration"""
        return f"/groups/{group_id}/integrations/nango/{cls.provider}"

    @classmethod
    def get_confirm_endpoint(cls, group_id: UUID) -> str | None:
        """Get the confirm endpoint of the integration"""
        return f"/groups/{group_id}/integrations/nango"

    @classmethod
    @abstractmethod
    def get_provider_credentials(
        cls,
        ctx: RemoteExecutionContext,
    ) -> NangoProviderCredentials:
        """Get the Nango credentials for this integration."""
        raise NotImplementedError(
            "Integration must implement get_provider_credentials() method",
        )

    @classmethod
    async def get_config(cls, ctx: RemoteExecutionContext) -> dict:
        """Get the config of the integration"""
        credentials = cls.get_provider_credentials(ctx)
        return {
            "credentials": credentials.model_dump(),
        }

    @classmethod
    async def get_credentials(cls, data: dict) -> dict:
        """Get the credentials of the integration"""

        connection_id = data["connection_id"]

        nango_secret_key = os.getenv("NANGO_SECRET_KEY")
        if not nango_secret_key:
            raise ValueError("NANGO_SECRET_KEY is not set")

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://api.nango.dev/connection/{connection_id}",
                headers={"Authorization": f"Bearer {nango_secret_key}"},
                params={"provider_config_key": cls.provider},
            )
            resp.raise_for_status()

            return resp.json().get("credentials", {})

    @classmethod
    async def is_connected(cls, data: dict, **kwargs) -> bool:
        """Get the status of the nango integration"""

        if "providers" in kwargs:
            return cls.provider in data and cls.provider in kwargs["providers"]

        return cls.provider in data

    @classmethod
    async def ensure_nango_integration(
        cls,
        ctx: RemoteExecutionContext,
        nango_secret_key: str,
    ) -> None:
        """Ensure the integration exists and is properly configured in Nango"""

        config = await cls.get_config(ctx)

        integration_data = {
            "unique_key": cls.provider,
            "provider": cls.provider,
            "display_name": cls.display_name,
            "credentials": config["credentials"],
        }

        headers = {
            "Authorization": f"Bearer {nango_secret_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            # First, try to get the existing integration
            try:
                existing_response = await client.get(
                    f"https://api.nango.dev/integrations/{cls.provider}",
                    headers=headers,
                    params={"include": "credentials"},
                )
                existing_response.raise_for_status()
                existing_integration = existing_response.json()["data"]

                # Check if configuration needs updating
                if any(
                    existing_integration["credentials"].get(k) != v
                    for k, v in integration_data["credentials"].items()
                ):
                    update_response = await client.patch(
                        f"https://api.nango.dev/integrations/{cls.provider}",
                        json={"credentials": integration_data["credentials"]},
                        headers=headers,
                    )
                    update_response.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.info(
                        f"Integration {cls.provider} not found in Nango, creating...",
                    )
                    create_response = await client.post(
                        "https://api.nango.dev/integrations",
                        json=integration_data,
                        headers=headers,
                    )
                    create_response.raise_for_status()
                else:
                    # Re-raise other HTTP errors
                    raise

    def connect(self, config: dict) -> None:
        """Connect to the integration"""
        self.config = config

    def update_config(self, config: dict) -> None:
        """Update the config of the integration"""
        self.config = config

    def disconnect(self) -> None:
        """Disconnect from the integration - use delete_integration for actual deletion"""
