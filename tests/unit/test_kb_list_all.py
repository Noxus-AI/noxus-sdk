"""Tests for KnowledgeBase.list_documents/iter_documents list-all behaviour."""

from __future__ import annotations

import httpx
import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources.knowledge_bases import (
    _DOCUMENT_STATUSES,
    KnowledgeBase,
)


def _doc(doc_id: str, status: str) -> dict:
    return {
        "id": doc_id,
        "name": f"{doc_id}.pdf",
        "prefix": "/",
        "status": status,
        "size": 1,
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }


def _kb(handler) -> KnowledgeBase:
    client = Client(
        api_key="k",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
    )
    # Only id + client are exercised by the document-listing paths.
    return KnowledgeBase.model_construct(client=client, id="kb1")


def test_list_all_iterates_every_status_and_excludes_folders() -> None:
    seen_statuses: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        status = request.url.path.rsplit("/", 1)[-1]
        seen_statuses.append(status)
        # One doc per status, single page.
        return httpx.Response(200, json={"items": [_doc(status, status)]})

    kb = _kb(handler)
    docs = kb.list_documents()
    assert {d.status for d in docs} == set(_DOCUMENT_STATUSES)
    assert "folder" not in seen_statuses


def test_list_all_paginates_within_a_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        status = request.url.path.rsplit("/", 1)[-1]
        page = int(request.url.params.get("page", "1"))
        if status == "trained" and page == 1:
            items = [_doc(f"t{i}", "trained") for i in range(100)]  # full page
        elif status == "trained" and page == 2:
            items = [_doc("t100", "trained")]  # partial → stop
        else:
            items = []
        return httpx.Response(200, json={"items": items})

    kb = _kb(handler)
    docs = list(kb.iter_documents(status="trained"))
    assert len(docs) == 101


def test_single_status_returns_one_page() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"items": [_doc("a", "uploaded")]})

    kb = _kb(handler)
    docs = kb.list_documents(status="uploaded")
    assert len(docs) == 1
    assert calls["n"] == 1  # no cross-status iteration


@pytest.mark.asyncio
async def test_async_list_all() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        status = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"items": [_doc(status, status)]})

    kb = _kb(handler)
    docs = await kb.alist_documents()
    assert {d.status for d in docs} == set(_DOCUMENT_STATUSES)
    await kb.client.aclose()


# ── service-level parity (what the MCP tools call) ──────────────────────


def _service_client(handler) -> Client:
    return Client(
        api_key="k",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
    )


def test_service_list_all_iterates_every_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        status = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"items": [_doc(status, status)]})

    client = _service_client(handler)
    docs = client.knowledge_bases.list_documents("kb1")
    assert {d.status for d in docs} == set(_DOCUMENT_STATUSES)


def test_service_single_status_is_one_page() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"items": [_doc("a", "trained")]})

    client = _service_client(handler)
    docs = client.knowledge_bases.list_documents("kb1", status="trained")
    assert len(docs) == 1
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_service_aiter_documents_paginates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        status = request.url.path.rsplit("/", 1)[-1]
        page = int(request.url.params.get("page", "1"))
        if status == "trained" and page == 1:
            items = [_doc(f"t{i}", "trained") for i in range(100)]
        elif status == "trained" and page == 2:
            items = [_doc("t100", "trained")]
        else:
            items = []
        return httpx.Response(200, json={"items": items})

    client = _service_client(handler)
    docs = [d async for d in client.knowledge_bases.aiter_documents("kb1")]
    assert len(docs) == 101
    await client.aclose()
