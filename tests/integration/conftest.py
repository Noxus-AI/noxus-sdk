import os
import uuid
from pathlib import Path

import httpx
import pytest
from filelock import FileLock
from noxus_sdk.client import Client
from noxus_sdk.resources.admin import Workspace
from noxus_sdk.resources.knowledge_bases import (
    KBConfigV3,
)


def _best_effort_delete(workspace: Workspace) -> None:
    # The workspace delete cascade occasionally 504s server-side; a cleanup
    # failure must not fail an otherwise-passing test. Stale sdk-* workspaces
    # are reaped at the start of the next session by `workspace_client`.
    try:
        workspace.delete()
    except httpx.HTTPError as exc:
        print(
            f"warning: best-effort workspace cleanup failed for {workspace.id}: {exc}"
        )


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def workspace_client():
    client = Client(
        os.environ.get("NOXUS_API_KEY", ""),
        base_url=os.environ.get("NOXUS_BASE_URL", "https://backend.noxus.ai"),
    )

    fn = Path(".workspace_lock")
    with FileLock(str(fn) + ".lock") as lock:
        if fn.is_file():
            pass
        else:
            for workspace in client.admin.list_workspaces():
                if workspace.name.startswith("sdk-"):
                    print("Deleting", workspace.name)
                    _best_effort_delete(workspace)
            fn.touch()

    return client


@pytest.fixture
def api_key(workspace_client: Client):
    workspace = workspace_client.admin.create_workspace(f"sdk-{uuid.uuid4()}")
    api_key = workspace.add_api_key("test_key")
    yield api_key.value
    _best_effort_delete(workspace)


@pytest.fixture
def client(api_key: str):
    return Client(
        api_key,
        base_url=os.environ.get("NOXUS_BASE_URL", "https://backend.noxus.ai"),
    )


@pytest.fixture
async def test_file():
    f = Path("test_file.txt")
    f.write_text("Test content for document upload")

    yield f

    try:
        f.unlink()
    except Exception:
        pass


@pytest.fixture
async def kb(client: Client, test_file: Path):
    settings = KBConfigV3()

    kb = await client.knowledge_bases.acreate(
        name="test_kb",
        description="Test Knowledge Base",
        document_types=["text"],
        settings_=settings,
    )
    # await kb.aupload_document([test_file], prefix="/test1")

    yield kb

    try:
        await kb.adelete()
    except Exception:
        pass
