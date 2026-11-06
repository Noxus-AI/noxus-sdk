"""``ctx.acomplete`` in a plugin node runs on the host as ``host.complete``.

The worker sends the call token, the models, the prompts and, for structured
output, the response model's JSON schema; the host's answer is validated back
into that model inside the sandbox.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import pytest
from pydantic import BaseModel

from noxus_sdk.nodes.base import BaseNode, NodeConfiguration
from noxus_sdk.plugins import BasePlugin, PluginConfiguration
from noxus_sdk.plugins.context import RemoteExecutionContext
from noxus_sdk.plugins.dispatch import PluginDispatcher
from noxus_sdk.plugins.jsonrpc import JsonRpcError, JsonRpcPeer
from noxus_sdk.plugins.types import PluginCategory
from noxus_sdk.plugins.worker import build_handlers


class Patient(BaseModel):
    name: str
    nif: str


class _Config(NodeConfiguration):
    pass


class ExtractNode(BaseNode[_Config]):
    node_name = "ExtractNode"
    title = "Extract"

    async def call(self, ctx: RemoteExecutionContext, text: str) -> dict[str, Any]:
        patient = await ctx.acomplete(
            ["preset:cost"], text, system_prompt="extract", response_format=Patient
        )
        return {"name": patient.name, "nif": patient.nif}


class SummariseNode(BaseNode[_Config]):
    node_name = "SummariseNode"
    title = "Summarise"

    async def call(self, ctx: RemoteExecutionContext, text: str) -> dict[str, Any]:
        return {"summary": await ctx.acomplete(["preset:cost"], text)}


class _Plugin(BasePlugin[PluginConfiguration]):
    name = "llm-callback-plugin"
    display_name = "LLM Callback"
    version = "0.0.1"
    description = "nodes that call ctx.acomplete"
    category = PluginCategory.OTHER
    author = "test"

    def nodes(self) -> list[type[BaseNode]]:
        return [ExtractNode, SummariseNode]


@contextlib.asynccontextmanager
async def _linked(host_complete):
    a2b: asyncio.Queue[str] = asyncio.Queue()
    b2a: asyncio.Queue[str] = asyncio.Queue()
    host = JsonRpcPeer(b2a.get, a2b.put)
    worker = JsonRpcPeer(a2b.get, b2a.put)
    host.register("host.complete", host_complete)
    for name, handler in build_handlers(
        PluginDispatcher(_Plugin, "llm-callback-plugin"), worker
    ).items():
        worker.register(name, handler)
    tasks = [asyncio.ensure_future(host.run()), asyncio.ensure_future(worker.run())]
    try:
        yield host
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def _execute(node_name: str) -> dict[str, Any]:
    return {
        "node_name": node_name,
        "ctx": {"call_token": "tok-1"},
        "inputs": {"text": "Maria, NIF 123"},
        "config": {},
    }


def test_structured_completion_round_trips_through_the_host() -> None:
    seen: list[dict] = []

    async def host_complete(params: dict) -> dict:
        seen.append(params)
        return {"output": {"name": "Maria", "nif": "123"}}

    async def scenario() -> dict:
        async with _linked(host_complete) as host:
            return await host.call("node.execute", _execute("ExtractNode"))

    result = asyncio.run(scenario())

    assert result["outputs"] == {"name": "Maria", "nif": "123"}
    [params] = seen
    assert params["call_token"] == "tok-1"
    assert params["models"] == ["preset:cost"]
    assert params["prompt"] == "Maria, NIF 123"
    assert params["system_prompt"] == "extract"
    assert params["schema_name"] == "Patient"
    assert set(params["json_schema"]["properties"]) == {"name", "nif"}


def test_text_completion_sends_no_schema() -> None:
    seen: list[dict] = []

    async def host_complete(params: dict) -> dict:
        seen.append(params)
        return {"output": "a summary"}

    async def scenario() -> dict:
        async with _linked(host_complete) as host:
            return await host.call("node.execute", _execute("SummariseNode"))

    assert asyncio.run(scenario())["outputs"] == {"summary": "a summary"}
    assert seen[0]["json_schema"] is None
    assert seen[0]["schema_name"] is None


def test_host_refusal_fails_the_node() -> None:
    async def host_complete(_params: dict) -> dict:
        raise JsonRpcError(-32003, "LLM completions are only available in a flow")

    async def scenario() -> dict:
        async with _linked(host_complete) as host:
            return await host.call("node.execute", _execute("SummariseNode"))

    with pytest.raises(JsonRpcError, match="only available in a flow"):
        asyncio.run(scenario())


def test_acomplete_without_a_host_says_why() -> None:
    with pytest.raises(RuntimeError, match="only available while the platform"):
        asyncio.run(RemoteExecutionContext().acomplete(["preset:cost"], "hi"))
