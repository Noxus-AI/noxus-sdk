"""DEV-1975: an ``aget → mutate → aupdate`` round-trip must not downgrade a V2 flow.

``WorkflowDefinition`` does not model ``flow_version``: ``_definition_flattener``
lifts only ``definition["nodes"]`` and ``["edges"]``, and ``to_noxus()`` rebuilds
the payload from those two keys alone. So every SDK round-trip silently drops the
one key that tells the platform this is a V2 flow — a rename over MCP converts a
V2 flow to V1, and the editor then renders every V2 node as "There was an error
with this node. Please delete and re-add it."

``save_version`` posts the same stripped ``{nodes, edges}`` dict, so version
snapshots taken over MCP are stored as V1 definitions too.
"""

from __future__ import annotations

from typing import Any

import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources.workflows import WorkflowService
from noxus_sdk.workflows.workflow import WorkflowDefinition


def _v2_payload() -> dict[str, Any]:
    return {
        "id": "77ad4d69-b6d7-429d-8fbb-de0e766aaae1",
        "name": "Projeto Fraque",
        "type": "flow",
        "definition": {"flow_version": "v2", "nodes": [], "edges": []},
    }


def _v1_payload() -> dict[str, Any]:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "Legacy flow",
        "type": "flow",
        "definition": {"nodes": [], "edges": []},
    }


class _Recorder:
    """Captures the body the SDK writes back, which is what the bug is about."""

    def __init__(self) -> None:
        self.body: dict[str, Any] | None = None


def _recording_client(response: dict[str, Any]) -> tuple[Client, _Recorder]:
    client = Client("test-key", "http://testserver", load_nodes=False, load_me=False)
    recorder = _Recorder()

    async def _apatch(url: str, body: Any, *_args: object, **_kwargs: object) -> dict:  # noqa: ANN401
        recorder.body = body
        return response

    async def _apost(
        url: str, body: Any = None, *_args: object, **_kwargs: object
    ) -> dict:  # noqa: ANN401
        recorder.body = body
        return {
            "id": "22222222-2222-2222-2222-222222222222",
            "name": body["name"],
            "description": body.get("description"),
            "created_at": "2026-08-17T10:00:00",
            "definition": body["definition"],
        }

    client.apatch = _apatch  # type: ignore[method-assign]
    client.apost = _apost  # type: ignore[method-assign]
    return client, recorder


def test_v2_definition_survives_a_write() -> None:
    wf = WorkflowDefinition.model_validate(_v2_payload())

    assert wf.to_noxus()["definition"]["flow_version"] == "v2"


def test_a_rename_round_trip_does_not_downgrade_the_flow() -> None:
    """The exact production incident: rename a V2 flow, get a V1 flow back."""
    wf = WorkflowDefinition.model_validate(_v2_payload())
    wf.name = "Projeto Fraque — renamed"

    assert wf.to_noxus()["definition"]["flow_version"] == "v2"


def test_v1_definitions_default_to_v1() -> None:
    wf = WorkflowDefinition.model_validate(_v1_payload())

    assert wf.to_noxus()["definition"]["flow_version"] == "v1"


@pytest.mark.asyncio
async def test_aupdate_writes_back_the_flow_version() -> None:
    payload = _v2_payload()
    client, recorder = _recording_client(payload)
    wf = WorkflowDefinition.model_validate(payload)

    await WorkflowService(client).aupdate(wf.id, wf)

    assert recorder.body is not None
    assert recorder.body["definition"]["flow_version"] == "v2"


@pytest.mark.asyncio
async def test_saved_versions_carry_the_flow_version() -> None:
    """A snapshot stored without ``flow_version`` restores as a broken V1 flow."""
    payload = _v2_payload()
    client, recorder = _recording_client(payload)
    wf = WorkflowDefinition.model_validate(payload)

    await WorkflowService(client).asave_version(wf.id, wf, name="F2", description=None)

    assert recorder.body is not None
    assert recorder.body["definition"]["flow_version"] == "v2"
