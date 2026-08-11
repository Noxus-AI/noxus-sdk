"""Unit tests for the SDK EvaluationService resource.

Mocks the Client (create_autospec) and asserts each method hits the right URL,
sends the right body, and deserializes realistic backend payloads.
"""

from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources.evaluations import EvaluationService


def _svc():
    client = create_autospec(Client, instance=True)
    return EvaluationService(client), client


@pytest.mark.asyncio
async def test_alist_agent_test_suites_deserializes() -> None:
    svc, client = _svc()
    gid, aid, sid = uuid4(), uuid4(), uuid4()
    client.aget.return_value = [
        {
            "id": str(sid),
            "group_id": str(gid),
            "agent_id": str(aid),
            "name": "Suite",
            "description": None,
            "created_at": "2026-06-18T00:00:00",
            "updated_at": "2026-06-18T00:00:00",
            "stats": {"test_count": 3, "pass_rate": 0.66},
        }
    ]

    suites = await svc.alist_agent_test_suites(str(gid), str(aid))

    client.aget.assert_awaited_once_with(f"/v1/groups/{gid}/agents/{aid}/test-suites")
    assert len(suites) == 1
    assert suites[0].name == "Suite"
    assert suites[0].agent_id == aid
    assert suites[0].stats == {"test_count": 3, "pass_rate": 0.66}


@pytest.mark.asyncio
async def test_alist_definitions_agent() -> None:
    svc, client = _svc()
    client.aget.return_value = [
        {
            "type": "agent_llm_judge",
            "display_name": "Semantic Similarity (LLM)",
            "description": "Uses an LLM judge",
            "icon": "Sparkles",
            "config_schema": {"rubric": {"display": {"type": "big_text"}}},
            "expected_schema": {"properties": {"reference_text": {"type": "string"}}},
            "category": "agent",
            "group": "Agent",
        }
    ]

    defs = await svc.alist_evaluator_definitions("agent")

    client.aget.assert_awaited_once_with("/v1/evaluator-definitions/agent")
    assert defs[0].type == "agent_llm_judge"
    assert defs[0].icon == "Sparkles"
    assert defs[0].expected_schema is not None


@pytest.mark.asyncio
async def test_acreate_evaluator_sends_body() -> None:
    svc, client = _svc()
    gid, sid, eid = uuid4(), uuid4(), uuid4()
    client.apost.return_value = {
        "id": str(eid),
        "test_suite_id": str(sid),
        "type": "agent_llm_judge",
        "name": "judge",
        "config": {"model": ["preset:cost"]},
    }

    evaluator = await svc.acreate_evaluator(
        str(gid), str(sid), "agent_llm_judge", "judge", {"model": ["preset:cost"]}
    )

    client.apost.assert_awaited_once_with(
        f"/v1/groups/{gid}/test-suites/{sid}/evaluators",
        {
            "type": "agent_llm_judge",
            "name": "judge",
            "config": {"model": ["preset:cost"]},
        },
    )
    assert evaluator.type == "agent_llm_judge"
    assert evaluator.config == {"model": ["preset:cost"]}


@pytest.mark.asyncio
async def test_arun_evaluation_sends_body_and_returns() -> None:
    svc, client = _svc()
    gid, sid = uuid4(), uuid4()
    client.apost.return_value = {"run_ids": ["r1", "r2"]}

    out = await svc.arun_evaluation(str(gid), str(sid), test_case_ids=["tc1"])

    client.apost.assert_awaited_once_with(
        f"/v1/groups/{gid}/test-suites/{sid}/run-evaluation",
        {
            "version_id": None,
            "test_case_ids": ["tc1"],
            "wait_for_completion": False,
        },
    )
    assert out == {"run_ids": ["r1", "r2"]}


@pytest.mark.asyncio
async def test_alist_evaluation_results_deserializes() -> None:
    svc, client = _svc()
    gid, sid = uuid4(), uuid4()
    client.apget.return_value = [
        {
            "id": str(uuid4()),
            "evaluator_id": str(uuid4()),
            "test_case_id": str(uuid4()),
            "score": 0.9,
            "passed": True,
            "feedback": "good",
            "status": "completed",
        }
    ]

    results = await svc.alist_evaluation_results(str(gid), str(sid))

    client.apget.assert_awaited_once_with(
        f"/v1/groups/{gid}/test-suites/{sid}/evaluation-results"
    )
    assert results[0].score == 0.9
    assert results[0].passed is True
    assert results[0].status == "completed"


def test_list_test_cases_sync_deserializes() -> None:
    svc, client = _svc()
    gid, sid = uuid4(), uuid4()
    expected = {"e1": {"reference_text": "x", "message_index": 0}}
    client.pget.return_value = [
        {
            "id": str(uuid4()),
            "test_suite_id": str(sid),
            "group_id": str(gid),
            "name": "tc",
            "inputs": {"messages": []},
            "expected_outputs": expected,
        }
    ]

    cases = svc.list_test_cases(str(gid), str(sid))

    client.pget.assert_called_once_with(
        f"/v1/groups/{gid}/test-suites/{sid}/test-cases"
    )
    assert cases[0].name == "tc"
    assert cases[0].expected_outputs == expected


@pytest.mark.asyncio
async def test_aget_test_case_deserializes() -> None:
    svc, client = _svc()
    gid, cid, sid = uuid4(), uuid4(), uuid4()
    client.aget.return_value = {
        "id": str(cid),
        "test_suite_id": str(sid),
        "group_id": str(gid),
        "name": "tc",
        "inputs": {"messages": [{"role": "user", "content": "hi"}]},
        "expected_outputs": {"e1": {"reference_text": "x", "message_index": 0}},
    }

    case = await svc.aget_test_case(str(gid), str(cid))

    client.aget.assert_awaited_once_with(f"/v1/groups/{gid}/test-cases/{cid}")
    assert case.id == cid
    assert case.inputs == {"messages": [{"role": "user", "content": "hi"}]}
