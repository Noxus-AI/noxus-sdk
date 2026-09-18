"""Device-code auth flow + credential write-back over the worker transport."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, ClassVar

from noxus_sdk.integrations.base import BaseCredentials, BaseIntegration
from noxus_sdk.integrations.schemas import DeviceAuthPoll, DeviceAuthStart
from noxus_sdk.nodes.base import BaseNode, NodeConfiguration
from noxus_sdk.plugins import BasePlugin, PluginConfiguration
from noxus_sdk.plugins.context import RemoteExecutionContext
from noxus_sdk.plugins.dispatch import PluginDispatcher
from noxus_sdk.plugins.jsonrpc import (
    COMPONENT_NOT_FOUND,
    JsonRpcError,
    JsonRpcPeer,
)
from noxus_sdk.plugins.types import PluginCategory
from noxus_sdk.plugins.worker import build_handlers


class DeviceCredentials(BaseCredentials):
    type: ClassVar[str] = "device_service"
    token: str = ""

    def is_ready(self) -> bool:
        return bool(self.token)


class DeviceIntegration(BaseIntegration[DeviceCredentials]):
    display_name = "Device Service"
    image = ""
    supports_device_auth = True
    device_auth_label = "Sign in with Device Service"

    @classmethod
    async def device_auth_start(cls, ctx: RemoteExecutionContext) -> DeviceAuthStart:
        return DeviceAuthStart(
            session_id="s1",
            verification_url="https://example.com/device",
            user_code="AAAA-BBBB",
        )

    @classmethod
    async def device_auth_poll(
        cls, ctx: RemoteExecutionContext, session_id: str
    ) -> DeviceAuthPoll:
        assert session_id == "s1"
        return DeviceAuthPoll(status="complete", credentials={"token": "tok"})


class PlainCredentials(BaseCredentials):
    type: ClassVar[str] = "plain_service"
    api_key: str = ""


class PlainIntegration(BaseIntegration[PlainCredentials]):
    display_name = "Plain Service"
    image = ""


class SyncConfig(NodeConfiguration):
    pass


class SyncNode(BaseNode[SyncConfig]):
    node_name = "SyncNode"
    title = "Sync Node"

    async def call(self, ctx: RemoteExecutionContext) -> dict[str, Any]:
        await ctx.update_integration_credentials("device_service", {"token": "fresh"})
        return {"ok": "yes"}


class _Config(PluginConfiguration):
    pass


class DevicePlugin(BasePlugin[_Config]):
    name = "device-plugin"
    display_name = "Device Plugin"
    version = "0.0.1"
    description = "test"
    category = PluginCategory.OTHER
    author = "test"

    def nodes(self) -> list[type[BaseNode]]:
        return [SyncNode]

    def integrations(self) -> list[type[BaseIntegration]]:
        return [DeviceIntegration, PlainIntegration]


def _dispatcher() -> PluginDispatcher:
    return PluginDispatcher(DevicePlugin, "device-auth-test-plugin")


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
        for t in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await t


def test_manifest_carries_device_auth() -> None:
    manifest = DevicePlugin.get_manifest()
    by_type = {i.type: i for i in manifest.integrations}
    assert by_type["device_service"].supports_device_auth is True
    assert by_type["device_service"].device_auth_label == "Sign in with Device Service"
    assert by_type["plain_service"].supports_device_auth is False


def test_device_auth_start_and_poll_over_rpc() -> None:
    async def scenario():
        dispatcher = _dispatcher()
        async with linked() as (host, worker):
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)

            start = await host.call(
                "integration.device_auth_start",
                {"integration_name": "device_service", "ctx": {}},
            )
            assert start["user_code"] == "AAAA-BBBB"
            assert start["verification_url"] == "https://example.com/device"

            poll = await host.call(
                "integration.device_auth_poll",
                {
                    "integration_name": "device_service",
                    "session_id": start["session_id"],
                    "ctx": {},
                },
            )
            assert poll["status"] == "complete"
            assert poll["credentials"] == {"token": "tok"}

    asyncio.run(scenario())


def test_device_auth_rejected_for_unsupported_integration() -> None:
    async def scenario():
        dispatcher = _dispatcher()
        async with linked() as (host, worker):
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)
            try:
                await host.call(
                    "integration.device_auth_start",
                    {"integration_name": "plain_service", "ctx": {}},
                )
            except JsonRpcError as e:
                assert e.code == COMPONENT_NOT_FOUND
            else:
                raise AssertionError("expected JsonRpcError")

    asyncio.run(scenario())


def test_credential_write_back_callback_carries_token_and_id() -> None:
    async def scenario():
        dispatcher = _dispatcher()
        received: list[dict] = []
        async with linked() as (host, worker):

            async def update_credentials(params: dict) -> dict:
                received.append(params)
                return {"status": "ok"}

            host.register("host.update_credentials", update_credentials)
            for name, handler in build_handlers(dispatcher, worker).items():
                worker.register(name, handler)

            result = await host.call(
                "node.execute",
                {
                    "node_name": "SyncNode",
                    "ctx": {
                        "call_token": "tkn",
                        "integration_credential_ids": {"device_service": "cred-1"},
                    },
                    "inputs": {},
                    "config": {},
                },
            )
        assert result["outputs"] == {"ok": "yes"}
        assert received == [
            {
                "integration_name": "device_service",
                "payload": {"token": "fresh"},
                # Auto-filled from ctx.integration_credential_ids so the host
                # updates the exact row the payload came from.
                "credential_id": "cred-1",
                "call_token": "tkn",
            }
        ]

    asyncio.run(scenario())
