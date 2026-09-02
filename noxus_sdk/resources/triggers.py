"""Triggers: read a workflow's triggers and browse the events they receive.

    for trigger in client.triggers.list("workflow-id"):
        for event in client.triggers.iter_events("workflow-id", trigger["id"]):
            print(event)

Creating and editing triggers is not yet part of the public API; use the app.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import Any

from noxus_sdk.resources.base import BaseService


class TriggerService(BaseService[dict]):
    def list(
        self, workflow_id: str, page: int = 1, page_size: int = 10
    ) -> builtins.list[dict]:
        """List a workflow's triggers."""
        return self.client.pget(
            f"/v1/workflows/{workflow_id}/triggers", page=page, page_size=page_size
        )

    async def alist(
        self, workflow_id: str, page: int = 1, page_size: int = 10
    ) -> builtins.list[dict]:
        return await self.client.apget(
            f"/v1/workflows/{workflow_id}/triggers", page=page, page_size=page_size
        )

    def list_events(
        self,
        workflow_id: str,
        trigger_id: str,
        *,
        search: str | None = None,
        errored: bool | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> builtins.list[dict]:
        """A page of events a specific trigger has received."""
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        if errored is not None:
            params["errored"] = errored
        return self.client.pget(
            f"/v1/workflows/{workflow_id}/triggers/{trigger_id}/events",
            params=params,
            page=page,
            page_size=page_size,
        )

    async def alist_events(
        self,
        workflow_id: str,
        trigger_id: str,
        *,
        search: str | None = None,
        errored: bool | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> builtins.list[dict]:
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        if errored is not None:
            params["errored"] = errored
        return await self.client.apget(
            f"/v1/workflows/{workflow_id}/triggers/{trigger_id}/events",
            params=params,
            page=page,
            page_size=page_size,
        )

    def iter_events(
        self,
        workflow_id: str,
        trigger_id: str,
        *,
        search: str | None = None,
        errored: bool | None = None,
        page_size: int = 100,
    ) -> Iterator[dict]:
        """Yield every event for a trigger, auto-paginating."""
        page = 1
        while True:
            batch = self.list_events(
                workflow_id,
                trigger_id,
                search=search,
                errored=errored,
                page=page,
                page_size=page_size,
            )
            yield from batch
            if len(batch) < page_size:
                return
            page += 1

    async def aiter_events(
        self,
        workflow_id: str,
        trigger_id: str,
        *,
        search: str | None = None,
        errored: bool | None = None,
        page_size: int = 100,
    ) -> AsyncIterator[dict]:
        page = 1
        while True:
            batch = await self.alist_events(
                workflow_id,
                trigger_id,
                search=search,
                errored=errored,
                page=page,
                page_size=page_size,
            )
            for event in batch:
                yield event
            if len(batch) < page_size:
                return
            page += 1

    def events(
        self,
        *,
        search: str | None = None,
        event_type: str | None = None,
        workflow_id: str | None = None,
        started_run: bool | None = None,
        errored: bool | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> builtins.list[dict]:
        """Browse every trigger event in the workspace, across all triggers."""
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        if event_type is not None:
            params["event_type"] = event_type
        if workflow_id is not None:
            params["workflow_id"] = workflow_id
        if started_run is not None:
            params["started_run"] = started_run
        if errored is not None:
            params["errored"] = errored
        return self.client.pget(
            "/v1/triggers/events", params=params, page=page, page_size=page_size
        )

    async def aevents(
        self,
        *,
        search: str | None = None,
        event_type: str | None = None,
        workflow_id: str | None = None,
        started_run: bool | None = None,
        errored: bool | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> builtins.list[dict]:
        params: dict[str, Any] = {}
        if search is not None:
            params["search"] = search
        if event_type is not None:
            params["event_type"] = event_type
        if workflow_id is not None:
            params["workflow_id"] = workflow_id
        if started_run is not None:
            params["started_run"] = started_run
        if errored is not None:
            params["errored"] = errored
        return await self.client.apget(
            "/v1/triggers/events", params=params, page=page, page_size=page_size
        )

    def create(
        self, workflow_id: str, definition: dict, workflow_version_id: str
    ) -> dict:
        """Create a trigger on a workflow (attributed to this API key)."""
        return self.client.post(
            f"/v1/workflows/{workflow_id}/triggers",
            {"definition": definition, "workflow_version_id": workflow_version_id},
        )

    async def acreate(
        self, workflow_id: str, definition: dict, workflow_version_id: str
    ) -> dict:
        return await self.client.apost(
            f"/v1/workflows/{workflow_id}/triggers",
            {"definition": definition, "workflow_version_id": workflow_version_id},
        )

    def update(
        self,
        workflow_id: str,
        trigger_id: str,
        definition: dict,
        *,
        workflow_version_id: str | None = None,
    ) -> dict:
        """Update a trigger's definition."""
        body: dict[str, Any] = {"definition": definition}
        if workflow_version_id is not None:
            body["workflow_version_id"] = workflow_version_id
        return self.client.patch(
            f"/v1/workflows/{workflow_id}/triggers/{trigger_id}", body
        )

    async def aupdate(
        self,
        workflow_id: str,
        trigger_id: str,
        definition: dict,
        *,
        workflow_version_id: str | None = None,
    ) -> dict:
        body: dict[str, Any] = {"definition": definition}
        if workflow_version_id is not None:
            body["workflow_version_id"] = workflow_version_id
        return await self.client.apatch(
            f"/v1/workflows/{workflow_id}/triggers/{trigger_id}", body
        )

    def delete(self, trigger_id: str) -> bool:
        """Delete a trigger by id."""
        return self.client.delete(f"/v1/triggers/{trigger_id}")["success"]

    async def adelete(self, trigger_id: str) -> bool:
        return (await self.client.adelete(f"/v1/triggers/{trigger_id}"))["success"]
