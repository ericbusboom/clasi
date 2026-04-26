"""Shared marker-block writer for platform-specific markdown files.

Both `claude.py` (CLAUDE.md) and `codex.py` (AGENTS.md) need to write the
same CLASI section into a host markdown file with idempotent
create/update/append semantics, preserving any user content outside the
marker block. This module centralizes that logic so the two platforms
cannot drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from clasi.templates import CLASI_SECTION_TEMPLATE

MARKER_START = "<!-- CLASI:START -->"
MARKER_END = "<!-- CLASI:END -->"


def render_section(entry_point: str) -> str:
    """Render the CLASI section content (including markers) for a platform.

    `entry_point` is the platform-specific sentence that tells the agent
    where to start reading (e.g. the Claude team-lead agent file, or the
    Codex SE skill file).
    """
    body = CLASI_SECTION_TEMPLATE.format(entry_point=entry_point)
    return f"{MARKER_START}\n{body}{MARKER_END}\n"


def write_section(
    file_path: Path,
    entry_point: str,
    legacy_match_substr: Optional[str] = None,
) -> bool:
    """Write or update the CLASI marker block in *file_path*.

    Behavior:
    - Existing fenced block (CLASI:START/END markers): replace in place.
    - Legacy fence-less block (matched via `legacy_match_substr`): replace
      and add markers.
    - Existing file with no CLASI block: append the section.
    - File does not exist: create it with the section.

    Returns True if the file was written/updated, False if unchanged.
    """
    section = render_section(entry_point)
    label = file_path.name

    if not file_path.exists():
        file_path.write_text(section, encoding="utf-8")
        click.echo(f"  Created: {label}")
        return True

    content = file_path.read_text(encoding="utf-8")

    if MARKER_START in content and MARKER_END in content:
        start_idx = content.index(MARKER_START)
        end_idx = content.index(MARKER_END) + len(MARKER_END)
        new_content = content[:start_idx] + section.strip() + content[end_idx:]
        if new_content != content:
            file_path.write_text(new_content, encoding="utf-8")
            click.echo(f"  Updated: {label} (replaced CLASI section)")
            return True
        click.echo(f"  Unchanged: {label}")
        return False

    if legacy_match_substr:
        heading = "# CLASI Software Engineering Process"
        if heading in content and legacy_match_substr in content:
            start_idx = content.index(heading)
            search_from = start_idx + len(heading)
            next_heading_idx = content.find("\n# ", search_from)
            end_idx = (
                len(content) if next_heading_idx == -1 else next_heading_idx + 1
            )
            new_content = (
                content[:start_idx] + section.strip() + "\n" + content[end_idx:]
            )
            if new_content != content:
                file_path.write_text(new_content, encoding="utf-8")
                click.echo(f"  Updated: {label} (added CLASI section markers)")
                return True
            click.echo(f"  Unchanged: {label}")
            return False

    if not content.endswith("\n"):
        content += "\n"
    content += "\n" + section
    file_path.write_text(content, encoding="utf-8")
    click.echo(f"  Updated: {label} (appended CLASI section)")
    return True


def strip_section(file_path: Path) -> bool:
    """Remove the CLASI marker block from *file_path*, preserving everything else.

    Deletes the file if it becomes empty (only whitespace).

    Returns True if anything was removed/changed, False otherwise.
    """
    label = file_path.name

    if not file_path.exists():
        click.echo(f"  Skipped: {label} (not found)")
        return False

    content = file_path.read_text(encoding="utf-8")
    if MARKER_START not in content or MARKER_END not in content:
        click.echo(f"  Unchanged: {label} (no CLASI section found)")
        return False

    start_idx = content.index(MARKER_START)
    end_idx = content.index(MARKER_END) + len(MARKER_END)
    before = content[:start_idx].rstrip("\n")
    after = content[end_idx:]
    new_content = before + ("\n" if after.strip() else "") + after

    if new_content.strip():
        file_path.write_text(new_content, encoding="utf-8")
        click.echo(f"  Removed: {label} (CLASI section)")
    else:
        file_path.unlink()
        click.echo(f"  Deleted: {label} (was only CLASI content)")
    return True
