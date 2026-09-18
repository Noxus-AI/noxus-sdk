from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class OAuth2TokenResponseDefinition(BaseModel):
    """Serializable OAuth token-response behaviour for plugin integrations."""

    expires_in_key: str = "expires_in"
    expires_at_key: str | None = None
    refresh_token_rotated: bool = False


class OAuth2RefreshDefinition(BaseModel):
    """Serializable OAuth refresh-request behaviour for plugin integrations."""

    refresh_extra_params: dict[str, str] = Field(default_factory=dict)
    refresh_grant_type: str = "refresh_token"
    refresh_url: str | None = None


class OAuth2ProviderDefinition(BaseModel):
    """OAuth endpoints and protocol details safe to store in a manifest."""

    authorize_url: str
    token_url: str
    scopes: list[str] = Field(default_factory=list)
    token_response: OAuth2TokenResponseDefinition = Field(
        default_factory=OAuth2TokenResponseDefinition
    )
    refresh: OAuth2RefreshDefinition = Field(default_factory=OAuth2RefreshDefinition)
    code_challenge_method: str | None = None
    extra_authorize_params: dict[str, str] = Field(default_factory=dict)
    revocation_url: str | None = None
    # Most OAuth servers use ``code``. Athom's Homey endpoint instead names
    # the form field ``authorization_code``.
    authorization_code_param: str = "code"
    # Name of the authorization URL's response-type query parameter. Set to
    # None only for providers that do not accept the standard parameter.
    response_type_param: str | None = "response_type"
    # Some providers reject redirect_uri during the token exchange even though
    # it was present in the authorization request.
    include_redirect_uri_in_token_request: bool = True


class IntegrationProviderDefinition(BaseModel):
    """An OAuth provider contributed by a sandboxed plugin."""

    key: str
    auth_type: Literal["oauth2", "oauth2_client_credentials", "ncs"]
    display_name: str = ""
    oauth2: OAuth2ProviderDefinition | None = None
    ncs_provider_key: str | None = None
    image: str = ""
    supports_refresh: bool = True


class DeviceAuthStart(BaseModel):
    """A started device-code sign-in: show the code + link, then poll."""

    session_id: str
    verification_url: str
    user_code: str
    expires_in_seconds: int = 900
    poll_interval_seconds: int = 3


class DeviceAuthPoll(BaseModel):
    """One poll of a device-code session. ``credentials`` is the payload to
    store as the integration credential when status is ``complete``."""

    status: Literal["pending", "complete", "failed", "expired"]
    credentials: dict | None = None
    error: str | None = None


class IntegrationDefinition(BaseModel):
    type: str
    display_name: str
    image: str
    description: str = ""
    scopes: list[str] | None = None
    properties: dict[str, str] | None = None
    providers: list[IntegrationProviderDefinition] = Field(default_factory=list)
    config: dict
    # Device-code sign-in (e.g. "Sign in with ChatGPT"): the platform renders a
    # generic start → show code → poll connect flow for integrations that
    # declare it, dispatched to the plugin's device_auth_start/poll hooks.
    supports_device_auth: bool = False
    device_auth_label: str | None = None
