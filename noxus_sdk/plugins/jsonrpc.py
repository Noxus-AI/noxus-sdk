"""A minimal bidirectional JSON-RPC 2.0 peer over line-delimited transports.

Both sides may issue requests: the platform calls into the worker
(``node.execute`` etc.), and mid-request the worker calls back to the host
(``host.get_content`` / ``host.upload_file``). One message per line keeps it
compatible with the sandbox manager's stdio<->WebSocket bridge, which
forwards each stdout line as one WebSocket frame and vice-versa.

The peer is transport-agnostic: it takes ``read_line``/``write_line``
callables, so the worker wires it to stdio while tests wire it to in-memory
queues.
"""

from __future__ import annotations

import asyncio
import contextvars
import itertools
import json
from typing import TYPE_CHECKING, Awaitable, Callable, TypeAlias

from loguru import logger

# Any value expressible in JSON — the honest type of an RPC result/param.
# Not a PEP 695 `type` statement: the SDK supports Python 3.10+, and plugin
# sandboxes may run older interpreters that reject the 3.12 syntax.
JsonValue: TypeAlias = (
    str | int | float | bool | None | dict[str, "JsonValue"] | list["JsonValue"]
)

if TYPE_CHECKING:
    ReadLine = Callable[[], Awaitable[str | None]]
    WriteLine = Callable[[str], Awaitable[None]]
    Handler = Callable[[dict], Awaitable[JsonValue]]

# JSON-RPC error codes. The negative range below -32000 is reserved by the
# spec for implementation-defined server errors; we carve out a code for the
# "node/integration not found" case so callers can distinguish it.
METHOD_NOT_FOUND = -32601
SERVER_ERROR = -32000
COMPONENT_NOT_FOUND = -32004

# Non-standard envelope member naming the request a peer was servicing when it
# issued this one. A worker is shared by every platform process, so a callback
# raised mid-request has to be answered by the *same* process that made that
# request — only it holds the call token the callback presents. Set
# automatically for calls made from inside a handler; ignored by peers that
# don't multiplex.
ORIGIN_KEY = "origin"

_current_request_id: contextvars.ContextVar[JsonValue] = contextvars.ContextVar(
    "jsonrpc_current_request_id", default=None
)


class JsonRpcError(Exception):
    """A JSON-RPC error, either received from the peer or raised by a handler.

    When raised inside a request handler, ``code``/``message``/``data`` are
    sent back verbatim as the error response — this is how the worker maps a
    missing node to :data:`COMPONENT_NOT_FOUND` without the peer needing to
    know about plugin semantics.
    """

    def __init__(self, code: int, message: str, data: JsonValue = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    @classmethod
    def from_payload(cls, payload: dict) -> JsonRpcError:
        return cls(
            code=int(payload.get("code", SERVER_ERROR)),
            message=str(payload.get("message", "")),
            data=payload.get("data"),
        )

    def to_payload(self) -> dict:
        payload: dict = {"code": self.code, "message": self.message}
        if self.data is not None:
            payload["data"] = self.data
        return payload


class JsonRpcPeer:
    """Drives a JSON-RPC session over a pair of line callables."""

    def __init__(
        self,
        read_line: ReadLine,
        write_line: WriteLine,
        handlers: dict[str, Handler] | None = None,
    ) -> None:
        self._read_line = read_line
        self._write_line = write_line
        self._handlers: dict[str, Handler] = handlers or {}
        self._pending: dict[int, asyncio.Future[JsonValue]] = {}
        self._ids = itertools.count(1)
        self._write_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[None]] = set()

    def register(self, method: str, handler: Handler) -> None:
        self._handlers[method] = handler

    # -- outbound ------------------------------------------------------------

    async def call(self, method: str, params: dict | None = None) -> JsonValue:
        """Send a request and await its result (raises on error response)."""
        msg_id = next(self._ids)
        fut: asyncio.Future[JsonValue] = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = fut
        try:
            await self._send(
                self._tag_origin(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "method": method,
                        "params": params or {},
                    }
                )
            )
            return await fut
        finally:
            # Drop the entry on cancellation/timeout too, or a long-lived peer
            # accumulates dangling futures across repeated wait_for timeouts.
            self._pending.pop(msg_id, None)

    async def notify(self, method: str, params: dict | None = None) -> None:
        """Send a notification (no response expected) — used for trigger events."""
        await self._send(
            self._tag_origin(
                {"jsonrpc": "2.0", "method": method, "params": params or {}}
            )
        )

    def _tag_origin(self, msg: dict) -> dict:
        origin = _current_request_id.get()
        return msg if origin is None else {**msg, ORIGIN_KEY: origin}

    # -- loop ----------------------------------------------------------------

    async def run(self) -> None:
        """Read and dispatch messages until the transport reaches EOF."""
        try:
            while True:
                raw = await self._read_line()
                if not raw:  # EOF (None or "")
                    break
                line = raw.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("Dropping non-JSON line on JSON-RPC transport")
                    continue
                if not isinstance(msg, dict):
                    continue
                if "method" in msg:
                    self._spawn(self._handle_request(msg))
                elif "id" in msg:
                    self._resolve_response(msg)
        finally:
            self._fail_pending(ConnectionError("JSON-RPC peer transport closed"))

    def _spawn(self, coro: Awaitable[None]) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _handle_request(self, msg: dict) -> None:
        method = msg["method"]
        params = msg.get("params") or {}
        msg_id = msg.get("id")
        handler = self._handlers.get(method)

        if handler is None:
            if msg_id is not None:
                await self._send_error(
                    msg_id,
                    JsonRpcError(METHOD_NOT_FOUND, f"Method not found: {method}"),
                )
            return

        # Each request is handled in its own task, so this stamps the id only
        # for the callbacks that this handler raises (see ORIGIN_KEY).
        _current_request_id.set(msg_id)
        try:
            result = await handler(params)
        except JsonRpcError as e:
            if msg_id is not None:
                await self._send_error(msg_id, e)
            return
        except Exception as e:  # noqa: BLE001 - untrusted plugin code; surface as error response
            logger.exception(f"Handler for {method} failed")
            if msg_id is not None:
                await self._send_error(msg_id, JsonRpcError(SERVER_ERROR, str(e)))
            return

        if msg_id is not None:
            await self._send({"jsonrpc": "2.0", "id": msg_id, "result": result})

    def _resolve_response(self, msg: dict) -> None:
        fut = self._pending.pop(msg["id"], None)
        if fut is None or fut.done():
            return
        error = msg.get("error")
        if error is not None:
            fut.set_exception(JsonRpcError.from_payload(error))
        else:
            fut.set_result(msg.get("result"))

    def _fail_pending(self, exc: BaseException) -> None:
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(exc)
        self._pending.clear()

    async def _send_error(self, msg_id: int, error: JsonRpcError) -> None:
        await self._send({"jsonrpc": "2.0", "id": msg_id, "error": error.to_payload()})

    async def _send(self, obj: dict) -> None:
        line = json.dumps(obj)
        async with self._write_lock:
            await self._write_line(line)
