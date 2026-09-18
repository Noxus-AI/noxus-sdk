"""Doc paths are looked up the way an agent types them."""

from __future__ import annotations

import pytest

from noxus_sdk import documentation
from noxus_sdk.documentation import DocEntry, read_page


@pytest.fixture()
def one_page(monkeypatch: pytest.MonkeyPatch) -> DocEntry:
    entry = DocEntry(
        path="core/concepts/knowledge-bases",
        title="Knowledge bases",
        description="",
        content="body",
        section="core",
    )
    index = documentation.DocsIndex()
    index.entries.append(entry)
    index.by_path[entry.path] = entry
    index.loaded = True
    monkeypatch.setattr(documentation, "load_index", lambda: index)
    return entry


@pytest.mark.parametrize(
    "typed",
    [
        "core/concepts/knowledge-bases",
        "/core/concepts/knowledge-bases/",
        "Core/Concepts/Knowledge-Bases",
        "core/concepts/knowledge-bases.mdx",
        "Core/Concepts/Knowledge-Bases.MDX",
    ],
)
def test_read_page_normalises_slashes_suffix_and_case(
    one_page: DocEntry, typed: str
) -> None:
    assert read_page(typed)["path"] == one_page.path


def test_read_page_names_the_missing_path(one_page: DocEntry) -> None:
    with pytest.raises(KeyError, match="core/concepts/nope"):
        read_page("core/concepts/nope")
