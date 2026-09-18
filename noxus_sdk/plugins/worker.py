"""Warm plugin worker: a JSON-RPC dispatcher hosted inside a sandbox.

The platform's plugin runtime starts ``noxus plugin worker`` once per plugin
inside an isolated sandbox. The plugin module graph is imported a single time;
every subsequent request (node execute/config, integration checks, trigger
poll, manifest) is dispatched to the already-warm process over a
line-delimited JSON-RPC channel on stdin/stdout, which the sandbox manager
bridges to every platform process holding the worker's WebSocket.

Two properties make this strictly better than running the plugin's HTTP
server inside the sandbox:

- No cold start per request — imports and any module-level state stay warm.
- No outbound network from the sandbox to the platform: file get/upload are
  serviced as JSON-RPC *callbacks* over the same channel (see
  :class:`RpcFileHelper`), so the plugin works even when the sandbox blocks
  egress to internal addresses.

stdout carries only protocol lines; all logging goes to stderr.
"""

from __future__ import annotations

import asyncio
import base64
import sys
from typing import TYPE_CHECKING, cast

from loguru import logger

from noxus_sdk.nodes.schemas import ConfigResponse
from noxus_sdk.plugins.context import (
    CredentialsHelper,
    FileHelper,
    RemoteExecutionContext,
)
from noxus_sdk.plugins.dispatch import ComponentNotFoundError, PluginDispatcher
from noxus_sdk.plugins.jsonrpc import (
    COMPONENT_NOT_FOUND,
    JsonRpcError,
    JsonRpcPeer,
    JsonValue,
)
from noxus_sdk.plugins.validate import discover_and_load_plugin

if TYPE_CHECKING:
    from pathlib import Path

    from noxus_sdk.files import File, SourceMetadata, SourceType
    from noxus_sdk.plugins.jsonrpc import Handler

# Ceiling on one JSON-RPC line. Kept in lockstep with the sandbox manager's
# STDIO_STREAM_LIMIT (agentsandbox/providers/base.py) and the platform's
# WS_MAX_MESSAGE_BYTES (spotflow/plugins_runtime.py) — the smallest of the
# three is what actually caps a file callback.
STDIO_STREAM_LIMIT = 2**27


class RpcFileHelper(FileHelper):
    """Services a plugin's file operations as callbacks to the host.

    Instead of HTTP-calling the platform (which a jailed sandbox cannot
    reach), each operation becomes an outbound JSON-RPC request on the same
    channel the call arrived on, answered in-process by the platform against
    its own DB and storage. ``call_token`` is minted per call by the host and
    is what scopes the operation to the calling workspace — without it the
    host refuses the callback.
    """

    def __init__(self, peer: JsonRpcPeer, call_token: str | None = None) -> None:
        self._peer = peer
        self._call_token = call_token

    async def get_content(self, file: File) -> bytes:
        result = await self._peer.call(
            "host.get_content",
            {"file": file.model_dump(), "call_token": self._call_token},
        )
        content = result.get("content_base64") if isinstance(result, dict) else None
        if not isinstance(content, str):
            raise RuntimeError("host.get_content returned no content")
        return base64.b64decode(content)

    async def upload_file(
        self,
        file_name: str,
        content: bytes,
        content_type: str = "text/plain",
        source_type: SourceType | str = "Document",
        source_metadata: SourceMetadata | dict | None = None,
        group_id: str | None = None,
    ) -> dict:
        source_type_val = getattr(source_type, "value", source_type)  # noqa: lint-ignore - external SDK, not under backend lint
        result = await self._peer.call(
            "host.upload_file",
            {
                "file_name": file_name,
                "content_base64": base64.b64encode(content).decode("utf-8"),
                "content_type": content_type,
                "source_type": source_type_val,
                "source_metadata": source_metadata,
                # The host resolves the workspace from call_token; group_id is
                # advisory and is rejected if it isn't the caller's own.
                "group_id": group_id,
                "call_token": self._call_token,
            },
        )
        return result if isinstance(result, dict) else {}


class RpcCredentialsHelper(CredentialsHelper):
    """Pushes an updated credential payload back to the host as a callback.

    Same channel and scoping model as :class:`RpcFileHelper`: the host
    resolves the workspace and owning plugin from ``call_token`` and refuses
    integrations the plugin does not declare."""

    def __init__(self, peer: JsonRpcPeer, call_token: str | None = None) -> None:
        self._peer = peer
        self._call_token = call_token

    async def update_integration_credentials(
        self,
        integration_name: str,
        payload: dict,
        credential_id: str | None = None,
    ) -> None:
        await self._peer.call(
            "host.update_credentials",
            {
                "integration_name": integration_name,
                "payload": payload,
                "credential_id": credential_id,
                "call_token": self._call_token,
            },
        )


def build_handlers(
    dispatcher: PluginDispatcher, peer: JsonRpcPeer
) -> dict[str, Handler]:
    """Map JSON-RPC methods onto dispatcher operations.

    This is the platform's whole plugin surface. The local-dev HTTP server
    (serve.py) mirrors all of it except ``trigger.poll``, which only the
    platform drives.
    """

    def _ctx(params: dict) -> RemoteExecutionContext:
        ctx = RemoteExecutionContext(**(params.get("ctx") or {}))
        ctx.set_file_helper(RpcFileHelper(peer, ctx.call_token))
        ctx.set_credentials_helper(RpcCredentialsHelper(peer, ctx.call_token))
        return ctx

    async def manifest(_: dict) -> JsonValue:
        return dispatcher.manifest().model_dump(mode="json")

    async def list_nodes(_: dict) -> JsonValue:
        return dispatcher.list_nodes()

    async def validate_config(params: dict) -> JsonValue:
        return dispatcher.validate_config(params.get("config") or {}).model_dump()

    async def node_execute(params: dict) -> JsonValue:
        try:
            result = await dispatcher.execute_node(
                params["node_name"],
                _ctx(params),
                params.get("inputs") or {},
                params.get("config") or {},
            )
        except ComponentNotFoundError as e:
            raise JsonRpcError(COMPONENT_NOT_FOUND, str(e)) from e
        return result.model_dump(mode="json")

    async def node_config(params: dict) -> JsonValue:
        try:
            result = await dispatcher.node_config(
                params["node_name"],
                _ctx(params),
                ConfigResponse(**(params.get("config") or {})),
                skip_cache=bool(params.get("skip_cache", False)),
            )
        except ComponentNotFoundError as e:
            raise JsonRpcError(COMPONENT_NOT_FOUND, str(e)) from e
        return result.model_dump(mode="json")

    async def integration_config(params: dict) -> JsonValue:
        try:
            return await dispatcher.integration_config(params["integration_name"])
        except ComponentNotFoundError as e:
            raise JsonRpcError(COMPONENT_NOT_FOUND, str(e)) from e

    async def integration_ready(params: dict) -> JsonValue:
        try:
            return await dispatcher.integration_ready(
                params["integration_name"], params.get("creds")
            )
        except ComponentNotFoundError as e:
            raise JsonRpcError(COMPONENT_NOT_FOUND, str(e)) from e

    async def integration_device_auth_start(params: dict) -> JsonValue:
        try:
            result = await dispatcher.integration_device_auth_start(
                params["integration_name"], _ctx(params)
            )
        except ComponentNotFoundError as e:
            raise JsonRpcError(COMPONENT_NOT_FOUND, str(e)) from e
        return result.model_dump(mode="json")

    async def integration_device_auth_poll(params: dict) -> JsonValue:
        try:
            result = await dispatcher.integration_device_auth_poll(
                params["integration_name"], _ctx(params), params["session_id"]
            )
        except ComponentNotFoundError as e:
            raise JsonRpcError(COMPONENT_NOT_FOUND, str(e)) from e
        return result.model_dump(mode="json")

    async def trigger_poll(params: dict) -> JsonValue:
        try:
            events, state = await dispatcher.trigger_poll(
                params["trigger_name"],
                _ctx(params),
                params.get("config") or {},
                params.get("state") or {},
            )
        except ComponentNotFoundError as e:
            raise JsonRpcError(COMPONENT_NOT_FOUND, str(e)) from e
        result: dict[str, JsonValue] = {
            "events": cast("list[JsonValue]", events),
            "state": cast("JsonValue", state),
        }
        return result

    async def datasource_fetch(params: dict) -> JsonValue:
        try:
            files = await dispatcher.datasource_fetch(
                params["datasource_name"],
                _ctx(params),
                params.get("config") or {},
            )
        except ComponentNotFoundError as e:
            raise JsonRpcError(COMPONENT_NOT_FOUND, str(e)) from e
        return cast("JsonValue", {"files": files})

    return {
        "manifest": manifest,
        "list_nodes": list_nodes,
        "validate_config": validate_config,
        "node.execute": node_execute,
        "node.config": node_config,
        "integration.config": integration_config,
        "integration.ready": integration_ready,
        "integration.device_auth_start": integration_device_auth_start,
        "integration.device_auth_poll": integration_device_auth_poll,
        "trigger.poll": trigger_poll,
        "datasource.fetch": datasource_fetch,
    }


def load_dispatcher(plugin_folder: Path) -> PluginDispatcher:
    """Discover and import the plugin, returning a ready dispatcher."""
    plugin_class, validation_result = discover_and_load_plugin(plugin_folder)
    if validation_result.errors or plugin_class is None:
        for error in validation_result.errors:
            logger.error(f"  - {error}")
        raise ValueError(
            f"Could not load plugin from {plugin_folder}: {validation_result.errors}"
        )
    for warning in validation_result.warnings:
        logger.warning(f"Plugin warning: {warning}")
    plugin_name = getattr(plugin_class, "__name__", plugin_folder.name)  # noqa: lint-ignore - external SDK
    return PluginDispatcher(plugin_class, plugin_name)


async def _stdio_lines() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Wrap process stdin/stdout as asyncio line streams.

    The limit is explicit and must stay >= the sandbox manager's
    STDIO_STREAM_LIMIT: a whole file crosses this channel base64-encoded on a
    single line (host.get_content), and asyncio's 64 KiB default made
    readline() raise on any file over ~48 KB. That raise unwinds peer.run(),
    which fails the in-flight callback with "JSON-RPC peer transport closed"
    and kills the worker for every other flow sharing it.
    """
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader(limit=STDIO_STREAM_LIMIT)
    await loop.connect_read_pipe(
        lambda: asyncio.StreamReaderProtocol(reader), sys.stdin
    )
    transport, protocol = await loop.connect_write_pipe(
        asyncio.streams.FlowControlMixin, sys.stdout
    )
    writer = asyncio.StreamWriter(transport, protocol, reader, loop)
    return reader, writer


async def run_worker(plugin_folder: Path) -> None:
    """Load the plugin and serve JSON-RPC over stdio until EOF."""
    # Keep stdout pristine for protocol frames; logs go to stderr only.
    logger.remove()
    logger.add(sys.stderr, level="INFO", diagnose=False)

    dispatcher = load_dispatcher(plugin_folder)
    reader, writer = await _stdio_lines()

    async def read_line() -> str | None:
        raw = await reader.readline()
        return raw.decode("utf-8", errors="replace") if raw else None

    async def write_line(line: str) -> None:
        writer.write((line + "\n").encode("utf-8"))
        await writer.drain()

    peer = JsonRpcPeer(read_line, write_line)
    for method, handler in build_handlers(dispatcher, peer).items():
        peer.register(method, handler)  # type: ignore[arg-type]

    logger.info(
        f"Plugin worker ready: {dispatcher.plugin_name} "
        f"({len(dispatcher.node_map)} nodes, "
        f"{len(dispatcher.integration_map)} integrations, "
        f"{len(dispatcher.trigger_map)} triggers, "
        f"{len(dispatcher.datasource_map)} datasources)"
    )
    await peer.run()
