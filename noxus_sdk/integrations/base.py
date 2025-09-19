from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Literal

from noxus_sdk.integrations.schemas import IntegrationDefinition

if TYPE_CHECKING:
    from uuid import UUID

    from noxus_sdk.plugins.context import RemoteExecutionContext


class BaseIntegration(ABC):
    """Base class for all integrations"""

    type: Literal["nango"]
    name: str
    display_name: str
    image: str
    description: str | None = None
    scopes: list[str]  # Will be set to an empty list if not set
    properties: dict  # Will be set to an empty dict if not set

    @classmethod
    def __init__subclass__(cls) -> None:
        if not cls.scopes:
            cls.scopes = []

        if not cls.properties:
            cls.properties = {}

    @classmethod
    def get_trigger_endpoint(cls, group_id: UUID) -> str | None:  # noqa: ARG003 - Here for documentation purposes
        """Get the trigger endpoint of the integration"""
        return None

    @classmethod
    def get_delete_endpoint(cls, group_id: UUID) -> str | None:  # noqa: ARG003 - Here for documentation purposes
        """Get the delete endpoint of the integration"""
        return None

    @classmethod
    def get_confirm_endpoint(cls, group_id: UUID) -> str | None:  # noqa: ARG003 - Here for documentation purposes
        """Get the confirm endpoint of the integration"""
        return None

    @classmethod
    async def get_config(cls, ctx: RemoteExecutionContext) -> dict:  # noqa: ARG003 - Here for documentation purposes
        """Get the config of the integration"""
        return {}

    @classmethod
    @abstractmethod
    async def is_connected(cls, data: dict, **kwargs) -> bool:
        """Get the status of the integration"""
        raise NotImplementedError("Integration must implement is_connected() method")

    @classmethod
    @abstractmethod
    async def get_credentials(cls, data: dict) -> dict:
        """Get the status of the integration"""
        return data

    @abstractmethod
    def connect(self, config: dict) -> None:
        """Connect to the integration"""
        raise NotImplementedError("Integration must implement connect() method")

    @abstractmethod
    def disconnect(self) -> None:
        """Get the auth type of the integration"""
        raise NotImplementedError("Integration must implement disconnect() method")

    @abstractmethod
    def update_config(self, config: dict) -> None:
        """Update the config of the integration"""
        raise NotImplementedError("Integration must implement update_config() method")

    @classmethod
    def get_definition(cls) -> IntegrationDefinition:
        """Convert integration class to IntegrationDefinition"""

        return IntegrationDefinition(
            name=cls.name,
            type=cls.type,  # type: ignore
            display_name=cls.display_name,
            description=cls.description,
            image=cls.image,
            scopes=cls.scopes,
            properties=cls.properties,
        )
