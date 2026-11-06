import os
from pathlib import Path
from typing import cast

import pytest

from noxus_sdk.files import (
    File,
    persist_files,
    persist_files_locally,
    safe_file_name,
    unique_local_path,
)
from noxus_sdk.plugins.context import RemoteExecutionContext


class _Helper:
    async def get_content(self, file: File) -> bytes:
        return file.name.encode()


class _Context:
    def get_file_helper(self) -> _Helper:
        return _Helper()


CTX = cast(RemoteExecutionContext, _Context())


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("../../site-packages/evil.pth", "evil.pth"),
        ("/etc/cron.d/job", "job"),
        ("..\\win.ini", "win.ini"),
        ("..", "file"),
        ("a\x00b.txt", "ab.txt"),
        ("Rapport\u00a0final.pdf", "Rapport\u00a0final.pdf"),
        ("a\u200db.txt", "a\u200db.txt"),
        ("invoice\u202egpj.exe", "invoicegpj.exe"),
        ("a\u2066b\u2069.txt", "ab.txt"),
    ],
)
def test_safe_file_name(name: str, expected: str) -> None:
    assert safe_file_name(name) == expected


@pytest.mark.asyncio
async def test_attachment_names_stay_inside_the_folder(tmp_path: Path) -> None:
    names = ["../escape.txt", "/tmp/abs.txt", "same.pdf", "x/same.pdf"]
    files = [File(uri="spot://x", name=name) for name in names]

    paths = await persist_files(CTX, files, str(tmp_path / "out"))

    assert [os.path.basename(p) for p in paths] == [
        "escape.txt",
        "abs.txt",
        "same.pdf",
        "same (1).pdf",
    ]
    assert all(Path(p).parent == (tmp_path / "out").resolve() for p in paths)
    assert [Path(p).read_bytes() for p in paths] == [n.encode() for n in names]
    assert not (tmp_path / "escape.txt").exists()


@pytest.mark.asyncio
async def test_persist_files_locally_returns_the_folder(tmp_path: Path) -> None:
    folder = await persist_files_locally(
        CTX, [File(uri="spot://x", name="../a.csv")], str(tmp_path / "out")
    )
    assert os.listdir(folder) == ["a.csv"]


@pytest.mark.parametrize(
    ("name", "ending"),
    [("a" * 251 + ".txt", " (1).txt"), ("a." + "x" * 253, " (1)")],
    ids=["long-stem", "long-extension"],
)
def test_a_numbered_name_still_fits_a_file_name(
    tmp_path: Path, name: str, ending: str
) -> None:
    first = unique_local_path(str(tmp_path), name)
    Path(first).write_bytes(b"1")
    second = unique_local_path(str(tmp_path), name)
    Path(second).write_bytes(b"2")

    assert second.endswith(ending)
    assert [len(os.path.basename(p).encode()) for p in (first, second)] == [255, 255]
