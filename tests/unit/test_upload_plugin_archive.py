import io
import tarfile
from pathlib import Path

import pytest

from noxus_sdk.plugins.sources import upload
from noxus_sdk.plugins.sources.upload import UploadPluginSource


def _tar_bytes(members: list[tarfile.TarInfo]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for info in members:
            if info.isreg():
                payload = b"import os"
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            else:
                archive.addfile(info)
    return buffer.getvalue()


def _member(
    name: str, kind: bytes = tarfile.REGTYPE, link: str = ""
) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = link
    return info


@pytest.mark.asyncio
async def test_tar_link_members_cannot_write_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outside = tmp_path / "site-packages"
    outside.mkdir()
    archive = _tar_bytes(
        [
            _member("plugin/manifest.json"),
            _member("plugin/escape", tarfile.SYMTYPE, str(outside)),
            _member("plugin/escape/evil.pth"),
            _member("plugin/hard", tarfile.LNKTYPE, "/etc/passwd"),
        ]
    )

    async def fetch(_file_id: str) -> bytes:
        return archive

    monkeypatch.setattr(upload, "_platform_file_fetcher", fetch)
    target = tmp_path / "out"
    source = UploadPluginSource(file_id="f", filename="plugin.tar.gz")
    await source.download_plugin(target)

    assert not (outside / "evil.pth").exists()
    assert (target / "manifest.json").is_file()
    assert not any(p.is_symlink() for p in target.rglob("*"))
    assert not (target / "hard").exists()
