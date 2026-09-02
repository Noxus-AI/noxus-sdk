"""Tests for the KB service methods that the public API exposed but the SDK
never wrapped: update, dismiss/retry, ingestion list, catalog, export/import."""

from __future__ import annotations

import json

import httpx
import pytest

from noxus_sdk.client import Client

_DOC = {
    "id": "d-1",
    "name": "a.pdf",
    "prefix": "/",
    "status": "error",
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00",
}

_KB = {
    "id": "kb1",
    "group_id": "g1",
    "name": "new",
    "status": "trained",
    "description": "d",
    "document_types": ["pdf"],
    "kb_type": "default",
    "size": 0,
    "num_docs": 0,
    "created_at": "2024-01-01T00:00:00",
    "updated_at": "2024-01-01T00:00:00",
    "total_documents": 0,
    "training_documents": 0,
    "trained_documents": 0,
    "error_documents": 0,
    "uploaded_documents": 0,
    "source_types": {},
    "training_source_types": [],
    "settings_": {
        "embedding_model": ["vertexai/text-multilingual-embedding-002"],
        "default_chunk_size": 2048,
        "default_chunk_overlap": 512,
        "csv_row_as_document": True,
    },
}


def _client(handler) -> Client:
    return Client(
        api_key="k",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
    )


def _body(request: httpx.Request) -> dict:
    return json.loads(request.content.decode())


def test_update_sends_only_provided_fields() -> None:
    """A PATCH must not clobber fields the caller never mentioned."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        return httpx.Response(200, json=_KB)

    kb = _client(handler).knowledge_bases.update("kb1", name="new")
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/v1/knowledge-bases/kb1"
    assert captured["body"] == {"name": "new"}
    assert kb.name == "new"


def test_update_can_send_several_fields() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = _body(request)
        return httpx.Response(200, json=_KB)

    _client(handler).knowledge_bases.update(
        "kb1", name="new", description="d", document_types=["pdf"]
    )
    assert captured["body"] == {
        "name": "new",
        "description": "d",
        "document_types": ["pdf"],
    }


def test_dismiss_document() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        return httpx.Response(200, json=_DOC)

    doc = _client(handler).knowledge_bases.dismiss_document("kb1", "d-1")
    assert captured["method"] == "PATCH"
    assert captured["path"] == "/v1/knowledge-bases/kb1/document/d-1/dismiss"
    assert doc.id == "d-1"


def test_retry_document_returns_run_id() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        return httpx.Response(200, json="run-123")

    assert _client(handler).knowledge_bases.retry_document("kb1", "d-1") == "run-123"
    assert captured["path"] == "/v1/knowledge-bases/kb1/document/d-1/retry"


def test_retry_all_returns_run_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/knowledge-bases/kb1/retry_all"
        return httpx.Response(200, json=["r1", "r2"])

    assert _client(handler).knowledge_bases.retry_all("kb1") == ["r1", "r2"]


def test_list_ingestion_documents() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/knowledge-bases/kb1/documents/ingestion"
        return httpx.Response(200, json=[_DOC])

    docs = _client(handler).knowledge_bases.list_ingestion_documents("kb1")
    assert [d.id for d in docs] == ["d-1"]


def test_catalog_endpoints() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/mime-types"):
            return httpx.Response(200, json=[{"mime_type": "application/pdf"}])
        return httpx.Response(200, json=[{"name": "custom"}])

    kb = _client(handler).knowledge_bases
    assert kb.get_mime_types() == [{"mime_type": "application/pdf"}]
    assert kb.get_types() == [{"name": "custom"}]


def test_export_defaults_to_auto_and_returns_bytes() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, content=b"bundle-bytes")

    data = _client(handler).knowledge_bases.export("kb1")
    assert captured["path"] == "/v1/knowledge-bases/kb1/export"
    assert captured["params"]["version"] == "auto"
    assert captured["params"]["set_active_on_import"] == "false"
    assert data == b"bundle-bytes"


def test_export_v4_is_opt_in() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, content=b"yaml")

    _client(handler).knowledge_bases.export("kb1", version="v4")
    assert captured["params"]["version"] == "v4"


def test_import_sends_definition_and_flags() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["body"] = _body(request)
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json=[{"id": "kb2"}])

    result = _client(handler).knowledge_bases.import_(
        "base64data", mode="replace", activate=True, dry_run=True
    )
    assert captured["path"] == "/v1/knowledge-bases/import"
    assert captured["body"] == {"definition": "base64data", "version": "auto"}
    assert captured["params"] == {
        "mode": "replace",
        "activate": "true",
        "dry_run": "true",
    }
    assert result == [{"id": "kb2"}]


def test_import_accepts_bytes_from_export() -> None:
    """export() returns bytes; import_() should take them without ceremony."""
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = _body(request)
        return httpx.Response(200, json=[])

    _client(handler).knowledge_bases.import_(b"raw-bundle")
    assert captured["body"]["definition"] == "raw-bundle"


@pytest.mark.asyncio
async def test_async_retry_and_export() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/export"):
            return httpx.Response(200, content=b"bytes")
        return httpx.Response(200, json=["r1"])

    client = _client(handler)
    assert await client.knowledge_bases.aretry_all("kb1") == ["r1"]
    assert await client.knowledge_bases.aexport("kb1") == b"bytes"
    await client.aclose()
