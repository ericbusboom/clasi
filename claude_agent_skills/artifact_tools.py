"""Artifact Management tools for the CLASI MCP server.

Read-write tools for creating, querying, and updating SE artifacts
(sprints, tickets, briefs, architecture, use cases).
"""

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from claude_agent_skills.frontmatter import read_document, read_frontmatter, write_frontmatter
from claude_agent_skills.mcp_server import server
from claude_agent_skills.state_db import (
    PHASES as _PHASES,
    advance_phase as _advance_phase,
    record_gate as _record_gate,
    acquire_lock as _acquire_lock,
    release_lock as _release_lock,
    get_sprint_state as _get_sprint_state,
    register_sprint as _register_sprint,
    rename_sprint as _rename_sprint,
    write_recovery_state as _write_recovery_state,
    get_recovery_state as _get_recovery_state,
    clear_recovery_state as _clear_recovery_state,
)
from claude_agent_skills.templates import (
    slugify,
    SPRINT_TEMPLATE,
    SPRINT_USECASES_TEMPLATE,
    SPRINT_ARCHITECTURE_TEMPLATE,
    SPRINT_ARCHITECTURE_UPDATE_TEMPLATE,
    TICKET_TEMPLATE,
    OVERVIEW_TEMPLATE,
)


def _plans_dir() -> Path:
    """Return the docs/clasi/ directory relative to cwd.

    Prefers docs/clasi/ (current name). Falls back to docs/plans/
    (legacy name) if it exists and docs/clasi/ does not — and renames
    it to docs/clasi/ so the migration happens automatically.
    """
    clasi = Path.cwd() / "docs" / "clasi"
    if clasi.is_dir():
        return clasi
    legacy = Path.cwd() / "docs" / "plans"
    if legacy.is_dir():
        legacy.rename(clasi)
        return clasi
    return clasi


def _sprints_dir() -> Path:
    """Return the docs/clasi/sprints/ directory."""
    return _plans_dir() / "sprints"


def resolve_artifact_path(path: str) -> Path:
    """Find a file whether it's in its original location or a done/ subdirectory.

    Resolution order:
    1. Given path as-is
    2. Insert done/ before the filename (e.g., tickets/001.md -> tickets/done/001.md)
    3. Remove done/ from the path (e.g., tickets/done/001.md -> tickets/001.md)

    Returns the resolved Path.
    Raises FileNotFoundError if none of the candidates exist.
    """
    p = Path(path)
    if p.exists():
        return p

    # Try inserting done/ before the filename
    with_done = p.parent / "done" / p.name
    if with_done.exists():
        return with_done

    # Try removing done/ from the path
    parts = p.parts
    if "done" in parts:
        without_done = Path(*[part for part in parts if part != "done"])
        if without_done.exists():
            return without_done

    raise FileNotFoundError(
        f"Artifact not found: {path} (also checked done/ variants)"
    )


def _find_sprint_dir(sprint_id: str) -> Path:
    """Find a sprint directory by its ID (checks active and done)."""
    sprints = _sprints_dir()
    # Check active sprints
    for d in sorted(sprints.iterdir()) if sprints.exists() else []:
        if d.is_dir() and d.name.startswith(sprint_id):
            fm = read_frontmatter(d / "sprint.md") if (d / "sprint.md").exists() else {}
            if fm.get("id") == sprint_id:
                return d
    # Check done sprints
    done_dir = sprints / "done"
    for d in sorted(done_dir.iterdir()) if done_dir.exists() else []:
        if d.is_dir() and d.name.startswith(sprint_id):
            fm = read_frontmatter(d / "sprint.md") if (d / "sprint.md").exists() else {}
            if fm.get("id") == sprint_id:
                return d
    raise ValueError(f"Sprint '{sprint_id}' not found")


def _next_sprint_id() -> str:
    """Determine the next sprint number (NNN format)."""
    sprints = _sprints_dir()
    max_id = 0
    for location in [sprints, sprints / "done"]:
        if not location.exists():
            continue
        for d in location.iterdir():
            if d.is_dir() and (d / "sprint.md").exists():
                fm = read_frontmatter(d / "sprint.md")
                try:
                    num = int(fm.get("id", "0"))
                    max_id = max(max_id, num)
                except (ValueError, TypeError):
                    pass
    return f"{max_id + 1:03d}"


def _next_ticket_id(sprint_dir: Path) -> str:
    """Determine the next ticket number within a sprint."""
    tickets_dir = sprint_dir / "tickets"
    max_id = 0
    for location in [tickets_dir, tickets_dir / "done"]:
        if not location.exists():
            continue
        for f in location.glob("*.md"):
            fm = read_frontmatter(f)
            try:
                num = int(fm.get("id", "0"))
                max_id = max(max_id, num)
            except (ValueError, TypeError):
                pass
    return f"{max_id + 1:03d}"


# --- Create tools (ticket 008) ---


def _find_latest_architecture() -> Path | None:
    """Find the most recent architecture document.

    Looks for the top-level file in docs/clasi/architecture/ (most recent
    version). Returns None if no architecture documents exist.
    """
    arch_dir = _plans_dir() / "architecture"
    if not arch_dir.exists():
        return None

    # Find architecture-NNN.md files at the top level (not in done/)
    candidates = sorted(arch_dir.glob("architecture-*.md"), reverse=True)
    return candidates[0] if candidates else None


@server.tool()
def create_sprint(title: str) -> str:
    """Create a new sprint directory with template planning documents.

    Auto-assigns the next sprint number and creates the full directory
    structure: sprint.md, usecases.md, architecture-update.md,
    and tickets/ + tickets/done/ directories.

    The sprint receives a lightweight architecture-update template instead
    of a full copy of the previous architecture.  The full architecture
    lives in ``docs/clasi/architecture/`` and is consolidated on demand.

    Args:
        title: The sprint title (e.g., 'MCP Server Implementation')
    """
    sprint_id = _next_sprint_id()
    slug = slugify(title)
    sprint_dir = _sprints_dir() / f"{sprint_id}-{slug}"

    if sprint_dir.exists():
        raise ValueError(f"Sprint directory already exists: {sprint_dir}")

    sprint_dir.mkdir(parents=True, exist_ok=True)
    (sprint_dir / "tickets").mkdir()
    (sprint_dir / "tickets" / "done").mkdir()

    fmt = {"id": sprint_id, "title": title, "slug": slug}

    files = {}
    for name, template in [
        ("sprint.md", SPRINT_TEMPLATE),
        ("usecases.md", SPRINT_USECASES_TEMPLATE),
    ]:
        path = sprint_dir / name
        path.write_text(template.format(**fmt), encoding="utf-8")
        files[name] = str(path)

    # Architecture: lightweight update template (not a full copy)
    arch_update_path = sprint_dir / "architecture-update.md"
    arch_update_path.write_text(
        SPRINT_ARCHITECTURE_UPDATE_TEMPLATE.format(**fmt), encoding="utf-8"
    )
    files["architecture-update.md"] = str(arch_update_path)

    # Register sprint in state database (lazy init)
    try:
        _register_sprint(
            str(_db_path()), sprint_id, slug, f"sprint/{sprint_id}-{slug}"
        )
    except Exception:
        pass  # Graceful degradation if DB fails

    return json.dumps({
        "id": sprint_id,
        "path": str(sprint_dir),
        "branch": f"sprint/{sprint_id}-{slug}",
        "files": files,
        "phase": "planning-docs",
    }, indent=2)


def _list_active_sprints() -> list[dict]:
    """Return all active (non-done) sprints sorted by numeric ID.

    Each entry has keys: id (int), str_id (str), dir (Path), slug (str).
    """
    sprints = _sprints_dir()
    if not sprints.exists():
        return []

    results = []
    for d in sorted(sprints.iterdir()):
        if not d.is_dir() or d.name == "done":
            continue
        sprint_file = d / "sprint.md"
        if not sprint_file.exists():
            continue
        fm = read_frontmatter(sprint_file)
        str_id = fm.get("id", "")
        try:
            num_id = int(str_id)
        except (ValueError, TypeError):
            continue
        # Extract slug: directory name minus the "NNN-" prefix
        slug = d.name[len(str_id) + 1:] if d.name.startswith(str_id) else d.name
        results.append({
            "id": num_id,
            "str_id": str_id,
            "dir": d,
            "slug": slug,
        })

    return sorted(results, key=lambda s: s["id"])


def _get_sprint_phase_safe(sprint_id: str) -> str | None:
    """Get a sprint's phase from the state DB, or None if unavailable."""
    db = _db_path()
    if not db.exists():
        return None
    try:
        state = _get_sprint_state(str(db), sprint_id)
        return state["phase"]
    except (ValueError, Exception):
        return None


def _renumber_sprint_dir(sprint_dir: Path, old_id: str, new_id: str) -> Path:
    """Rename a sprint directory and update all internal references.

    Updates:
    - Directory name (NNN-slug -> MMM-slug)
    - sprint.md frontmatter (id, branch)
    - sprint.md body references to "Sprint NNN"
    - Ticket frontmatter (no sprint_id field, but just in case)
    - usecases.md body references to "Sprint NNN"
    - architecture.md body references to "Sprint NNN"

    Returns the new directory path.
    """
    # Rename directory
    slug = sprint_dir.name[len(old_id) + 1:] if sprint_dir.name.startswith(old_id) else sprint_dir.name
    new_dir_name = f"{new_id}-{slug}"
    new_dir = sprint_dir.parent / new_dir_name

    sprint_dir.rename(new_dir)

    # Update sprint.md frontmatter
    sprint_file = new_dir / "sprint.md"
    if sprint_file.exists():
        fm = read_frontmatter(sprint_file)
        fm["id"] = new_id
        fm["branch"] = f"sprint/{new_id}-{slug}"
        write_frontmatter(sprint_file, fm)

        # Update body references: "Sprint NNN" -> "Sprint MMM"
        content = sprint_file.read_text(encoding="utf-8")
        content = content.replace(f"Sprint {old_id}", f"Sprint {new_id}")
        sprint_file.write_text(content, encoding="utf-8")

    # Update body references in usecases.md and architecture-update.md
    for doc_name in ("usecases.md", "architecture-update.md", "architecture.md"):
        doc = new_dir / doc_name
        if doc.exists():
            content = doc.read_text(encoding="utf-8")
            updated = content.replace(f"Sprint {old_id}", f"Sprint {new_id}")
            if updated != content:
                doc.write_text(updated, encoding="utf-8")

    # Update ticket frontmatter (sprint_id field if present)
    for ticket_location in [new_dir / "tickets", new_dir / "tickets" / "done"]:
        if not ticket_location.exists():
            continue
        for ticket_file in ticket_location.glob("*.md"):
            fm = read_frontmatter(ticket_file)
            if fm.get("sprint_id") == old_id:
                fm["sprint_id"] = new_id
                write_frontmatter(ticket_file, fm)

    return new_dir


@server.tool()
def insert_sprint(after_sprint_id: str, title: str) -> str:
    """Insert a new sprint after the given sprint ID, renumbering subsequent sprints.

    Only sprints in planning-docs phase can be renumbered. If any sprint
    that would need renumbering is in a later phase, the operation is
    refused.

    Args:
        after_sprint_id: The sprint ID to insert after (e.g., '012')
        title: The new sprint's title
    """
    # Validate the anchor sprint exists
    try:
        _find_sprint_dir(after_sprint_id)
    except ValueError:
        raise ValueError(f"Sprint '{after_sprint_id}' not found")

    anchor_num = int(after_sprint_id)
    new_id = f"{anchor_num + 1:03d}"

    # Find all active sprints that need renumbering (id >= new_id)
    active_sprints = _list_active_sprints()
    to_renumber = [s for s in active_sprints if s["id"] >= anchor_num + 1]

    # Check that all sprints to renumber are in planning-docs phase
    for sprint in to_renumber:
        phase = _get_sprint_phase_safe(sprint["str_id"])
        if phase is not None and phase != "planning-docs":
            raise ValueError(
                f"Cannot insert sprint: sprint '{sprint['str_id']}' "
                f"({sprint['slug']}) is in '{phase}' phase and cannot "
                f"be renumbered. Only sprints in 'planning-docs' phase "
                f"can be renumbered."
            )

    # Renumber existing sprints in reverse order (highest first) to avoid
    # directory name collisions
    renumbered = []
    db = _db_path()
    for sprint in reversed(to_renumber):
        old_str_id = sprint["str_id"]
        new_num = sprint["id"] + 1
        new_str_id = f"{new_num:03d}"

        new_dir = _renumber_sprint_dir(sprint["dir"], old_str_id, new_str_id)

        # Update state database if it exists
        if db.exists():
            try:
                _rename_sprint(
                    str(db), old_str_id, new_str_id,
                    new_branch=f"sprint/{new_dir.name}",
                )
            except (ValueError, Exception):
                pass  # Graceful degradation

        renumbered.append({
            "old_id": old_str_id,
            "new_id": new_str_id,
            "old_dir": str(sprint["dir"]),
            "new_dir": str(new_dir),
        })

    # Reverse so the output is in ascending order
    renumbered.reverse()

    # Now create the new sprint at the insertion point
    slug = slugify(title)
    sprint_dir = _sprints_dir() / f"{new_id}-{slug}"

    sprint_dir.mkdir(parents=True, exist_ok=True)
    (sprint_dir / "tickets").mkdir()
    (sprint_dir / "tickets" / "done").mkdir()

    fmt = {"id": new_id, "title": title, "slug": slug}
    files = {}
    for name, template in [
        ("sprint.md", SPRINT_TEMPLATE),
        ("usecases.md", SPRINT_USECASES_TEMPLATE),
    ]:
        path = sprint_dir / name
        path.write_text(template.format(**fmt), encoding="utf-8")
        files[name] = str(path)

    # Architecture: lightweight update template (not a full copy)
    arch_update_path = sprint_dir / "architecture-update.md"
    arch_update_path.write_text(
        SPRINT_ARCHITECTURE_UPDATE_TEMPLATE.format(**fmt), encoding="utf-8"
    )
    files["architecture-update.md"] = str(arch_update_path)

    # Register in state database
    try:
        _register_sprint(
            str(_db_path()), new_id, slug, f"sprint/{new_id}-{slug}"
        )
    except Exception:
        pass  # Graceful degradation

    return json.dumps({
        "id": new_id,
        "path": str(sprint_dir),
        "branch": f"sprint/{new_id}-{slug}",
        "files": files,
        "phase": "planning-docs",
        "renumbered": renumbered,
    }, indent=2)


def _check_sprint_phase_for_ticketing(sprint_id: str) -> None:
    """Check that a sprint is in ticketing phase or later.

    Degrades gracefully: if the DB doesn't exist or the sprint isn't
    registered, the check is skipped (backward compatibility).
    """
    db = _db_path()
    if not db.exists():
        return
    try:
        state = _get_sprint_state(str(db), sprint_id)
        phase_idx = _PHASES.index(state["phase"])
        ticketing_idx = _PHASES.index("ticketing")
        if phase_idx < ticketing_idx:
            raise ValueError(
                f"Cannot create tickets: sprint '{sprint_id}' is in "
                f"'{state['phase']}' phase. Tickets can only be created "
                f"in 'ticketing' phase or later. Complete the review gates first."
            )
    except ValueError as e:
        if "not registered" in str(e):
            return  # Sprint not in DB — allow (backward compat)
        raise


@server.tool()
def create_ticket(
    sprint_id: str,
    title: str,
    todo: str | list[str] | None = None,
) -> str:
    """Create a new ticket in a sprint's tickets/ directory.

    Auto-assigns the next ticket number within the sprint.
    Checks sprint phase if the state database exists.

    When ``todo`` is provided (a filename or list of filenames), the
    ticket's frontmatter ``todo`` field is set and the referenced TODO
    files are updated with ``status: in-progress``, the sprint ID, and
    the ticket ID.

    Args:
        sprint_id: The sprint ID (e.g., '001')
        title: The ticket title
        todo: Optional TODO filename or list of filenames that this
              ticket addresses (e.g., 'my-idea.md' or
              ['idea-a.md', 'idea-b.md'])
    """
    _check_sprint_phase_for_ticketing(sprint_id)
    sprint_dir = _find_sprint_dir(sprint_id)
    ticket_id = _next_ticket_id(sprint_dir)
    slug = slugify(title)
    tickets_dir = sprint_dir / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)

    path = tickets_dir / f"{ticket_id}-{slug}.md"
    if path.exists():
        raise ValueError(f"Ticket file already exists: {path}")

    content = TICKET_TEMPLATE.format(id=ticket_id, title=title)
    path.write_text(content, encoding="utf-8")

    # Set the todo field in the ticket frontmatter if provided
    if todo is not None:
        todo_list = [todo] if isinstance(todo, str) else list(todo)
        ticket_fm = read_frontmatter(path)
        if len(todo_list) == 1:
            ticket_fm["todo"] = todo_list[0]
        else:
            ticket_fm["todo"] = todo_list
        write_frontmatter(path, ticket_fm)

        # Update each referenced TODO file
        full_ticket_id = f"{sprint_id}-{ticket_id}"
        todo_directory = _todo_dir()
        for todo_filename in todo_list:
            todo_path = todo_directory / todo_filename
            if not todo_path.exists():
                continue  # Skip missing TODOs gracefully
            todo_fm = read_frontmatter(todo_path)
            todo_fm["status"] = "in-progress"
            todo_fm["sprint"] = sprint_id
            # Append ticket ID to the tickets list
            existing_tickets = todo_fm.get("tickets", [])
            if isinstance(existing_tickets, str):
                existing_tickets = [existing_tickets]
            if full_ticket_id not in existing_tickets:
                existing_tickets.append(full_ticket_id)
            todo_fm["tickets"] = existing_tickets
            write_frontmatter(todo_path, todo_fm)

    return json.dumps({
        "id": ticket_id,
        "path": str(path),
        "template_content": content,
    }, indent=2)


@server.tool()
def create_overview() -> str:
    """Create the top-level project overview (docs/clasi/overview.md).

    This is the recommended way to start a new project. The overview
    replaces the separate brief, use cases, and architecture files
    with a single lightweight document. Detailed planning lives in sprints.

    Returns an error if the file already exists.
    """
    path = _plans_dir() / "overview.md"
    if path.exists():
        raise ValueError(f"Overview already exists: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(OVERVIEW_TEMPLATE, encoding="utf-8")

    return json.dumps({"path": str(path)}, indent=2)


# --- Query tools (ticket 009) ---


@server.tool()
def list_sprints(status: Optional[str] = None) -> str:
    """List all sprints with their metadata.

    Args:
        status: Optional filter by status (planning, active, done)

    Returns JSON array of {id, title, status, path, branch}.
    """
    results = []
    sprints = _sprints_dir()

    for location in [sprints, sprints / "done"]:
        if not location.exists():
            continue
        for d in sorted(location.iterdir()):
            sprint_file = d / "sprint.md"
            if not d.is_dir() or not sprint_file.exists():
                continue
            fm = read_frontmatter(sprint_file)
            sprint_status = fm.get("status", "unknown")
            if status and sprint_status != status:
                continue
            results.append({
                "id": fm.get("id", ""),
                "title": fm.get("title", ""),
                "status": sprint_status,
                "path": str(d),
                "branch": fm.get("branch", ""),
            })

    return json.dumps(results, indent=2)


@server.tool()
def list_tickets(sprint_id: Optional[str] = None, status: Optional[str] = None) -> str:
    """List tickets, optionally filtered by sprint and/or status.

    Args:
        sprint_id: Optional sprint ID to filter by
        status: Optional status filter (todo, in-progress, done)

    Returns JSON array of {id, title, status, sprint_id, path}.
    """
    results = []
    sprints = _sprints_dir()

    # Collect sprint directories to scan
    sprint_dirs = []
    if sprint_id:
        try:
            sprint_dirs.append(_find_sprint_dir(sprint_id))
        except ValueError:
            return json.dumps([], indent=2)
    else:
        for location in [sprints, sprints / "done"]:
            if not location.exists():
                continue
            for d in sorted(location.iterdir()):
                if d.is_dir() and (d / "sprint.md").exists():
                    sprint_dirs.append(d)

    for sprint_dir in sprint_dirs:
        sprint_fm = read_frontmatter(sprint_dir / "sprint.md")
        sid = sprint_fm.get("id", "")

        for ticket_location in [sprint_dir / "tickets", sprint_dir / "tickets" / "done"]:
            if not ticket_location.exists():
                continue
            for f in sorted(ticket_location.glob("*.md")):
                fm = read_frontmatter(f)
                if not fm.get("id"):
                    continue
                ticket_status = fm.get("status", "unknown")
                if status and ticket_status != status:
                    continue
                results.append({
                    "id": fm.get("id", ""),
                    "title": fm.get("title", ""),
                    "status": ticket_status,
                    "sprint_id": sid,
                    "path": str(f),
                })

    return json.dumps(results, indent=2)


@server.tool()
def get_sprint_status(sprint_id: str) -> str:
    """Get a summary of a sprint's status including ticket counts.

    Args:
        sprint_id: The sprint ID (e.g., '001')

    Returns JSON with {id, title, status, branch, tickets: {todo, in_progress, done}}.
    """
    sprint_dir = _find_sprint_dir(sprint_id)
    fm = read_frontmatter(sprint_dir / "sprint.md")

    counts = {"todo": 0, "in_progress": 0, "done": 0}
    for ticket_location in [sprint_dir / "tickets", sprint_dir / "tickets" / "done"]:
        if not ticket_location.exists():
            continue
        for f in sorted(ticket_location.glob("*.md")):
            ticket_fm = read_frontmatter(f)
            if not ticket_fm.get("id"):
                continue
            s = ticket_fm.get("status", "todo")
            if s == "in-progress":
                s = "in_progress"
            if s in counts:
                counts[s] += 1

    return json.dumps({
        "id": fm.get("id", ""),
        "title": fm.get("title", ""),
        "status": fm.get("status", ""),
        "branch": fm.get("branch", ""),
        "tickets": counts,
    }, indent=2)


# --- Update tools (ticket 010) ---


@server.tool()
def update_ticket_status(path: str, status: str) -> str:
    """Update a ticket's status in its YAML frontmatter.

    Args:
        path: Path to the ticket file
        status: New status (todo, in-progress, done)

    Returns JSON with {path, old_status, new_status}.
    """
    valid_statuses = {"todo", "in-progress", "done"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(valid_statuses))}")

    try:
        ticket_path = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"Ticket not found: {path}")

    fm = read_frontmatter(ticket_path)
    old_status = fm.get("status", "unknown")
    fm["status"] = status
    write_frontmatter(ticket_path, fm)

    return json.dumps({
        "path": str(ticket_path),
        "old_status": old_status,
        "new_status": status,
    }, indent=2)


@server.tool()
def move_ticket_to_done(path: str) -> str:
    """Move a ticket (and its plan file if exists) to the sprint's tickets/done/ directory.

    Args:
        path: Path to the ticket file

    Returns JSON with {old_path, new_path}.
    """
    try:
        ticket_path = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"Ticket not found: {path}")

    # If resolved to done/, the parent is already the done dir — go up one more
    tickets_dir = ticket_path.parent
    if tickets_dir.name == "done":
        tickets_dir = tickets_dir.parent
    done_dir = tickets_dir / "done"
    done_dir.mkdir(parents=True, exist_ok=True)

    new_path = done_dir / ticket_path.name
    ticket_path.rename(new_path)

    result = {"old_path": str(ticket_path), "new_path": str(new_path)}

    # Also move the plan file if it exists
    plan_name = ticket_path.stem + "-plan.md"
    plan_path = tickets_dir / plan_name
    if plan_path.exists():
        new_plan_path = done_dir / plan_name
        plan_path.rename(new_plan_path)
        result["plan_old_path"] = str(plan_path)
        result["plan_new_path"] = str(new_plan_path)

    return json.dumps(result, indent=2)


@server.tool()
def reopen_ticket(path: str) -> str:
    """Reopen a completed ticket by moving it from done/ back to the sprint's tickets/ directory.

    Behaviour:
    - If the ticket is in tickets/done/, move it back to tickets/ and reset status to "todo".
    - If the ticket exists but is NOT in done/, just reset status to "todo".
    - If the ticket file doesn't exist anywhere, raise an error.

    Also moves the plan file back if one exists in done/.

    Args:
        path: Path to the ticket file

    Returns JSON with {old_path, new_path, old_status, new_status}.
    """
    try:
        ticket_path = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"Ticket not found: {path}")

    fm = read_frontmatter(ticket_path)
    old_status = fm.get("status", "unknown")

    # Determine if ticket is in a done/ directory
    in_done = ticket_path.parent.name == "done"

    if in_done:
        # Move from tickets/done/ back to tickets/
        tickets_dir = ticket_path.parent.parent
        new_path = tickets_dir / ticket_path.name
        ticket_path.rename(new_path)

        # Also move plan file if it exists in done/
        plan_name = ticket_path.stem + "-plan.md"
        plan_path = ticket_path.parent / plan_name
        result = {"old_path": str(ticket_path), "new_path": str(new_path)}
        if plan_path.exists():
            new_plan_path = tickets_dir / plan_name
            plan_path.rename(new_plan_path)
            result["plan_old_path"] = str(plan_path)
            result["plan_new_path"] = str(new_plan_path)

        # Update frontmatter on the moved file
        fm["status"] = "todo"
        write_frontmatter(new_path, fm)
    else:
        # Ticket exists but not in done/ — just reset status
        new_path = ticket_path
        fm["status"] = "todo"
        write_frontmatter(ticket_path, fm)
        result = {"old_path": str(ticket_path), "new_path": str(new_path)}

    result["old_status"] = old_status
    result["new_status"] = "todo"
    return json.dumps(result, indent=2)


@server.tool()
def close_sprint(
    sprint_id: str,
    branch_name: Optional[str] = None,
    main_branch: str = "master",
    push_tags: bool = True,
    delete_branch: bool = True,
) -> str:
    """Close a sprint by updating its status and moving it to sprints/done/.

    When branch_name is provided, executes the full lifecycle including
    pre-condition verification with self-repair, test run, archive, state
    DB update, version bump, git merge, push tags, and branch deletion.

    When branch_name is omitted, falls back to legacy behavior (archive
    + state only, no git operations).

    Args:
        sprint_id: The sprint ID (e.g., '001')
        branch_name: Sprint branch name (e.g., 'sprint/001-my-sprint').
            When provided, enables full lifecycle with git operations.
        main_branch: Target branch for merge (default: 'master')
        push_tags: Whether to push tags after tagging (default: True)
        delete_branch: Whether to delete the sprint branch after merge (default: True)

    Returns JSON with structured result (success or error).
    """
    if branch_name is not None:
        return _close_sprint_full(
            sprint_id, branch_name, main_branch, push_tags, delete_branch
        )
    return _close_sprint_legacy(sprint_id)


def _close_sprint_legacy(sprint_id: str) -> str:
    """Original close_sprint behavior: archive + state, no git."""
    sprint_dir = _find_sprint_dir(sprint_id)

    # Update sprint status to done
    sprint_file = sprint_dir / "sprint.md"
    fm = read_frontmatter(sprint_file)
    fm["status"] = "done"
    write_frontmatter(sprint_file, fm)

    # Move linked TODOs to done
    moved_todos: list[str] = []
    todo_directory = _todo_dir()
    if todo_directory.exists():
        for todo_file in sorted(todo_directory.glob("*.md")):
            todo_fm = read_frontmatter(todo_file)
            if todo_fm.get("sprint") == sprint_id:
                todo_fm["status"] = "done"
                write_frontmatter(todo_file, todo_fm)
                todo_done = todo_directory / "done"
                todo_done.mkdir(parents=True, exist_ok=True)
                dest_todo = todo_done / todo_file.name
                todo_file.rename(dest_todo)
                moved_todos.append(todo_file.name)

    # Copy architecture-update to the architecture directory
    arch_update = sprint_dir / "architecture-update.md"
    if arch_update.exists():
        arch_dir = _plans_dir() / "architecture"
        arch_dir.mkdir(parents=True, exist_ok=True)
        dest = arch_dir / f"architecture-update-{sprint_id}.md"
        shutil.copy2(str(arch_update), str(dest))

    # Move to done directory
    done_dir = _sprints_dir() / "done"
    done_dir.mkdir(parents=True, exist_ok=True)
    new_path = done_dir / sprint_dir.name

    if new_path.exists():
        raise ValueError(f"Destination already exists: {new_path}")

    shutil.move(str(sprint_dir), str(new_path))

    # Update state database: advance to done and release lock
    db = _db_path()
    if db.exists():
        try:
            state = _get_sprint_state(str(db), sprint_id)
            from claude_agent_skills.state_db import PHASES
            phase_idx = PHASES.index(state["phase"])
            done_idx = PHASES.index("done")
            while phase_idx < done_idx:
                _advance_phase(str(db), sprint_id)
                phase_idx += 1
            if state["lock"]:
                _release_lock(str(db), sprint_id)
        except (ValueError, Exception):
            pass  # Graceful degradation

    # Auto-version after archiving (respects version_trigger setting)
    version = None
    try:
        from claude_agent_skills.versioning import (
            compute_next_version,
            create_version_tag,
            detect_version_file,
            load_version_trigger,
            should_version,
            update_version_file,
        )
        trigger = load_version_trigger()
        if should_version(trigger, "sprint_close"):
            version = compute_next_version()
            detected = detect_version_file(Path.cwd())
            if detected:
                update_version_file(detected[0], detected[1], version)
            create_version_tag(version)
    except Exception as exc:
        import sys
        print(f"[CLASI] Versioning failed: {exc}", file=sys.stderr)

    result: dict = {
        "old_path": str(sprint_dir),
        "new_path": str(new_path),
    }
    if moved_todos:
        result["moved_todos"] = moved_todos
    if version:
        result["version"] = version
        result["tag"] = f"v{version}"

    return json.dumps(result, indent=2)


def _close_sprint_full(
    sprint_id: str,
    branch_name: str,
    main_branch: str,
    push_tags_flag: bool,
    delete_branch_flag: bool,
) -> str:
    """Full lifecycle close: preconditions, tests, archive, git ops."""
    db = _db_path()
    db_str = str(db)
    completed_steps: list[str] = []
    repairs: list[str] = []

    # ── Step 1: Pre-condition verification with self-repair ──

    # 1a. Check tickets — all should be in tickets/done/ with status done
    try:
        sprint_dir = _find_sprint_dir(sprint_id)
    except ValueError:
        # Sprint dir might already be archived (idempotent retry)
        done_dir = _sprints_dir() / "done"
        sprint_dir_in_done = None
        if done_dir.exists():
            for d in sorted(done_dir.iterdir()):
                if d.is_dir() and d.name.startswith(sprint_id):
                    fm_check = read_frontmatter(d / "sprint.md") if (d / "sprint.md").exists() else {}
                    if fm_check.get("id") == sprint_id:
                        sprint_dir_in_done = d
                        break
        if sprint_dir_in_done is None:
            return json.dumps({
                "status": "error",
                "error": {
                    "step": "precondition",
                    "message": f"Sprint '{sprint_id}' not found in active or done",
                    "recovery": {"recorded": False, "allowed_paths": [], "instruction": "Create or restore the sprint directory."},
                },
                "completed_steps": [],
                "remaining_steps": ["precondition", "tests", "archive", "db_update", "version_bump", "merge", "push_tags", "delete_branch"],
            }, indent=2)

    tickets_dir = sprint_dir / "tickets"
    done_tickets_dir = tickets_dir / "done"
    if tickets_dir.exists():
        for ticket_file in sorted(tickets_dir.glob("*.md")):
            if ticket_file.name == "done":
                continue
            t_fm = read_frontmatter(ticket_file)
            if t_fm.get("status") == "done":
                # Self-repair: move to done/
                done_tickets_dir.mkdir(parents=True, exist_ok=True)
                dest = done_tickets_dir / ticket_file.name
                ticket_file.rename(dest)
                # Also move plan file if exists
                plan_file = ticket_file.with_suffix("").with_name(ticket_file.stem + "-plan.md")
                if plan_file.exists():
                    plan_file.rename(done_tickets_dir / plan_file.name)
                repairs.append(f"moved ticket {t_fm.get('id', ticket_file.stem)} to done/")
            elif t_fm.get("status") != "done":
                # Ticket not done — unrepairable
                error_msg = f"Ticket {t_fm.get('id', ticket_file.stem)} has status '{t_fm.get('status')}', not 'done'"
                if db.exists():
                    _write_recovery_state(
                        db_str, sprint_id, "precondition",
                        [str(ticket_file)], error_msg,
                    )
                return json.dumps({
                    "status": "error",
                    "error": {
                        "step": "precondition",
                        "message": error_msg,
                        "recovery": {
                            "recorded": db.exists(),
                            "allowed_paths": [str(ticket_file)],
                            "instruction": f"Complete ticket {t_fm.get('id', ticket_file.stem)} and set status to 'done', then call close_sprint again.",
                        },
                    },
                    "completed_steps": [],
                    "remaining_steps": ["precondition", "tests", "archive", "db_update", "version_bump", "merge", "push_tags", "delete_branch"],
                }, indent=2)

    # 1b. Check TODOs — sprint-tagged TODOs should be resolved
    todo_directory = _todo_dir()
    if todo_directory.exists():
        for todo_file in sorted(todo_directory.glob("*.md")):
            t_fm = read_frontmatter(todo_file)
            if t_fm.get("sprint") == sprint_id:
                if t_fm.get("status") in ("done", "complete", "completed"):
                    # Self-repair: move to done/
                    t_fm["status"] = "done"
                    write_frontmatter(todo_file, t_fm)
                    todo_done = todo_directory / "done"
                    todo_done.mkdir(parents=True, exist_ok=True)
                    todo_file.rename(todo_done / todo_file.name)
                    repairs.append(f"moved TODO {todo_file.name} to done/")

    # 1c. Check state DB phase — self-repair: advance if behind
    if db.exists():
        try:
            state = _get_sprint_state(db_str, sprint_id)
            phase = state["phase"]
            if phase != "done":
                phase_idx = _PHASES.index(phase)
                # We need to be at least in 'closing' before we proceed
                closing_idx = _PHASES.index("closing")
                while phase_idx < closing_idx:
                    try:
                        _advance_phase(db_str, sprint_id)
                        phase_idx += 1
                        repairs.append(f"advanced DB phase to '{_PHASES[phase_idx]}'")
                    except ValueError:
                        # Can't advance further (missing gate, etc.) — skip
                        break
        except ValueError:
            pass  # Sprint not in DB — skip DB checks

    # 1d. Check execution lock — self-repair: re-acquire if not held
    if db.exists():
        try:
            state = _get_sprint_state(db_str, sprint_id)
            if not state["lock"]:
                try:
                    _acquire_lock(db_str, sprint_id)
                    repairs.append("re-acquired execution lock")
                except ValueError:
                    pass  # Another sprint holds it — continue anyway
        except ValueError:
            pass

    completed_steps.append("precondition_verification")

    # ── Step 2: Run tests ──
    all_steps = ["precondition_verification", "tests", "archive", "db_update", "version_bump", "merge", "push_tags", "delete_branch"]

    try:
        test_result = subprocess.run(
            ["uv", "run", "pytest"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if test_result.returncode != 0:
            error_msg = f"Tests failed (exit code {test_result.returncode})"
            test_output = test_result.stdout[-2000:] if test_result.stdout else ""
            if test_result.stderr:
                test_output += "\n" + test_result.stderr[-500:]
            if db.exists():
                _write_recovery_state(
                    db_str, sprint_id, "tests", [], error_msg,
                )
            return json.dumps({
                "status": "error",
                "error": {
                    "step": "tests",
                    "message": error_msg,
                    "output": test_output.strip(),
                    "recovery": {
                        "recorded": db.exists(),
                        "allowed_paths": [],
                        "instruction": "Fix failing tests, then call close_sprint again.",
                    },
                },
                "completed_steps": completed_steps,
                "remaining_steps": [s for s in all_steps if s not in completed_steps],
            }, indent=2)
    except FileNotFoundError:
        # uv not available — skip tests
        repairs.append("skipped tests (uv not found)")
    except subprocess.TimeoutExpired:
        error_msg = "Test suite timed out after 300 seconds"
        if db.exists():
            _write_recovery_state(db_str, sprint_id, "tests", [], error_msg)
        return json.dumps({
            "status": "error",
            "error": {
                "step": "tests",
                "message": error_msg,
                "recovery": {
                    "recorded": db.exists(),
                    "allowed_paths": [],
                    "instruction": "Investigate slow tests, then call close_sprint again.",
                },
            },
            "completed_steps": completed_steps,
            "remaining_steps": [s for s in all_steps if s not in completed_steps],
        }, indent=2)

    completed_steps.append("tests")

    # ── Step 3: Archive sprint directory ──
    done_dir = _sprints_dir() / "done"
    already_archived = False

    # Check if already archived (idempotent)
    if done_dir.exists():
        for d in sorted(done_dir.iterdir()):
            if d.is_dir() and d.name.startswith(sprint_id):
                fm_check = read_frontmatter(d / "sprint.md") if (d / "sprint.md").exists() else {}
                if fm_check.get("id") == sprint_id:
                    already_archived = True
                    new_path = d
                    # sprint_dir might still point to active — update
                    sprint_dir = d
                    break

    if not already_archived:
        # Update sprint status to done
        sprint_file = sprint_dir / "sprint.md"
        fm = read_frontmatter(sprint_file)
        fm["status"] = "done"
        write_frontmatter(sprint_file, fm)

        # Move linked TODOs to done
        if todo_directory.exists():
            for todo_file in sorted(todo_directory.glob("*.md")):
                todo_fm = read_frontmatter(todo_file)
                if todo_fm.get("sprint") == sprint_id:
                    todo_fm["status"] = "done"
                    write_frontmatter(todo_file, todo_fm)
                    todo_done = todo_directory / "done"
                    todo_done.mkdir(parents=True, exist_ok=True)
                    todo_file.rename(todo_done / todo_file.name)

        # Copy architecture-update
        arch_update = sprint_dir / "architecture-update.md"
        if arch_update.exists():
            arch_dir = _plans_dir() / "architecture"
            arch_dir.mkdir(parents=True, exist_ok=True)
            dest = arch_dir / f"architecture-update-{sprint_id}.md"
            shutil.copy2(str(arch_update), str(dest))

        # Move to done directory
        done_dir.mkdir(parents=True, exist_ok=True)
        new_path = done_dir / sprint_dir.name

        if new_path.exists():
            raise ValueError(f"Destination already exists: {new_path}")

        old_path_str = str(sprint_dir)
        shutil.move(str(sprint_dir), str(new_path))
    else:
        old_path_str = str(new_path)

    completed_steps.append("archive")

    # ── Step 4: Update state DB ──
    if db.exists():
        try:
            state = _get_sprint_state(db_str, sprint_id)
            if state["phase"] != "done":
                phase_idx = _PHASES.index(state["phase"])
                done_idx = _PHASES.index("done")
                while phase_idx < done_idx:
                    try:
                        _advance_phase(db_str, sprint_id)
                    except ValueError:
                        break
                    phase_idx += 1
            if state["lock"]:
                try:
                    _release_lock(db_str, sprint_id)
                except ValueError:
                    pass
        except (ValueError, Exception):
            pass

    completed_steps.append("db_update")

    # ── Step 5: Version bump ──
    version = None
    try:
        from claude_agent_skills.versioning import (
            compute_next_version,
            create_version_tag,
            detect_version_file,
            load_version_trigger,
            should_version,
            update_version_file,
        )
        trigger = load_version_trigger()
        if should_version(trigger, "sprint_close"):
            version = compute_next_version()
            detected = detect_version_file(Path.cwd())
            if detected:
                update_version_file(detected[0], detected[1], version)
            create_version_tag(version)
    except Exception as exc:
        import sys
        print(f"[CLASI] Versioning failed: {exc}", file=sys.stderr)

    completed_steps.append("version_bump")

    # ── Step 6: Git merge ──
    merged = False
    # Check if already merged (idempotent): branch doesn't exist or is ancestor of main
    branch_exists = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        capture_output=True, text=True,
    ).returncode == 0

    if not branch_exists:
        # Branch already deleted/merged — skip
        merged = True
    else:
        # Check if branch is already merged into main
        is_ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", branch_name, main_branch],
            capture_output=True, text=True,
        ).returncode == 0

        if is_ancestor:
            merged = True
        else:
            # Perform the merge
            checkout = subprocess.run(
                ["git", "checkout", main_branch],
                capture_output=True, text=True,
            )
            if checkout.returncode != 0:
                error_msg = f"Failed to checkout {main_branch}: {checkout.stderr.strip()}"
                if db.exists():
                    _write_recovery_state(db_str, sprint_id, "merge", [], error_msg)
                return json.dumps({
                    "status": "error",
                    "error": {
                        "step": "merge",
                        "message": error_msg,
                        "recovery": {
                            "recorded": db.exists(),
                            "allowed_paths": [],
                            "instruction": f"Resolve checkout issues, then call close_sprint again.",
                        },
                    },
                    "completed_steps": completed_steps,
                    "remaining_steps": [s for s in all_steps if s not in completed_steps],
                }, indent=2)

            merge = subprocess.run(
                ["git", "merge", "--no-ff", branch_name],
                capture_output=True, text=True,
            )
            if merge.returncode != 0:
                # Parse conflicted files
                conflict_result = subprocess.run(
                    ["git", "diff", "--name-only", "--diff-filter=U"],
                    capture_output=True, text=True,
                )
                conflicted = [f.strip() for f in conflict_result.stdout.strip().split("\n") if f.strip()]
                # Abort the failed merge
                subprocess.run(["git", "merge", "--abort"], capture_output=True)
                error_msg = f"Merge conflict: {merge.stderr.strip()}"
                if db.exists():
                    _write_recovery_state(db_str, sprint_id, "merge", conflicted, error_msg)
                return json.dumps({
                    "status": "error",
                    "error": {
                        "step": "merge",
                        "message": error_msg,
                        "recovery": {
                            "recorded": db.exists(),
                            "allowed_paths": conflicted,
                            "instruction": "Resolve the merge conflicts in the listed files, then call close_sprint again.",
                        },
                    },
                    "completed_steps": completed_steps,
                    "remaining_steps": [s for s in all_steps if s not in completed_steps],
                }, indent=2)
            merged = True

    completed_steps.append("merge")

    # ── Step 7: Push tags ──
    tags_pushed = False
    if push_tags_flag and version:
        tag_name = f"v{version}"
        push_result = subprocess.run(
            ["git", "push", "--tags"],
            capture_output=True, text=True,
        )
        tags_pushed = push_result.returncode == 0

    completed_steps.append("push_tags")

    # ── Step 8: Delete branch ──
    branch_deleted = False
    if delete_branch_flag and branch_exists:
        del_result = subprocess.run(
            ["git", "branch", "-d", branch_name],
            capture_output=True, text=True,
        )
        branch_deleted = del_result.returncode == 0

    completed_steps.append("delete_branch")

    # ── Step 9: Clear recovery state ──
    if db.exists():
        try:
            _clear_recovery_state(db_str)
        except Exception:
            pass

    # ── Step 10: Return structured result ──
    result: dict = {
        "status": "success",
        "old_path": old_path_str,
        "new_path": str(new_path),
        "repairs": repairs,
    }
    if version:
        result["version"] = version
        result["tag"] = f"v{version}"
    result["git"] = {
        "merged": merged,
        "merge_strategy": "--no-ff",
        "merge_target": main_branch,
        "tags_pushed": tags_pushed,
        "branch_deleted": branch_deleted,
        "branch_name": branch_name,
    }

    return json.dumps(result, indent=2)


@server.tool()
def clear_sprint_recovery(sprint_id: str) -> str:
    """Clear the recovery state record for a sprint.

    Use this after manually resolving a failure that was recorded
    during close_sprint.

    Args:
        sprint_id: The sprint ID (for confirmation; currently unused
            since recovery_state is a singleton)

    Returns JSON with {cleared: true/false}.
    """
    db = _db_path()
    if not db.exists():
        return json.dumps({"cleared": False, "reason": "No state database found"}, indent=2)
    result = _clear_recovery_state(str(db))
    return json.dumps(result, indent=2)


# --- State management tools (ticket 005) ---


def _db_path() -> Path:
    """Return the default state database path."""
    return _plans_dir() / ".clasi.db"


@server.tool()
def get_sprint_phase(sprint_id: str) -> str:
    """Get a sprint's current lifecycle phase and gate status.

    Args:
        sprint_id: The sprint ID (e.g., '002')

    Returns JSON with {id, phase, gates, lock}.
    """
    try:
        state = _get_sprint_state(str(_db_path()), sprint_id)
        return json.dumps(state, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


@server.tool()
def advance_sprint_phase(sprint_id: str) -> str:
    """Advance a sprint to the next lifecycle phase.

    Validates that exit conditions are met (review gates passed,
    execution lock held, etc.) before allowing the transition.

    Args:
        sprint_id: The sprint ID (e.g., '002')

    Returns JSON with {sprint_id, old_phase, new_phase}.
    """
    try:
        result = _advance_phase(str(_db_path()), sprint_id)
        return json.dumps(result, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


@server.tool()
def record_gate_result(
    sprint_id: str,
    gate: str,
    result: str,
    notes: Optional[str] = None,
) -> str:
    """Record a review gate result for a sprint.

    Args:
        sprint_id: The sprint ID
        gate: Gate name ('architecture_review' or 'stakeholder_approval')
        result: 'passed' or 'failed'
        notes: Optional notes about the review

    Returns JSON with {sprint_id, gate_name, result, recorded_at}.
    """
    try:
        gate_result = _record_gate(str(_db_path()), sprint_id, gate, result, notes)
        return json.dumps(gate_result, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


@server.tool()
def acquire_execution_lock(sprint_id: str) -> str:
    """Acquire the execution lock for a sprint.

    Only one sprint can hold the lock at a time. Prevents concurrent
    sprint execution in the same repository.

    Args:
        sprint_id: The sprint ID

    Returns JSON with {sprint_id, acquired_at, reentrant}.
    """
    try:
        lock = _acquire_lock(str(_db_path()), sprint_id)
        return json.dumps(lock, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


@server.tool()
def release_execution_lock(sprint_id: str) -> str:
    """Release the execution lock held by a sprint.

    Args:
        sprint_id: The sprint ID

    Returns JSON with {sprint_id, released}.
    """
    try:
        result = _release_lock(str(_db_path()), sprint_id)
        return json.dumps(result, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


# --- TODO management tools ---


def _todo_dir() -> Path:
    """Return the docs/clasi/todo/ directory."""
    return _plans_dir() / "todo"


@server.tool()
def list_todos() -> str:
    """List all active TODO files with sprint/ticket linkage.

    Scans docs/clasi/todo/*.md (excludes done/ subdirectory).

    Returns JSON array of {filename, title, status, sprint, tickets}.
    The sprint and tickets fields are present only for in-progress TODOs.
    """
    todo = _todo_dir()
    results = []
    if todo.exists():
        for f in sorted(todo.glob("*.md")):
            title = f.stem
            # Extract title from first # heading
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            fm = read_frontmatter(f)
            entry: dict = {"filename": f.name, "title": title}
            status = fm.get("status", "pending")
            entry["status"] = status
            if status == "in-progress":
                sprint = fm.get("sprint")
                if sprint:
                    entry["sprint"] = sprint
                tickets = fm.get("tickets")
                if tickets:
                    entry["tickets"] = tickets
            results.append(entry)
    return json.dumps(results, indent=2)


@server.tool()
def move_todo_to_done(
    filename: str,
    sprint_id: str | None = None,
    ticket_ids: list[str] | None = None,
) -> str:
    """Move a TODO file to the done/ subdirectory.

    Args:
        filename: The TODO filename (e.g., 'my-idea.md')
        sprint_id: Optional sprint ID that consumed this TODO
        ticket_ids: Optional list of ticket IDs that address this TODO

    Returns JSON with {old_path, new_path}.
    """
    todo = _todo_dir()
    src = todo / filename
    if not src.exists():
        raise ValueError(f"TODO not found: {filename}")

    # Write traceability frontmatter before moving
    fm = read_frontmatter(src)
    fm["status"] = "done"
    if sprint_id is not None:
        fm["sprint"] = sprint_id
    if ticket_ids is not None:
        fm["tickets"] = ticket_ids
    write_frontmatter(src, fm)

    done = todo / "done"
    done.mkdir(parents=True, exist_ok=True)
    dst = done / filename
    src.rename(dst)

    return json.dumps({
        "old_path": str(src),
        "new_path": str(dst),
    }, indent=2)


@server.tool()
def create_github_issue(title: str, body: str, labels: list[str] | None = None) -> str:
    """Create a GitHub issue in the current repository.

    This tool prefers direct GitHub API access when a token is available in
    the environment. If the token is missing or API access fails, it returns
    metadata so an agent can use the GitHub MCP server instead.

    Args:
        title: The issue title
        body: The issue body/description in markdown format
        labels: Optional list of label names to apply to the issue

    Returns JSON with {issue_number, url, title}.

    Note: This tool prefers direct GitHub API access when a token is available in
    the environment. If the token is missing or API access fails, it returns
    metadata so an agent can use the GitHub MCP server instead.
    """
    repo = _get_github_repo()
    token = _get_github_token()
    if token and repo and not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            issue = _create_github_issue_api(
                repo=repo,
                title=title,
                body=body,
                labels=labels or [],
                token=token,
            )
            return json.dumps({
                "issue_number": issue.get("number"),
                "url": issue.get("html_url"),
                "title": issue.get("title"),
            }, indent=2)
        except Exception as exc:
            return json.dumps({
                "tool": "create_github_issue",
                "title": title,
                "body": body,
                "labels": labels or [],
                "error": str(exc),
                "note": (
                    "Direct GitHub API creation failed. Use GitHub MCP tools "
                    "(github-mcp-server) to create the actual issue. "
                    "Example: Use github_create_issue() from the GitHub MCP server."
                )
            }, indent=2)

    note_bits = []
    if not token:
        note_bits.append("missing GITHUB_TOKEN or GH_TOKEN")
    if not repo:
        note_bits.append("could not resolve repository")
    if os.environ.get("PYTEST_CURRENT_TEST"):
        note_bits.append("disabled during tests")

    note_suffix = f" ({', '.join(note_bits)})" if note_bits else ""
    return json.dumps({
        "tool": "create_github_issue",
        "title": title,
        "body": body,
        "labels": labels or [],
        "note": (
            "This tool provides issue metadata. Use GitHub MCP tools "
            "(github-mcp-server) to create the actual issue. "
            "Example: Use github_create_issue() from the GitHub MCP server."
            f"{note_suffix}"
        )
    }, indent=2)


def _get_github_token() -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    return token.strip() if token else None


def _get_github_repo() -> str | None:
    env_repo = os.environ.get("GITHUB_REPOSITORY")
    if env_repo:
        return env_repo.strip()

    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    remote = result.stdout.strip()
    if not remote:
        return None

    match = re.search(r"github\.com[:/](?P<repo>[^\s]+)", remote)
    if not match:
        return None

    repo = match.group("repo")
    if repo.endswith(".git"):
        repo = repo[:-4]
    return repo.strip("/")


def _create_github_issue_api(
    *,
    repo: str,
    title: str,
    body: str,
    labels: list[str],
    token: str,
) -> dict:
    url = f"https://api.github.com/repos/{repo}/issues"
    payload = {
        "title": title,
        "body": body,
    }
    if labels:
        payload["labels"] = labels

    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST")
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body_text = response.read().decode("utf-8")
            return json.loads(body_text)
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(
            f"GitHub API error {exc.code}: {error_body or exc.reason}"
        )


def _check_gh_access(repo: str | None = None) -> tuple[bool, str]:
    """Check whether the gh CLI can access issues for a repository.

    Args:
        repo: GitHub repository in owner/repo format. If None, resolves
              via _get_github_repo().

    Returns:
        (True, repo) on success, or (False, error_message) on failure.
    """
    if repo is None:
        repo = _get_github_repo()
    if repo is None:
        return (
            False,
            "Could not determine repository. Specify repo explicitly "
            "or ensure a git remote is configured.",
        )

    try:
        subprocess.run(
            ["gh", "issue", "list", "--repo", repo, "--limit", "1", "--json", "number"],
            capture_output=True,
            text=True,
            check=True,
        )
        return (True, repo)
    except subprocess.CalledProcessError:
        return (
            False,
            f"Cannot access issues for {repo}. "
            "Run `gh auth login` or check `gh auth status`.",
        )
    except FileNotFoundError:
        return (False, "gh CLI not found. Install it from https://cli.github.com/")


@server.tool()
def list_github_issues(
    repo: str | None = None,
    labels: str | None = None,
    state: str = "open",
    limit: int = 30,
) -> str:
    """List GitHub issues for a repository using the gh CLI.

    Args:
        repo: GitHub repository in owner/repo format. Defaults to the
              current repository detected from git remotes.
        labels: Comma-separated label names to filter by.
        state: Issue state filter: "open", "closed", or "all". Default "open".
        limit: Maximum number of issues to return. Default 30.

    Returns JSON array of issue objects with number, title, body, labels, url.
    """
    # During tests, return an empty list to avoid real gh calls
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return json.dumps([])

    ok, result = _check_gh_access(repo)
    if not ok:
        return json.dumps({"error": result})
    repo = result

    cmd = [
        "gh", "issue", "list",
        "--repo", repo,
        "--state", state,
        "--limit", str(limit),
        "--json", "number,title,body,labels,url",
    ]
    if labels:
        cmd.extend(["--label", labels])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        issues = json.loads(proc.stdout)
        return json.dumps(issues)
    except subprocess.CalledProcessError as exc:
        return json.dumps({"error": f"gh issue list failed: {exc.stderr or exc}"})
    except (json.JSONDecodeError, ValueError) as exc:
        return json.dumps({"error": f"Failed to parse gh output: {exc}"})


@server.tool()
def close_github_issue(issue_number: int, repo: str | None = None) -> str:
    """Close a GitHub issue using the gh CLI.

    Args:
        issue_number: The issue number to close. Must be a positive integer.
        repo: GitHub repository in owner/repo format. Defaults to the
              current repository detected from git remotes.

    Returns JSON with {issue_number, repo, closed} on success,
    or {issue_number, repo, closed: false, error} on failure.
    """
    # Validate issue_number is a positive integer
    if not isinstance(issue_number, int) or issue_number <= 0:
        return json.dumps({
            "issue_number": issue_number,
            "repo": repo,
            "closed": False,
            "error": "issue_number must be a positive integer",
        })

    # Resolve repo if not provided
    if repo is None:
        repo = _get_github_repo()

    # During tests, return mock success to avoid real gh calls
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return json.dumps({
            "issue_number": issue_number,
            "repo": repo,
            "closed": True,
        })

    ok, result = _check_gh_access(repo)
    if not ok:
        return json.dumps({
            "issue_number": issue_number,
            "repo": repo,
            "closed": False,
            "error": result,
        })
    repo = result

    try:
        subprocess.run(
            ["gh", "issue", "close", str(issue_number), "--repo", repo],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.dumps({
            "issue_number": issue_number,
            "repo": repo,
            "closed": True,
        })
    except subprocess.CalledProcessError as exc:
        return json.dumps({
            "issue_number": issue_number,
            "repo": repo,
            "closed": False,
            "error": exc.stderr or str(exc),
        })
    except Exception as exc:
        return json.dumps({
            "issue_number": issue_number,
            "repo": repo,
            "closed": False,
            "error": str(exc),
        })


# --- Frontmatter tools ---


@server.tool()
def read_artifact_frontmatter(path: str) -> str:
    """Read YAML frontmatter from a file.

    Uses resolve_artifact_path to find files in original or done/ locations.

    Args:
        path: Path to the file

    Returns JSON dict of frontmatter fields.
    """
    try:
        resolved = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"File not found: {path}")

    fm = read_frontmatter(resolved)
    return json.dumps(fm, indent=2)


@server.tool()
def write_artifact_frontmatter(path: str, updates: str) -> str:
    """Update YAML frontmatter on a file, merging with existing fields.

    Uses resolve_artifact_path to find files in original or done/ locations.
    Creates frontmatter on a plain file that has none.

    Args:
        path: Path to the file
        updates: JSON string of fields to merge (e.g., '{"status": "done"}')

    Returns JSON with {path, updated_fields}.
    """
    try:
        resolved = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"File not found: {path}")

    try:
        update_dict = json.loads(updates)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Invalid JSON for updates: {e}")

    fm = read_frontmatter(resolved)
    fm.update(update_dict)
    write_frontmatter(resolved, fm)

    return json.dumps({
        "path": str(resolved),
        "updated_fields": list(update_dict.keys()),
    }, indent=2)


# --- Versioning tools ---


@server.tool()
def tag_version(major: int = 0) -> str:
    """Compute the next version, update pyproject.toml, and create a git tag.

    Version format: <major>.<YYYYMMDD>.<build>
    Build auto-increments within the same date, resets to 1 on new date.

    Args:
        major: Major version number (default 0)

    Returns JSON with {version, tag}.
    """
    from claude_agent_skills.versioning import (
        compute_next_version,
        create_version_tag,
        detect_version_file,
        update_version_file,
    )

    version = compute_next_version(major)
    detected = detect_version_file(Path.cwd())
    if detected:
        update_version_file(detected[0], detected[1], version)
    create_version_tag(version)

    result = {
        "version": version,
        "tag": f"v{version}",
    }
    if detected:
        result["file_type"] = detected[1]
        result["file_path"] = str(detected[0])
    return json.dumps(result, indent=2)


# --- Sprint review tools ---


def _get_template_body(template_str: str) -> str:
    """Extract the body (after frontmatter) from a template string.

    Strips the {id}, {title}, {slug} placeholders so we can compare
    the structural content, not the filled-in values.
    """
    if not template_str.startswith("---"):
        return template_str.strip()
    end = template_str.find("---", 3)
    if end == -1:
        return template_str.strip()
    end_of_line = template_str.find("\n", end)
    if end_of_line == -1:
        return ""
    body = template_str[end_of_line + 1:].strip()
    # Remove format placeholders so we match on structure
    body = re.sub(r"\{(id|title|slug)\}", "", body)
    return body


_PLACEHOLDER_MARKERS = [
    "(Describe what this sprint aims to accomplish.)",
    "(What problem does this sprint address?)",
    "(High-level description of the approach.)",
    "(How will we know the sprint succeeded?)",
    "(What needs to be done and why.)",
    "(How the components fit together.)",
    "(Unresolved design decisions.)",
    "SUC-001: (Title)",
    "Parent: UC-XXX",
    "### Component: (Name)",
    "(current architecture version, e.g., architecture-",
]


def _is_template_placeholder(file_path: Path, template_str: str) -> bool:
    """Check if a file still contains template placeholder content."""
    _, body = read_document(file_path)
    body = body.strip()
    if not body:
        return True
    # If 3+ placeholder markers remain, it's still a template
    marker_count = sum(1 for m in _PLACEHOLDER_MARKERS if m in body)
    return marker_count >= 3


def _check_git_branch() -> str:
    """Return the current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _collect_tickets(sprint_dir: Path) -> list:
    """Collect all tickets from a sprint directory with their metadata."""
    tickets = []
    for ticket_location in [sprint_dir / "tickets", sprint_dir / "tickets" / "done"]:
        if not ticket_location.exists():
            continue
        for f in sorted(ticket_location.glob("*.md")):
            fm = read_frontmatter(f)
            if not fm.get("id"):
                continue
            tickets.append({
                "id": fm.get("id", ""),
                "title": fm.get("title", ""),
                "status": fm.get("status", "unknown"),
                "path": str(f),
                "in_done_dir": "done" in f.parent.name,
            })
    return tickets


@server.tool()
def review_sprint_pre_execution(sprint_id: str) -> str:
    """Validate sprint state before execution begins.

    Checks that planning docs are complete, not template placeholders,
    and tickets exist in todo status.

    Args:
        sprint_id: The sprint ID (e.g., '015')

    Returns JSON with {passed, issues[]}.
    """
    issues = []

    # Find sprint directory
    try:
        sprint_dir = _find_sprint_dir(sprint_id)
    except ValueError:
        return json.dumps({
            "passed": False,
            "issues": [{
                "severity": "error",
                "check": "sprint_dir_exists",
                "message": f"Sprint '{sprint_id}' directory not found",
                "fix": "Create the sprint with create_sprint(title)",
                "path": None,
            }],
        }, indent=2)

    sprint_fm = read_frontmatter(sprint_dir / "sprint.md")
    expected_branch = sprint_fm.get("branch", f"sprint/{sprint_id}")

    # Check branch
    current_branch = _check_git_branch()
    if current_branch and current_branch != expected_branch:
        issues.append({
            "severity": "error",
            "check": "correct_branch",
            "message": f"On branch '{current_branch}', expected '{expected_branch}'",
            "fix": f"Run: git checkout {expected_branch}",
            "path": None,
        })

    # Check planning docs exist and have correct status
    planning_docs = {
        "sprint.md": SPRINT_TEMPLATE,
        "usecases.md": SPRINT_USECASES_TEMPLATE,
        "architecture-update.md": SPRINT_ARCHITECTURE_UPDATE_TEMPLATE,
    }

    for filename, template in planning_docs.items():
        filepath = sprint_dir / filename
        if not filepath.exists():
            issues.append({
                "severity": "error",
                "check": f"{filename.replace('.', '_')}_exists",
                "message": f"{filename} does not exist",
                "fix": f"Create {filename} in the sprint directory",
                "path": str(filepath),
            })
            continue

        fm = read_frontmatter(filepath)
        status = fm.get("status", "draft")

        if status == "draft":
            issues.append({
                "severity": "error",
                "check": f"{filename.replace('.', '_')}_status",
                "message": f"{filename} has status 'draft'",
                "fix": f"Update {filename} frontmatter status from 'draft' to an appropriate value",
                "path": str(filepath),
            })

        # Check for template placeholder content
        if _is_template_placeholder(filepath, template):
            issues.append({
                "severity": "error",
                "check": f"{filename.replace('.', '_')}_content",
                "message": f"{filename} still contains template placeholder content",
                "fix": f"Replace template placeholders in {filename} with real content",
                "path": str(filepath),
            })

    # Check tickets exist
    tickets_dir = sprint_dir / "tickets"
    if not tickets_dir.exists():
        issues.append({
            "severity": "error",
            "check": "tickets_dir_exists",
            "message": "tickets/ directory does not exist",
            "fix": "Create tickets using create_ticket(sprint_id, title)",
            "path": str(tickets_dir),
        })
    else:
        tickets = _collect_tickets(sprint_dir)
        if not tickets:
            issues.append({
                "severity": "error",
                "check": "tickets_exist",
                "message": "No tickets found in the sprint",
                "fix": "Create tickets using create_ticket(sprint_id, title)",
                "path": str(tickets_dir),
            })
        else:
            for t in tickets:
                if t["status"] not in ("todo", "in-progress"):
                    issues.append({
                        "severity": "warning",
                        "check": "ticket_status_pre_execution",
                        "message": f"Ticket #{t['id']} has unexpected status"
                                   f" '{t['status']}' before execution",
                        "fix": f"Verify ticket #{t['id']} status is correct",
                        "path": t["path"],
                    })

    return json.dumps({
        "passed": not any(i["severity"] == "error" for i in issues),
        "issues": issues,
    }, indent=2)


@server.tool()
def review_sprint_pre_close(sprint_id: str) -> str:
    """Validate sprint state before closing.

    Checks that all tickets are done and in tickets/done/, planning docs
    have correct status, and no template placeholders remain.

    Args:
        sprint_id: The sprint ID (e.g., '015')

    Returns JSON with {passed, issues[]}.
    """
    issues = []

    try:
        sprint_dir = _find_sprint_dir(sprint_id)
    except ValueError:
        return json.dumps({
            "passed": False,
            "issues": [{
                "severity": "error",
                "check": "sprint_dir_exists",
                "message": f"Sprint '{sprint_id}' directory not found",
                "fix": "Check the sprint ID is correct",
                "path": None,
            }],
        }, indent=2)

    sprint_fm = read_frontmatter(sprint_dir / "sprint.md")
    expected_branch = sprint_fm.get("branch", f"sprint/{sprint_id}")

    # Check branch
    current_branch = _check_git_branch()
    if current_branch and current_branch != expected_branch:
        issues.append({
            "severity": "error",
            "check": "correct_branch",
            "message": f"On branch '{current_branch}', expected '{expected_branch}'",
            "fix": f"Run: git checkout {expected_branch}",
            "path": None,
        })

    # Check all tickets are done and in done/ directory
    tickets = _collect_tickets(sprint_dir)
    if not tickets:
        issues.append({
            "severity": "error",
            "check": "tickets_exist",
            "message": "No tickets found in the sprint",
            "fix": "Sprint should have tickets before closing",
            "path": str(sprint_dir / "tickets"),
        })

    for t in tickets:
        if t["status"] != "done":
            issues.append({
                "severity": "error",
                "check": "ticket_done",
                "message": f"Ticket #{t['id']} ({t['title']}) has status"
                           f" '{t['status']}', expected 'done'",
                "fix": f"Complete ticket #{t['id']} and set status to 'done'",
                "path": t["path"],
            })
        if not t["in_done_dir"]:
            issues.append({
                "severity": "error",
                "check": "ticket_in_done_dir",
                "message": f"Ticket #{t['id']} is not in tickets/done/ directory",
                "fix": f"Move ticket #{t['id']} to tickets/done/ using"
                       " move_ticket_to_done",
                "path": t["path"],
            })

    # Check planning docs status and content
    planning_docs = {
        "sprint.md": SPRINT_TEMPLATE,
        "usecases.md": SPRINT_USECASES_TEMPLATE,
        "architecture-update.md": SPRINT_ARCHITECTURE_UPDATE_TEMPLATE,
    }

    for filename, template in planning_docs.items():
        filepath = sprint_dir / filename
        if not filepath.exists():
            issues.append({
                "severity": "error",
                "check": f"{filename.replace('.', '_')}_exists",
                "message": f"{filename} does not exist",
                "fix": f"Create {filename} — this should have been done"
                       " during planning",
                "path": str(filepath),
            })
            continue

        fm = read_frontmatter(filepath)
        status = fm.get("status", "draft")

        if status == "draft":
            issues.append({
                "severity": "error",
                "check": f"{filename.replace('.', '_')}_status",
                "message": f"{filename} still has status 'draft'",
                "fix": f"Update {filename} frontmatter status from 'draft'",
                "path": str(filepath),
            })

        if _is_template_placeholder(filepath, template):
            issues.append({
                "severity": "error",
                "check": f"{filename.replace('.', '_')}_content",
                "message": f"{filename} still contains template placeholder"
                           " content",
                "fix": f"Replace template placeholders in {filename}"
                       " with real content",
                "path": str(filepath),
            })

    return json.dumps({
        "passed": not any(i["severity"] == "error" for i in issues),
        "issues": issues,
    }, indent=2)


@server.tool()
def review_sprint_post_close(sprint_id: str) -> str:
    """Validate sprint state after closing.

    Checks that sprint directory is archived, all tickets are done,
    planning docs have final status, and we're back on master.

    Args:
        sprint_id: The sprint ID (e.g., '015')

    Returns JSON with {passed, issues[]}.
    """
    issues = []

    # Check we're on master/main
    current_branch = _check_git_branch()
    if current_branch and current_branch not in ("master", "main"):
        issues.append({
            "severity": "error",
            "check": "on_main_branch",
            "message": f"On branch '{current_branch}',"
                       " expected 'master' or 'main'",
            "fix": "Run: git checkout master",
            "path": None,
        })

    # Check sprint is in done/ directory
    done_dir = _sprints_dir() / "done"
    sprint_in_done = False
    sprint_dir = None

    if done_dir.exists():
        for d in done_dir.iterdir():
            if d.is_dir() and (d / "sprint.md").exists():
                fm = read_frontmatter(d / "sprint.md")
                if fm.get("id") == sprint_id:
                    sprint_in_done = True
                    sprint_dir = d
                    break

    if not sprint_in_done:
        # Check if it's still in the active directory
        active_dir = None
        if _sprints_dir().exists():
            for d in _sprints_dir().iterdir():
                if d.is_dir() and d.name != "done" and (d / "sprint.md").exists():
                    fm = read_frontmatter(d / "sprint.md")
                    if fm.get("id") == sprint_id:
                        active_dir = d
                        break

        if active_dir:
            issues.append({
                "severity": "error",
                "check": "sprint_archived",
                "message": f"Sprint directory still in active location:"
                           f" {active_dir.name}",
                "fix": "Close the sprint using close_sprint MCP tool"
                       " to archive it",
                "path": str(active_dir),
            })
            sprint_dir = active_dir
        else:
            issues.append({
                "severity": "error",
                "check": "sprint_dir_exists",
                "message": f"Sprint '{sprint_id}' directory not found anywhere",
                "fix": "Check the sprint ID is correct",
                "path": None,
            })

    if sprint_dir:
        # Check all tickets are done
        tickets = _collect_tickets(sprint_dir)
        for t in tickets:
            if t["status"] != "done":
                issues.append({
                    "severity": "error",
                    "check": "ticket_done",
                    "message": f"Ticket #{t['id']} has status"
                               f" '{t['status']}', expected 'done'",
                    "fix": f"Set ticket #{t['id']} status to 'done'",
                    "path": t["path"],
                })
            if not t["in_done_dir"]:
                issues.append({
                    "severity": "error",
                    "check": "ticket_in_done_dir",
                    "message": f"Ticket #{t['id']} is not in tickets/done/",
                    "fix": f"Move ticket #{t['id']} to tickets/done/",
                    "path": t["path"],
                })

        # Check planning docs
        for filename in ["sprint.md", "usecases.md", "architecture-update.md"]:
            filepath = sprint_dir / filename
            if filepath.exists():
                fm = read_frontmatter(filepath)
                status = fm.get("status", "draft")
                if status == "draft":
                    issues.append({
                        "severity": "error",
                        "check": f"{filename.replace('.', '_').replace('-', '_')}"
                                 "_status",
                        "message": f"{filename} still has status 'draft'",
                        "fix": f"Update {filename} frontmatter status"
                               " from 'draft'",
                        "path": str(filepath),
                    })

    return json.dumps({
        "passed": not any(i["severity"] == "error" for i in issues),
        "issues": issues,
    }, indent=2)
