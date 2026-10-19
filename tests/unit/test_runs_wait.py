"""Run waits must confirm stored status even after a terminal event or EOF."""

import json
from typing import Callable

import httpx
import pytest

from noxus_sdk.client import Client
from noxus_sdk.resources.runs import Run, RunFailureError

_FAILURE_META = {
    "error": "This workspace has used all 2 of its AI Operations",
    "error_code": "payment_required",
    "error_type": "PaymentRequiredError",
}


def _run(
    handler: Callable[[httpx.Request], httpx.Response], status: str = "running"
) -> Run:
    client = Client(
        api_key="test",
        load_nodes=False,
        load_me=False,
        transport=httpx.MockTransport(handler),
    )
    return Run(
        client=client,
        id="run",
        group_id="group",
        workflow_id="workflow",
        input={},
        status=status,
        progress=0,
        created_at="2026-10-16T00:00:00Z",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    ("stream", "status"),
    [
        ("terminal", "completed"),
        ("eof", "completed"),
        ("error", "completed"),
        ("terminal", "failed"),
        ("eof", "awaiting_human_feedback"),
    ],
)
async def test_wait_confirms_terminal_status(
    asynchronous: bool, stream: str, status: str
) -> None:
    reads = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal reads
        if request.url.path.endswith("/events"):
            if stream == "error":
                return httpx.Response(503)
            data = json.dumps({"data": {"workflow_status": status}})
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=f"event: message\ndata: {data}\n\n"
                if stream == "terminal"
                else "",
            )
        if request.url.path == "/v1/runs/run":
            return httpx.Response(200, json={"meta": _FAILURE_META})
        reads += 1
        assert reads <= 2, "wait kept polling after the stored status became terminal"
        return httpx.Response(
            200,
            json={
                "status": "running" if reads == 1 else status,
                "output": None if reads == 1 else {"answer": "ready"},
            },
        )

    run = _run(handler)

    async def wait() -> Run | dict | None:
        if asynchronous:
            return await run.a_wait(interval=0, output_only=True)
        return run.wait(interval=0, output_only=True)

    if status == "failed":
        with pytest.raises(
            RunFailureError, match="used all 2 of its AI Operations"
        ) as e:
            await wait()
        assert (e.value.error_code, e.value.error_type) == (
            "payment_required",
            "PaymentRequiredError",
        )
    else:
        assert await wait() == {"answer": "ready"}
    assert run.status == status
    assert reads == 2


def test_a_failed_run_still_raises_when_its_reason_cannot_be_read() -> None:
    run = _run(lambda request: httpx.Response(403), status="failed")

    with pytest.raises(RunFailureError, match="^failed$") as e:
        run.wait(interval=0)
    assert e.value.error is None
