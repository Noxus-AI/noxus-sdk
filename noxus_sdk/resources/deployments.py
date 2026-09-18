"""Deployments: publish an agent to a channel (embed widget, Slack, form, ...).

    dep = client.deployments.create(
        agent_id, channel_type="embed_widget", name="Website widget"
    )
    client.deployments.activate(agent_id, dep["id"])

Channel-specific config goes in ``config`` and is validated server-side; call
``client.deployments.list_channels()`` to discover the available channel types.
"""

from __future__ import annotations

import builtins
from collections.abc import AsyncIterator, Iterator
from typing import Any

from noxus_sdk.resources.base import BaseService


class DeploymentService(BaseService[dict]):
    def list_channels(self) -> builtins.list[dict]:
        """Metadata for every deployment channel available to this workspace."""
        return self.client.get("/v1/channels")

    async def alist_channels(self) -> builtins.list[dict]:
        return await self.client.aget("/v1/channels")

    def list(self, agent_id: str) -> builtins.list[dict]:
        """Every deployment of an agent."""
        return self.client.get(f"/v1/agents/{agent_id}/deployments")

    async def alist(self, agent_id: str) -> builtins.list[dict]:
        return await self.client.aget(f"/v1/agents/{agent_id}/deployments")

    def get(self, agent_id: str, deployment_id: str) -> dict:
        return self.client.get(f"/v1/agents/{agent_id}/deployments/{deployment_id}")

    async def aget(self, agent_id: str, deployment_id: str) -> dict:
        return await self.client.aget(
            f"/v1/agents/{agent_id}/deployments/{deployment_id}"
        )

    def create(
        self,
        agent_id: str,
        *,
        channel_type: str,
        name: str | None = None,
        alias: str | None = None,
        config: dict[str, Any] | None = None,
        assistant_version_id: str | None = None,
    ) -> dict:
        return self.client.post(
            f"/v1/agents/{agent_id}/deployments",
            self._create_body(channel_type, name, alias, config, assistant_version_id),
        )

    async def acreate(
        self,
        agent_id: str,
        *,
        channel_type: str,
        name: str | None = None,
        alias: str | None = None,
        config: dict[str, Any] | None = None,
        assistant_version_id: str | None = None,
    ) -> dict:
        return await self.client.apost(
            f"/v1/agents/{agent_id}/deployments",
            self._create_body(channel_type, name, alias, config, assistant_version_id),
        )

    def update(self, agent_id: str, deployment_id: str, body: dict[str, Any]) -> dict:
        """Patch a deployment. Only the keys present in ``body`` change; pass
        ``alias: None`` to clear the alias."""
        return self.client.patch(
            f"/v1/agents/{agent_id}/deployments/{deployment_id}", body
        )

    async def aupdate(
        self, agent_id: str, deployment_id: str, body: dict[str, Any]
    ) -> dict:
        return await self.client.apatch(
            f"/v1/agents/{agent_id}/deployments/{deployment_id}", body
        )

    def delete(self, agent_id: str, deployment_id: str) -> bool:
        return self.client.delete(f"/v1/agents/{agent_id}/deployments/{deployment_id}")[
            "success"
        ]

    async def adelete(self, agent_id: str, deployment_id: str) -> bool:
        return (
            await self.client.adelete(
                f"/v1/agents/{agent_id}/deployments/{deployment_id}"
            )
        )["success"]

    def activate(self, agent_id: str, deployment_id: str) -> dict:
        """Publish the deployment (builds its trigger). Needs a pinned version."""
        return self.client.post(
            f"/v1/agents/{agent_id}/deployments/{deployment_id}/activate"
        )

    async def aactivate(self, agent_id: str, deployment_id: str) -> dict:
        return await self.client.apost(
            f"/v1/agents/{agent_id}/deployments/{deployment_id}/activate"
        )

    def deactivate(self, agent_id: str, deployment_id: str) -> dict:
        return self.client.post(
            f"/v1/agents/{agent_id}/deployments/{deployment_id}/deactivate"
        )

    async def adeactivate(self, agent_id: str, deployment_id: str) -> dict:
        return await self.client.apost(
            f"/v1/agents/{agent_id}/deployments/{deployment_id}/deactivate"
        )

    def list_events(
        self, agent_id: str, deployment_id: str, *, page: int = 1, page_size: int = 10
    ) -> builtins.list[dict]:
        """A page of events the deployment's trigger has received."""
        return self.client.pget(
            f"/v1/agents/{agent_id}/deployments/{deployment_id}/events",
            page=page,
            page_size=page_size,
        )

    async def alist_events(
        self, agent_id: str, deployment_id: str, *, page: int = 1, page_size: int = 10
    ) -> builtins.list[dict]:
        return await self.client.apget(
            f"/v1/agents/{agent_id}/deployments/{deployment_id}/events",
            page=page,
            page_size=page_size,
        )

    def iter_events(
        self, agent_id: str, deployment_id: str, *, page_size: int = 100
    ) -> Iterator[dict]:
        page = 1
        while True:
            batch = self.list_events(
                agent_id, deployment_id, page=page, page_size=page_size
            )
            if not batch:
                return
            yield from batch
            if len(batch) < page_size:
                return
            page += 1

    async def aiter_events(
        self, agent_id: str, deployment_id: str, *, page_size: int = 100
    ) -> AsyncIterator[dict]:
        page = 1
        while True:
            batch = await self.alist_events(
                agent_id, deployment_id, page=page, page_size=page_size
            )
            if not batch:
                return
            for event in batch:
                yield event
            if len(batch) < page_size:
                return
            page += 1

    @staticmethod
    def _create_body(
        channel_type: str,
        name: str | None,
        alias: str | None,
        config: dict[str, Any] | None,
        assistant_version_id: str | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"channel_type": channel_type, "config": config or {}}
        if name is not None:
            body["name"] = name
        if alias is not None:
            body["alias"] = alias
        if assistant_version_id is not None:
            body["assistant_version_id"] = assistant_version_id
        return body
