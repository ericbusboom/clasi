"""Artifact: a markdown file with YAML frontmatter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from clasi.frontmatter import (
    read_document as _read_document,
    read_frontmatter as _read_frontmatter,
    write_frontmatter as _write_frontmatter,
)


class Artifact:
    """A markdown file with YAML frontmatter.

    Delegates to the existing frontmatter module for parsing and
    serialisation.
    """

    def __init__(self, path: str | Path):
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def exists(self) -> bool:
        return self._path.exists()

    @property
    def frontmatter(self) -> dict[str, Any]:
        """Read and return YAML frontmatter."""
        return _read_frontmatter(self._path)

    @property
    def content(self) -> str:
        """Read and return markdown body (after frontmatter)."""
        _, body = _read_document(self._path)
        return body

    def read_document(self) -> tuple[dict[str, Any], str]:
        """Read both frontmatter and content."""
        return _read_document(self._path)

    def write(self, frontmatter: dict[str, Any], content: str) -> None:
        """Write frontmatter and content to file.

        Creates parent directories if they do not exist.
        """
        from clasi.frontmatter import _write_document

        self._path.parent.mkdir(parents=True, exist_ok=True)
        _write_document(self._path, frontmatter, content)

    def update_frontmatter(self, **fields: Any) -> None:
        """Update specific frontmatter fields, preserving others."""
        fm, body = _read_document(self._path)
        fm.update(fields)
        self.write(fm, body)
