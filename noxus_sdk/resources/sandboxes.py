"""Sandboxes: create isolated environments and run commands in them.

with client.sandboxes.create(label="report") as sb:
    sb.files.write("/work/run.py", "print('hi')")
    result = sb.commands.run("python /work/run.py")
    print(result.stdout)
"""

from __future__ import annotations

import base64

from pydantic import BaseModel

from noxus_sdk.resources.base import BaseResource, BaseService


class Execution(BaseModel):
    """The result of a command run inside a sandbox."""

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def __repr__(self) -> str:
        return (
            f"Execution(exit_code={self.exit_code}, "
            f"stdout={self.stdout[:40]!r}, stderr={self.stderr[:40]!r})"
        )


class SandboxCommands:
    """``sandbox.commands`` — run shell commands."""

    def __init__(self, sandbox: "Sandbox") -> None:
        self._sandbox = sandbox

    def run(self, command: str, timeout: int | None = None) -> Execution:
        body: dict[str, str | int] = {"command": command}
        if timeout is not None:
            body["timeout"] = timeout
        response = self._sandbox.client.post(
            f"/v1/sandboxes/{self._sandbox.id}/commands", body
        )
        return Execution(**response)

    async def arun(self, command: str, timeout: int | None = None) -> Execution:
        body: dict[str, str | int] = {"command": command}
        if timeout is not None:
            body["timeout"] = timeout
        response = await self._sandbox.client.apost(
            f"/v1/sandboxes/{self._sandbox.id}/commands", body
        )
        return Execution(**response)


class SandboxFiles:
    """``sandbox.files`` — read and write files inside the sandbox."""

    def __init__(self, sandbox: "Sandbox") -> None:
        self._sandbox = sandbox

    def _write_body(self, path: str, content: str | bytes) -> dict[str, str]:
        if isinstance(content, bytes):
            return {
                "path": path,
                "content": base64.b64encode(content).decode(),
                "encoding": "base64",
            }
        return {"path": path, "content": content, "encoding": "utf-8"}

    def write(self, path: str, content: str | bytes) -> str:
        """Write text or bytes to ``path``; returns the path written."""
        response = self._sandbox.client.post(
            f"/v1/sandboxes/{self._sandbox.id}/files", self._write_body(path, content)
        )
        return response["path"]

    async def awrite(self, path: str, content: str | bytes) -> str:
        response = await self._sandbox.client.apost(
            f"/v1/sandboxes/{self._sandbox.id}/files", self._write_body(path, content)
        )
        return response["path"]

    def read(self, path: str) -> str:
        """Read ``path`` as utf-8 text. Use ``read_bytes`` for binary files."""
        response = self._sandbox.client.get(
            f"/v1/sandboxes/{self._sandbox.id}/files",
            params={"path": path, "encoding": "utf-8"},
        )
        return response["content"]

    async def aread(self, path: str) -> str:
        response = await self._sandbox.client.aget(
            f"/v1/sandboxes/{self._sandbox.id}/files",
            params={"path": path, "encoding": "utf-8"},
        )
        return response["content"]

    def read_bytes(self, path: str) -> bytes:
        response = self._sandbox.client.get(
            f"/v1/sandboxes/{self._sandbox.id}/files",
            params={"path": path, "encoding": "base64"},
        )
        return base64.b64decode(response["content"])

    async def aread_bytes(self, path: str) -> bytes:
        response = await self._sandbox.client.aget(
            f"/v1/sandboxes/{self._sandbox.id}/files",
            params={"path": path, "encoding": "base64"},
        )
        return base64.b64decode(response["content"])


class Sandbox(BaseResource):
    id: str
    status: str
    created_at: str
    last_activity: str
    label: str | None = None

    @property
    def commands(self) -> SandboxCommands:
        return SandboxCommands(self)

    @property
    def files(self) -> SandboxFiles:
        return SandboxFiles(self)

    def refresh(self) -> "Sandbox":
        response = self.client.get(f"/v1/sandboxes/{self.id}")
        return Sandbox(client=self.client, **response)

    async def arefresh(self) -> "Sandbox":
        response = await self.client.aget(f"/v1/sandboxes/{self.id}")
        return Sandbox(client=self.client, **response)

    def kill(self) -> bool:
        """Destroy the sandbox and its filesystem."""
        response = self.client.delete(f"/v1/sandboxes/{self.id}")
        return response["success"]

    async def akill(self) -> bool:
        response = await self.client.adelete(f"/v1/sandboxes/{self.id}")
        return response["success"]

    def __enter__(self) -> "Sandbox":
        return self

    def __exit__(self, *exc: object) -> None:
        self.kill()

    async def __aenter__(self) -> "Sandbox":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.akill()

    def __repr__(self) -> str:
        return f"Sandbox(id={self.id!r}, label={self.label!r}, status={self.status!r})"


class SandboxService(BaseService[Sandbox]):
    def create(self, label: str | None = None, *, persistent: bool = False) -> Sandbox:
        """Create a sandbox. Use it as a context manager to auto-destroy it."""
        response = self.client.post(
            "/v1/sandboxes", {"label": label, "persistent": persistent}
        )
        return Sandbox(client=self.client, **response)

    async def acreate(
        self, label: str | None = None, *, persistent: bool = False
    ) -> Sandbox:
        response = await self.client.apost(
            "/v1/sandboxes", {"label": label, "persistent": persistent}
        )
        return Sandbox(client=self.client, **response)

    def list(self) -> list[Sandbox]:
        response = self.client.get("/v1/sandboxes")
        return [Sandbox(client=self.client, **s) for s in response]

    async def alist(self) -> list[Sandbox]:
        response = await self.client.aget("/v1/sandboxes")
        return [Sandbox(client=self.client, **s) for s in response]

    def get(self, sandbox_id: str) -> Sandbox:
        response = self.client.get(f"/v1/sandboxes/{sandbox_id}")
        return Sandbox(client=self.client, **response)

    async def aget(self, sandbox_id: str) -> Sandbox:
        response = await self.client.aget(f"/v1/sandboxes/{sandbox_id}")
        return Sandbox(client=self.client, **response)

    def delete(self, sandbox_id: str) -> bool:
        response = self.client.delete(f"/v1/sandboxes/{sandbox_id}")
        return response["success"]

    async def adelete(self, sandbox_id: str) -> bool:
        response = await self.client.adelete(f"/v1/sandboxes/{sandbox_id}")
        return response["success"]
