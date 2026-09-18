from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from noxus_sdk.client import Client

_RESULT = {"succeeded": 1, "failed": 0, "errors": {}, "matched": 1}


def _client(handler) -> Client:
    return Client(
        api_key="k",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
    )


def test_delete_one_run() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        return httpx.Response(200, json=_RESULT)

    result = _client(handler).runs.delete("r-1")
    assert (captured["method"], captured["path"]) == ("DELETE", "/v1/runs/r-1")
    assert result.succeeded == 1 and result.matched == 1


def test_bulk_delete_sends_older_than_as_utc() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={**_RESULT, "succeeded": 0, "matched": 3})

    cutoff = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=2)))
    result = _client(handler).runs.bulk_delete(
        older_than=cutoff, workflow_id="wf-1", expected_count=3, dry_run=True
    )
    assert captured["path"] == "/v1/runs/bulk/delete"
    assert captured["body"] == {
        "dry_run": True,
        "filters": {"to_date": "2026-01-01T10:00:00+00:00", "workflow_id": "wf-1"},
        "expected_count": 3,
    }
    assert result.matched == 3


def test_bulk_delete_by_ids() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_RESULT)

    _client(handler).runs.bulk_delete(run_ids=["a", "b"])
    assert captured["body"] == {"dry_run": False, "run_ids": ["a", "b"]}


def test_bulk_delete_rejects_naive_older_than() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not reach the server")

    with pytest.raises(ValueError, match="timezone"):
        _client(handler).runs.bulk_delete(older_than=datetime(2026, 1, 1, 12))
    with pytest.raises(ValueError, match="timezone"):
        _client(handler).runs.bulk_delete(older_than="2026-01-01T12:00:00")


def test_bulk_delete_normalises_offset_strings_to_utc() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json=_RESULT)

    _client(handler).runs.bulk_delete(older_than="2026-01-01T12:00:00+02:00")
    assert captured["body"]["filters"]["to_date"] == "2026-01-01T10:00:00+00:00"
