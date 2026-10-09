import git
import pytest

from noxus_sdk.plugins.exceptions import GitAuthenticationError
from noxus_sdk.plugins.sources.git import GitPluginSource, redact_credentials


@pytest.mark.parametrize(
    ("repo_url", "token", "expected"),
    [
        (
            "https://github.com/acme/plugins.git",
            "ghp_abc",
            "https://x-access-token:ghp_abc@github.com/acme/plugins.git",
        ),
        (
            "https://gitlab.com/acme/plugins.git",
            "glpat-abc",
            "https://oauth2:glpat-abc@gitlab.com/acme/plugins.git",
        ),
        (
            "https://bitbucket.org/acme/plugins.git",
            "ATCTT3x=",
            "https://x-token-auth:ATCTT3x%3D@bitbucket.org/acme/plugins.git",
        ),
        (
            "https://bitbucket.org/acme/plugins.git",
            "ATATT3x=",
            "https://x-bitbucket-api-token-auth:ATATT3x%3D@bitbucket.org/acme/plugins.git",
        ),
        (
            "https://git.example.com:8443/acme/plugins.git",
            "tok",
            "https://x-access-token:tok@git.example.com:8443/acme/plugins.git",
        ),
    ],
)
def test_token_goes_in_password_slot(repo_url: str, token: str, expected: str) -> None:
    source = GitPluginSource(repo_url=repo_url, token=token)
    assert source._get_authenticated_url() == expected


def test_username_password_are_url_encoded() -> None:
    source = GitPluginSource(
        repo_url="https://bitbucket.org/acme/plugins.git",
        username="me@acme.com",
        password="p@ss/word=",
    )
    assert (
        source._get_authenticated_url()
        == "https://me%40acme.com:p%40ss%2Fword%3D@bitbucket.org/acme/plugins.git"
    )


def test_no_credentials_and_ssh_are_untouched() -> None:
    assert (
        GitPluginSource(repo_url="https://github.com/a/b.git")._get_authenticated_url()
        == "https://github.com/a/b.git"
    )
    assert (
        GitPluginSource(
            repo_url="git@github.com:a/b.git", token="t"
        )._get_authenticated_url()
        == "git@github.com:a/b.git"
    )


def test_redact_credentials() -> None:
    assert (
        redact_credentials(
            "fatal: could not read Password for 'https://ATCTT3x=@bitbucket.org'"
        )
        == "fatal: could not read Password for 'https://***@bitbucket.org'"
    )
    assert (
        redact_credentials("https://u:p@host/x https://host/y")
        == "https://***@host/x https://host/y"
    )


def test_password_prompt_is_an_auth_error_without_the_token() -> None:
    source = GitPluginSource(
        repo_url="https://bitbucket.org/acme/plugins.git", token="ATCTT3x="
    )
    error = git.GitCommandError(
        ["git", "clone"],
        128,
        stderr="fatal: could not read Password for 'https://ATCTT3x=@bitbucket.org': No such device",
    )
    converted = source._handle_git_error(error)
    assert isinstance(converted, GitAuthenticationError)
    assert "ATCTT3x=" not in str(converted)


def test_fallback_error_never_contains_credentials() -> None:
    source = GitPluginSource(
        repo_url="https://bitbucket.org/acme/plugins.git", token="ATCTT3x="
    )
    error = git.GitCommandError(
        ["git", "clone"],
        128,
        stderr="fatal: something odd happened at https://x-token-auth:ATCTT3x=@bitbucket.org/acme",
    )
    message = str(source._handle_git_error(error))
    assert "ATCTT3x=" not in message
    assert "https://***@bitbucket.org/acme" in message
