"""Dispatch logging for CLASI subagent dispatches.

Logs the full prompt sent to each subagent dispatch, with YAML
frontmatter for structured metadata.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from claude_agent_skills.frontmatter import read_document, write_frontmatter


def _log_dir() -> Path:
    """Return the log directory (``docs/clasi/log/``) relative to cwd."""
    return Path.cwd() / "docs" / "clasi" / "log"


def _next_sequence(directory: Path, prefix: str) -> int:
    """Scan *directory* for files matching ``<prefix>-NNN.md`` and return the next number.

    When *prefix* is empty, matches bare ``NNN.md`` filenames instead.
    Returns 1 if no matching files exist.
    """
    if not directory.is_dir():
        return 1

    if prefix:
        pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)\.md$")
    else:
        pattern = re.compile(r"^(\d+)\.md$")

    max_seq = 0
    for entry in directory.iterdir():
        m = pattern.match(entry.name)
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    return max_seq + 1


def log_dispatch(
    parent: str,
    child: str,
    scope: str,
    prompt: str,
    sprint_name: str | None = None,
    ticket_id: str | None = None,
) -> Path:
    """Log a subagent dispatch and return the path of the created log file.

    Routing rules:
    - sprint_name + ticket_id  -> ``log/sprints/<sprint>/ticket-<ticket>-NNN.md``
    - sprint_name, no ticket   -> ``log/sprints/<sprint>/sprint-planner-NNN.md``
    - no sprint_name           -> ``log/adhoc/NNN.md``

    Directories are created on demand.
    """
    base = _log_dir()

    if sprint_name and ticket_id:
        directory = base / "sprints" / sprint_name
        prefix = f"ticket-{ticket_id}"
    elif sprint_name:
        directory = base / "sprints" / sprint_name
        prefix = "sprint-planner"
    else:
        directory = base / "adhoc"
        prefix = ""

    directory.mkdir(parents=True, exist_ok=True)
    seq = _next_sequence(directory, prefix)

    if prefix:
        filename = f"{prefix}-{seq:03d}.md"
    else:
        filename = f"{seq:03d}.md"

    log_path = directory / filename

    # Build frontmatter
    fm: dict = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "parent": parent,
        "child": child,
        "scope": scope,
    }
    if sprint_name:
        fm["sprint"] = sprint_name
    if ticket_id:
        fm["ticket"] = ticket_id

    # Build body
    body = f"\n# Dispatch: {parent} → {child}\n\n{prompt}\n"

    # Write frontmatter + body
    write_frontmatter(log_path, fm)
    # Re-read to append body (write_frontmatter creates the file with empty body)
    content = log_path.read_text(encoding="utf-8")
    content += body
    log_path.write_text(content, encoding="utf-8")

    return log_path


def update_dispatch_result(
    log_path: Path,
    result: str,
    files_modified: list[str],
) -> None:
    """Add *result* and *files_modified* to an existing dispatch log's frontmatter."""
    fm, body = read_document(log_path)
    fm["result"] = result
    fm["files_modified"] = files_modified
    write_frontmatter(log_path, fm)
