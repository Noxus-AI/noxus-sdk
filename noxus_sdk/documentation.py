"""Noxus documentation index — shared core for MCP tools and agent toolsets.

Lazily parses all MDX files from the noxus-docs directory into an in-memory
index. Provides list, read, and search operations over the index.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz

# Directories that are not documentation content
_SKIP_DIRS = {"images", "logo", "videos", "snippets", "openapi"}

# Matches JSX-style components: <Component>, <Component />, </Component>,
# and <Component prop="value">
_JSX_TAG_RE = re.compile(r"</?[A-Z][A-Za-z]*(?:\s[^>]*)?\s*/?>")


@dataclass
class DocEntry:
    """A single documentation page."""

    path: str  # e.g. "platform/agents/introduction"
    title: str
    description: str
    content: str  # stripped markdown (no frontmatter, no JSX)
    section: str  # top-level dir: "core", "platform", "sdk", etc.


@dataclass
class DocsIndex:
    """Lazy-loaded in-memory index of all documentation pages."""

    entries: list[DocEntry] = field(default_factory=list)
    by_path: dict[str, DocEntry] = field(default_factory=dict)
    loaded: bool = False


_index = DocsIndex()


def get_docs_dir() -> Path | None:
    """Resolve the noxus-docs directory."""
    from_env = os.environ.get("NOXUS_DOCS_DIR")
    if from_env:
        p = Path(from_env)
        return p if p.is_dir() else None

    # Auto-detect: noxus-docs lives at the monorepo root, three levels up
    # from this file (documentation.py → noxus_sdk → noxus-sdk → repo root)
    candidate = Path(__file__).resolve().parent.parent.parent / "noxus-docs"
    return candidate if candidate.is_dir() else None


def _parse_frontmatter(text: str) -> tuple[str, str, str]:
    """Extract title, description, and body from MDX with YAML frontmatter."""
    title = ""
    description = ""
    body = text

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            body = parts[2].strip()
            for line in fm.strip().splitlines():
                line = line.strip()
                if line.startswith("title:"):
                    title = line[6:].strip().strip("\"'")
                elif line.startswith("description:"):
                    description = line[12:].strip().strip("\"'")

    return title, description, body


def _strip_jsx(text: str) -> str:
    """Remove JSX components from MDX, keeping plain markdown."""
    return _JSX_TAG_RE.sub("", text)


def load_index() -> DocsIndex:
    """Parse all MDX files and populate the index. Returns the singleton index."""
    if _index.loaded:
        return _index

    docs_dir = get_docs_dir()
    if docs_dir is None:
        _index.loaded = True
        return _index

    for mdx_path in sorted(docs_dir.rglob("*.mdx")):
        rel = mdx_path.relative_to(docs_dir)

        # Skip non-content directories
        if rel.parts[0] in _SKIP_DIRS:
            continue

        section = rel.parts[0]
        doc_path = str(rel.with_suffix(""))  # e.g. "platform/agents/introduction"

        try:
            raw = mdx_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        title, description, body = _parse_frontmatter(raw)
        content = _strip_jsx(body)

        if not title:
            title = rel.stem.replace("-", " ").title()

        entry = DocEntry(
            path=doc_path,
            title=title,
            description=description,
            content=content,
            section=section,
        )
        _index.entries.append(entry)
        _index.by_path[doc_path] = entry

    _index.loaded = True
    return _index


def _search_blob(entry: DocEntry) -> str:
    """Build a searchable string for fuzzy matching."""
    return " ".join(
        [
            entry.title.lower(),
            entry.description.lower(),
            entry.section.lower(),
            entry.path.replace("/", " ").lower(),
            entry.content[:500].lower(),
        ]
    )


# ── Public API ──────────────────────────────────────────────────────


def list_sections() -> list[dict[str, str | int | list[dict[str, str]]]]:
    """List all documentation sections with their pages."""
    index = load_index()
    sections: dict[str, list[dict[str, str]]] = {}
    for entry in index.entries:
        sections.setdefault(entry.section, []).append(
            {
                "path": entry.path,
                "title": entry.title,
                "description": entry.description,
            }
        )
    return [
        {"section": section, "page_count": len(pages), "pages": pages}
        for section, pages in sorted(sections.items())
    ]


def read_page(path: str) -> dict[str, str]:
    """Read the full content of a documentation page by path."""
    index = load_index()
    path = path.strip("/").removesuffix(".mdx")
    entry = index.by_path.get(path)
    if entry is None:
        available = [e.path for e in index.entries if path.split("/")[-1] in e.path]
        hint = f" Similar: {available[:5]}" if available else ""
        raise KeyError(f"Documentation page '{path}' not found.{hint}")
    return {
        "path": entry.path,
        "title": entry.title,
        "description": entry.description,
        "section": entry.section,
        "content": entry.content,
    }


def search(query: str, limit: int = 10) -> list[dict[str, str | float]]:
    """Search documentation pages by keyword or topic."""
    index = load_index()
    q = query.lower()
    scored: list[tuple[float, DocEntry]] = []
    for entry in index.entries:
        s = fuzz.token_set_ratio(q, _search_blob(entry))
        if s >= 40:
            scored.append((s, entry))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "path": entry.path,
            "title": entry.title,
            "description": entry.description,
            "section": entry.section,
            "score": round(score, 1),
        }
        for score, entry in scored[:limit]
    ]
