"""Document download path: file_id parsing and the get_document → files.get chain."""

from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources.files import FileService
from noxus_sdk.resources.knowledge_bases import (
    KnowledgeBaseDocument,
    KnowledgeBaseService,
)


def _client():
    client = create_autospec(Client, instance=True)
    client.files = create_autospec(FileService, instance=True)
    return client


def _backend_document(**overrides) -> dict:
    doc = {
        "id": str(uuid4()),
        "summary": None,
        "short_summary": None,
        "doc_type": None,
        "source_type": "Document",
        "source_external_id": None,
        "source_metadata": None,
        "content_type": "application/pdf",
        "has_conversion": False,
        "status": "trained",
        "doc_metadata": {},
        "error": None,
        "name": "report.pdf",
        "prefix": "/",
        "uri": None,
        "updated_at": "2026-06-04T00:00:00Z",
        "created_at": "2026-06-04T00:00:00Z",
        "size": 1234,
        "file_id": str(uuid4()),
        "run_id": None,
        "dismissed": None,
        "warnings": None,
        "needs_reingestion": None,
    }
    doc.update(overrides)
    return doc


def test_document_parses_file_id_and_content_type():
    payload = _backend_document()
    doc = KnowledgeBaseDocument(**payload)
    assert doc.file_id == payload["file_id"]
    assert doc.content_type == "application/pdf"


def test_document_without_file_id_defaults_to_none():
    payload = _backend_document()
    del payload["file_id"]
    del payload["content_type"]
    doc = KnowledgeBaseDocument(**payload)
    assert doc.file_id is None
    assert doc.content_type is None


def test_download_document_returns_file_bytes():
    client = _client()
    payload = _backend_document()
    client.get.return_value = payload
    client.files.get.return_value = b"%PDF-1.7 raw bytes"

    kb_id = str(uuid4())
    content = KnowledgeBaseService(client).download_document(kb_id, payload["id"])

    assert content == b"%PDF-1.7 raw bytes"
    client.get.assert_called_once_with(
        f"/v1/knowledge-bases/{kb_id}/document/{payload['id']}"
    )
    client.files.get.assert_called_once_with(payload["file_id"])


def test_download_document_without_file_raises():
    client = _client()
    payload = _backend_document(file_id=None)
    client.get.return_value = payload

    with pytest.raises(ValueError, match="no downloadable file"):
        KnowledgeBaseService(client).download_document(str(uuid4()), payload["id"])
    client.files.get.assert_not_called()


@pytest.mark.anyio
async def test_adownload_document_returns_file_bytes():
    client = _client()
    payload = _backend_document()
    client.aget.return_value = payload
    client.files.aget.return_value = b"async bytes"

    content = await KnowledgeBaseService(client).adownload_document(
        str(uuid4()), payload["id"]
    )

    assert content == b"async bytes"
    client.files.aget.assert_awaited_once_with(payload["file_id"])


@pytest.fixture
def anyio_backend():
    return "asyncio"
