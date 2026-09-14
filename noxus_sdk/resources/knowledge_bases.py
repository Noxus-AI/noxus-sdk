import builtins
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeAlias

import aiofiles
from pydantic import BaseModel, ConfigDict, Field

from noxus_sdk.resources._exports import (
    ExportFormat,
    ImportMode,
    import_body,
    import_params,
)
from noxus_sdk.resources.base import BaseResource, BaseService
from noxus_sdk.resources.runs import Run

if TYPE_CHECKING:
    from noxus_sdk.client import HttpxFile


RunStatus = Literal["queued", "running", "failed", "completed", "stopped"]
DocumentStatus = Literal["trained", "training", "error", "uploaded", "folder"]

# Every non-folder document status, used to enumerate "all documents".
_DOCUMENT_STATUSES: tuple[DocumentStatus, ...] = (
    "trained",
    "training",
    "error",
    "uploaded",
)


def _statuses_to_iter(
    status: DocumentStatus | None, *, include_folders: bool
) -> tuple[DocumentStatus, ...]:
    if status is not None:
        return (status,)
    if include_folders:
        return (*_DOCUMENT_STATUSES, "folder")
    return _DOCUMENT_STATUSES


SourceType = Literal[
    "document", "google_drive", "onedrive", "sharepoint", "website", "custom"
]

RunID: TypeAlias = str


def _prune(body: dict[str, Any]) -> dict[str, Any]:
    """Drop unset fields so a PATCH only sends what the caller asked to change."""
    return {k: v for k, v in body.items() if v is not None}


class File(BaseModel):
    name: str
    size: int
    content_type: str
    source_type: str
    uri: str


class GoogleFile(BaseModel):
    id: str
    name: str
    mime_type: str
    size: int


class OneDriveFile(BaseModel):
    id: str
    name: str
    size: int
    web_url: str


class WebsiteWithDepth(BaseModel):
    url: str
    depth: int = 1


# Base document source config
class BaseDocumentSourceConfig(BaseModel):
    pass


# Regular document source config
class SpotFileConfig(BaseDocumentSourceConfig):
    files: list[File]


# Upload document source config
class UploadFileConfig(BaseDocumentSourceConfig):
    name: str
    content: bytes
    content_type: str


# Document source with discriminated union
class DocumentSourceConfig(BaseModel):
    files: builtins.list[File]


class DocumentSource(BaseModel):
    config: DocumentSourceConfig
    source_type: Literal["document"] = "document"
    subtype: str | None = None


class Source(BaseModel):
    source: DocumentSource


class KnowledgeBaseIngestion(BaseModel):
    batch_size: int
    default_chunk_size: int
    default_chunk_overlap: int
    enrich_chunks_mode: Literal["inject_summary", "contextual"] = "contextual"
    enrich_pre_made_qa: bool


class KnowledgeBaseRetrieval(BaseModel):
    type: Literal[
        "full_text_search", "semantic_search", "hybrid_search", "hybrid_reranking"
    ] = "hybrid_reranking"
    hybrid_settings: dict
    reranker_settings: dict


class KnowledgeBaseHybridSettings(BaseModel):
    fts_weight: float


class KnowledgeBaseSettings(BaseModel):
    ingestion: KnowledgeBaseIngestion
    retrieval: KnowledgeBaseRetrieval


class KBConfigV3(BaseModel):
    embedding_model: list[str] = Field(
        default=["vertexai/text-multilingual-embedding-002"],
        min_length=1,
    )
    default_chunk_size: int = 2048
    default_chunk_overlap: int = 512
    csv_row_as_document: bool = True


class KnowledgeBaseDocument(BaseModel):
    id: str
    name: str
    prefix: str
    status: DocumentStatus
    size: int = 0
    source_type: str | None = None
    file_id: str | None = None
    content_type: str | None = None
    created_at: str
    updated_at: str
    error: dict | None = None


class DocumentResult(BaseModel):
    id: str
    created_at: str
    updated_at: str
    group_id: str
    kb_id: str
    file_id: str | None = None
    name: str
    status: DocumentStatus
    short_summary: str | None = None
    summary: str | None = None
    doc_type: str | None = None
    doc_metadata: dict
    prefix: str
    m_source_type: str
    m_source_metadata: dict | None = None


class SearchResult(BaseModel):
    score: float
    content: str
    source: str | None = None
    document_source: DocumentResult


class CreateDocument(BaseModel):
    name: str
    prefix: str = "/"
    status: str = "uploaded"
    # source_type: str = "document"


class UpdateDocument(BaseModel):
    prefix: str | None = None
    status: DocumentStatus | None = None


class KnowledgeBase(BaseResource):
    model_config = ConfigDict(validate_assignment=True)

    id: str
    group_id: str
    name: str
    status: str
    description: str
    document_types: builtins.list[str]
    kb_type: str
    size: int
    num_docs: int
    created_at: str
    updated_at: str
    total_documents: int
    training_documents: int
    trained_documents: int
    error_documents: int
    uploaded_documents: int
    source_types: dict
    training_source_types: builtins.list[str]
    settings_: KnowledgeBaseSettings | KBConfigV3
    retrieval: dict | None = None
    error: dict | None = None
    embeddings: dict | None = None
    documents: builtins.list[KnowledgeBaseDocument] = []
    version: Literal["v2", "v3"] = "v3"

    def refresh(self) -> "KnowledgeBase":
        response = self.client.get(f"/v1/knowledge-bases/{self.id}")
        for key, value in response.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    async def arefresh(self) -> "KnowledgeBase":
        response = await self.client.aget(f"/v1/knowledge-bases/{self.id}")
        for key, value in response.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def delete(self) -> bool:
        response = self.client.delete(f"/v1/knowledge-bases/{self.id}")
        return response["success"]

    async def adelete(self) -> bool:
        response = await self.client.adelete(f"/v1/knowledge-bases/{self.id}")
        return response["success"]

    def get_runs(
        self, status: RunStatus | None = None, run_ids: str | None = None
    ) -> builtins.list[Run]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if run_ids:
            params["run_ids"] = run_ids

        response = self.client.get(f"/v1/knowledge-bases/{self.id}/runs", params=params)
        return [Run(client=self.client, **run) for run in response]

    async def aget_runs(
        self, status: RunStatus | None = None, run_ids: str | None = None
    ) -> builtins.list[Run]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if run_ids:
            params["run_ids"] = run_ids

        response = await self.client.aget(
            f"/v1/knowledge-bases/{self.id}/runs", params=params
        )
        return [Run(client=self.client, **run) for run in response]

    def get_document(self, document_id: str) -> KnowledgeBaseDocument:
        response = self.client.get(
            f"/v1/knowledge-bases/{self.id}/document/{document_id}"
        )
        return KnowledgeBaseDocument(**response)

    async def aget_document(self, document_id: str) -> KnowledgeBaseDocument:
        response = await self.client.aget(
            f"/v1/knowledge-bases/{self.id}/document/{document_id}"
        )
        return KnowledgeBaseDocument(**response)

    def create_document(self, document: CreateDocument) -> KnowledgeBaseDocument:
        response = self.client.post(
            f"/v1/knowledge-bases/{self.id}/document", body=document.model_dump()
        )
        return KnowledgeBaseDocument(**response)

    async def acreate_document(self, document: CreateDocument) -> KnowledgeBaseDocument:
        response = await self.client.apost(
            f"/v1/knowledge-bases/{self.id}/document", body=document.model_dump()
        )
        return KnowledgeBaseDocument(**response)

    def upload_document(
        self, files: builtins.list[str | Path], prefix: str = "/"
    ) -> builtins.list[RunID]:
        files_list: builtins.list[HttpxFile] = []
        for file in files:
            with open(str(file), "rb") as f:
                files_list.append(("files", (Path(file).name, f.read(), None)))

        return self.client.post(  # type: ignore[return-value]
            f"/v1/knowledge-bases/{self.id}/upload_train",
            files=files_list,
            params={"prefix": prefix},
        )

    async def aupload_document(
        self, files: builtins.list[str | Path], prefix: str = "/"
    ) -> builtins.list[RunID]:
        files_list: builtins.list[HttpxFile] = []
        for file in files:
            async with aiofiles.open(str(file), "rb") as f:
                content = await f.read()
                files_list.append(("files", (Path(file).name, content, None)))

        return await self.client.apost(  # type: ignore[return-value]
            f"/v1/knowledge-bases/{self.id}/upload_train",
            files=files_list,
            params={"prefix": prefix},
        )

    def get_tree(self, folder: str = "/", max_depth: int = 3) -> str:
        response = self.client.get(
            f"/v1/knowledge-bases/{self.id}/tree",
            params={"folder": folder, "max_depth": max_depth},
        )
        return response  # type: ignore[return-value]

    async def aget_tree(self, folder: str = "/", max_depth: int = 3) -> str:
        response = await self.client.aget(
            f"/v1/knowledge-bases/{self.id}/tree",
            params={"folder": folder, "max_depth": max_depth},
        )
        return response  # type: ignore[return-value]

    def list_folder(self, folder: str = "/") -> str:
        response = self.client.get(
            f"/v1/knowledge-bases/{self.id}/ls",
            params={"folder": folder},
        )
        return response  # type: ignore[return-value]

    async def alist_folder(self, folder: str = "/") -> str:
        response = await self.client.aget(
            f"/v1/knowledge-bases/{self.id}/ls",
            params={"folder": folder},
        )
        return response  # type: ignore[return-value]

    def search_documents(
        self, query: str, prefix: str | None = None, limit: int = 25
    ) -> builtins.list[KnowledgeBaseDocument]:
        params: dict[str, str | int] = {"query": query, "limit": limit}
        if prefix is not None:
            params["prefix"] = prefix
        response = self.client.get(
            f"/v1/knowledge-bases/{self.id}/documents/search",
            params=params,
        )
        return [KnowledgeBaseDocument(**doc) for doc in response]

    async def asearch_documents(
        self, query: str, prefix: str | None = None, limit: int = 25
    ) -> builtins.list[KnowledgeBaseDocument]:
        params: dict[str, str | int] = {"query": query, "limit": limit}
        if prefix is not None:
            params["prefix"] = prefix
        response = await self.client.aget(
            f"/v1/knowledge-bases/{self.id}/documents/search",
            params=params,
        )
        return [KnowledgeBaseDocument(**doc) for doc in response]

    def search(self, query: str, prefix: str = "/") -> builtins.list[SearchResult]:
        response = self.client.post(
            f"/v1/knowledge-bases/{self.id}/search",
            params={"query": query, "prefix": prefix},
        )
        return [SearchResult(**result) for result in response]

    async def asearch(
        self, query: str, prefix: str = "/"
    ) -> builtins.list[SearchResult]:
        response = await self.client.apost(
            f"/v1/knowledge-bases/{self.id}/search",
            params={"query": query, "prefix": prefix},
        )
        return [SearchResult(**result) for result in response]

    def update_document(
        self, document_id: str, update: UpdateDocument
    ) -> KnowledgeBaseDocument:
        response = self.client.patch(
            f"/v1/knowledge-bases/{self.id}/document/{document_id}",
            update.model_dump(exclude_none=True),
        )
        return KnowledgeBaseDocument(**response)

    async def aupdate_document(
        self, document_id: str, update: UpdateDocument
    ) -> KnowledgeBaseDocument:
        response = await self.client.apatch(
            f"/v1/knowledge-bases/{self.id}/document/{document_id}",
            update.model_dump(exclude_none=True),
        )
        return KnowledgeBaseDocument(**response)

    def delete_document(self, document_id: str) -> KnowledgeBaseDocument:
        response = self.client.delete(
            f"/v1/knowledge-bases/{self.id}/document/{document_id}"
        )
        return KnowledgeBaseDocument(**response)

    async def adelete_document(self, document_id: str) -> KnowledgeBaseDocument:
        response = await self.client.adelete(
            f"/v1/knowledge-bases/{self.id}/document/{document_id}"
        )
        return KnowledgeBaseDocument(**response)

    def _documents_page(
        self, status: DocumentStatus, page: int, page_size: int
    ) -> builtins.list[KnowledgeBaseDocument]:
        response = self.client.get(
            f"/v1/knowledge-bases/{self.id}/documents/{status}",
            params={"page": page, "page_size": page_size},
        )
        return [KnowledgeBaseDocument(**doc) for doc in response["items"]]

    async def _adocuments_page(
        self, status: DocumentStatus, page: int, page_size: int
    ) -> builtins.list[KnowledgeBaseDocument]:
        response = await self.client.aget(
            f"/v1/knowledge-bases/{self.id}/documents/{status}",
            params={"page": page, "page_size": page_size},
        )
        return [KnowledgeBaseDocument(**doc) for doc in response["items"]]

    def iter_documents(
        self,
        status: DocumentStatus | None = None,
        *,
        page_size: int = 100,
        include_folders: bool = False,
    ) -> Iterator[KnowledgeBaseDocument]:
        """Yield every document, auto-paginating.

        With ``status=None`` iterates across every document status (folders are
        excluded unless ``include_folders`` is set).
        """
        for st in _statuses_to_iter(status, include_folders=include_folders):
            page = 1
            while True:
                batch = self._documents_page(st, page, page_size)
                yield from batch
                if len(batch) < page_size:
                    break
                page += 1

    async def aiter_documents(
        self,
        status: DocumentStatus | None = None,
        *,
        page_size: int = 100,
        include_folders: bool = False,
    ) -> AsyncIterator[KnowledgeBaseDocument]:
        for st in _statuses_to_iter(status, include_folders=include_folders):
            page = 1
            while True:
                batch = await self._adocuments_page(st, page, page_size)
                for doc in batch:
                    yield doc
                if len(batch) < page_size:
                    break
                page += 1

    def list_documents(
        self,
        status: DocumentStatus | None = None,
        page: int = 1,
        page_size: int = 10,
        *,
        include_folders: bool = False,
    ) -> builtins.list[KnowledgeBaseDocument]:
        """List documents.

        Pass a ``status`` for a single page (legacy behaviour); pass ``None`` to
        return every document across all statuses and pages.
        """
        if status is not None:
            return self._documents_page(status, page, page_size)
        return list(
            self.iter_documents(page_size=page_size, include_folders=include_folders)
        )

    async def alist_documents(
        self,
        status: DocumentStatus | None = None,
        page: int = 1,
        page_size: int = 10,
        *,
        include_folders: bool = False,
    ) -> builtins.list[KnowledgeBaseDocument]:
        if status is not None:
            return await self._adocuments_page(status, page, page_size)
        return [
            doc
            async for doc in self.aiter_documents(
                page_size=page_size, include_folders=include_folders
            )
        ]


class KnowledgeBaseService(BaseService[KnowledgeBase]):
    def list(self, page: int = 1, page_size: int = 10) -> builtins.list[KnowledgeBase]:
        knowledge_bases = self.client.pget(
            "/v1/knowledge-bases",
            params={"page": page, "page_size": page_size},
            page=page,
            page_size=page_size,
        )
        return [
            KnowledgeBase(client=self.client, **knowledge_base)
            for knowledge_base in knowledge_bases
        ]

    async def alist(
        self, page: int = 1, page_size: int = 10
    ) -> builtins.list[KnowledgeBase]:
        knowledge_bases = await self.client.apget(
            "/v1/knowledge-bases",
            params={"page": page, "page_size": page_size},
            page=page,
            page_size=page_size,
        )
        return [
            KnowledgeBase(client=self.client, **knowledge_base)
            for knowledge_base in knowledge_bases
        ]

    def get(self, knowledge_base_id: str) -> KnowledgeBase:
        knowledge_base = self.client.get(f"/v1/knowledge-bases/{knowledge_base_id}")
        return KnowledgeBase(client=self.client, **knowledge_base)

    async def aget(self, knowledge_base_id: str) -> KnowledgeBase:
        knowledge_base = await self.client.aget(
            f"/v1/knowledge-bases/{knowledge_base_id}"
        )
        return KnowledgeBase(client=self.client, **knowledge_base)

    def create(
        self,
        name: str,
        description: str,
        document_types: builtins.list[str],
        settings_: KnowledgeBaseSettings | KBConfigV3,
        version: Literal["v2", "v3"] = "v3",
    ) -> KnowledgeBase:
        knowledge_base = self.client.post(
            "/v1/knowledge-bases",
            {
                "name": name,
                "description": description,
                "document_types": document_types,
                "settings_": settings_.model_dump(),
                "kb_type": "entity",
                "version": version,
            },
        )
        return KnowledgeBase(client=self.client, **knowledge_base)

    async def acreate(
        self,
        name: str,
        description: str,
        document_types: builtins.list[str],
        settings_: KnowledgeBaseSettings | KBConfigV3,
        version: Literal["v2", "v3"] = "v3",
    ) -> KnowledgeBase:
        knowledge_base = await self.client.apost(
            "/v1/knowledge-bases",
            {
                "name": name,
                "description": description,
                "document_types": document_types,
                "settings_": settings_.model_dump(),
                "kb_type": "entity",
                "version": version,
            },
        )

        return KnowledgeBase(client=self.client, **knowledge_base)

    def search(
        self, knowledge_base_id: str, query: str, prefix: str = "/"
    ) -> builtins.list[SearchResult]:
        response = self.client.post(
            f"/v1/knowledge-bases/{knowledge_base_id}/search",
            params={"query": query, "prefix": prefix},
        )
        return [SearchResult(**result) for result in response]

    async def asearch(
        self, knowledge_base_id: str, query: str, prefix: str = "/"
    ) -> builtins.list[SearchResult]:
        response = await self.client.apost(
            f"/v1/knowledge-bases/{knowledge_base_id}/search",
            params={"query": query, "prefix": prefix},
        )
        return [SearchResult(**result) for result in response]

    def delete(self, knowledge_base_id: str) -> bool:
        response = self.client.delete(f"/v1/knowledge-bases/{knowledge_base_id}")
        return response["success"]

    async def adelete(self, knowledge_base_id: str) -> bool:
        response = await self.client.adelete(f"/v1/knowledge-bases/{knowledge_base_id}")
        return response["success"]

    def get_tree(
        self, knowledge_base_id: str, folder: str = "/", max_depth: int = 3
    ) -> str:
        response = self.client.get(
            f"/v1/knowledge-bases/{knowledge_base_id}/tree",
            params={"folder": folder, "max_depth": max_depth},
        )
        return response  # type: ignore[return-value]

    async def aget_tree(
        self, knowledge_base_id: str, folder: str = "/", max_depth: int = 3
    ) -> str:
        response = await self.client.aget(
            f"/v1/knowledge-bases/{knowledge_base_id}/tree",
            params={"folder": folder, "max_depth": max_depth},
        )
        return response  # type: ignore[return-value]

    def list_folder(self, knowledge_base_id: str, folder: str = "/") -> str:
        response = self.client.get(
            f"/v1/knowledge-bases/{knowledge_base_id}/ls",
            params={"folder": folder},
        )
        return response  # type: ignore[return-value]

    async def alist_folder(self, knowledge_base_id: str, folder: str = "/") -> str:
        response = await self.client.aget(
            f"/v1/knowledge-bases/{knowledge_base_id}/ls",
            params={"folder": folder},
        )
        return response  # type: ignore[return-value]

    def search_documents(
        self,
        knowledge_base_id: str,
        query: str,
        prefix: str | None = None,
        limit: int = 25,
    ) -> builtins.list[KnowledgeBaseDocument]:
        params: dict[str, str | int] = {"query": query, "limit": limit}
        if prefix is not None:
            params["prefix"] = prefix
        response = self.client.get(
            f"/v1/knowledge-bases/{knowledge_base_id}/documents/search",
            params=params,
        )
        return [KnowledgeBaseDocument(**doc) for doc in response]

    async def asearch_documents(
        self,
        knowledge_base_id: str,
        query: str,
        prefix: str | None = None,
        limit: int = 25,
    ) -> builtins.list[KnowledgeBaseDocument]:
        params: dict[str, str | int] = {"query": query, "limit": limit}
        if prefix is not None:
            params["prefix"] = prefix
        response = await self.client.aget(
            f"/v1/knowledge-bases/{knowledge_base_id}/documents/search",
            params=params,
        )
        return [KnowledgeBaseDocument(**doc) for doc in response]

    def get_runs(
        self,
        knowledge_base_id: str,
        status: RunStatus | None = None,
        run_ids: str | None = None,
    ) -> builtins.list[Run]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if run_ids:
            params["run_ids"] = run_ids

        response = self.client.get(
            f"/v1/knowledge-bases/{knowledge_base_id}/runs", params=params
        )
        return [Run(client=self.client, **run) for run in response]

    async def aget_runs(
        self,
        knowledge_base_id: str,
        status: RunStatus | None = None,
        run_ids: str | None = None,
    ) -> builtins.list[Run]:
        params: dict[str, str] = {}
        if status:
            params["status"] = status
        if run_ids:
            params["run_ids"] = run_ids

        response = await self.client.aget(
            f"/v1/knowledge-bases/{knowledge_base_id}/runs", params=params
        )
        return [Run(client=self.client, **run) for run in response]

    def get_document(
        self, knowledge_base_id: str, document_id: str
    ) -> KnowledgeBaseDocument:
        response = self.client.get(
            f"/v1/knowledge-bases/{knowledge_base_id}/document/{document_id}"
        )
        return KnowledgeBaseDocument(**response)

    async def aget_document(
        self, knowledge_base_id: str, document_id: str
    ) -> KnowledgeBaseDocument:
        response = await self.client.aget(
            f"/v1/knowledge-bases/{knowledge_base_id}/document/{document_id}"
        )
        return KnowledgeBaseDocument(**response)

    def download_document(self, knowledge_base_id: str, document_id: str) -> bytes:
        document = self.get_document(knowledge_base_id, document_id)
        if document.file_id is None:
            raise ValueError(f"Document {document_id} has no downloadable file")
        return self.client.files.get(document.file_id)

    async def adownload_document(
        self, knowledge_base_id: str, document_id: str
    ) -> bytes:
        document = await self.aget_document(knowledge_base_id, document_id)
        if document.file_id is None:
            raise ValueError(f"Document {document_id} has no downloadable file")
        return await self.client.files.aget(document.file_id)

    def update_document(
        self, knowledge_base_id: str, document_id: str, update: UpdateDocument
    ) -> KnowledgeBaseDocument:
        response = self.client.patch(
            f"/v1/knowledge-bases/{knowledge_base_id}/document/{document_id}",
            update.model_dump(exclude_none=True),
        )
        return KnowledgeBaseDocument(**response)

    async def aupdate_document(
        self, knowledge_base_id: str, document_id: str, update: UpdateDocument
    ) -> KnowledgeBaseDocument:
        response = await self.client.apatch(
            f"/v1/knowledge-bases/{knowledge_base_id}/document/{document_id}",
            update.model_dump(exclude_none=True),
        )
        return KnowledgeBaseDocument(**response)

    def delete_document(
        self, knowledge_base_id: str, document_id: str
    ) -> KnowledgeBaseDocument:
        response = self.client.delete(
            f"/v1/knowledge-bases/{knowledge_base_id}/document/{document_id}"
        )
        return KnowledgeBaseDocument(**response)

    async def adelete_document(
        self, knowledge_base_id: str, document_id: str
    ) -> KnowledgeBaseDocument:
        response = await self.client.adelete(
            f"/v1/knowledge-bases/{knowledge_base_id}/document/{document_id}"
        )
        return KnowledgeBaseDocument(**response)

    def _documents_page(
        self,
        knowledge_base_id: str,
        status: DocumentStatus,
        page: int,
        page_size: int,
    ) -> builtins.list[KnowledgeBaseDocument]:
        response = self.client.get(
            f"/v1/knowledge-bases/{knowledge_base_id}/documents/{status}",
            params={"page": page, "page_size": page_size},
        )
        return [KnowledgeBaseDocument(**doc) for doc in response["items"]]

    async def _adocuments_page(
        self,
        knowledge_base_id: str,
        status: DocumentStatus,
        page: int,
        page_size: int,
    ) -> builtins.list[KnowledgeBaseDocument]:
        response = await self.client.aget(
            f"/v1/knowledge-bases/{knowledge_base_id}/documents/{status}",
            params={"page": page, "page_size": page_size},
        )
        return [KnowledgeBaseDocument(**doc) for doc in response["items"]]

    def iter_documents(
        self,
        knowledge_base_id: str,
        status: DocumentStatus | None = None,
        *,
        page_size: int = 100,
        include_folders: bool = False,
    ) -> Iterator[KnowledgeBaseDocument]:
        """Yield every document in a knowledge base, auto-paginating."""
        for st in _statuses_to_iter(status, include_folders=include_folders):
            page = 1
            while True:
                batch = self._documents_page(knowledge_base_id, st, page, page_size)
                yield from batch
                if len(batch) < page_size:
                    break
                page += 1

    async def aiter_documents(
        self,
        knowledge_base_id: str,
        status: DocumentStatus | None = None,
        *,
        page_size: int = 100,
        include_folders: bool = False,
    ) -> AsyncIterator[KnowledgeBaseDocument]:
        for st in _statuses_to_iter(status, include_folders=include_folders):
            page = 1
            while True:
                batch = await self._adocuments_page(
                    knowledge_base_id, st, page, page_size
                )
                for doc in batch:
                    yield doc
                if len(batch) < page_size:
                    break
                page += 1

    def list_documents(
        self,
        knowledge_base_id: str,
        status: DocumentStatus | None = None,
        page: int = 1,
        page_size: int = 10,
        *,
        include_folders: bool = False,
    ) -> builtins.list[KnowledgeBaseDocument]:
        """List documents; ``status=None`` returns every document across all statuses."""
        if status is not None:
            return self._documents_page(knowledge_base_id, status, page, page_size)
        return list(
            self.iter_documents(
                knowledge_base_id,
                page_size=page_size,
                include_folders=include_folders,
            )
        )

    async def alist_documents(
        self,
        knowledge_base_id: str,
        status: DocumentStatus | None = None,
        page: int = 1,
        page_size: int = 10,
        *,
        include_folders: bool = False,
    ) -> builtins.list[KnowledgeBaseDocument]:
        if status is not None:
            return await self._adocuments_page(
                knowledge_base_id, status, page, page_size
            )
        return [
            doc
            async for doc in self.aiter_documents(
                knowledge_base_id,
                page_size=page_size,
                include_folders=include_folders,
            )
        ]

    def create_document(
        self, knowledge_base_id: str, document: CreateDocument
    ) -> KnowledgeBaseDocument:
        response = self.client.post(
            f"/v1/knowledge-bases/{knowledge_base_id}/document",
            body=document.model_dump(),
        )
        return KnowledgeBaseDocument(**response)

    async def acreate_document(
        self, knowledge_base_id: str, document: CreateDocument
    ) -> KnowledgeBaseDocument:
        response = await self.client.apost(
            f"/v1/knowledge-bases/{knowledge_base_id}/document",
            body=document.model_dump(),
        )
        return KnowledgeBaseDocument(**response)

    def train_document(
        self, knowledge_base_id: str, source: Source, prefix: str = "/"
    ) -> builtins.list[RunID]:
        return self.client.post(  # type: ignore[return-value]
            f"/v1/knowledge-bases/{knowledge_base_id}/generic_train",
            body=source.model_dump(),
            params={"prefix": prefix},
        )

    async def atrain_document(
        self, knowledge_base_id: str, source: Source, prefix: str = "/"
    ) -> builtins.list[RunID]:
        return await self.client.apost(  # type: ignore[return-value]
            f"/v1/knowledge-bases/{knowledge_base_id}/generic_train",
            body=source.model_dump(),
            params={"prefix": prefix},
        )

    def upload_document(
        self,
        knowledge_base_id: str,
        files: builtins.list[str | Path],
        prefix: str = "/",
    ) -> builtins.list[RunID]:
        files_list: builtins.list[HttpxFile] = []
        for file in files:
            with open(str(file), "rb") as f:
                files_list.append(("files", (Path(file).name, f.read(), None)))

        return self.client.post(  # type: ignore[return-value]
            f"/v1/knowledge-bases/{knowledge_base_id}/upload_train",
            files=files_list,
            params={"prefix": prefix},
        )

    async def aupload_document(
        self,
        knowledge_base_id: str,
        files: builtins.list[str | Path],
        prefix: str = "/",
    ) -> builtins.list[RunID]:
        files_list: builtins.list[HttpxFile] = []
        for file in files:
            async with aiofiles.open(str(file), "rb") as f:
                content = await f.read()
                files_list.append(("files", (Path(file).name, content, None)))

        return await self.client.apost(  # type: ignore[return-value]
            f"/v1/knowledge-bases/{knowledge_base_id}/upload_train",
            files=files_list,
            params={"prefix": prefix},
        )

    # ── knowledge base updates ─────────────────────────────────────────
    def update(
        self,
        knowledge_base_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        document_types: builtins.list[str] | None = None,
    ) -> KnowledgeBase:
        """Update a knowledge base. Only the fields you pass are sent."""
        body = _prune(
            {
                "name": name,
                "description": description,
                "document_types": document_types,
            }
        )
        response = self.client.patch(f"/v1/knowledge-bases/{knowledge_base_id}", body)
        return KnowledgeBase(client=self.client, **response)

    async def aupdate(
        self,
        knowledge_base_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        document_types: builtins.list[str] | None = None,
    ) -> KnowledgeBase:
        body = _prune(
            {
                "name": name,
                "description": description,
                "document_types": document_types,
            }
        )
        response = await self.client.apatch(
            f"/v1/knowledge-bases/{knowledge_base_id}", body
        )
        return KnowledgeBase(client=self.client, **response)

    # ── ingestion recovery ─────────────────────────────────────────────
    def dismiss_document(
        self, knowledge_base_id: str, document_id: str
    ) -> KnowledgeBaseDocument:
        """Dismiss a failed document so it stops surfacing as an error."""
        response = self.client.patch(
            f"/v1/knowledge-bases/{knowledge_base_id}/document/{document_id}/dismiss",
            {},
        )
        return KnowledgeBaseDocument(**response)

    async def adismiss_document(
        self, knowledge_base_id: str, document_id: str
    ) -> KnowledgeBaseDocument:
        response = await self.client.apatch(
            f"/v1/knowledge-bases/{knowledge_base_id}/document/{document_id}/dismiss",
            {},
        )
        return KnowledgeBaseDocument(**response)

    def retry_document(self, knowledge_base_id: str, document_id: str) -> RunID:
        """Re-run ingestion for one document; returns the new run id."""
        return self.client.post(
            f"/v1/knowledge-bases/{knowledge_base_id}/document/{document_id}/retry"
        )

    async def aretry_document(self, knowledge_base_id: str, document_id: str) -> RunID:
        return await self.client.apost(
            f"/v1/knowledge-bases/{knowledge_base_id}/document/{document_id}/retry"
        )

    def retry_all(self, knowledge_base_id: str) -> builtins.list[RunID]:
        """Re-run ingestion for every failed document; returns the run ids."""
        return self.client.post(f"/v1/knowledge-bases/{knowledge_base_id}/retry_all")

    async def aretry_all(self, knowledge_base_id: str) -> builtins.list[RunID]:
        return await self.client.apost(
            f"/v1/knowledge-bases/{knowledge_base_id}/retry_all"
        )

    def list_ingestion_documents(
        self, knowledge_base_id: str
    ) -> builtins.list[KnowledgeBaseDocument]:
        """Documents currently being ingested."""
        response = self.client.get(
            f"/v1/knowledge-bases/{knowledge_base_id}/documents/ingestion"
        )
        return [KnowledgeBaseDocument(**doc) for doc in response]

    async def alist_ingestion_documents(
        self, knowledge_base_id: str
    ) -> builtins.list[KnowledgeBaseDocument]:
        response = await self.client.aget(
            f"/v1/knowledge-bases/{knowledge_base_id}/documents/ingestion"
        )
        return [KnowledgeBaseDocument(**doc) for doc in response]

    # ── catalog ────────────────────────────────────────────────────────
    def get_mime_types(self) -> builtins.list[dict]:
        """Mime types a knowledge base can ingest."""
        return self.client.get("/v1/knowledge-bases/mime-types")

    async def aget_mime_types(self) -> builtins.list[dict]:
        return await self.client.aget("/v1/knowledge-bases/mime-types")

    def get_types(self) -> builtins.list[dict]:
        """Knowledge base types available to this workspace."""
        return self.client.get("/v1/knowledge-bases/types")

    async def aget_types(self) -> builtins.list[dict]:
        return await self.client.aget("/v1/knowledge-bases/types")

    # ── export / import ────────────────────────────────────────────────
    def export(
        self,
        knowledge_base_id: str,
        *,
        version: ExportFormat = "auto",
        set_active_on_import: bool = False,
    ) -> bytes:
        """Export a knowledge base bundle.

        ``auto`` (the default) emits the legacy base64 bundle for back-compat;
        pass ``v4`` for plaintext multi-doc YAML (.nx) or ``v3`` for base64.
        """
        response = self.client._request(
            "POST",
            f"/v1/knowledge-bases/{knowledge_base_id}/export",
            params={
                "version": version,
                "set_active_on_import": set_active_on_import,
            },
        )
        return response.content

    async def aexport(
        self,
        knowledge_base_id: str,
        *,
        version: ExportFormat = "auto",
        set_active_on_import: bool = False,
    ) -> bytes:
        response = await self.client._arequest(
            "POST",
            f"/v1/knowledge-bases/{knowledge_base_id}/export",
            params={
                "version": version,
                "set_active_on_import": set_active_on_import,
            },
        )
        return response.content

    def import_(
        self,
        definition: str | bytes,
        *,
        version: ExportFormat = "auto",
        mode: ImportMode = "clone",
        activate: bool = False,
        dry_run: bool = False,
    ) -> builtins.list[dict]:
        """Import a bundle produced by ``export``.

        ``dry_run=True`` reports what would land without writing anything.
        """
        return self.client.post(
            "/v1/knowledge-bases/import",
            import_body(definition, version),
            params=import_params(mode, activate, dry_run),
        )

    async def aimport_(
        self,
        definition: str | bytes,
        *,
        version: ExportFormat = "auto",
        mode: ImportMode = "clone",
        activate: bool = False,
        dry_run: bool = False,
    ) -> builtins.list[dict]:
        return await self.client.apost(
            "/v1/knowledge-bases/import",
            import_body(definition, version),
            params=import_params(mode, activate, dry_run),
        )
