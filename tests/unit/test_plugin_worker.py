"""Spike + unit tests for the warm plugin worker transport.

The riskiest part of the sandbox plugin engine is the bidirectional channel:
the host calls the worker (``node.execute``) and, *mid-request*, the worker
calls back to the host (``host.get_content``). These tests exercise that over
in-memory line transports — no sandbox, no subprocess — and assert parity
between the JSON-RPC path and calling the dispatcher directly (the serve.py
path).
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from noxus_sdk.files import File

from noxus_sdk.ncl import Parameter
from noxus_sdk.nodes.base import (
    BaseNode,
    BaseNodeV2,
    NodeConfiguration,
    NodeOutputs,
)
from noxus_sdk.plugins import BasePlugin, PluginConfiguration
from noxus_sdk.plugins.context import RemoteExecutionContext
from noxus_sdk.plugins.dispatch import PluginDispatcher
from noxus_sdk.plugins.jsonrpc import (
    COMPONENT_NOT_FOUND,
    METHOD_NOT_FOUND,
    JsonRpcError,
    JsonRpcPeer,
)
from noxus_sdk.datasources import BaseDataSource, DatasourceConfiguration
from noxus_sdk.plugins.types import PluginCategory
from noxus_sdk.plugins.worker import build_handlers
from noxus_sdk.triggers import BasePollingTrigger, TriggerConfiguration


# --------------------------------------------------------------------------- #
# A real, minimal plugin: one plain node and one node that uses the file
# helper callback during execution.
# --------------------------------------------------------------------------- #
class EchoConfig(NodeConfiguration):
    pass


class EchoNode(BaseNode[EchoConfig]):
    node_name = "EchoNode"
    title = "Echo Node"

    async def call(self, ctx: RemoteExecutionContext, text: str) -> dict[str, Any]:
        return {"echo": text}


class FetchConfig(NodeConfiguration):
    pass


class FetchNode(BaseNode[FetchConfig]):
    node_name = "FetchNode"
    title = "Fetch Node"

    async def call(self, ctx: RemoteExecutionContext, uri: str) -> dict[str, Any]:
        from noxus_sdk.files import File

        content = await ctx.get_file_helper().get_content(
            File(uri=uri, name="probe.txt")
        )
        return {"content": content.decode("utf-8")}


class CounterTriggerConfig(TriggerConfiguration):
    step: int = 1


class CounterTrigger(BasePollingTrigger[CounterTriggerConfig]):
    trigger_name = "CounterTrigger"
    title = "Counter Trigger"
    outputs = {"count": "int"}

    async def poll(
        self, ctx: RemoteExecutionContext, state: dict
    ) -> tuple[list[dict], dict]:
        count = int(state.get("count", 0)) + self.config.step
        return [{"count": count}], {"count": count}


class DriveConfig(DatasourceConfiguration):
    folder: str = ""


class DriveDatasource(BaseDataSource[DriveConfig]):
    datasource_name = "E2EDrive"
    title = "E2E Drive"
    description = "Returns one file per configured folder"
    integrations = ["e2e_drive"]

    async def fetch(self, ctx: RemoteExecutionContext) -> list[File]:
        from noxus_sdk.files import File

        return [File(uri="spot://f1", name=f"{self.config.folder}/a.txt")]


class ExampleConfig(PluginConfiguration):
    pass


class ExamplePlugin(BasePlugin[ExampleConfig]):
    name = "worker-test-plugin"
    display_name = "Worker Test Plugin"
    version = "0.0.1"
    description = "Plugin exercising the worker transport"
    category = PluginCategory.OTHER
    author = "tests"
    execution = "runtime"

    def nodes(self) -> list[type[BaseNode]]:
        return [EchoNode, FetchNode]

    def triggers(self) -> list[type[BasePollingTrigger]]:
        return [CounterTrigger]

    def datasources(self) -> list[type[BaseDataSource]]:
        return [DriveDatasource]


# --------------------------------------------------------------------------- #
# Harness: two cross-wired peers over in-memory line queues.
# --------------------------------------------------------------------------- #
@contextlib.asynccontextmanager
async def linked():
    a2b: asyncio.Queue[str] = asyncio.Queue()
    b2a: asyncio.Queue[str] = asyncio.Queue()
    host = JsonRpcPeer(b2a.get, a2b.put)
    worker = JsonRpcPeer(a2b.get, b2a.put)
    tasks = [asyncio.ensure_future(host.run()), asyncio.ensure_future(worker.run())]
    try:
        yield host, worker
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def run(coro) -> Any:
    return asyncio.run(coro)


# --------------------------------------------------------------------------- #
# Pure peer behaviour
# --------------------------------------------------------------------------- #
def test_request_response_round_trip():
    async def scenario():
        async with linked() as (host, worker):
            worker.register("add", lambda p: _ok(p["a"] + p["b"]))
            assert await host.call("add", {"a": 2, "b": 3}) == 5

    run(scenario())


def test_method_not_found():
    async def scenario():
        async with linked() as (host, worker):
            try:
                await host.call("nope")
            except JsonRpcError as e:
                assert e.code == METHOD_NOT_FOUND
            else:
                raise AssertionError("expected JsonRpcError")

    run(scenario())


def test_handler_error_propagates_code():
    async def scenario():
        async with linked() as (host, worker):

            async def boom(_: dict) -> object:
                raise JsonRpcError(COMPONENT_NOT_FOUND, "missing thing")

            worker.register("boom", boom)
            try:
                await host.call("boom")
            except JsonRpcError as e:
                assert e.code == COMPONENT_NOT_FOUND
                assert "missing thing" in e.message
            else:
                raise AssertionError("expected JsonRpcError")

    run(scenario())


def test_mid_request_callback_round_trip():
    """The decisive spike: worker calls back to host while handling a request."""

    async def scenario():
        async with linked() as (host, worker):
            host.register("host.ping", lambda p: _ok(f"pong:{p['n']}"))

            async def relay(params: dict) -> object:
                # Issue an outbound call to the host from inside a handler.
                return await worker.call("host.ping", {"n": params["n"]})

            worker.register("relay", relay)
            assert await host.call("relay", {"n": 7}) == "pong:7"

    run(scenario())


# --------------------------------------------------------------------------- #
# Worker handlers over a real dispatcher
# --------------------------------------------------------------------------- #
def _dispatcher() -> PluginDispatcher:
    return PluginDispatcher(ExamplePlugin, "worker-test-plugin")


def test_worker_node_execute_matches_direct_dispatch():
    async def scenario():
        dispatcher = _dispatcher()
        async with linked() as (host, worker):
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)

            rpc = await host.call(
                "node.execute",
                {
                    "node_name": "EchoNode",
                    "ctx": {},
                    "inputs": {"text": "hi"},
                    "config": {},
                },
            )

        # Parity with the serve.py path (direct dispatch, no transport).
        direct = await dispatcher.execute_node(
            "EchoNode", RemoteExecutionContext(), {"text": "hi"}, {}
        )
        assert rpc == direct.model_dump(mode="json")
        assert rpc["outputs"] == {"echo": "hi"}

    run(scenario())


def test_worker_file_callback_during_execute():
    async def scenario():
        dispatcher = _dispatcher()
        async with linked() as (host, worker):
            # Host services the plugin's file fetch over the same channel.
            def get_content(params: dict) -> object:
                assert params["file"]["uri"] == "spot://probe"
                return _ok_dict(
                    {"content_base64": base64.b64encode(b"hello world").decode()}
                )

            host.register("host.get_content", get_content)
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)

            rpc = await host.call(
                "node.execute",
                {
                    "node_name": "FetchNode",
                    "ctx": {},
                    "inputs": {"uri": "spot://probe"},
                    "config": {},
                },
            )
        assert rpc["outputs"] == {"content": "hello world"}

    run(scenario())


def test_file_callback_carries_the_originating_request_id():
    """One warm worker is shared by every platform process, and only the process
    that issued a call can resolve the call token its callbacks present. The
    session multiplexer routes a callback by this `origin`, so the worker has to
    stamp it — see agentsandbox.worker_session._callback_client."""

    async def scenario():
        dispatcher = _dispatcher()
        a2b: asyncio.Queue[str] = asyncio.Queue()
        b2a: asyncio.Queue[str] = asyncio.Queue()
        worker_frames: list[dict] = []

        async def worker_writes(line: str) -> None:
            worker_frames.append(json.loads(line))
            await b2a.put(line)

        host = JsonRpcPeer(b2a.get, a2b.put)
        worker = JsonRpcPeer(a2b.get, worker_writes)
        tasks = [asyncio.ensure_future(host.run()), asyncio.ensure_future(worker.run())]
        try:
            host.register(
                "host.get_content",
                lambda _p: _ok_dict(
                    {"content_base64": base64.b64encode(b"hi").decode()}
                ),
            )
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)

            await host.call(
                "node.execute",
                {
                    "node_name": "FetchNode",
                    "ctx": {},
                    "inputs": {"uri": "spot://probe"},
                    "config": {},
                },
            )
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        request = next(
            f for f in worker_frames if f.get("method") == "host.get_content"
        )
        response = next(f for f in worker_frames if "result" in f)
        # The id the host used for node.execute — a real deployment sees the
        # session's composite "{client}:{id}" here, opaque to the worker.
        assert request["origin"] == response["id"]

    run(scenario())


def test_response_frames_carry_no_origin():
    async def scenario():
        frames: list[dict] = []
        a2b: asyncio.Queue[str] = asyncio.Queue()
        b2a: asyncio.Queue[str] = asyncio.Queue()

        async def worker_writes(line: str) -> None:
            frames.append(json.loads(line))
            await b2a.put(line)

        host = JsonRpcPeer(b2a.get, a2b.put)
        worker = JsonRpcPeer(a2b.get, worker_writes)
        tasks = [asyncio.ensure_future(host.run()), asyncio.ensure_future(worker.run())]
        try:
            worker.register("add", lambda p: _ok(p["a"] + p["b"]))
            assert await host.call("add", {"a": 1, "b": 1}) == 2
        finally:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        assert frames and all("origin" not in f for f in frames)

    run(scenario())


def test_worker_unknown_node_maps_to_component_not_found():
    async def scenario():
        dispatcher = _dispatcher()
        async with linked() as (host, worker):
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)
            try:
                await host.call(
                    "node.execute",
                    {"node_name": "Ghost", "ctx": {}, "inputs": {}, "config": {}},
                )
            except JsonRpcError as e:
                assert e.code == COMPONENT_NOT_FOUND
                assert "Ghost" in e.message
            else:
                raise AssertionError("expected JsonRpcError")

    run(scenario())


def test_worker_manifest_and_list_nodes():
    async def scenario():
        dispatcher = _dispatcher()
        async with linked() as (host, worker):
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)
            manifest = await host.call("manifest")
            listing = await host.call("list_nodes")
        assert manifest["name"] == "worker-test-plugin"
        node_names = {n["name"] for n in listing["nodes"]}
        assert {"EchoNode", "FetchNode"} <= node_names
        assert manifest["triggers"][0]["type"] == "CounterTrigger"
        # The datasource surfaces in the manifest alongside nodes/triggers.
        assert manifest["datasources"][0]["type"] == "E2EDrive"
        assert manifest["datasources"][0]["integrations"] == ["e2e_drive"]

    run(scenario())


def test_worker_datasource_fetch_returns_files():
    async def scenario():
        dispatcher = _dispatcher()
        async with linked() as (host, worker):
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)
            result = await host.call(
                "datasource.fetch",
                {
                    "datasource_name": "E2EDrive",
                    "ctx": {},
                    "config": {"folder": "docs"},
                },
            )
        # Files come back as JSON descriptors, config threaded through.
        assert [f["name"] for f in result["files"]] == ["docs/a.txt"]

    run(scenario())


def test_worker_unknown_datasource_maps_to_component_not_found():
    async def scenario():
        dispatcher = _dispatcher()
        async with linked() as (host, worker):
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)
            try:
                await host.call(
                    "datasource.fetch",
                    {"datasource_name": "Ghost", "ctx": {}, "config": {}},
                )
            except JsonRpcError as e:
                assert e.code == COMPONENT_NOT_FOUND
                assert "Ghost" in e.message
            else:
                raise AssertionError("expected JsonRpcError")

    run(scenario())


def test_worker_trigger_poll_carries_state():
    async def scenario():
        dispatcher = _dispatcher()
        async with linked() as (host, worker):
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)
            first = await host.call(
                "trigger.poll",
                {
                    "trigger_name": "CounterTrigger",
                    "ctx": {},
                    "config": {"step": 3},
                    "state": {},
                },
            )
            second = await host.call(
                "trigger.poll",
                {
                    "trigger_name": "CounterTrigger",
                    "ctx": {},
                    "config": {"step": 3},
                    "state": first["state"],
                },
            )
        assert first == {"events": [{"count": 3}], "state": {"count": 3}}
        assert second == {"events": [{"count": 6}], "state": {"count": 6}}

    run(scenario())


def test_worker_unknown_trigger_maps_to_component_not_found():
    async def scenario():
        dispatcher = _dispatcher()
        async with linked() as (host, worker):
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)
            try:
                await host.call(
                    "trigger.poll",
                    {"trigger_name": "Ghost", "ctx": {}, "config": {}, "state": {}},
                )
            except JsonRpcError as e:
                assert e.code == COMPONENT_NOT_FOUND
                assert "Ghost" in e.message
            else:
                raise AssertionError("expected JsonRpcError")

    run(scenario())


# small async helpers so handlers can be plain lambdas returning awaitables
async def _ok(value: object) -> object:
    return value


async def _ok_dict(value: dict) -> dict:
    return value


# --------------------------------------------------------------------------- #
# V1 and V2 nodes are declared side by side and split into separate manifest
# lists by their base class — a plugin ships both as distinct entities.
# --------------------------------------------------------------------------- #
class _EchoV2Config(NodeConfiguration):
    text: str = Parameter(default="", bindable=True)


class _EchoV2Outputs(NodeOutputs):
    echo: str


class _EchoV2Node(BaseNodeV2[_EchoV2Config, _EchoV2Outputs]):
    node_name = "EchoV2Node"
    title = "Echo V2"

    async def call(self, ctx: RemoteExecutionContext) -> dict[str, Any]:
        return {"echo": self.config.text}


class _MixedPlugin(BasePlugin[ExampleConfig]):
    name = "mixed-plugin"
    display_name = "Mixed Plugin"
    version = "0.0.1"
    description = "V1 + V2 nodes"
    author = "tests"

    def nodes(self) -> list[type[BaseNode]]:
        return [EchoNode, _EchoV2Node]


def test_manifest_splits_v1_and_v2_nodes():
    manifest = _MixedPlugin.get_manifest()
    assert [n.type for n in manifest.nodes] == ["EchoNode"]
    assert [n.type for n in manifest.nodes_v2] == ["EchoV2Node"]
