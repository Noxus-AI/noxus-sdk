"""Content hash of an SDK source tree.

Stdlib only and runnable as a script: the sandbox image build stamps the hash
of the tree it wheeled into the plugin wheelhouse, and the platform compares
it against the SDK tree bundled in its own image before deciding whether that
wheel can stand in for an upload + editable install.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HASH_FILENAME = "noxus-sdk.sha256"


def sdk_source_hash(tree: Path) -> str:
    digest = hashlib.sha256()
    package = tree / "noxus_sdk"
    files = [tree / "pyproject.toml", *package.rglob("*")]
    for path in sorted(files, key=lambda p: p.relative_to(tree).as_posix()):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        digest.update(path.relative_to(tree).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


if __name__ == "__main__":
    sys.stdout.write(sdk_source_hash(Path(sys.argv[1])) + "\n")
