"""Shared marker-block writer for platform-specific markdown files.

Both `claude.py` (CLAUDE.md) and `codex.py` (AGENTS.md) need to write the
same CLASI section into a host markdown file with idempotent
create/update/append semantics, preserving any user content outside the
marker block. This module centralizes that logic so the two platforms
cannot drift.

Named-block API
---------------
`write_named_section(file_path, block_name, content)` and
`strip_named_section(file_path, block_name)` support multiple independent
CLASI-managed blocks in the same file.  Each block is delimited by::

    <!-- CLASI:{block_name}:START -->
    <!-- CLASI:{block_name}:END -->

Multiple differently-named blocks can coexist; each function operates only
on the block whose name matches `block_name`.  The existing
`write_section`/`strip_section` pair (which uses `CLASI:START/END`) is
unchanged and continues to work independently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import click

from clasi.templates import CLASI_SECTION_TEMPLATE

MARKER_START = "<!-- CLASI:START -->"
MARKER_END = "<!-- CLASI:END -->"


def _current_version() -> str:
    """Return the installed clasi version, falling back to 'unknown'."""
    try:
        from clasi import __version__
        return __version__
    except Exception:
        return "unknown"


def write_version_stamp(target: Path) -> None:
    """Write the installed clasi version to <target>/.clasi/clasi-version.

    A single-line file (version + newline) so a reader can tell which
    clasi release populated this directory. Each platform installer
    calls this once per target root.

    Stale per-platform stamp files from old installs are deleted
    opportunistically: .claude/.clasi-version, .codex/.clasi-version,
    .agents/.clasi-version, .github/.clasi-version.
    """
    dest = target / ".clasi" / "clasi-version"
    dest.parent.mkdir(parents=True, exist_ok=True)
    version = _current_version()
    dest.write_text(f"{version}\n", encoding="utf-8")
    click.echo(f"  Wrote: .clasi/clasi-version ({version})")

    # Opportunistically remove stale per-platform stamp files from old installs.
    _stale_dirs = [".claude", ".codex", ".agents", ".github"]
    for stale_dir in _stale_dirs:
        stale = target / stale_dir / ".clasi-version"
        if stale.exists():
            stale.unlink()
            click.echo(f"  Removed stale: {stale_dir}/.clasi-version")


def remove_version_stamp(target: Path) -> None:
    """Remove <target>/.clasi/clasi-version on uninstall.

    Removes the .clasi/ directory as well if it becomes empty after
    the stamp file is deleted.  Does nothing if the file does not exist.
    """
    stamp = target / ".clasi" / "clasi-version"
    if stamp.exists():
        stamp.unlink()
        click.echo("  Removed: .clasi/clasi-version")
    else:
        click.echo("  Skipped: .clasi/clasi-version (not found)")

    clasi_dir = target / ".clasi"
    if clasi_dir.exists():
        try:
            next(clasi_dir.iterdir())
        except StopIteration:
            clasi_dir.rmdir()
            click.echo("  Removed: .clasi/ (empty)")


def render_section(entry_point: str, version: Optional[str] = None) -> str:
    """Render the CLASI section content (including markers) for a platform.

    `entry_point` is the platform-specific sentence that tells the agent
    where to start reading (e.g. the Claude team-lead agent file, or the
    Codex SE skill file).

    `version` is embedded in the rendered block so readers can tell which
    clasi release wrote it. Defaults to the installed clasi version.
    """
    if version is None:
        version = _current_version()
    body = CLASI_SECTION_TEMPLATE.format(entry_point=entry_point, version=version)
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


def write_named_section(file_path: Path, block_name: str, content: str) -> bool:
    """Write or replace the named CLASI block in *file_path*.

    The block is delimited by::

        <!-- CLASI:{block_name}:START -->
        <!-- CLASI:{block_name}:END -->

    Behavior:

    - Block already present: replace in place.
    - File exists, block absent: append at end.
    - File does not exist: create with just the block.

    If a malformed file contains the START marker more than once, the
    replacement spans from the first START to the first END of that name.

    Returns True if the file was written/updated, False if unchanged.
    """
    marker_start = f"<!-- CLASI:{block_name}:START -->"
    marker_end = f"<!-- CLASI:{block_name}:END -->"
    section = f"{marker_start}\n{content}\n{marker_end}\n"
    label = file_path.name

    if not file_path.exists():
        file_path.write_text(section, encoding="utf-8")
        click.echo(f"  Created: {label}")
        return True

    existing = file_path.read_text(encoding="utf-8")

    if marker_start in existing and marker_end in existing:
        start_idx = existing.index(marker_start)
        end_idx = existing.index(marker_end) + len(marker_end)
        new_content = existing[:start_idx] + section.strip() + existing[end_idx:]
        if new_content != existing:
            file_path.write_text(new_content, encoding="utf-8")
            click.echo(f"  Updated: {label} (replaced CLASI:{block_name} section)")
            return True
        click.echo(f"  Unchanged: {label}")
        return False

    if not existing.endswith("\n"):
        existing += "\n"
    new_content = existing + "\n" + section
    file_path.write_text(new_content, encoding="utf-8")
    click.echo(f"  Updated: {label} (appended CLASI:{block_name} section)")
    return True


def strip_named_section(file_path: Path, block_name: str) -> bool:
    """Remove the named CLASI block from *file_path*, preserving everything else.

    Deletes the file if it becomes empty (only whitespace).

    Returns True if anything was removed/changed, False otherwise.
    """
    marker_start = f"<!-- CLASI:{block_name}:START -->"
    marker_end = f"<!-- CLASI:{block_name}:END -->"
    label = file_path.name

    if not file_path.exists():
        click.echo(f"  Skipped: {label} (not found)")
        return False

    content = file_path.read_text(encoding="utf-8")
    if marker_start not in content or marker_end not in content:
        click.echo(f"  Unchanged: {label} (no CLASI:{block_name} section found)")
        return False

    start_idx = content.index(marker_start)
    end_idx = content.index(marker_end) + len(marker_end)
    before = content[:start_idx].rstrip("\n")
    after = content[end_idx:]
    new_content = before + ("\n" if after.strip() else "") + after

    if new_content.strip():
        file_path.write_text(new_content, encoding="utf-8")
        click.echo(f"  Removed: {label} (CLASI:{block_name} section)")
    else:
        file_path.unlink()
        click.echo(f"  Deleted: {label} (was only CLASI content)")
    return True
