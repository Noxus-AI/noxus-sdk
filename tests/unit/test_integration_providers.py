"""Plugin OAuth provider declarations survive manifest serialization."""

from noxus_sdk.integrations import (
    BaseCredentials,
    BaseIntegration,
    IntegrationProviderDefinition,
    OAuth2ProviderDefinition,
    OAuth2TokenResponseDefinition,
)


class _Credentials(BaseCredentials):
    type = "oauth_plugin_test"


class _Integration(BaseIntegration[_Credentials]):
    display_name = "OAuth plugin test"
    image = "https://example.com/icon.png"
    providers = [
        IntegrationProviderDefinition(
            key="oauth_plugin_test_provider",
            auth_type="oauth2",
            display_name="OAuth account",
            oauth2=OAuth2ProviderDefinition(
                authorize_url="https://example.com/authorize",
                token_url="https://example.com/token",
                extra_authorize_params={"authorization_type": "code"},
                authorization_code_param="authorization_code",
                response_type_param=None,
                include_redirect_uri_in_token_request=False,
                token_response=OAuth2TokenResponseDefinition(
                    refresh_token_rotated=True
                ),
            ),
        )
    ]


def test_oauth_provider_is_serialized_in_integration_definition() -> None:
    definition = _Integration.get_definition()

    assert len(definition.providers) == 1
    provider = definition.providers[0]
    assert provider.key == "oauth_plugin_test_provider"
    assert provider.auth_type == "oauth2"
    assert provider.oauth2 is not None
    assert provider.oauth2.authorization_code_param == "authorization_code"
    assert provider.oauth2.response_type_param is None
    assert provider.oauth2.include_redirect_uri_in_token_request is False
    assert provider.oauth2.extra_authorize_params == {"authorization_type": "code"}
    assert provider.oauth2.token_response.refresh_token_rotated is True
