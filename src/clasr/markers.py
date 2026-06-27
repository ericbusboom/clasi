"""
clasr/markers.py

Named provider-scoped marker block writer and stripper for Markdown files.

This module is a leaf node: it has no clasr or clasi imports, no platform
knowledge, and performs only string manipulation + file I/O.

Marker format::

    <!-- BEGIN clasr:<provider> -->
    ...content...
    <!-- END clasr:<provider> -->

Multiple providers can coexist in the same file.  Operations on one
provider's block never touch another provider's block.
"""

from __future__ import annotations

from pathlib import Path


def _begin_tag(provider: str) -> str:
    return f"<!-- BEGIN clasr:{provider} -->"


def _end_tag(provider: str) -> str:
    return f"<!-- END clasr:{provider} -->"


def _make_block(provider: str, content: str) -> str:
    """Return a complete marker block (no trailing newline after END tag)."""
    return f"{_begin_tag(provider)}\n{content}\n{_end_tag(provider)}"


def write_block(file_path: Path, provider: str, content: str) -> bool:
    """Write *content* inside the named marker block for *provider*.

    Behaviour:

    * If the file does not exist, create it containing only the block.
    * If the file exists and already contains a block for *provider*,
      replace it in place.
    * If the file exists but has no block for *provider*, append the
      block (preceded by a newline if the file does not already end with
      one).
    * Returns ``True`` if the file was written or changed, ``False`` if
      the file already contained identical content (no write performed).

    Parameters
    ----------
    file_path:
        Path to the target Markdown file.
    provider:
        Provider name, e.g. ``"claude"`` or ``"copilot"``.
    content:
        The content to place inside the marker delimiters.  Should not
        include the delimiter lines themselves.

    Returns
    -------
    bool
        ``True`` if a write occurred, ``False`` if the file was unchanged.
    """
    begin = _begin_tag(provider)
    end = _end_tag(provider)
    new_block = _make_block(provider, content)

    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(new_block + "\n", encoding="utf-8")
        return True

    existing = file_path.read_text(encoding="utf-8")

    begin_idx = existing.find(begin)
    if begin_idx != -1:
        # Block exists — find its end and replace in place.
        end_idx = existing.find(end, begin_idx)
        if end_idx == -1:
            # Malformed: missing END tag — treat entire tail as the block.
            end_idx = len(existing) - len(end)
        end_idx += len(end)
        new_text = existing[:begin_idx] + new_block + existing[end_idx:]
    else:
        # No block for this provider — append.
        sep = "" if existing.endswith("\n") else "\n"
        new_text = existing + sep + new_block + "\n"

    if new_text == existing:
        return False

    file_path.write_text(new_text, encoding="utf-8")
    return True


def strip_block(file_path: Path, provider: str) -> bool:
    """Remove the named marker block for *provider* from *file_path*.

    All other content — including blocks from other providers — is
    preserved verbatim.

    If the file does not exist, or does not contain a block for *provider*,
    returns ``False`` without touching anything.

    If the file becomes empty (or contains only whitespace) after stripping,
    it is deleted and ``True`` is returned.

    Parameters
    ----------
    file_path:
        Path to the target Markdown file.
    provider:
        Provider name whose block should be removed.

    Returns
    -------
    bool
        ``True`` if anything changed (block removed or file deleted),
        ``False`` otherwise.
    """
    if not file_path.exists():
        return False

    begin = _begin_tag(provider)
    end = _end_tag(provider)

    existing = file_path.read_text(encoding="utf-8")

    begin_idx = existing.find(begin)
    if begin_idx == -1:
        return False

    end_idx = existing.find(end, begin_idx)
    if end_idx == -1:
        # Malformed: no END tag — remove from BEGIN to end of file.
        end_idx = len(existing)
    else:
        end_idx += len(end)

    # Also consume exactly one trailing newline after the END tag, if present,
    # to avoid leaving a blank line in its place.
    if end_idx < len(existing) and existing[end_idx] == "\n":
        end_idx += 1

    new_text = existing[:begin_idx] + existing[end_idx:]

    if not new_text.strip():
        file_path.unlink()
        return True

    file_path.write_text(new_text, encoding="utf-8")
    return True
