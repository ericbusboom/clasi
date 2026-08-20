"""
Utility for reading and writing YAML frontmatter in markdown files.

Frontmatter is delimited by --- lines at the top of a file:

    ---
    key: value
    ---

    Body content here.

Implemented using the python-frontmatter package.
"""

import os
import stat
import tempfile
from pathlib import Path
from typing import Any

import frontmatter as _fm
import yaml


class MalformedFrontmatterError(ValueError):
    """Raised when a file's frontmatter fence is present but malformed.

    This is a subclass of ``ValueError`` for backwards compatibility with
    callers that already catch ``ValueError``.
    """


def read_document(path: str | Path) -> tuple[dict[str, Any], str]:
    """Read a markdown file and return (frontmatter_dict, body_str).

    If the file has no frontmatter, returns ({}, full_content).

    Raises:
        MalformedFrontmatterError: If the file has content whose first line
            starts with ``-`` but is not exactly ``---``.
    """
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    return _parse(content, source_path=path)


def _parse(
    content: str, source_path: str | Path | None = None
) -> tuple[dict[str, Any], str]:
    """Parse a string and return (frontmatter_dict, body_str).

    Preserves the exact body text as it appears in the file after the
    closing ``---`` delimiter.

    Args:
        content: Raw file content to parse.
        source_path: Optional path used in error messages.

    Raises:
        MalformedFrontmatterError: If content starts with ``-`` but the
            first line is not exactly ``---``.
    """
    if not content.startswith("-"):
        # Genuine no-frontmatter: first character is not '-'.
        return {}, content

    first_line = content.split("\n", 1)[0].rstrip("\r")
    if first_line != "---":
        path_label = str(source_path) if source_path is not None else "<unknown>"
        raise MalformedFrontmatterError(
            f"Malformed frontmatter fence in {path_label!r}: "
            f"expected '---' but got {first_line!r}"
        )

    # Use python-frontmatter to extract metadata
    post = _fm.loads(content)
    metadata = dict(post.metadata)

    # Locate the body start in the raw content so we return exactly
    # what follows the closing ---, including any leading/trailing newlines.
    # This is line-anchored: only a line that is *exactly* "---" (modulo a
    # trailing \r for CRLF files) closes the fence. A "---" that merely
    # appears somewhere inside a frontmatter value (a multi-line scalar, a
    # markdown horizontal rule folded into a quoted string, etc.) must not
    # be mistaken for the closing delimiter — doing so mis-slices the body,
    # and the next write would persist that corruption to disk.
    body_start = _find_body_start(content)
    if body_start == -1:
        # No line-anchored closing fence found — fall back to raw parse,
        # returning the full content as body (matching original behaviour
        # for e.g. a fence with no closing "---" line at all).
        return {}, content

    body = content[body_start:]
    return metadata, body


def _find_body_start(content: str) -> int:
    """Return the index in ``content`` where the frontmatter body begins.

    Scans line-by-line, starting after the opening ``---`` line, for the
    first line that is *exactly* ``---`` (ignoring a trailing ``\\r`` for
    CRLF files). Returns the index of the character immediately following
    that line's terminator (i.e. where the body starts), or -1 if no such
    line is found.
    """
    lines = content.splitlines(keepends=True)
    if not lines:
        return -1

    pos = len(lines[0])  # Skip past the opening fence line.
    for line in lines[1:]:
        pos += len(line)
        if line.rstrip("\r\n") == "---":
            return pos

    return -1


def read_frontmatter(path: str | Path) -> dict[str, Any]:
    """Read just the YAML frontmatter from a markdown file.

    Returns an empty dict if the file has no frontmatter.
    """
    fm, _ = read_document(path)
    return fm


def write_frontmatter(path: str | Path, data: dict[str, Any]) -> None:
    """Update the YAML frontmatter of a markdown file, preserving the body.

    If the file has no existing frontmatter, prepends it.
    """
    path = Path(path)

    if path.exists():
        _, body = read_document(path)
    else:
        body = ""

    _write_document(path, data, body)


def _write_document(path: Path, data: dict[str, Any], body: str) -> None:
    """Write frontmatter + body to path in the canonical format, atomically.

    Writes the full content to a temp file in the *same directory* as
    ``path`` (so ``os.replace`` — atomic only within a filesystem — is
    guaranteed to land on the same filesystem), then atomically replaces
    ``path`` with it. A crash or exception at any point before the
    ``os.replace`` call leaves the original file completely untouched,
    instead of the previous truncate-in-place ``write_text`` which could
    leave a half-written, corrupt file on disk.

    Preserves the existing file's permission bits, if any — a plain
    ``os.replace`` would otherwise hand the destination path the temp
    file's (umask-derived) permissions.

    Uses ``yaml.safe_dump`` rather than ``yaml.dump`` — the frontmatter
    values passed here always originate from data previously loaded as
    YAML (or plain JSON-compatible dicts), so there is no legitimate need
    for ``yaml.dump``'s unsafe Python-object tags.
    """
    yaml_str = yaml.safe_dump(data, default_flow_style=False, sort_keys=False).strip()
    content = f"---\n{yaml_str}\n---\n{body}"

    existing_mode: int | None = None
    if path.exists():
        existing_mode = stat.S_IMODE(path.stat().st_mode)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        if existing_mode is not None:
            os.chmod(tmp_path, existing_mode)
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
