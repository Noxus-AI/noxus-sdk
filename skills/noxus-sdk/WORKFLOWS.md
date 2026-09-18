# Workflows, Runs & Agent-flows

`client.workflows` builds and versions flows; `client.runs` executes them and
reads results; `client.agentflows` is the same shape for agent-flow definitions.

## Building a workflow

A workflow is a graph of **nodes** connected by **edges**. Build it with
`WorkflowDefinition`, then `save` it. Node types come from the catalog the client
loads at startup (keep `load_nodes=True`, the default, when building).

```python
from noxus_sdk.workflows import WorkflowDefinition

wf = WorkflowDefinition(name="Joke + fact")

# .node(<NodeType>) adds a node; .config(**kwargs) sets its configuration.
inp = wf.node("InputNode").config(
    label="Fixed Input", fixed_value=True, value="Write a joke.", type="str"
)
ai = wf.node("TextGenerationNode").config(
    template="Add an animal fact after: ((Input 1))",
    model=["gpt-4o-mini"],
)
out = wf.node("OutputNode")

# .link(from_node.output(...), to_node.input(...)) wires edges.
wf.link(inp.output(), ai.input("variables", "Input 1"))
wf.link(ai.output(), out.input())

saved = client.workflows.save(wf)     # -> WorkflowDefinition (now has .id)
print(saved.id)
```

Node wiring API:
- `node.output(name=None)` / `node.input(handle=None, label=None)` return
  `EdgePoint`s for `link`.
- `wf.link(from_point, to_point)` connects one edge; `wf.link_many(*nodes)`
  chains a linear sequence.
- `wf.node(name)` re-fetches a node you already added by label.
- The graph need not be linear — branch and merge freely as long as types match
  (a string input needs a string output, a file input needs a file, etc.).

## Managing workflows

```python
client.workflows.list(page=1, page_size=10)     # -> list[WorkflowDefinition]
client.workflows.get(workflow_id)               # -> WorkflowDefinition
client.workflows.save(wf)                        # create new
client.workflows.update(workflow_id, wf, force=False)   # overwrite; force past conflict
client.workflows.delete(workflow_id)
```

From a `WorkflowDefinition` object you can also call `.save()`, `.update()`,
`.refresh()` directly.

### Versions

```python
v = client.workflows.save_version(workflow_id, wf, name="v2", description="…")
client.workflows.list_versions(workflow_id)      # -> list[WorkflowVersion]
client.workflows.update_version(workflow_id, version_id, name, description, definition)
```

### Logs, export & import

```python
client.workflows.get_logs(workflow_id)           # -> dict (run history/log rows)
client.workflows.get_logs_columns(workflow_id)   # -> list[str]

blob = client.workflows.export(workflow_id, version="auto", include_dependencies=True)
client.workflows.export_preview(workflow_id)     # -> dict (what an export contains)
client.workflows.import_(blob, mode="clone", activate=False, dry_run=False)
```

`version` is `"auto" | "v3" | "v4"` (auto = base64 v3 for pipeline compatibility;
v4 is YAML, opt-in). `mode` is `"clone" | "version" | "replace"`. `dry_run=True`
validates without writing and returns what *would* happen.

## Running a workflow

Two ways to execute:

**1. From the definition object → a `Run` you poll or stream**
```python
wf = client.workflows.get(workflow_id)
run = wf.run({"Input 1": "hello"})               # -> Run (queued)
result = run.wait(output_only=True)              # blocks (polls every 5s), returns output
# or step through progress events:
for event in wf.run_and_stream({"Input 1": "hello"}):
    print(event)
```

**2. Synchronous one-shot via the runs service**
```python
out = client.runs.run_sync(workflow_id, {"Input 1": "hello"}, output_only=True)
```

`body`/`input` is a dict keyed by the workflow's input labels.

## The runs service

```python
client.runs.list(workflow_id, page=1, page_size=10)      # -> list[Run]
client.runs.get(workflow_id, run_id)                     # -> Run
client.runs.run_sync(workflow_id, input, output_only=False)
client.runs.stop(run_id)                                 # -> Run (cancel)
client.runs.get_data(run_id, fetch_structured_data=True) # full run payload
client.runs.get_node_io(run_id, node_id, it=0)           # a node's inputs/outputs
client.runs.search("invoice", limit=10, exact=True, search_in=None)  # search across runs
```

### The `Run` object

Fields: `id`, `status`, `progress`, `progress_details`, `workflow_id`, `input`,
`output`, `created_at`, `finished_at`.

Methods (each with an `a`-prefixed async twin):
```python
run.wait(interval=5, output_only=False)   # poll until terminal; returns Run or output dict
run.get_status()                          # -> str
run.refresh()                             # re-fetch
run.stop()                                # cancel
run.data(fetch_structured_data=True)      # full payload
for event in run.stream(etag=None):       # live RunEvents
    print(event)
```

`wait(output_only=True)` returns just the output dict; otherwise it returns the
refreshed `Run`. Streaming yields `RunEvent`s as the run progresses.

## Agent-flows

`client.agentflows` mirrors `client.workflows` for agent-flow definitions:
`list`, `get`, `save`, `update(..., force=False)`, `delete` (+ async twins),
operating on `AgentFlowDefinition`.
