"""Agent insight dashboards.

Read-only analytics for an agent — topics, sentiment, CSAT, funnel, and the
conversations behind any of them. Every method takes an agent id and returns
the raw dashboard payload as a dict.

    ins = client.insights
    print(ins.csat_score(agent_id, days=30))
    for topic in ins.top_topics(agent_id)["items"]:
        print(topic)
"""

from __future__ import annotations

from typing import Any, Literal

from noxus_sdk.resources.base import BaseService

MessageLength = Literal["short", "medium", "long"]
DrilldownKind = Literal["topic", "subtopic", "driver", "custom", "cx"]


def _window(
    days: int,
    deployment_id: str | None,
    message_length: MessageLength | None,
    **extra: Any,
) -> dict[str, Any]:
    params: dict[str, Any] = {"days": days, **extra}
    if deployment_id is not None:
        params["deployment_id"] = deployment_id
    if message_length is not None:
        params["message_length"] = message_length
    return params


class InsightService(BaseService[dict]):
    def _base(self, agent_id: str) -> str:
        return f"/v1/agents/{agent_id}/insights"

    # ── dashboards ─────────────────────────────────────────────────────
    def sentiment_over_time(
        self,
        agent_id: str,
        *,
        days: int = 7,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        return self.client.get(
            f"{self._base(agent_id)}/sentiment-over-time",
            params=_window(days, deployment_id, message_length),
        )

    def rating_drivers(
        self,
        agent_id: str,
        *,
        days: int = 7,
        limit: int = 8,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        return self.client.get(
            f"{self._base(agent_id)}/rating-drivers",
            params=_window(days, deployment_id, message_length, limit=limit),
        )

    def custom_insights(
        self,
        agent_id: str,
        *,
        days: int = 7,
        limit: int = 20,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        return self.client.get(
            f"{self._base(agent_id)}/custom-insights",
            params=_window(days, deployment_id, message_length, limit=limit),
        )

    def top_topics(
        self,
        agent_id: str,
        *,
        days: int = 7,
        limit: int = 10,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        return self.client.get(
            f"{self._base(agent_id)}/top-topics",
            params=_window(days, deployment_id, message_length, limit=limit),
        )

    def sub_topics(
        self,
        agent_id: str,
        *,
        days: int = 7,
        parent: str | None = None,
        limit: int = 20,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        params = _window(days, deployment_id, message_length, limit=limit)
        if parent is not None:
            params["parent"] = parent
        return self.client.get(f"{self._base(agent_id)}/sub-topics", params=params)

    def noticed(self, agent_id: str, *, limit: int = 12) -> dict:
        return self.client.get(
            f"{self._base(agent_id)}/noticed", params={"limit": limit}
        )

    def conversation_funnel(
        self,
        agent_id: str,
        *,
        days: int = 7,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        return self.client.get(
            f"{self._base(agent_id)}/conversation-funnel",
            params=_window(days, deployment_id, message_length),
        )

    def csat_score(
        self,
        agent_id: str,
        *,
        days: int = 7,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        return self.client.get(
            f"{self._base(agent_id)}/csat-score",
            params=_window(days, deployment_id, message_length),
        )

    def conversations(
        self,
        agent_id: str,
        *,
        kind: DrilldownKind,
        key: str,
        days: int = 7,
        limit: int = 20,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        """The conversations behind a clicked insight value (topic, CX rating, …)."""
        return self.client.get(
            f"{self._base(agent_id)}/conversations",
            params=_window(
                days, deployment_id, message_length, kind=kind, key=key, limit=limit
            ),
        )

    def bootstrap_status(self, agent_id: str) -> dict:
        """Whether enough data exists to show the insights dashboard."""
        return self.client.get(f"{self._base(agent_id)}/bootstrap")

    # ── async ──────────────────────────────────────────────────────────
    async def asentiment_over_time(
        self,
        agent_id: str,
        *,
        days: int = 7,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        return await self.client.aget(
            f"{self._base(agent_id)}/sentiment-over-time",
            params=_window(days, deployment_id, message_length),
        )

    async def atop_topics(
        self,
        agent_id: str,
        *,
        days: int = 7,
        limit: int = 10,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        return await self.client.aget(
            f"{self._base(agent_id)}/top-topics",
            params=_window(days, deployment_id, message_length, limit=limit),
        )

    async def acsat_score(
        self,
        agent_id: str,
        *,
        days: int = 7,
        deployment_id: str | None = None,
        message_length: MessageLength | None = None,
    ) -> dict:
        return await self.client.aget(
            f"{self._base(agent_id)}/csat-score",
            params=_window(days, deployment_id, message_length),
        )

    async def abootstrap_status(self, agent_id: str) -> dict:
        return await self.client.aget(f"{self._base(agent_id)}/bootstrap")
