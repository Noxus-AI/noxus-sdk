"""Workspace analytics.

from datetime import datetime, timedelta, timezone

end = datetime.now(timezone.utc)
result = client.analytics.get("flow_runs", end - timedelta(days=7), end)
print(result.type, result.value)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from noxus_sdk.resources.base import BaseService

if TYPE_CHECKING:
    from datetime import datetime


class AnalyticsResult(BaseModel):
    """A metric's shape depends on the metric: a scalar, bar charts, or a
    (possibly paginated) table. ``type`` says which."""

    type: str
    value: Any


def _stamp(moment: datetime) -> str:
    if moment.tzinfo is None:
        raise ValueError(
            "time_start/time_end must be timezone-aware; the API rejects naive datetimes"
        )
    return moment.isoformat()


class AnalyticsService(BaseService[AnalyticsResult]):
    def _params(
        self,
        time_start: datetime,
        time_end: datetime,
        page: int | None,
        page_size: int | None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "time_start": _stamp(time_start),
            "time_end": _stamp(time_end),
        }
        if page is not None:
            params["page"] = page
        if page_size is not None:
            params["page_size"] = page_size
        return params

    def get(
        self,
        metric: str,
        time_start: datetime,
        time_end: datetime,
        *,
        page: int | None = None,
        page_size: int | None = None,
    ) -> AnalyticsResult:
        """Query one metric (e.g. "flow_runs") over a time range."""
        response = self.client.get(
            f"/analytics/{metric}",
            params=self._params(time_start, time_end, page, page_size),
        )
        return AnalyticsResult(**response)

    async def aget(
        self,
        metric: str,
        time_start: datetime,
        time_end: datetime,
        *,
        page: int | None = None,
        page_size: int | None = None,
    ) -> AnalyticsResult:
        response = await self.client.aget(
            f"/analytics/{metric}",
            params=self._params(time_start, time_end, page, page_size),
        )
        return AnalyticsResult(**response)
