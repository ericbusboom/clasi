"""Artifact Management tools for the CLASI MCP server.

Read-write tools for creating, querying, and updating SE artifacts
(sprints, tickets, briefs, architecture, use cases).
"""

import json
import logging
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from claude_agent_skills.frontmatter import read_document, read_frontmatter
from claude_agent_skills.mcp_server import server, get_project

logger = logging.getLogger("clasi.artifact")
from claude_agent_skills.state_db import (
    PHASES as _PHASES,
    rename_sprint as _rename_sprint,
)
from claude_agent_skills.templates import (
    slugify,
    SPRINT_TEMPLATE,
    SPRINT_USECASES_TEMPLATE,
    SPRINT_ARCHITECTURE_UPDATE_TEMPLATE,
    TICKET_TEMPLATE,
    OVERVIEW_TEMPLATE,
)


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



def _is_ticket_done(ticket_ref: str) -> bool:
    """Check if a ticket (referenced as 'sprint_id-ticket_id') has status done.

    Searches both active and done ticket directories across all sprints.
    Returns True if the ticket is found with status 'done', False otherwise.
    """
    parts = ticket_ref.split("-", 1)
    if len(parts) != 2:
        return False
    sprint_id, ticket_id = parts
    try:
        sprint = get_project().get_sprint(sprint_id)
        ticket = sprint.get_ticket(ticket_id)
        return ticket.status == "done"
    except ValueError:
        return False




# --- Create tools (ticket 008) ---


def _find_latest_architecture() -> Path | None:
    """Find the most recent architecture document.

    Looks for the top-level file in docs/clasi/architecture/ (most recent
    version). Returns None if no architecture documents exist.
    """
    arch_dir = get_project().clasi_dir / "architecture"
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
    project = get_project()
    sprint = project.create_sprint(title)

    # Register sprint in state database (lazy init)
    try:
        project.db.register_sprint(
            sprint.id, sprint.slug, f"sprint/{sprint.id}-{sprint.slug}"
        )
    except Exception:
        pass  # Graceful degradation if DB fails

    files = {
        "sprint.md": str(sprint.path / "sprint.md"),
        "usecases.md": str(sprint.path / "usecases.md"),
        "architecture-update.md": str(sprint.path / "architecture-update.md"),
    }

    return json.dumps({
        "id": sprint.id,
        "path": str(sprint.path),
        "branch": f"sprint/{sprint.id}-{sprint.slug}",
        "files": files,
        "phase": "planning-docs",
    }, indent=2)


def _list_active_sprints() -> list[dict]:
    """Return all active (non-done) sprints sorted by numeric ID.

    Each entry has keys: id (int), str_id (str), dir (Path), slug (str).
    """
    project = get_project()
    results = []
    for sprint in project.list_sprints():
        # Only active (not in done/)
        if sprint.path.parent.name == "done":
            continue
        str_id = sprint.id
        try:
            num_id = int(str_id)
        except (ValueError, TypeError):
            continue
        results.append({
            "id": num_id,
            "str_id": str_id,
            "dir": sprint.path,
            "slug": sprint.slug,
        })

    return sorted(results, key=lambda s: s["id"])


def _get_sprint_phase_safe(sprint_id: str) -> str | None:
    """Get a sprint's phase from the state DB, or None if unavailable."""
    project = get_project()
    if not project.db.path.exists():
        return None
    try:
        state = project.db.get_sprint_state(sprint_id)
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
    from claude_agent_skills.artifact import Artifact

    # Rename directory
    slug = sprint_dir.name[len(old_id) + 1:] if sprint_dir.name.startswith(old_id) else sprint_dir.name
    new_dir_name = f"{new_id}-{slug}"
    new_dir = sprint_dir.parent / new_dir_name

    sprint_dir.rename(new_dir)

    # Update sprint.md frontmatter
    sprint_file = new_dir / "sprint.md"
    if sprint_file.exists():
        Artifact(sprint_file).update_frontmatter(id=new_id, branch=f"sprint/{new_id}-{slug}")

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
            artifact = Artifact(ticket_file)
            fm = artifact.frontmatter
            if fm.get("sprint_id") == old_id:
                artifact.update_frontmatter(sprint_id=new_id)

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
    project = get_project()
    try:
        project.get_sprint(after_sprint_id)
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
    for sprint in reversed(to_renumber):
        old_str_id = sprint["str_id"]
        new_num = sprint["id"] + 1
        new_str_id = f"{new_num:03d}"

        new_dir = _renumber_sprint_dir(sprint["dir"], old_str_id, new_str_id)

        # Update state database if it exists
        if project.db.path.exists():
            try:
                _rename_sprint(
                    str(project.db.path), old_str_id, new_str_id,
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
    # NOTE: Cannot use project.create_sprint() here because it auto-assigns
    # the next ID, but we need a specific ID (the insertion point).
    # TODO: Add Project.create_sprint_with_id() to support insert_sprint.
    slug = slugify(title)
    sprint_dir = project.sprints_dir / f"{new_id}-{slug}"

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
        project.db.register_sprint(new_id, slug, f"sprint/{new_id}-{slug}")
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
    project = get_project()
    if not project.db.path.exists():
        return
    try:
        state = project.db.get_sprint_state(sprint_id)
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
    project = get_project()
    sprint = project.get_sprint(sprint_id)

    # Determine todo_arg for Sprint.create_ticket (single string or None)
    todo_list: list[str] | None = None
    todo_arg: str | None = None
    if todo is not None:
        todo_list = [todo] if isinstance(todo, str) else list(todo)
        if len(todo_list) == 1:
            todo_arg = todo_list[0]

    ticket = sprint.create_ticket(title, todo=todo_arg)

    # If multiple TODOs, set the todo field to a list
    if todo_list and len(todo_list) > 1:
        ticket._artifact.update_frontmatter(todo=todo_list)

    # Update each referenced TODO file and move to in-progress
    if todo_list:
        full_ticket_id = f"{sprint_id}-{ticket.id}"
        for todo_filename in todo_list:
            try:
                todo_obj = project.get_todo(todo_filename)
            except ValueError:
                continue  # Skip missing TODOs gracefully
            todo_obj.move_to_in_progress(sprint_id, full_ticket_id)

    content = TICKET_TEMPLATE.format(id=ticket.id, title=title)

    return json.dumps({
        "id": ticket.id,
        "path": str(ticket.path),
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
    path = get_project().clasi_dir / "overview.md"
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
    for s in get_project().list_sprints(status=status):
        results.append({
            "id": s.id,
            "title": s.title,
            "status": s.status,
            "path": str(s.path),
            "branch": s.branch,
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
    project = get_project()
    results = []

    if sprint_id:
        try:
            sprints_to_scan = [project.get_sprint(sprint_id)]
        except ValueError:
            return json.dumps([], indent=2)
    else:
        sprints_to_scan = project.list_sprints()

    for sprint in sprints_to_scan:
        for ticket in sprint.list_tickets(status=status):
            if not ticket.id:
                continue
            results.append({
                "id": ticket.id,
                "title": ticket.title,
                "status": ticket.status,
                "sprint_id": sprint.id,
                "path": str(ticket.path),
            })

    return json.dumps(results, indent=2)


@server.tool()
def get_sprint_status(sprint_id: str) -> str:
    """Get a summary of a sprint's status including ticket counts.

    Args:
        sprint_id: The sprint ID (e.g., '001')

    Returns JSON with {id, title, status, branch, tickets: {todo, in_progress, done}}.
    """
    sprint = get_project().get_sprint(sprint_id)

    counts = {"todo": 0, "in_progress": 0, "done": 0}
    for ticket in sprint.list_tickets():
        if not ticket.id:
            continue
        s = ticket.status
        if s == "in-progress":
            s = "in_progress"
        if s in counts:
            counts[s] += 1

    return json.dumps({
        "id": sprint.id,
        "title": sprint.title,
        "status": sprint.status,
        "branch": sprint.branch,
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
    from claude_agent_skills.artifact import Artifact

    valid_statuses = {"todo", "in-progress", "done"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(valid_statuses))}")

    try:
        ticket_path = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"Ticket not found: {path}")

    artifact = Artifact(ticket_path)
    old_status = artifact.frontmatter.get("status", "unknown")
    artifact.update_frontmatter(status=status)

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
    from claude_agent_skills.ticket import Ticket
    from claude_agent_skills.sprint import Sprint

    try:
        ticket_path = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"Ticket not found: {path}")

    old_path = ticket_path

    # Determine the tickets_dir (go up from done/ if already there)
    tickets_dir = ticket_path.parent
    if tickets_dir.name == "done":
        tickets_dir = tickets_dir.parent
    sprint_dir = tickets_dir.parent

    # Create domain objects
    project = get_project()
    sprint = Sprint(sprint_dir, project)
    ticket = Ticket(ticket_path, sprint)

    # Move the ticket
    new_path = ticket.move_to_done()

    result: dict = {"old_path": str(old_path), "new_path": str(new_path)}

    # Also move the plan file if it exists
    plan_name = old_path.stem + "-plan.md"
    plan_path = tickets_dir / plan_name
    if plan_path.exists():
        done_dir = tickets_dir / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        new_plan_path = done_dir / plan_name
        plan_path.rename(new_plan_path)
        result["plan_old_path"] = str(plan_path)
        result["plan_new_path"] = str(new_plan_path)

    # Check if this ticket references any TODOs and trigger completion
    todo_refs = ticket.todo_ref
    if todo_refs is not None:
        todo_list = [todo_refs] if isinstance(todo_refs, str) else list(todo_refs)
        completed_todos: list[str] = []
        for todo_filename in todo_list:
            try:
                todo = project.get_todo(todo_filename)
            except ValueError:
                continue
            # Only process in-progress TODOs
            if todo.status != "in-progress":
                continue
            ref_tickets = todo.tickets
            # Check if ALL referencing tickets are done
            all_done = True
            for ref_ticket_id in ref_tickets:
                if not _is_ticket_done(ref_ticket_id):
                    all_done = False
                    break
            if all_done and ref_tickets:
                todo.move_to_done()
                completed_todos.append(todo_filename)
        if completed_todos:
            result["completed_todos"] = completed_todos

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
    from claude_agent_skills.artifact import Artifact

    try:
        ticket_path = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"Ticket not found: {path}")

    artifact = Artifact(ticket_path)
    old_status = artifact.frontmatter.get("status", "unknown")

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
        result: dict = {"old_path": str(ticket_path), "new_path": str(new_path)}
        if plan_path.exists():
            new_plan_path = tickets_dir / plan_name
            plan_path.rename(new_plan_path)
            result["plan_old_path"] = str(plan_path)
            result["plan_new_path"] = str(new_plan_path)

        # Update frontmatter on the moved file
        Artifact(new_path).update_frontmatter(status="todo")
    else:
        # Ticket exists but not in done/ — just reset status
        new_path = ticket_path
        artifact.update_frontmatter(status="todo")
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
    from claude_agent_skills.todo import Todo

    project = get_project()
    sprint = project.get_sprint(sprint_id)
    sprint_dir = sprint.path

    # Update sprint status to done
    sprint.sprint_doc.update_frontmatter(status="done")

    # Check in-progress TODOs — they should already be resolved individually
    unresolved_todos: list[str] = []
    todo_directory = project.todo_dir
    in_progress_todo_dir = todo_directory / "in-progress"
    if in_progress_todo_dir.exists():
        for todo_file in sorted(in_progress_todo_dir.glob("*.md")):
            todo = Todo(todo_file, project)
            if todo.sprint == sprint_id:
                if todo.status in ("done", "complete", "completed"):
                    # Self-repair: move to done/
                    todo.move_to_done()
                else:
                    unresolved_todos.append(todo_file.name)

    # Also check legacy pending TODOs tagged with this sprint
    moved_todos: list[str] = []
    if todo_directory.exists():
        for todo_file in sorted(todo_directory.glob("*.md")):
            todo = Todo(todo_file, project)
            if todo.sprint == sprint_id:
                if todo.status in ("done", "complete", "completed"):
                    todo.move_to_done()
                    moved_todos.append(todo_file.name)

    # Copy architecture-update to the architecture directory
    arch_update = sprint_dir / "architecture-update.md"
    if arch_update.exists():
        arch_dir = project.clasi_dir / "architecture"
        arch_dir.mkdir(parents=True, exist_ok=True)
        dest = arch_dir / f"architecture-update-{sprint_id}.md"
        shutil.copy2(str(arch_update), str(dest))

    # Move to done directory
    done_dir = project.sprints_dir / "done"
    done_dir.mkdir(parents=True, exist_ok=True)
    new_path = done_dir / sprint_dir.name

    if new_path.exists():
        raise ValueError(f"Destination already exists: {new_path}")

    shutil.move(str(sprint_dir), str(new_path))

    # Update state database: advance to done and release lock
    db = project.db
    if db.path.exists():
        try:
            state = db.get_sprint_state(sprint_id)
            from claude_agent_skills.state_db import PHASES
            phase_idx = PHASES.index(state["phase"])
            done_idx = PHASES.index("done")
            while phase_idx < done_idx:
                db.advance_phase(sprint_id)
                phase_idx += 1
            if state["lock"]:
                db.release_lock(sprint_id)
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
            detected = detect_version_file(project.root)
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
    if unresolved_todos:
        result["unresolved_todos"] = unresolved_todos
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
    from claude_agent_skills.sprint import Sprint
    from claude_agent_skills.ticket import Ticket
    from claude_agent_skills.todo import Todo

    project = get_project()
    db = project.db
    completed_steps: list[str] = []
    repairs: list[str] = []

    # ── Step 1: Pre-condition verification with self-repair ──

    # 1a. Check tickets — all should be in tickets/done/ with status done
    try:
        sprint = project.get_sprint(sprint_id)
        sprint_dir = sprint.path
    except ValueError:
        # Sprint dir might already be archived (idempotent retry)
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
            ticket = Ticket(ticket_file, sprint)
            if ticket.status == "done":
                # Self-repair: move to done/
                ticket.move_to_done()
                # Also move plan file if exists
                plan_file = ticket_file.with_suffix("").with_name(ticket_file.stem + "-plan.md")
                if plan_file.exists():
                    done_tickets_dir.mkdir(parents=True, exist_ok=True)
                    plan_file.rename(done_tickets_dir / plan_file.name)
                repairs.append(f"moved ticket {ticket.id or ticket_file.stem} to done/")
            else:
                # Ticket not done — unrepairable
                error_msg = f"Ticket {ticket.id or ticket_file.stem} has status '{ticket.status}', not 'done'"
                if db.path.exists():
                    db.write_recovery_state(
                        sprint_id, "precondition",
                        [str(ticket_file)], error_msg,
                    )
                return json.dumps({
                    "status": "error",
                    "error": {
                        "step": "precondition",
                        "message": error_msg,
                        "recovery": {
                            "recorded": db.path.exists(),
                            "allowed_paths": [str(ticket_file)],
                            "instruction": f"Complete ticket {ticket.id or ticket_file.stem} and set status to 'done', then call close_sprint again.",
                        },
                    },
                    "completed_steps": [],
                    "remaining_steps": ["precondition", "tests", "archive", "db_update", "version_bump", "merge", "push_tags", "delete_branch"],
                }, indent=2)

    # 1b. Check TODOs — in-progress TODOs for this sprint must be resolved
    todo_directory = project.todo_dir
    in_progress_todo_dir = todo_directory / "in-progress"
    if in_progress_todo_dir.exists():
        for todo_file in sorted(in_progress_todo_dir.glob("*.md")):
            todo = Todo(todo_file, project)
            if todo.sprint == sprint_id:
                if todo.status in ("done", "complete", "completed"):
                    # Self-repair: move to done/
                    todo.move_to_done()
                    repairs.append(f"moved TODO {todo_file.name} to done/")
                else:
                    # TODO still in-progress — unrepairable
                    error_msg = f"TODO {todo_file.name} is still in-progress for sprint {sprint_id}"
                    if db.path.exists():
                        db.write_recovery_state(
                            sprint_id, "precondition",
                            [str(todo_file)], error_msg,
                        )
                    return json.dumps({
                        "status": "error",
                        "error": {
                            "step": "precondition",
                            "message": error_msg,
                            "recovery": {
                                "recorded": db.path.exists(),
                                "allowed_paths": [str(todo_file)],
                                "instruction": f"Complete all tickets referencing {todo_file.name}, then call close_sprint again.",
                            },
                        },
                        "completed_steps": [],
                        "remaining_steps": ["precondition", "tests", "archive", "db_update", "version_bump", "merge", "push_tags", "delete_branch"],
                    }, indent=2)
    # Also check pending TODOs in todo/ that are tagged with this sprint (legacy)
    if todo_directory.exists():
        for todo_file in sorted(todo_directory.glob("*.md")):
            todo = Todo(todo_file, project)
            if todo.sprint == sprint_id:
                if todo.status in ("done", "complete", "completed"):
                    # Self-repair: move to done/
                    todo.move_to_done()
                    repairs.append(f"moved TODO {todo_file.name} to done/")

    # 1c. Check state DB phase — self-repair: advance if behind
    if db.path.exists():
        try:
            state = db.get_sprint_state(sprint_id)
            phase = state["phase"]
            if phase != "done":
                phase_idx = _PHASES.index(phase)
                # We need to be at least in 'closing' before we proceed
                closing_idx = _PHASES.index("closing")
                while phase_idx < closing_idx:
                    try:
                        db.advance_phase(sprint_id)
                        phase_idx += 1
                        repairs.append(f"advanced DB phase to '{_PHASES[phase_idx]}'")
                    except ValueError:
                        # Can't advance further (missing gate, etc.) — skip
                        break
        except ValueError:
            pass  # Sprint not in DB — skip DB checks

    # 1d. Check execution lock — self-repair: re-acquire if not held
    if db.path.exists():
        try:
            state = db.get_sprint_state(sprint_id)
            if not state["lock"]:
                try:
                    db.acquire_lock(sprint_id)
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
            if db.path.exists():
                db.write_recovery_state(
                    sprint_id, "tests", [], error_msg,
                )
            return json.dumps({
                "status": "error",
                "error": {
                    "step": "tests",
                    "message": error_msg,
                    "output": test_output.strip(),
                    "recovery": {
                        "recorded": db.path.exists(),
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
        if db.path.exists():
            db.write_recovery_state(sprint_id, "tests", [], error_msg)
        return json.dumps({
            "status": "error",
            "error": {
                "step": "tests",
                "message": error_msg,
                "recovery": {
                    "recorded": db.path.exists(),
                    "allowed_paths": [],
                    "instruction": "Investigate slow tests, then call close_sprint again.",
                },
            },
            "completed_steps": completed_steps,
            "remaining_steps": [s for s in all_steps if s not in completed_steps],
        }, indent=2)

    completed_steps.append("tests")

    # ── Step 3: Archive sprint directory ──
    done_dir = project.sprints_dir / "done"
    already_archived = sprint_dir.parent.name == "done"

    if already_archived:
        new_path = sprint_dir
        old_path_str = str(new_path)
    else:
        # Update sprint status to done
        sprint.sprint_doc.update_frontmatter(status="done")

        # NOTE: TODOs are not bulk-moved at sprint close.
        # They are moved individually by move_ticket_to_done when all
        # referencing tickets are done. The precondition check (step 1b)
        # already verified that no in-progress TODOs remain for this sprint.

        # Copy architecture-update
        arch_update = sprint_dir / "architecture-update.md"
        if arch_update.exists():
            arch_dir = project.clasi_dir / "architecture"
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

    completed_steps.append("archive")

    # ── Step 4: Update state DB ──
    if db.path.exists():
        try:
            state = db.get_sprint_state(sprint_id)
            if state["phase"] != "done":
                phase_idx = _PHASES.index(state["phase"])
                done_idx = _PHASES.index("done")
                while phase_idx < done_idx:
                    try:
                        db.advance_phase(sprint_id)
                    except ValueError:
                        break
                    phase_idx += 1
            if state["lock"]:
                try:
                    db.release_lock(sprint_id)
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
            detected = detect_version_file(project.root)
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
                if db.path.exists():
                    db.write_recovery_state(sprint_id, "merge", [], error_msg)
                return json.dumps({
                    "status": "error",
                    "error": {
                        "step": "merge",
                        "message": error_msg,
                        "recovery": {
                            "recorded": db.path.exists(),
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
                if db.path.exists():
                    db.write_recovery_state(sprint_id, "merge", conflicted, error_msg)
                return json.dumps({
                    "status": "error",
                    "error": {
                        "step": "merge",
                        "message": error_msg,
                        "recovery": {
                            "recorded": db.path.exists(),
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
    if db.path.exists():
        try:
            db.clear_recovery_state()
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
    project = get_project()
    if not project.db.path.exists():
        return json.dumps({"cleared": False, "reason": "No state database found"}, indent=2)
    result = project.db.clear_recovery_state()
    return json.dumps(result, indent=2)


# --- State management tools (ticket 005) ---



@server.tool()
def get_sprint_phase(sprint_id: str) -> str:
    """Get a sprint's current lifecycle phase and gate status.

    Args:
        sprint_id: The sprint ID (e.g., '002')

    Returns JSON with {id, phase, gates, lock}.
    """
    try:
        state = get_project().db.get_sprint_state(sprint_id)
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
        sprint = get_project().get_sprint(sprint_id)
        result = sprint.advance_phase()
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
        sprint = get_project().get_sprint(sprint_id)
        gate_result = sprint.record_gate(gate, result, notes)
        return json.dumps(gate_result, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


@server.tool()
def acquire_execution_lock(sprint_id: str) -> str:
    """Acquire the execution lock for a sprint and create the sprint branch.

    Only one sprint can hold the lock at a time. Prevents concurrent
    sprint execution in the same repository.

    Late branching: the sprint branch (``sprint/NNN-slug``) is created
    here, not during planning. All planning (roadmap and detail phases)
    happens on main. The branch is only created when execution begins.

    If the lock is re-entrant (already held by this sprint), the branch
    is assumed to already exist and is not re-created.

    Args:
        sprint_id: The sprint ID

    Returns JSON with {sprint_id, acquired_at, reentrant, branch}.
    """
    try:
        project = get_project()
        sprint = project.get_sprint(sprint_id)
        lock = sprint.acquire_lock()

        # Late branching: create the sprint branch when acquiring
        # the execution lock (not during planning).
        if not lock.get("reentrant"):
            state = project.db.get_sprint_state(sprint_id)
            slug = state.get("slug", "")
            branch_name = f"sprint/{sprint_id}-{slug}" if slug else f"sprint/{sprint_id}"
            branch_result = subprocess.run(
                ["git", "checkout", "-b", branch_name],
                capture_output=True,
                text=True,
            )
            if branch_result.returncode != 0:
                # Branch may already exist -- try checking it out
                branch_result = subprocess.run(
                    ["git", "checkout", branch_name],
                    capture_output=True,
                    text=True,
                )
                if branch_result.returncode != 0:
                    return json.dumps({
                        "error": (
                            f"Failed to create/checkout branch "
                            f"'{branch_name}': "
                            f"{branch_result.stderr.strip()}"
                        ),
                        "lock": lock,
                    }, indent=2)
            lock["branch"] = branch_name
        else:
            # Re-entrant: look up existing branch
            state = project.db.get_sprint_state(sprint_id)
            lock["branch"] = state.get("branch", "")

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
        sprint = get_project().get_sprint(sprint_id)
        result = sprint.release_lock()
        return json.dumps(result, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


# --- TODO management tools ---



@server.tool()
def list_todos() -> str:
    """List all active TODO files with sprint/ticket linkage.

    Scans docs/clasi/todo/*.md (pending) and docs/clasi/todo/in-progress/*.md.
    Excludes the done/ subdirectory.

    Returns JSON array of {filename, title, status, sprint, tickets}.
    The sprint and tickets fields are present only for in-progress TODOs.
    """
    project = get_project()
    results = []

    for todo in project.list_todos():
        entry: dict = {"filename": todo.path.name, "title": todo.title}
        entry["status"] = todo.status
        if todo.status == "in-progress":
            if todo.sprint:
                entry["sprint"] = todo.sprint
            if todo.tickets:
                entry["tickets"] = todo.tickets
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
    project = get_project()
    try:
        todo = project.get_todo(filename)
    except ValueError:
        raise ValueError(f"TODO not found: {filename}")
    old_path = todo.path

    # Write traceability frontmatter before moving
    if sprint_id is not None:
        todo._artifact.update_frontmatter(sprint=sprint_id)
    if ticket_ids is not None:
        todo._artifact.update_frontmatter(tickets=ticket_ids)

    todo.move_to_done()

    return json.dumps({
        "old_path": str(old_path),
        "new_path": str(todo.path),
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
    from claude_agent_skills.artifact import Artifact

    try:
        resolved = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"File not found: {path}")

    fm = Artifact(resolved).frontmatter
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
    from claude_agent_skills.artifact import Artifact

    try:
        resolved = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"File not found: {path}")

    try:
        update_dict = json.loads(updates)
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"Invalid JSON for updates: {e}")

    Artifact(resolved).update_frontmatter(**update_dict)

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
    detected = detect_version_file(get_project().root)
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
    from claude_agent_skills.sprint import Sprint

    sprint = Sprint(sprint_dir, get_project())
    tickets = []
    for ticket in sprint.list_tickets():
        if not ticket.id:
            continue
        tickets.append({
            "id": ticket.id,
            "title": ticket.title,
            "status": ticket.status,
            "path": str(ticket.path),
            "in_done_dir": ticket.path.parent.name == "done",
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

    # Find sprint
    try:
        sprint = get_project().get_sprint(sprint_id)
        sprint_dir = sprint.path
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

    expected_branch = sprint.branch or f"sprint/{sprint_id}"

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
        sprint = get_project().get_sprint(sprint_id)
        sprint_dir = sprint.path
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

    expected_branch = sprint.branch or f"sprint/{sprint_id}"

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
    project = get_project()
    sprint_in_done = False
    sprint_dir = None

    try:
        sprint = project.get_sprint(sprint_id)
        sprint_dir = sprint.path
        sprint_in_done = sprint_dir.parent.name == "done"
    except ValueError:
        sprint_dir = None

    if sprint_dir and not sprint_in_done:
        issues.append({
            "severity": "error",
            "check": "sprint_archived",
            "message": f"Sprint directory still in active location:"
                       f" {sprint_dir.name}",
            "fix": "Close the sprint using close_sprint MCP tool"
                   " to archive it",
            "path": str(sprint_dir),
        })
    elif sprint_dir is None:
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
