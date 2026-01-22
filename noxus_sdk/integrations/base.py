from __future__ import annotations

from typing import Any, ClassVar, Generic, Type, TypeVar, get_args

from pydantic import BaseModel

from noxus_sdk.integrations.schemas import IntegrationDefinition
from noxus_sdk.ncl import serialize_config


class BaseCredentials(BaseModel):
    type: ClassVar[str] = "base"

    def is_ready(self) -> bool:
        return True


CredentialsType = TypeVar("CredentialsType", bound=BaseCredentials)


class BaseIntegration(Generic[CredentialsType]):
    """Base class for all integrations"""

    type: ClassVar[str] = "base"
    display_name: str
    image: str
    visible: bool = True
    scopes: list[str] | None = None  # Will be set to an empty list if not set
    properties: dict[str, str] | None = None  # Will be set to an empty dict if not set
    credentials_class: Type[CredentialsType]
    plugin_id: str | None = (
        None  # ID of the plugin that this integration belongs to (None for integrations that don't come from a plugin)
    )
    plugin_name: str | None = (
        None  # Name of the plugin that this integration belongs to (None for integrations that don't come from a plugin)
    )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        cls.credentials_class = get_args(cls.__orig_bases__[0])[0]  # type: ignore

        # Dynamically set type from credentials_class if it exists
        if hasattr(cls, "credentials_class") and hasattr(cls.credentials_class, "type"):
            cls.type = cls.credentials_class.type

        if cls.scopes is None:
            cls.scopes = []

        if cls.properties is None:
            cls.properties = {}

    @classmethod
    def get_credentials(cls, creds: dict[str, Any] | None) -> CredentialsType | None:
        """Get the credentials of the integration"""
        if creds is None:
            return None

        try:
            # the old credentials were stored in the data field
            # so for backwards compatibility of any new credential that is migrated
            # we load from both sides
            return cls.credentials_class(**creds, **creds.get("data", {}))
        except Exception:
            return None

    @classmethod
    async def is_ready(cls, creds: dict[str, Any] | None) -> bool:
        """Check if credentials are ready to use"""
        _creds = cls.get_credentials(creds)
        if _creds is None:
            return False

        return _creds.is_ready()

    @classmethod
    def get_config(cls) -> dict:
        """Get the config of the integration"""
        config = serialize_config(cls.credentials_class)
        return config

    @classmethod
    def override_visible(cls, feature_flags: Any) -> bool:
        """Override the visible of the integration"""

        # Feature flags are a object of type FeatureFlags, but we cant type it here because its outside the scope of this package
        return cls.visible

    @classmethod
    def get_definition(cls) -> IntegrationDefinition:
        """Convert integration class to IntegrationDefinition"""

        return IntegrationDefinition(
            type=cls.type,
            display_name=cls.display_name,
            image=cls.image,
            scopes=cls.scopes,
            properties=cls.properties,
            config=cls.get_config(),
        )
