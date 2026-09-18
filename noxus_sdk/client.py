from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING, Any, BinaryIO, cast

import httpx
from httpx_sse import ServerSentEvent, aconnect_sse, connect_sse

from noxus_sdk.errors import (
    NoxusApiError,
    RateLimitedError,
    RequestFailedError,
    raise_for_status,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

FileContent = BinaryIO | bytes | str
HttpxFile = tuple[str, tuple[str, FileContent, str | None]]
RequestFiles = dict[str, Any] | list[HttpxFile] | None

DEFAULT_TIMEOUT = 120
DEFAULT_MAX_RETRIES = 5
_MAX_BACKOFF_SECONDS = 30.0

__all__ = [
    "Client",
    "NoxusApiError",
    "RateLimitedError",
    "RequestFailedError",
    "Requester",
]


class Requester:
    def __init__(
        self,
        api_key: str,
        extra_headers: dict | None = None,
        *,
        base_url: str | None = None,
        transport: httpx.BaseTransport | httpx.AsyncBaseTransport | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self.api_key = api_key
        self.extra_headers = extra_headers
        # Explicit argument > NOXUS_BACKEND_URL > production default, resolved
        # at construction time so env changes after import still apply.
        self.base_url = base_url or os.environ.get(
            "NOXUS_BACKEND_URL", "https://backend.noxus.ai"
        )
        self._transport = transport
        self._max_retries = max_retries
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    # ── client lifecycle ────────────────────────────────────────────────
    def _http(self) -> httpx.Client:
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                transport=cast("httpx.BaseTransport | None", self._transport),
                follow_redirects=True,
            )
        return self._sync_client

    def _ahttp(self) -> httpx.AsyncClient:
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                transport=cast("httpx.AsyncBaseTransport | None", self._transport),
                follow_redirects=True,
            )
        return self._async_client

    def close(self) -> None:
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    async def aclose(self) -> None:
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def __enter__(self) -> Requester:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    async def __aenter__(self) -> Requester:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    # ── request helpers ─────────────────────────────────────────────────
    def _headers(self, headers: dict | None) -> dict:
        headers_ = {"X-API-Key": self.api_key}
        if headers:
            headers_.update(headers)
        if self.extra_headers:
            headers_.update(self.extra_headers)
        return headers_

    def _backoff_seconds(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), _MAX_BACKOFF_SECONDS)
            except ValueError:
                pass
        return min(2.0**attempt, _MAX_BACKOFF_SECONDS)

    async def _arequest(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        json: dict | None = None,
        files: RequestFiles = None,
        params: dict | None = None,
        timeout: int | None = None,
    ) -> httpx.Response:
        headers_ = self._headers(headers)
        client = self._ahttp()
        for attempt in range(self._max_retries + 1):
            response = await client.request(
                method,
                f"{self.base_url}{url}",
                headers=headers_,
                json=json,
                files=files,
                params=params,
                timeout=timeout or DEFAULT_TIMEOUT,
            )
            if response.status_code == 429 and attempt < self._max_retries:
                await asyncio.sleep(self._backoff_seconds(response, attempt))
                continue
            raise_for_status(response)
            return response
        raise RateLimitedError("Rate limit exceeded", status_code=429)

    async def arequest(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        json: dict | None = None,
        files: RequestFiles = None,
        params: dict | None = None,
        timeout: int | None = None,
    ) -> dict:
        return (
            await self._arequest(
                method,
                url,
                headers=headers,
                json=json,
                files=files,
                params=params,
                timeout=timeout,
            )
        ).json()

    async def aget(
        self,
        url: str,
        headers: dict | None = None,
        params: dict | None = None,
        timeout: int | None = None,
    ) -> Any:  # noqa: ANN401
        return await self.arequest(
            "GET",
            url,
            headers=headers,
            params=params,
            timeout=timeout,
        )

    async def apget(
        self,
        url: str,
        headers: dict | None = None,
        params: dict | None = None,
        page: int = 1,
        page_size: int = 10,
        timeout: int | None = None,
    ) -> list[dict]:
        params_ = params or {}
        params_["page"] = params_.get("page", page)
        params_["size"] = params_.get("page_size", page_size)
        result = await self.arequest(
            "GET",
            url,
            headers=headers,
            params=params_,
            timeout=timeout,
        )
        if "items" not in result:
            return []
        return result["items"]

    async def apost(
        self,
        url: str,
        body: Any | None = None,  # noqa: ANN401
        headers: dict | None = None,
        files: RequestFiles = None,
        params: dict | None = None,
        timeout: int | None = None,
    ) -> dict:
        return await self.arequest(
            "POST",
            url,
            json=body,
            headers=headers,
            files=files,
            params=params,
            timeout=timeout,
        )

    async def apatch(
        self,
        url: str,
        body: Any,  # noqa: ANN401
        headers: dict | None = None,
        timeout: int | None = None,
        params: dict | None = None,
    ) -> dict:
        return await self.arequest(
            "PATCH",
            url,
            json=body,
            headers=headers,
            timeout=timeout,
            params=params,
        )

    async def adelete(
        self,
        url: str,
        headers: dict | None = None,
        timeout: int | None = None,
    ) -> dict:
        return await self.arequest("DELETE", url, headers=headers, timeout=timeout)

    def _request(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        json: dict | None = None,
        files: RequestFiles = None,
        params: dict | None = None,
        timeout: int | None = None,
    ) -> httpx.Response:
        headers_ = self._headers(headers)
        client = self._http()
        for attempt in range(self._max_retries + 1):
            response = client.request(
                method,
                f"{self.base_url}{url}",
                headers=headers_,
                json=json,
                files=files,
                params=params,
                timeout=timeout or DEFAULT_TIMEOUT,
            )
            if response.status_code == 429 and attempt < self._max_retries:
                time.sleep(self._backoff_seconds(response, attempt))
                continue
            raise_for_status(response)
            return response
        raise RateLimitedError("Rate limit exceeded", status_code=429)

    def request(
        self,
        method: str,
        url: str,
        headers: dict | None = None,
        json: dict | None = None,
        files: RequestFiles = None,
        params: dict | None = None,
        timeout: int | None = None,
    ) -> dict:
        response = self._request(
            method,
            url,
            headers=headers,
            json=json,
            files=files,
            params=params,
            timeout=timeout,
        )
        return response.json()

    def event_stream(
        self,
        url: str,
        headers: dict | None = None,
        json: dict | None = None,
        files: RequestFiles = None,
        params: dict | None = None,
        timeout: int | None = None,
        method: str = "GET",
    ) -> Iterator[ServerSentEvent]:
        headers_ = self._headers(headers)
        client = self._http()
        for attempt in range(self._max_retries + 1):
            with connect_sse(
                client=client,
                method=method,
                url=f"{self.base_url}{url}",
                headers=headers_,
                json=json,
                files=files,
                params=params,
                timeout=timeout or DEFAULT_TIMEOUT,
            ) as response:
                if response.response.status_code == 429 and attempt < self._max_retries:
                    time.sleep(self._backoff_seconds(response.response, attempt))
                    continue
                if not response.response.is_success:
                    response.response.read()
                raise_for_status(response.response)
                yield from response.iter_sse()
                return
        raise RateLimitedError("Rate limit exceeded", status_code=429)

    async def aevent_stream(
        self,
        url: str,
        headers: dict | None = None,
        json: dict | None = None,
        files: RequestFiles = None,
        params: dict | None = None,
        timeout: int | None = None,
        method: str = "GET",
    ) -> AsyncIterator[ServerSentEvent]:
        headers_ = self._headers(headers)
        client = self._ahttp()
        for attempt in range(self._max_retries + 1):
            async with aconnect_sse(
                client=client,
                method=method,
                url=f"{self.base_url}{url}",
                headers=headers_,
                json=json,
                files=files,
                params=params,
                timeout=timeout or DEFAULT_TIMEOUT,
            ) as response:
                if response.response.status_code == 429 and attempt < self._max_retries:
                    await asyncio.sleep(
                        self._backoff_seconds(response.response, attempt)
                    )
                    continue
                if not response.response.is_success:
                    await response.response.aread()
                raise_for_status(response.response)
                async for event in response.aiter_sse():
                    yield event
                return
        raise RateLimitedError("Rate limit exceeded", status_code=429)

    def get(
        self,
        url: str,
        headers: dict | None = None,
        params: dict | None = None,
        timeout: int | None = None,
    ) -> Any:  # noqa: ANN401
        return self.request("GET", url, headers=headers, params=params, timeout=timeout)

    def pget(
        self,
        url: str,
        headers: dict | None = None,
        params: dict | None = None,
        page: int = 1,
        page_size: int = 10,
        timeout: int | None = None,
    ) -> list[dict]:
        params_ = params or {}
        params_["page"] = params_.get("page", page)
        params_["size"] = params_.get("page_size", page_size)
        result = self.request(
            "GET",
            url,
            headers=headers,
            params=params_,
            timeout=timeout,
        )
        if "items" not in result:
            return []
        return result["items"]

    def patch(
        self,
        url: str,
        body: Any,  # noqa: ANN401
        headers: dict | None = None,
        timeout: int | None = None,
        params: dict | None = None,
    ) -> Any:  # noqa: ANN401
        return self.request(
            "PATCH",
            url,
            json=body,
            headers=headers,
            timeout=timeout,
            params=params,
        )

    def post(
        self,
        url: str,
        body: Any | None = None,  # noqa: ANN401
        headers: dict | None = None,
        files: RequestFiles = None,
        params: dict | None = None,
        timeout: int | None = None,
    ) -> Any:  # noqa: ANN401
        return self.request(
            "POST",
            url,
            json=body,
            headers=headers,
            files=files,
            params=params,
            timeout=timeout,
        )

    def delete(
        self,
        url: str,
        headers: dict | None = None,
        timeout: int | None = None,
    ) -> Any:  # noqa: ANN401
        return self.request("DELETE", url, headers=headers, timeout=timeout)


class Client(Requester):
    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        extra_headers: dict | None = None,
        *,
        load_nodes: bool = True,
        load_me: bool = True,
        transport: httpx.BaseTransport | httpx.AsyncBaseTransport | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        from noxus_sdk.resources.admin import AdminService
        from noxus_sdk.resources.agentflows import AgentFlowService
        from noxus_sdk.resources.analytics import AnalyticsService
        from noxus_sdk.resources.insights import InsightService
        from noxus_sdk.resources.assistants import AgentService
        from noxus_sdk.resources.conversations import ConversationService
        from noxus_sdk.resources.deployments import DeploymentService
        from noxus_sdk.resources.evaluations import EvaluationService
        from noxus_sdk.resources.files import FileService
        from noxus_sdk.resources.knowledge_bases import KnowledgeBaseService
        from noxus_sdk.resources.runs import RunService
        from noxus_sdk.resources.sandboxes import SandboxService
        from noxus_sdk.resources.tables import TableService
        from noxus_sdk.resources.triggers import TriggerService
        from noxus_sdk.resources.variables import VariableService
        from noxus_sdk.resources.workflows import WorkflowService
        from noxus_sdk.workflows import load_node_catalog, set_node_types

        # Explicit argument wins; NOXUS_BACKEND_URL only fills the default
        # (via the Requester class attribute) when no base_url is passed.
        super().__init__(
            api_key,
            extra_headers,
            base_url=base_url,
            transport=transport,
            max_retries=max_retries,
        )

        if load_nodes:
            # Raw response bytes feed a digest-memoized decode+parse — the
            # 16MB catalog is decoded and validated once per process, not
            # once per Client.
            response = self._request("GET", "/v1/nodes")
            self.nodes, parsed = load_node_catalog(response.content)
            set_node_types(parsed)
        else:
            self.nodes = []

        self.workflows = WorkflowService(self)
        self.agentflows = AgentFlowService(self)
        self.agents = AgentService(self)
        self.conversations = ConversationService(self)
        self.knowledge_bases = KnowledgeBaseService(self)
        self.runs = RunService(self)
        self.evaluations = EvaluationService(self)
        self.admin = AdminService(self, enabled=bool(not load_me))
        self.files = FileService(self)
        self.sandboxes = SandboxService(self)
        self.tables = TableService(self)
        self.triggers = TriggerService(self)
        self.deployments = DeploymentService(self)
        self.variables = VariableService(self)
        self.analytics = AnalyticsService(self)
        self.insights = InsightService(self)
        if load_me:
            self.admin.enabled = self.admin.get_me().tenant_admin

    @classmethod
    def from_env(
        cls,
        *,
        load_nodes: bool = True,
        load_me: bool = True,
    ) -> Client:
        """Build a client from ``NOXUS_API_KEY`` / ``NOXUS_BACKEND_URL``."""
        api_key = os.environ.get("NOXUS_API_KEY")
        if not api_key:
            raise ValueError("NOXUS_API_KEY is not set")
        base_url = os.environ.get("NOXUS_BACKEND_URL", "https://backend.noxus.ai")
        return cls(
            api_key=api_key,
            base_url=base_url,
            load_nodes=load_nodes,
            load_me=load_me,
        )

    def get_nodes(self) -> list[dict]:
        return self.get("/v1/nodes")

    async def aget_nodes(self) -> list[dict]:
        return await self.aget("/v1/nodes")

    def get_models(self) -> list[dict]:
        return self.get("/v1/models/llms")

    async def aget_models(self) -> list[dict]:
        return await self.aget("/v1/models/llms")

    def get_chat_presets(self) -> list[dict]:
        return self.get("/v1/models/llms/presets")

    async def aget_chat_presets(self) -> list[dict]:
        return await self.aget("/v1/models/llms/presets")
