"""The worker's *real* stdio transport, over real pipes.

test_plugin_worker.py wires peers to in-memory queues, which have no line
limit — so it could not see that ``_stdio_lines`` inherited asyncio's 64 KiB
default. A plugin calling ``get_content`` on any file over ~48 KB blew that
limit; ``readline()`` raised, unwound ``peer.run()``, and the in-flight
callback came back as "JSON-RPC peer transport closed" — reported against
whichever node was running, with the worker process dead behind it.
"""

from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import sys
import textwrap

import pytest

from noxus_sdk.plugins.worker import STDIO_STREAM_LIMIT

CHILD = textwrap.dedent(
    """
    import asyncio
    import base64
    from noxus_sdk.plugins.jsonrpc import JsonRpcPeer
    from noxus_sdk.plugins.worker import _stdio_lines

    async def main():
        reader, writer = await _stdio_lines()

        async def read_line():
            raw = await reader.readline()
            return raw.decode("utf-8", errors="replace") if raw else None

        async def write_line(line):
            writer.write((line + "\\n").encode("utf-8"))
            await writer.drain()

        peer = JsonRpcPeer(read_line, write_line)

        async def node_execute(params):
            result = await peer.call("host.get_content", {"file": {"id": "x"}})
            return {"size": len(base64.b64decode(result["content_base64"]))}

        peer.register("node.execute", node_execute)
        await peer.run()

    asyncio.run(main())
    """
)


async def _execute_with_file_of(size: int, script: str) -> dict:
    """Run one node.execute against the child worker, answering its
    get_content callback with `size` bytes, and return the response."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-c",
        script,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        limit=STDIO_STREAM_LIMIT,
    )

    async def send(msg: dict) -> None:
        proc.stdin.write((json.dumps(msg) + "\n").encode())
        await proc.stdin.drain()

    try:
        await send({"jsonrpc": "2.0", "id": 1, "method": "node.execute", "params": {}})
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                pytest.fail(f"worker died without responding (rc={proc.returncode})")
            msg = json.loads(raw)
            if msg.get("method") == "host.get_content":
                await send(
                    {
                        "jsonrpc": "2.0",
                        "id": msg["id"],
                        "result": {
                            "content_base64": base64.b64encode(b"x" * size).decode()
                        },
                    }
                )
                continue
            if msg.get("id") == 1:
                return msg
    finally:
        proc.kill()
        await proc.wait()


@pytest.mark.parametrize("size", [10_000, 1_000_000])
def test_file_callback_survives_payloads_past_the_asyncio_default(size: int):
    response = asyncio.run(_execute_with_file_of(size, CHILD))
    assert "error" not in response, response.get("error")
    assert response["result"] == {"size": size}


def test_stdio_limit_matches_the_manager():
    # agentsandbox.providers.base.STDIO_STREAM_LIMIT — the manager reads the
    # worker's stdout with this, and a smaller limit on either side is the
    # one that bites.
    assert STDIO_STREAM_LIMIT == 2**27
