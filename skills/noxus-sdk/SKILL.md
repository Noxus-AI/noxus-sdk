---
name: noxus-sdk
description: >
  Write Python that drives the Noxus AI platform through the public `noxus-sdk`
  (`noxus_sdk`) — run and build workflows, chat with agents, manage knowledge
  bases, query data tables, execute code in sandboxes, publish agents to
  channels (deployments), manage triggers, variables, files, analytics, and
  workspace/user administration. Use this whenever the task is to script the
  Noxus backend over HTTP from Python, author example code, or answer "how do I
  do X with the SDK". Covers auth/scopes, the typed error hierarchy, sync vs
  async, pagination, and per-domain recipes.
---

# Noxus SDK (`noxus_sdk`)

The public Python SDK for the Noxus AI backend. One `Client`, then everything
hangs off it as a resource service (`client.workflows`, `client.agents`, …).
Every method has a **sync** form and an **async** form prefixed with `a`
(`list` / `alist`, `create` / `acreate`). This skill documents v0.6.0.

> This is the **customer-facing** SDK (package `noxus_sdk`, repo `noxus-sdk/`).
> Do not confuse it with the internal `noxus/` core library. When editing the
> SDK itself, note it is gated by **ruff + its own pytest only** (not ty/pyright).

## Quick reference — the 15 services

| `client.<service>` | Domain | Reference |
|---|---|---|
| `workflows` | Build / version / export flows | [WORKFLOWS.md](WORKFLOWS.md) |
| `runs` | Execute flows, stream, search runs | [WORKFLOWS.md](WORKFLOWS.md) |
| `agentflows` | Agent-flow definitions | [WORKFLOWS.md](WORKFLOWS.md) |
| `agents` | Agents (co-workers): CRUD, versions, publish | [AGENTS.md](AGENTS.md) |
| `conversations` | Chat with an agent, stream messages | [AGENTS.md](AGENTS.md) |
| `insights` | Agent insight dashboards (CSAT, topics…) | [AGENTS.md](AGENTS.md) |
| `knowledge_bases` | KBs, documents, ingestion, search | [KNOWLEDGE_BASES.md](KNOWLEDGE_BASES.md) |
| `tables` | Workspace data tables + SQL | [TABLES.md](TABLES.md) |
| `sandboxes` | Ephemeral code-execution sandboxes | [SANDBOXES.md](SANDBOXES.md) |
| `deployments` | Publish an agent to a channel | [DEPLOYMENTS.md](DEPLOYMENTS.md) |
| `triggers` | Workflow triggers + their events | [DEPLOYMENTS.md](DEPLOYMENTS.md) |
| `variables` | Workspace variables & secrets | [ADMIN.md](ADMIN.md) |
| `files` | Upload / download raw files | [ADMIN.md](ADMIN.md) |
| `analytics` | Platform usage metrics | [ADMIN.md](ADMIN.md) |
| `admin` | Workspaces, users, roles, system keys | [ADMIN.md](ADMIN.md) |

## Install

```bash
pip install noxus-sdk          # requires Python >= 3.10
```

The SDK ships `py.typed`, so downstream type-checkers see its types.

## Create a client

```python
from noxus_sdk.client import Client

client = Client(api_key="sk-...")                     # simplest
client = Client.from_env()                            # NOXUS_API_KEY + NOXUS_BACKEND_URL
```

`Client.__init__(api_key, base_url="https://backend.noxus.ai", extra_headers=None, *, load_nodes=True, load_me=True, max_retries=5)`

- **`base_url`** — override the backend; also read from `NOXUS_BACKEND_URL`.
- **`load_nodes=False`** — skip fetching the node catalog on construction. Set it
  when you don't build workflows; avoids a network round-trip at startup.
- **`load_me=False`** — skip the auth "who am I" probe. With it on, `client.admin`
  is enabled only if the key is tenant-admin; a bad key surfaces here immediately.
- **`max_retries`** — bounded exponential backoff for `429` responses (honors
  `Retry-After`); raises `RateLimitedError` on exhaustion. It is **not** an
  infinite loop.

Get your API key in the Noxus UI: **Settings → Organization → Workspaces →
(pick a workspace) → API Keys**. A key is **scoped to one workspace**.

### Connection pooling & cleanup (context managers)

The client keeps pooled `httpx` clients alive across calls. Close them when done:

```python
with Client.from_env() as client:            # sync — auto-closes the pool
    workflows = client.workflows.list()

async with Client.from_env() as client:      # async
    workflows = await client.workflows.alist()

# or explicitly
client.close()          # sync pool
await client.aclose()   # async pool
```

## Sync vs async

Every service method exists twice. Same arguments, `a`-prefixed for async:

```python
kbs = client.knowledge_bases.list()                 # sync
kbs = await client.knowledge_bases.alist()          # async
```

Returned resource objects also carry async variants (`agent.update` /
conversation `chat`/`achat`, `run.wait`/`run.a_wait`, `table.insert`/`ainsert`).

## Error handling

All HTTP failures raise a typed exception from `noxus_sdk.errors`. Catch the
specific one you care about, or the `NoxusApiError` base:

```python
from noxus_sdk.errors import NoxusApiError, NotFoundError, RateLimitedError

try:
    agent = client.agents.get(agent_id)
except NotFoundError:
    ...                        # 404
except RateLimitedError as e:
    ...                        # 429 after retries exhausted
except NoxusApiError as e:     # any other 4xx/5xx
    print(e.status_code, e.body, e.request_id)
```

Hierarchy (all subclass `NoxusApiError` → `NoxusError` → `Exception`):

| Class | Status |
|---|---|
| `BadRequestError` | 400 |
| `UnauthorizedError` | 401 |
| `ForbiddenError` | 403 |
| `NotFoundError` | 404 |
| `ValidationError` | 422 |
| `RateLimitedError` | 429 |
| `ServerError` | 5xx |

`NoxusApiError` carries `.status_code`, `.body` (parsed JSON or text), and
`.request_id`; its message is `"{status} {server detail}"`. `RequestFailedError`
is a back-compat alias of the base — prefer `NoxusApiError` in new code.

## Pagination

List endpoints take `page` / `page_size`. For "give me everything", the domains
that page provide auto-paginating iterators (`iter_*` / async `aiter_*`) so you
never hand-roll page loops:

```python
for doc in client.knowledge_bases.iter_documents(kb_id):   # all statuses, all pages
    print(doc.name)

for row in table.iter_rows(search="active"):
    print(row)

async for event in client.deployments.aiter_events(agent_id, dep_id):
    print(event)
```

Iterators exist for: KB documents (`knowledge_bases.iter_documents`), table rows
(`table.iter_rows`), trigger events (`triggers.iter_events`), and deployment
events (`deployments.iter_events`) — each with an `a`-prefixed async twin.

## Common recipes

**Run a workflow and get its output**
```python
run = client.workflows.get(workflow_id).run({"Input 1": "hello"})
output = run.wait(output_only=True)          # blocks until done, returns output
```

**Chat with an agent in a fresh conversation**
```python
from noxus_sdk.resources.conversations import MessageRequest

convo = client.conversations.create(name="Support", agent_id=agent_id)
reply = convo.chat(MessageRequest(content="What are your hours?"))
print(reply)
```

**Export every document in a KB to an Excel file** (the flagship data task)
```python
import openpyxl
wb = openpyxl.Workbook(); ws = wb.active
ws.append(["name", "status", "size", "content_type"])
for doc in client.knowledge_bases.iter_documents(kb_id):
    ws.append([doc.name, doc.status, doc.size, doc.content_type])
wb.save("kb_documents.xlsx")
```

**Run one-off Python against the platform in a sandbox**
```python
with client.sandboxes.create(label="job") as sb:
    sb.files.write("/work/run.py", "print('hi from the sandbox')")
    result = sb.commands.run("python /work/run.py")
    print(result.stdout, result.exit_code)
```

## Reference files

Read the per-domain file for the full method list, request/response shapes, and
worked examples:

- [WORKFLOWS.md](WORKFLOWS.md) — build, version, run, stream, search, export/import
- [AGENTS.md](AGENTS.md) — agents, conversations/chat, insight dashboards
- [KNOWLEDGE_BASES.md](KNOWLEDGE_BASES.md) — KBs, documents, ingestion, search
- [TABLES.md](TABLES.md) — data tables, columns, rows, SQL, CSV
- [SANDBOXES.md](SANDBOXES.md) — code-execution sandboxes, files, commands
- [DEPLOYMENTS.md](DEPLOYMENTS.md) — channels/deployments + workflow triggers
- [ADMIN.md](ADMIN.md) — workspaces, users, roles, system keys, variables, files, analytics
