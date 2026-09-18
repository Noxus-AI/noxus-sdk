"""Typed exception hierarchies for SDK HTTP requests and plugin code.

Every failed HTTP response is mapped to a :class:`NoxusApiError` subclass so
callers can catch the specific failure they care about instead of matching on
raw ``httpx`` status codes. ``RequestFailedError`` is retained as an alias of
the base class for backwards compatibility.

Plugin exceptions cross the JSON-RPC boundary as user-facing failure messages;
their concrete types do not survive that boundary, so messages should remain
actionable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    import httpx


class NoxusError(Exception):
    """Base class for every error raised by the SDK."""


class NoxusApiError(NoxusError):
    """An HTTP request to the Noxus backend returned an error response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        body: object = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body
        self.request_id = request_id

    @classmethod
    def from_response(cls, response: httpx.Response) -> NoxusApiError:
        body: object
        try:
            body = response.json()
        except ValueError:
            body = response.text
        detail = _extract_detail(body) or response.reason_phrase or "request failed"
        request_id = response.headers.get("x-request-id") or response.headers.get(
            "x-noxus-request-id",
        )
        exc_cls = _STATUS_MAP.get(response.status_code, cls)
        message = f"{response.status_code} {detail}"
        if request_id:
            message = f"{message} (request id: {request_id})"
        return exc_cls(
            message,
            status_code=response.status_code,
            body=body,
            request_id=request_id,
        )


class BadRequestError(NoxusApiError):
    """400 — the request was malformed."""


class UnauthorizedError(NoxusApiError):
    """401 — the API key is missing or invalid."""


class ForbiddenError(NoxusApiError):
    """403 — the API key lacks permission for this resource."""


class NotFoundError(NoxusApiError):
    """404 — the requested resource does not exist."""


class ValidationError(NoxusApiError):
    """422 — the request failed server-side validation."""


class RateLimitedError(NoxusApiError):
    """429 — rate limit exceeded and retries were exhausted."""


class ServerError(NoxusApiError):
    """5xx — the backend failed to handle the request."""


# Back-compat: the SDK previously exposed only ``RequestFailedError``.
RequestFailedError = NoxusApiError


_STATUS_MAP: dict[int, type[NoxusApiError]] = {
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    422: ValidationError,
    429: RateLimitedError,
}


def _extract_detail(body: object) -> str | None:
    if isinstance(body, dict):
        mapping = cast("dict[str, object]", body)
        for key in ("detail", "message", "error"):
            value = mapping.get(key)
            if isinstance(value, str):
                return value
            if value is not None:
                return str(value)
    if isinstance(body, str) and body.strip():
        return body.strip()
    return None


def raise_for_status(response: httpx.Response) -> None:
    """Raise the mapped :class:`NoxusApiError` when *response* is an error."""
    if response.is_success:
        return
    if response.status_code >= 500 and response.status_code not in _STATUS_MAP:
        raise ServerError.from_response(response)
    raise NoxusApiError.from_response(response)


class NoxusPluginError(NoxusError):
    """Base class for errors raised by plugin code."""


class IntegrationFailedError(NoxusPluginError):
    """An integration/API call failed — bad credentials, connectivity, or an
    error returned by the upstream service. Use this (not a bare Exception) so
    the message reads as a user-actionable integration problem."""


class UnexpectedError(NoxusPluginError):
    """An unexpected failure inside plugin code that the author did not
    anticipate."""
