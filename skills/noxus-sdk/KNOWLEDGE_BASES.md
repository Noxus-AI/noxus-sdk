# Knowledge Bases

`client.knowledge_bases` manages KBs and their documents: ingestion (upload &
train), listing, semantic search, and export/import. A KB stores documents as
vectors so agents and workflows can retrieve from them.

## Create a KB

Use a **v3** config (the current format). `KBConfigV3` has sensible defaults, so
you usually only set the embedding model if you need a specific one.

```python
from noxus_sdk.resources.knowledge_bases import KBConfigV3

kb = client.knowledge_bases.create(
    name="Product Docs",
    description="Everything about the product",
    document_types=["pdf", "docx", "txt", "md"],
    settings_=KBConfigV3(),          # defaults: multilingual embeddings, 2048/512 chunks
    version="v3",
)
print(kb.id)
```

`KBConfigV3` fields: `embedding_model: list[str]`
(default `["vertexai/text-multilingual-embedding-002"]`), `default_chunk_size`
(2048), `default_chunk_overlap` (512), `csv_row_as_document` (True).

## Manage KBs

```python
client.knowledge_bases.list(page=1, page_size=10)     # -> list[KnowledgeBase]
client.knowledge_bases.get(kb_id)
client.knowledge_bases.update(kb_id, name=None, description=None, document_types=None)
client.knowledge_bases.delete(kb_id)                  # -> bool
```

## Adding documents

**Upload local files** (they ingest & train asynchronously — returns run ids):

```python
run_ids = client.knowledge_bases.upload_document(
    kb_id, files=["./guide.pdf", "./faq.md"], prefix="/manuals"
)
# wait for ingestion to finish:
for run in client.knowledge_bases.get_runs(kb_id, run_ids=",".join(run_ids)):
    run.wait()
```

**Train from a source** (URL / connector / etc. via a `Source`):

```python
from noxus_sdk.resources.knowledge_bases import Source
client.knowledge_bases.train_document(kb_id, source=Source(...), prefix="/")
```

**Create a bare document row** (e.g. a folder or a placeholder):

```python
from noxus_sdk.resources.knowledge_bases import CreateDocument
doc = client.knowledge_bases.create_document(
    kb_id, CreateDocument(name="notes.txt", prefix="/misc")
)
```

## Listing & iterating documents

`status` is one of `trained | training | error | uploaded | folder`. Omit it to
list **all** statuses (the SDK loops them for you). Prefer the iterator to walk
every document without hand-rolling pages:

```python
# one page, one status
client.knowledge_bases.list_documents(kb_id, status="trained", page=1, page_size=10)

# every document, every status, auto-paginated
for doc in client.knowledge_bases.iter_documents(kb_id):
    print(doc.name, doc.status, doc.size, doc.content_type)

# only documents mid-ingestion
client.knowledge_bases.list_ingestion_documents(kb_id)
```

`KnowledgeBaseDocument` fields: `id`, `name`, `prefix`, `status`, `size`,
`source_type`, `file_id`, `content_type`, `created_at`, `updated_at`, `error`.

## Document operations

```python
client.knowledge_bases.get_document(kb_id, document_id)
client.knowledge_bases.download_document(kb_id, document_id)          # -> bytes
client.knowledge_bases.update_document(kb_id, document_id, UpdateDocument(prefix="/new"))
client.knowledge_bases.delete_document(kb_id, document_id)
client.knowledge_bases.dismiss_document(kb_id, document_id)           # ignore an errored doc
client.knowledge_bases.retry_document(kb_id, document_id)             # re-ingest one
client.knowledge_bases.retry_all(kb_id)                              # re-ingest all failed
```

## Search

**Semantic search** returns scored chunks:

```python
for hit in client.knowledge_bases.search(kb_id, query="refund window", prefix="/"):
    print(hit.score, hit.content, hit.source)   # SearchResult: score, content, source, document_source
```

**Document search** returns matching documents (metadata), not chunks:

```python
client.knowledge_bases.search_documents(kb_id, query="invoice", limit=25)
```

## Structure, types & export

```python
client.knowledge_bases.get_tree(kb_id, folder="/", max_depth=3)   # nested folder view
client.knowledge_bases.list_folder(kb_id, folder="/manuals")
client.knowledge_bases.get_types()          # supported document types
client.knowledge_bases.get_mime_types()     # supported MIME types

blob = client.knowledge_bases.export(kb_id, version="auto", set_active_on_import=False)
client.knowledge_bases.import_(blob, version="auto", mode="clone", dry_run=False)
```

`version` is `"auto" | "v3" | "v4"`; `mode` is `"clone" | "version" | "replace"`.

## Recipe: export a KB's documents to a spreadsheet

```python
import openpyxl
wb = openpyxl.Workbook(); ws = wb.active
ws.append(["name", "status", "size", "content_type", "created_at"])
for doc in client.knowledge_bases.iter_documents(kb_id):
    ws.append([doc.name, doc.status, doc.size, doc.content_type, doc.created_at])
wb.save("kb_documents.xlsx")
```
