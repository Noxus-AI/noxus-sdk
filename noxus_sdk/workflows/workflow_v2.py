"""V2 workflow builder for the noxus SDK.

V2 flows have a different shape from V1: a node's inputs are config fields
that carry inline `:var[<node_id>.<output_name>]` refs (the runtime
deep-walks node_config and substitutes them before the node runs). Edges
exist for the canvas *and* for scheduling — the engine runs a node once all
its edge-predecessors are done — but they don't carry data themselves.

This module mirrors the V1 builder API (`WorkflowDefinition`, `Node`,
`Edge`) just enough to author V2 flows in smoketests and snippets, post
them to the same `/v1/workflows` endpoint (the backend keys off
`definition.flow_version` to route the run through the V2 engine), and
trigger runs against them.

The SDK does NOT validate node types or config schemas — that's the
backend's job on save/run. Smoketests opt in to fast iteration over
type safety.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, AsyncIterator, Iterator, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from noxus_sdk.client import Client

if TYPE_CHECKING:
    from noxus_sdk.resources.runs import Run, RunEvent


def _add_var_key(node_config: dict, connector_name: str, key: str) -> None:
    """Register `key` under `node_config.__var_keys[connector_name]`.

    The V2 editor stores user-added keys on variable-size connectors
    here so `_build_connector_config` (server-side) injects them into
    the runtime connector. The SDK does the same on-the-fly so
    explicit `<conn>__<key>` wiring works without the user
    hand-maintaining the annotation.
    """
    raw = node_config.setdefault("__var_keys", {})
    if not isinstance(raw, dict):
        return
    keys = raw.setdefault(connector_name, [])
    if not isinstance(keys, list):
        return
    if key not in keys:
        keys.append(key)


class NodeV2(BaseModel):
    """A single node in a V2 workflow. Mirrors
    `spotflow.flow_v2.schemas.NodeDefinitionV2`."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    # Parent reference; excluded from serialization so each node is
    # standalone in `to_noxus()` output.
    workflow: "WorkflowDefinitionV2 | None" = Field(default=None, exclude=True)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    name: str | None = None
    node_config: dict = Field(default_factory=dict)
    variable_bindings: dict[str, str] = Field(default_factory=dict)
    iterate_overrides: dict[str, bool] = Field(default_factory=dict)
    parent_id: str | None = None
    display: dict = Field(default_factory=dict)

    def config(self, **kwargs: Any) -> "NodeV2":
        """Merge values into `node_config`. Chainable."""
        self.node_config.update(kwargs)
        return self

    def declare_var_input(self, connector: str, key: str) -> "NodeV2":
        """Register `key` on the input variable-connector named `connector`.

        Mirrors what the V2 editor writes into `node_config.__var_keys`.
        Needed so the V1 runtime's `run()` and `build_result_containers()`
        iterate `connector.keys` and actually pass per-key inputs/outputs
        to the node (otherwise they silently see an empty keys list and
        drop the value). Called automatically by `bind` when the `field`
        matches `<connector>__<key>`.
        """
        _add_var_key(self.node_config, connector, key)
        return self

    def declare_var_output(self, connector: str, key: str) -> "NodeV2":
        """Register `key` on the output variable-connector named `connector`.

        Sibling of `declare_var_input` for output-side variable connectors
        (e.g. InvokeSubflowNode's `outputs`). Called automatically by
        `bind` when the source's `output_name` isn't the default `"output"`.
        """
        _add_var_key(self.node_config, connector, key)
        return self

    def bind(
        self,
        field: str,
        source: "NodeV2 | str",
        output_name: str = "output",
        *,
        source_output_connector: str = "outputs",
    ) -> "NodeV2":
        """Wire `field` on this node to an upstream output.

        `source` may be a `NodeV2` (uses `<source.id>.<output_name>`) or
        a raw `"<node_id>.<output_name>"` string for cases like loop-scope
        broadcasts where the target isn't a NodeV2 instance.

        When `field` matches `<connector>__<key>`, the connector key is
        auto-registered on THIS node via `declare_var_input` so the V1
        runtime picks it up. When `output_name` differs from the default
        `"output"` and `source` is a `NodeV2`, the same is done on the
        source via `declare_var_output(source_output_connector, output_name)`.
        Most variable-output V1 nodes (InvokeSubflowNode, CodeExecution*)
        name that connector `"outputs"`; override via the keyword if not.
        """
        if isinstance(source, NodeV2):
            self.variable_bindings[field] = f"{source.id}.{output_name}"
            if output_name != "output":
                source.declare_var_output(source_output_connector, output_name)
        else:
            self.variable_bindings[field] = source

        connector_name, sep, key = field.partition("__")
        if sep and connector_name and key:
            self.declare_var_input(connector_name, key)

        return self

    def ref(self, output_name: str = "output") -> str:
        """Return the binding string downstream nodes use to read an
        output (`"<node_id>.<output_name>"`)."""
        return f"{self.id}.{output_name}"


class EdgeV2(BaseModel):
    """V2 edge — visual hint only. Data flow lives in `variable_bindings`
    on each node, so edges are non-load-bearing for execution but the
    backend still expects the field, and the canvas uses them to render
    connections."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    target: str
    source_handle: str | None = None
    target_handle: str | None = None


class WorkflowDefinitionV2(BaseModel):
    """Top-level V2 workflow. Built fluently; serializes via `to_noxus()`
    into the dict shape `POST /v1/workflows` expects (the backend reads
    `definition.flow_version == "v2"` and routes runs through the V2
    engine)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: Client | None = Field(default=None, exclude=True)
    id: str = ""
    group_id: str | None = Field(default=None)
    name: str = "Untitled V2 Workflow"
    type: str = "flow"
    flow_version: Literal["v2"] = "v2"
    nodes: list[NodeV2] = Field(default_factory=list)
    edges: list[EdgeV2] = Field(default_factory=list)
    # Internal X cursor for default node placement so generated flows
    # don't pile every node at the origin on the canvas.
    _x: int = 0

    @model_validator(mode="before")
    @classmethod
    def _definition_flattener(cls, values: Any) -> Any:
        """Mirror V1's flattener: if a `definition` key is present (the
        server returns this on save/get), lift nodes/edges/flow_version
        up so the model populates cleanly."""
        if isinstance(values, dict) and "definition" in values:
            definition = values["definition"] or {}
            values["nodes"] = definition.get("nodes", [])
            values["edges"] = definition.get("edges", [])
            if "flow_version" in definition:
                values["flow_version"] = definition["flow_version"]
        return values

    # ─── builder API ─────────────────────────────────────────────────────

    def node(
        self, type: str, *, name: str | None = None, x: int | None = None
    ) -> NodeV2:
        """Add a node of `type` and return it for further configuration.

        Auto-spaces nodes left-to-right unless `x` is supplied — keeps the
        rendered canvas readable when saved flows are opened in the editor.
        """
        self._x += 350 if x is None else 0
        position_x = x if x is not None else self._x
        n = NodeV2(
            type=type,
            name=name,
            display={"position": {"x": position_x, "y": 0}},
            workflow=self,
        )
        self.nodes.append(n)
        return n

    def input(self, label: str, type: str = "str", **extra: Any) -> NodeV2:
        """Shortcut for `node("InputNodeV2").config(label=label, type=type, ...)`."""
        return self.node("InputNodeV2").config(label=label, type=type, **extra)

    def output(self, label: str, type: str = "str", **extra: Any) -> NodeV2:
        """Shortcut for `node("OutputNodeV2").config(label=label, type=type, ...)`."""
        return self.node("OutputNodeV2").config(label=label, type=type, **extra)

    def link(
        self,
        source: NodeV2,
        target: NodeV2,
        *,
        field: str = "value",
        source_output: str = "output",
        source_handle: str | None = None,
        target_handle: str | None = None,
    ) -> EdgeV2:
        """Bind `target.<field>` to `source.<source_output>` and draw the edge.

        Native V2 nodes resolve their inputs from config-level `:var[...]`
        refs (deep-walked before `call()`), so this writes
        ``node_config[field] = ":var[<source.id>.<source_output>]"`` and adds
        a visual/scheduling `EdgeV2`. For bindings that live *inside* a config
        value — a `CombineTextV2` template that interpolates the ref, or a
        dict-rows field like `InvokeSubflowV2Node.inputs` — set the `:var[...]`
        token via `.config()` yourself and wire ordering with `edge()`.
        """
        target.node_config[field] = f":var[{source.id}.{source_output}]"
        return self.edge(
            source, target, source_handle=source_handle, target_handle=target_handle
        )

    def edge(
        self,
        source: NodeV2,
        target: NodeV2,
        *,
        source_handle: str | None = None,
        target_handle: str | None = None,
    ) -> EdgeV2:
        """Record a `source → target` edge without binding any field.

        The V2 scheduler orders execution off edges (a node runs once all its
        predecessors are done), so a node whose binding is set via `.config()`
        still needs an edge to be scheduled after its upstream."""
        e = EdgeV2(
            source=source.id,
            target=target.id,
            source_handle=source_handle,
            target_handle=target_handle,
        )
        self.edges.append(e)
        return e

    # ─── (de)serialization + client integration ──────────────────────────

    def to_noxus(self) -> dict:
        """Shape the backend's `POST /v1/workflows` (and update) accept."""
        definition = {
            "flow_version": self.flow_version,
            "nodes": [n.model_dump() for n in self.nodes],
            "edges": [e.model_dump() for e in self.edges],
        }
        return {
            "name": self.name,
            "type": self.type,
            "definition": definition,
        }

    def refresh_from_data(
        self, client: Client | None = None, **data: Any
    ) -> "WorkflowDefinitionV2":
        n = self.__class__.model_validate(data)
        for k in n.model_fields_set:
            setattr(self, k, getattr(n, k))
        self.client = client
        return self

    def save(self) -> "WorkflowDefinitionV2":
        """POST a new workflow. Mutates `self` with the server-assigned id."""
        if not self.client:
            raise ValueError("Client not set")
        w = self.client.post("/v1/workflows", self.to_noxus())
        self.refresh_from_data(client=self.client, **w)
        return self

    async def asave(self) -> "WorkflowDefinitionV2":
        if not self.client:
            raise ValueError("Client not set")
        w = await self.client.apost("/v1/workflows", self.to_noxus())
        self.refresh_from_data(client=self.client, **w)
        return self

    def update(self, force: bool = False) -> "WorkflowDefinitionV2":
        if not self.client:
            raise ValueError("Client not set")
        w = self.client.patch(f"/v1/workflows/{self.id}?force={force}", self.to_noxus())
        self.refresh_from_data(client=self.client, **w)
        return self

    async def aupdate(self, force: bool = False) -> "WorkflowDefinitionV2":
        if not self.client:
            raise ValueError("Client not set")
        w = await self.client.apatch(
            f"/v1/workflows/{self.id}?force={force}", self.to_noxus()
        )
        self.refresh_from_data(client=self.client, **w)
        return self

    def run(
        self,
        body: dict[str, Any],
        workflow_version_id: uuid.UUID | str | None = None,
        callback_url: str | None = None,
    ) -> "Run":
        """Start a run. `body` is keyed by InputNode labels.

        Hits the V1 runs endpoint — the backend dispatches to the V2
        engine based on the workflow's stored `flow_version`.
        """
        from noxus_sdk.resources.runs import Run

        if not self.client:
            raise ValueError("Client not set")
        req: dict[str, Any] = {"input": body}
        if workflow_version_id:
            req["workflow_version_id"] = str(workflow_version_id)
        if callback_url:
            req["callback_url"] = callback_url
        response = self.client.post(f"/v1/workflows/{self.id}/runs", req)
        return Run(client=self.client, **response)

    async def arun(
        self,
        body: dict[str, Any],
        workflow_version_id: uuid.UUID | str | None = None,
        callback_url: str | None = None,
    ) -> "Run":
        from noxus_sdk.resources.runs import Run

        if not self.client:
            raise ValueError("Client not set")
        req: dict[str, Any] = {"input": body}
        if workflow_version_id:
            req["workflow_version_id"] = str(workflow_version_id)
        if callback_url:
            req["callback_url"] = callback_url
        response = await self.client.apost(f"/v1/workflows/{self.id}/runs", req)
        return Run(client=self.client, **response)

    def run_and_stream(
        self,
        body: dict[str, Any],
        workflow_version_id: uuid.UUID | str | None = None,
    ) -> Iterator["RunEvent"]:
        run = self.run(body, workflow_version_id=workflow_version_id)
        yield from run.stream()

    async def arun_and_stream(
        self,
        body: dict[str, Any],
        workflow_version_id: uuid.UUID | str | None = None,
    ) -> AsyncIterator["RunEvent"]:
        run = await self.arun(body, workflow_version_id=workflow_version_id)
        async for event in run.astream():
            yield event


NodeV2.model_rebuild()
