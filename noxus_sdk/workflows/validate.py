"""Structural validation for a workflow definition.

Single source of truth shared by the MCP ``workflows_validate`` tool and the
Genie workflow-building evals, so "valid" means the same thing in both.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from noxus_sdk.workflows.workflow import NODE_TYPES, WorkflowDefinition


@dataclass
class ValidationResult:
    valid: bool
    node_count: int
    edge_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_workflow_definition(wf: WorkflowDefinition) -> ValidationResult:
    """Validate a workflow's structure and surface actionable errors/warnings."""
    errors: list[str] = []
    warnings: list[str] = []

    if not wf.nodes:
        errors.append("Workflow has no nodes")
        return ValidationResult(
            valid=False,
            node_count=0,
            edge_count=0,
            errors=errors,
            warnings=warnings,
        )

    node_types = [n.type for n in wf.nodes]
    if "InputNode" not in node_types:
        errors.append("Missing InputNode — workflow needs an input")
    if "OutputNode" not in node_types:
        errors.append("Missing OutputNode — workflow needs an output")

    node_ids = {n.id for n in wf.nodes}
    has_incoming = {n.id: False for n in wf.nodes}
    has_outgoing = {n.id: False for n in wf.nodes}
    for edge in wf.edges:
        if edge.from_id.node_id in node_ids:
            has_outgoing[edge.from_id.node_id] = True
        if edge.to_id.node_id in node_ids:
            has_incoming[edge.to_id.node_id] = True

    for i, node in enumerate(wf.nodes):
        if node.type == "InputNode":
            if not has_outgoing[node.id]:
                warnings.append(f"Node {i} ({node.name}) has no outgoing edges")
        elif node.type == "OutputNode":
            if not has_incoming[node.id]:
                warnings.append(f"Node {i} ({node.name}) has no incoming edges")
        else:
            if not has_incoming[node.id]:
                warnings.append(f"Node {i} ({node.name}) has no incoming edges")
            if not has_outgoing[node.id]:
                warnings.append(f"Node {i} ({node.name}) has no outgoing edges")

    for i, node in enumerate(wf.nodes):
        node_def = NODE_TYPES.get(node.type)
        if not node_def:
            continue
        for key, cfg in node_def.config.items():
            if not cfg.visible:
                continue
            if not cfg.optional and cfg.default is None:
                if key not in node.node_config:
                    errors.append(
                        f"Node {i} ({node.name}): missing required config '{key}'"
                    )

    return ValidationResult(
        valid=len(errors) == 0,
        node_count=len(wf.nodes),
        edge_count=len(wf.edges),
        errors=errors,
        warnings=warnings,
    )
