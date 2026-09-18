from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterator, Literal

from pydantic import BaseModel, ConfigDict

from noxus_sdk.resources.base import BaseResource, BaseService

if TYPE_CHECKING:
    import builtins

# Which part of a run `RunService.search` looks in.
SearchIn = Literal["input", "output", "other", "run_id"]


class RunFailureError(Exception):
    pass


class RunDeletion(BaseModel):
    """Outcome of a deletion: ``matched`` finished runs were selected,
    ``succeeded`` of them are gone, ``errors`` maps a run id to why it was
    skipped (still running, purge failure)."""

    succeeded: int
    failed: int
    errors: dict[str, str]
    matched: int


def _older_than_iso(value: datetime | str) -> str:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        raise ValueError("older_than must carry a timezone offset")
    return value.astimezone(timezone.utc).isoformat()


class RunEvent:
    """A single event from a run's SSE stream."""

    def __init__(self, *, type: str, data: dict[str, Any], redis_id: str | None = None):
        self.type = type
        self.data = data
        self.redis_id = redis_id

    @property
    def is_terminal(self) -> bool:
        return self.data.get("workflow_status") in ("completed", "failed")

    def __repr__(self) -> str:
        return f"RunEvent(type={self.type!r}, data={self.data!r})"


class Run(BaseResource):
    model_config = ConfigDict(validate_assignment=True)

    id: str
    group_id: str
    workflow_id: str
    input: dict
    node_ids: list[str] | None = None
    status: str
    progress: int
    progress_details: dict | None = None
    created_at: str
    finished_at: str | None = None
    output: dict | None = None

    def refresh(self) -> Run:
        response = self.client.get(f"/v1/workflows/{self.workflow_id}/runs/{self.id}")
        for key, value in response.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    async def arefresh(self) -> Run:
        response = await self.client.aget(
            f"/v1/workflows/{self.workflow_id}/runs/{self.id}",
        )
        for key, value in response.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def stop(self) -> Run:
        """Stop this run; returns the run in its post-stop state."""
        response = self.client.post(f"/v1/runs/{self.id}/stop")
        return Run(client=self.client, **response)

    async def astop(self) -> Run:
        response = await self.client.apost(f"/v1/runs/{self.id}/stop")
        return Run(client=self.client, **response)

    def data(self, *, fetch_structured_data: bool = True) -> dict:
        """Full run data — per-node inputs/outputs and execution detail."""
        return self.client.get(
            f"/v1/runs/{self.id}/data",
            params={"fetch_structured_data": fetch_structured_data},
        )

    async def adata(self, *, fetch_structured_data: bool = True) -> dict:
        return await self.client.aget(
            f"/v1/runs/{self.id}/data",
            params={"fetch_structured_data": fetch_structured_data},
        )

    def stream(self, etag: str | None = None) -> Iterator[RunEvent]:
        """Stream run events via SSE. Yields RunEvent objects until the run completes."""
        params: dict[str, str] = {}
        if etag:
            params["etag"] = etag

        for sse_event in self.client.event_stream(
            f"/v1/runs/{self.id}/events",
            params=params or None,
        ):
            if sse_event.event != "message":
                continue
            payload = json.loads(sse_event.data)
            event = RunEvent(
                type=payload.get("type", ""),
                data=payload.get("data", {}),
                redis_id=payload.get("redisId"),
            )
            yield event
            if event.is_terminal:
                return

    async def astream(self, etag: str | None = None) -> AsyncIterator[RunEvent]:
        """Stream run events via SSE (async). Yields RunEvent objects until the run completes."""
        params: dict[str, str] = {}
        if etag:
            params["etag"] = etag

        async for sse_event in self.client.aevent_stream(
            f"/v1/runs/{self.id}/events",
            params=params or None,
        ):
            if sse_event.event != "message":
                continue
            payload = json.loads(sse_event.data)
            event = RunEvent(
                type=payload.get("type", ""),
                data=payload.get("data", {}),
                redis_id=payload.get("redisId"),
            )
            yield event
            if event.is_terminal:
                return

    def wait(
        self,
        interval: int = 5,
        *,
        output_only: bool = False,
    ) -> Run | dict | None:
        if self.status in ("failed", "completed", "awaiting_human_feedback"):
            if self.status == "failed":
                raise RunFailureError(self.status)
            return self.output if output_only else self

        # Try SSE stream first — no polling, instant notification
        try:
            for event in self.stream():
                if event.is_terminal:
                    break
        except Exception:
            # Fall back to polling if SSE fails (e.g. older server)
            while self.status not in ("failed", "completed", "awaiting_human_feedback"):
                time.sleep(interval)
                self.refresh()

        # Refresh to get final output/status
        self.refresh()

        if self.status == "failed":
            raise RunFailureError(self.status)

        if output_only:
            return self.output
        return self

    async def a_wait(
        self,
        interval: int = 5,
        *,
        output_only: bool = False,
    ) -> Run | dict | None:
        if self.status in ("failed", "completed", "awaiting_human_feedback"):
            if self.status == "failed":
                raise RunFailureError(self.status)
            return self.output if output_only else self

        # Try SSE stream first — no polling, instant notification
        try:
            async for event in self.astream():
                if event.is_terminal:
                    break
        except Exception:
            # Fall back to polling if SSE fails (e.g. older server)
            while self.status not in ("failed", "completed", "awaiting_human_feedback"):
                await asyncio.sleep(interval)
                await self.arefresh()

        # Refresh to get final output/status
        await self.arefresh()

        if self.status == "failed":
            raise RunFailureError(self.status)

        if output_only:
            return self.output
        return self

    def get_status(self) -> str:
        return self.status

    def delete(self) -> RunDeletion:
        """Delete this finished run with its data. Needs a key carrying
        ``resource:delete_history``."""
        return RunDeletion(**self.client.delete(f"/v1/runs/{self.id}"))

    async def adelete(self) -> RunDeletion:
        return RunDeletion(**await self.client.adelete(f"/v1/runs/{self.id}"))


class RunService(BaseService[Run]):
    def get(self, workflow_id: str, run_id: str) -> Run:
        response = self.client.get(f"/v1/workflows/{workflow_id}/runs/{run_id}")
        return Run(client=self.client, **response)

    async def aget(self, workflow_id: str, run_id: str) -> Run:
        response = await self.client.aget(f"/v1/workflows/{workflow_id}/runs/{run_id}")
        return Run(client=self.client, **response)

    def stop(self, run_id: str) -> Run:
        return Run(client=self.client, **self.client.post(f"/v1/runs/{run_id}/stop"))

    async def astop(self, run_id: str) -> Run:
        response = await self.client.apost(f"/v1/runs/{run_id}/stop")
        return Run(client=self.client, **response)

    def get_data(self, run_id: str, *, fetch_structured_data: bool = True) -> dict:
        return self.client.get(
            f"/v1/runs/{run_id}/data",
            params={"fetch_structured_data": fetch_structured_data},
        )

    async def aget_data(
        self, run_id: str, *, fetch_structured_data: bool = True
    ) -> dict:
        return await self.client.aget(
            f"/v1/runs/{run_id}/data",
            params={"fetch_structured_data": fetch_structured_data},
        )

    def _search_body(
        self,
        query: str,
        limit: int,
        offset: int,
        exact: bool,
        search_in: builtins.list[SearchIn] | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "exact": exact,
        }
        if search_in is not None:
            body["search_in"] = search_in
        return body

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        exact: bool = True,
        search_in: builtins.list[SearchIn] | None = None,
    ) -> builtins.list[dict]:
        """Full-text search across this workspace's run inputs/outputs."""
        response = self.client.post(
            "/v1/runs/search",
            self._search_body(query, limit, offset, exact, search_in),
        )
        return response.get("items", [])

    async def asearch(
        self,
        query: str,
        *,
        limit: int = 10,
        offset: int = 0,
        exact: bool = True,
        search_in: builtins.list[SearchIn] | None = None,
    ) -> builtins.list[dict]:
        response = await self.client.apost(
            "/v1/runs/search",
            self._search_body(query, limit, offset, exact, search_in),
        )
        return response.get("items", [])

    def run_sync(
        self,
        workflow_id: str,
        input: dict,
        *,
        output_only: bool = False,
    ) -> dict:
        """Run a workflow and block until it finishes, returning its output."""
        return self.client.post(
            f"/v1/workflows/{workflow_id}/runs/sync",
            {"input": input},
            params={"output_only": output_only},
        )

    async def arun_sync(
        self,
        workflow_id: str,
        input: dict,
        *,
        output_only: bool = False,
    ) -> dict:
        return await self.client.apost(
            f"/v1/workflows/{workflow_id}/runs/sync",
            {"input": input},
            params={"output_only": output_only},
        )

    def _delete_body(
        self,
        run_ids: builtins.list[str] | None,
        older_than: datetime | str | None,
        workflow_id: str | None,
        expected_count: int | None,
        dry_run: bool,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"dry_run": dry_run}
        if run_ids:
            body["run_ids"] = list(run_ids)
        filters: dict[str, str] = {}
        if older_than is not None:
            filters["to_date"] = _older_than_iso(older_than)
        if workflow_id is not None:
            filters["workflow_id"] = workflow_id
        if filters:
            body["filters"] = filters
        if expected_count is not None:
            body["expected_count"] = expected_count
        return body

    def delete(self, run_id: str) -> RunDeletion:
        """Delete one finished run with its data (inputs, outputs, logs,
        traces, files only it references). Needs a key carrying
        ``resource:delete_history``, which only a platform administrator can
        grant. A run still in flight is reported under ``errors``."""
        return RunDeletion(**self.client.delete(f"/v1/runs/{run_id}"))

    async def adelete(self, run_id: str) -> RunDeletion:
        return RunDeletion(**await self.client.adelete(f"/v1/runs/{run_id}"))

    def bulk_delete(
        self,
        *,
        run_ids: builtins.list[str] | None = None,
        older_than: datetime | str | None = None,
        workflow_id: str | None = None,
        expected_count: int | None = None,
        dry_run: bool = False,
    ) -> RunDeletion:
        """Delete finished runs by id, or every finished run created before
        ``older_than`` (optionally of one ``workflow_id``). ``dry_run=True``
        only counts; ``expected_count`` refuses with HTTP 409 when the count
        changed since a preview. Usage analytics and billing are unaffected."""
        return RunDeletion(
            **self.client.post(
                "/v1/runs/bulk/delete",
                self._delete_body(
                    run_ids, older_than, workflow_id, expected_count, dry_run
                ),
            )
        )

    async def abulk_delete(
        self,
        *,
        run_ids: builtins.list[str] | None = None,
        older_than: datetime | str | None = None,
        workflow_id: str | None = None,
        expected_count: int | None = None,
        dry_run: bool = False,
    ) -> RunDeletion:
        return RunDeletion(
            **await self.client.apost(
                "/v1/runs/bulk/delete",
                self._delete_body(
                    run_ids, older_than, workflow_id, expected_count, dry_run
                ),
            )
        )

    def get_node_io(self, run_id: str, node_id: str, it: int = 0) -> dict:
        """Per-node IO for one iteration. ``it`` is the server's 1-based
        iteration; 0 (the default) is accepted as the first."""
        return self.client.get(f"/v1/runs/{run_id}/io/{node_id}", params={"it": it})

    async def aget_node_io(self, run_id: str, node_id: str, it: int = 0) -> dict:
        return await self.client.aget(
            f"/v1/runs/{run_id}/io/{node_id}", params={"it": it}
        )

    def list(
        self, workflow_id: str, page: int = 1, page_size: int = 10
    ) -> builtins.list[Run]:
        response = self.client.pget(
            f"/v1/workflows/{workflow_id}/runs",
            params={"page": page, "page_size": page_size},
        )
        return [Run(client=self.client, **run) for run in response]

    async def alist(
        self,
        workflow_id: str,
        page: int = 1,
        page_size: int = 10,
    ) -> builtins.list[Run]:
        response = await self.client.apget(
            f"/v1/workflows/{workflow_id}/runs",
            params={"page": page, "page_size": page_size},
            page=page,
            page_size=page_size,
        )
        return [Run(client=self.client, **run) for run in response]
