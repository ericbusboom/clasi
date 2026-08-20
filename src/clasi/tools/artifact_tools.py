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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from clasi.artifact import Artifact
from clasi.frontmatter import read_document, read_frontmatter
from clasi.mcp_server import server, get_project
from clasi.project import (
    Project,
    SprintNotFoundError,
    SprintFrontmatterError,
    SprintIdMismatchError,
    _load_config,
)
from clasi.sprint import MergeConflictError, Sprint
from clasi.state_db import (
    PHASES as _PHASES,
    rename_sprint as _rename_sprint,
)
from clasi.templates import (
    slugify,
    SPRINT_TEMPLATE,
    TICKET_TEMPLATE,
)
from clasi.ticket import Ticket
from clasi.issue import Issue
from clasi.versioning import (
    compute_next_version,
    create_version_tag,
    detect_version_file,
    load_version_trigger,
    should_version,
    update_version_file,
)

logger = logging.getLogger("clasi.artifact")


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


def _any_ticket_suppresses_issue(ticket_refs: list[str], issue_filename: str) -> bool:
    """Return True if any referencing ticket has completes_issue: false for the given issue.

    Iterates over all ticket references (as 'sprint_id-ticket_id' strings) and
    calls ``Ticket.completes_issue_for(issue_filename)`` on each one that can be
    loaded.  If any ticket returns ``False``, archival should be suppressed.

    Returns False (do not suppress) if no tickets can be loaded or all return True.
    """
    for ticket_ref in ticket_refs:
        parts = ticket_ref.split("-", 1)
        if len(parts) != 2:
            continue
        sprint_id, ticket_id = parts
        try:
            sprint = get_project().get_sprint(sprint_id)
            ticket = sprint.get_ticket(ticket_id)
        except ValueError:
            continue
        if not ticket.completes_issue_for(issue_filename):
            return True
    return False


def _issue_is_deferred(sprint: Sprint, issue_filename: str) -> bool:
    """Return True if an issue is intentionally deferred by a ticket in this sprint.

    An issue is considered deferred when at least one ticket in ``sprint`` that
    lists ``issue_filename`` in its ``issue`` frontmatter field has
    ``completes_issue: false`` for that filename.

    This is used by the close_sprint precondition check: if every ticket that
    references the issue has ``completes_issue: true`` (or absent), the issue
    should have been archived and its in-progress state is an error.  But if
    any ticket deliberately set ``completes_issue: false``, the issue is expected
    to remain in-progress for future sprints, and the precondition should allow
    the sprint to close.

    Returns False (not deferred) if no tickets in the sprint reference the issue,
    or if all referencing tickets have ``completes_issue: true`` (default).
    """
    for location in [sprint.tickets_dir, sprint.tickets_done_dir]:
        if not location.exists():
            continue
        for ticket_file in sorted(location.glob("*.md")):
            ticket = Ticket(ticket_file, sprint)
            issue_ref = ticket.issue_ref
            if issue_ref is None:
                continue
            linked = [issue_ref] if isinstance(issue_ref, str) else list(issue_ref)
            if issue_filename not in linked:
                continue
            if not ticket.completes_issue_for(issue_filename):
                return True
    return False


def _sweep_done_issues(sprint: Sprint) -> list[str]:
    """Sweep sprint issues and complete any whose tickets are all done.

    Scans two sources for in-progress issues assigned to this sprint:
    1. Sprint-scoped issues in ``<sprint>/issues/*.md``.
    2. Pending-pool issues in ``project.issues_dir/*.md`` with
       ``issue.sprint == sprint.id``.

    For each in-progress issue, if all entries in ``issue.tickets`` are done
    (via ``_is_ticket_done``) and the list is non-empty, and no ticket
    suppresses completion (via ``_any_ticket_suppresses_todo``), the issue
    is moved to done.

    Pending-pool issues are physically relocated to
    ``<sprint>/issues/done/<filename>`` before ``move_to_done()`` is called,
    so they end up in the sprint directory rather than the pool's done/.

    Returns the list of issue filenames that were completed.
    """
    project = get_project()
    completed: list[str] = []

    def _try_complete(issue, filename: str) -> bool:
        """Return True if issue was completed."""
        if issue.status != "in-progress":
            return False
        ref_tickets = issue.tickets
        if not ref_tickets:
            return False
        all_done = all(_is_ticket_done(t) for t in ref_tickets)
        if not all_done:
            return False
        if _any_ticket_suppresses_issue(ref_tickets, filename):
            return False
        return True

    # Source 1: sprint-scoped issues in <sprint>/issues/*.md
    sprint_issues_dir = sprint.path / "issues"
    if sprint_issues_dir.exists():
        for issue_file in sorted(sprint_issues_dir.glob("*.md")):
            from clasi.issue import Issue as _Issue
            issue = _Issue(issue_file, project)
            if issue.sprint != sprint.id:
                continue
            if _try_complete(issue, issue_file.name):
                issue.move_to_done()
                completed.append(issue_file.name)

    # Source 2: pending-pool issues tagged with this sprint
    pending_pool = project.issues_dir
    if pending_pool.exists():
        for issue_file in sorted(pending_pool.glob("*.md")):
            from clasi.issue import Issue as _Issue
            issue = _Issue(issue_file, project)
            if issue.sprint != sprint.id:
                continue
            if _try_complete(issue, issue_file.name):
                # Relocate to <sprint>/issues/done/ before calling move_to_done
                target_dir = sprint.path / "issues" / "done"
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / issue_file.name
                issue_file.rename(target_path)
                from clasi.artifact import Artifact as _Artifact
                issue._artifact = _Artifact(target_path)
                # File is already in done/; move_to_done() just updates frontmatter
                issue.move_to_done()
                completed.append(issue_file.name)

    return completed


# --- Create tools (ticket 008) ---


@server.tool()
def create_sprint(title: str) -> str:
    """Create a new sprint directory with a template sprint.md.

    Auto-assigns the next sprint number and writes only sprint.md
    (roadmap phase). Under the single-doc model, use cases and
    architecture are sections within sprint.md rather than separate
    files — they get filled in when the sprint is detail-promoted, not
    scaffolded here. The full architecture history lives in
    ``docs/clasi/architecture/`` and is consolidated on demand.

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

    return json.dumps(sprint.to_dict(), indent=2)


@server.tool()
def detail_sprint(sprint_id: str) -> str:
    """Promote a roadmap sprint to detail planning.

    Creates tickets/ and tickets/done/ for the given sprint and advances
    the state DB phase from roadmap to planning-docs. Use cases and
    architecture are filled in as sections of the sprint's existing
    sprint.md, not scaffolded as separate files.

    Args:
        sprint_id: The sprint ID (e.g., '017')

    Returns JSON with {sprint_id, phase, files_written}.
    """
    try:
        project = get_project()
        sprint = project.get_sprint(sprint_id)
        result = sprint.detail_promote()
        return json.dumps(result)
    except (ValueError, FileNotFoundError) as e:
        return json.dumps({"error": str(e)})


def _resolve_overlay_doc_path(project: Project, doc_name: str) -> Path:
    """Resolve a *doc_names* entry to an absolute canonical design-doc path.

    Two accepted forms:

    - A bare filename with no path separators (e.g. ``"design.md"``,
      ``"clasi-tools.md"``) is resolved relative to ``project.design_dir``
      (``docs/design/`` by default) — the system doc / legacy pre-co-location
      form.
    - A path containing a separator (e.g. ``"src/firm/app/DESIGN.md"``) is
      resolved relative to ``project.root`` directly — a co-located
      subsystem's canonical source path, reachable with no ``../../``
      escape.
    """
    if "/" in doc_name or "\\" in doc_name:
        return (project.root / doc_name).resolve()
    return (project.design_dir / doc_name).resolve()


def _derive_overlay_slug(project: Project, canonical_path: Path) -> str:
    """Derive a unique, stable, reversible overlay filename for *canonical_path*.

    The sprint ``design/`` overlay directory is flat, but the co-located
    design-doc model (sprint 022) names every subsystem's canonical doc
    ``DESIGN.md`` — so two co-located docs seeded in the same call would
    collide on a bare basename. This function derives a per-doc slug that
    keeps the directory flat while staying unique across subsystems.

    **Transform**: if *canonical_path* is located under one of
    ``project.sources`` (the configured source-tree roots), the slug is
    the path's components relative to that source root, with all but the
    final component joined by ``-`` and the final ``DESIGN.md``/``design.md``
    filename kept verbatim, e.g. ``src/firm/app/DESIGN.md`` under source
    root ``src`` becomes ``firm-app-DESIGN.md``. If *canonical_path* is not
    under any configured source root (e.g. the system-level doc at
    ``docs/design/design.md``), the slug is just the basename, unchanged
    (e.g. ``design.md``) — already unique since only one system doc exists.

    This transform is stable and reversible in the sense that matters here:
    it does not need to round-trip back to the canonical path on its own
    (the ``_sources.json`` manifest carries the true canonical path for
    that), but re-seeding the same canonical doc always reproduces the same
    slug, so a re-seed overwrites its own prior copy rather than
    accumulating a duplicate under a different name.
    """
    resolved = canonical_path.resolve()
    for source_root in project.sources:
        try:
            rel = resolved.relative_to(source_root)
        except ValueError:
            continue
        parts = rel.parts
        if len(parts) <= 1:
            return rel.name
        return "-".join(parts[:-1]) + "-" + parts[-1]
    return resolved.name


@server.tool()
def seed_sprint_design_overlay(sprint_id: str, doc_names: Optional[list] = None) -> str:
    """Seed and commit pristine copies of canonical design docs into a sprint's overlay.

    Gated on the doc-set opt-in flag (``Project.design_docs_opt_in``); a
    no-op when opt-in is unset or off, or when *doc_names* is empty/omitted
    (no design/ directory is created and no commit is made). Otherwise
    copies each named canonical doc verbatim into the sprint's ``design/``
    directory, under a derived overlay slug (see below), and commits them
    in a single commit, before any sprint-planner edits land (SUC-005).

    Called by the sprint-planner once it has identified which canonical
    docs the sprint's changes affect (Phase 2 planning) — not necessarily
    at ``create_sprint`` time, since the affected doc list is not known
    that early. Runs on ``main``, before ``acquire_execution_lock`` branches
    the sprint off of it (see sprint.md Open Question 3's resolution), so
    the sprint branch, once created, already contains this commit.

    Args:
        sprint_id: The sprint ID (e.g., '021').
        doc_names: Canonical design doc paths to seed. Two forms are
            accepted per entry: a bare filename with no path separator
            (e.g. ``"design.md"``, ``"clasi-tools.md"``), resolved relative
            to ``docs/design/`` (the system doc / legacy form); or a
            co-located canonical source path (e.g.
            ``"src/firm/app/DESIGN.md"``), resolved relative to the repo
            root — no ``../../`` escape required. Omit (or pass
            "NONE"/empty) to no-op.

    Each doc is written into the overlay under a derived slug rather than
    its bare basename, so co-located docs that share the ``DESIGN.md``
    basename do not collide: the slug is the doc's path components
    relative to its nearest enclosing ``project.sources`` root, joined
    with ``-``, keeping the final filename (e.g. ``src/firm/app/DESIGN.md``
    under source root ``src`` becomes ``firm-app-DESIGN.md``); a doc with
    no enclosing source root (the system doc) keeps its bare basename
    (e.g. ``design.md``) unchanged. See
    :func:`_derive_overlay_slug` for the full transform. The
    ``_sources.json`` manifest is keyed by this same slug, not the
    canonical basename.

    Returns JSON with {sprint_id, opted_in, seeded: [str, ...]}.
    """
    project = get_project()
    opted_in = bool(project.design_docs_opt_in)
    if not opted_in or not doc_names:
        return json.dumps({
            "sprint_id": sprint_id,
            "opted_in": opted_in,
            "seeded": [],
        }, indent=2)

    from clasi.design.overlay import seed_and_commit

    sprint = project.get_sprint(sprint_id)
    canonical_paths = [_resolve_overlay_doc_path(project, name) for name in doc_names]
    slugs = [_derive_overlay_slug(project, p) for p in canonical_paths]
    seeded = seed_and_commit(
        canonical_paths,
        sprint.design_dir,
        repo_root=project.root,
        slugs=slugs,
        commit_message=f"chore: seed sprint {sprint_id} design overlay",
    )
    return json.dumps({
        "sprint_id": sprint_id,
        "opted_in": True,
        "seeded": [str(p) for p in seeded],
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
        Artifact(sprint_file).update_frontmatter(id=new_id, branch=f"sprint/{new_id}-{slug}")

        # Update body references: "Sprint NNN" -> "Sprint MMM"
        content = sprint_file.read_text(encoding="utf-8")
        content = content.replace(f"Sprint {old_id}", f"Sprint {new_id}")
        sprint_file.write_text(content, encoding="utf-8")

    # Update body references in architecture.md (unrelated pre-existing
    # entry, not written by Sprint, left untouched by this change)
    for doc_name in ("architecture.md",):
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

    # Check that all sprints to renumber are in a pre-planning phase
    _renameable_phases = {"roadmap", "planning-docs"}
    for sprint in to_renumber:
        phase = _get_sprint_phase_safe(sprint["str_id"])
        if phase is not None and phase not in _renameable_phases:
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
    _new_sprint = Sprint(sprint_dir, project)
    _new_sprint.tickets_dir.mkdir()
    _new_sprint.tickets_done_dir.mkdir()

    fmt = {"id": new_id, "title": title, "slug": slug}
    files = {}
    for name, path, template in [
        ("sprint.md", _new_sprint.sprint_md, SPRINT_TEMPLATE),
    ]:
        path.write_text(template.format(**fmt), encoding="utf-8")
        files[name] = str(path)

    # Register in state database
    try:
        project.db.register_sprint(new_id, slug, f"sprint/{new_id}-{slug}")
    except Exception:
        pass  # Graceful degradation

    result = _new_sprint.to_dict()
    result["renumbered"] = renumbered
    return json.dumps(result, indent=2)


@server.tool()
def link_sprint_issues(sprint_id: str, issue_filenames: list[str]) -> str:
    """Establish bidirectional sprint↔issue links during the roadmap phase.

    For each issue filename provided, writes ``sprint: <sprint_id>`` to the
    issue's frontmatter and ensures the sprint's ``sprint.md`` frontmatter has
    an ``issues:`` list that includes the filename.  The operation is
    idempotent: calling it again with the same arguments produces no change.

    Args:
        sprint_id: The sprint ID (e.g., '017').
        issue_filenames: List of issue filenames (e.g., ['my-feature.md']).

    Returns JSON with {sprint_id, linked, already_linked, not_found}.
    """
    project = get_project()

    try:
        sprint = project.get_sprint(sprint_id)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    linked: list[str] = []
    already_linked: list[str] = []
    not_found: list[str] = []

    for filename in issue_filenames:
        try:
            issue = project.get_issue(filename)
        except ValueError:
            not_found.append(filename)
            continue

        if issue.sprint == sprint_id:
            already_linked.append(filename)
            continue

        issue._artifact.update_frontmatter(sprint=sprint_id)
        linked.append(filename)

    # Update sprint.md issues: list — merge linked filenames (no duplicates)
    sprint_artifact = sprint.sprint_doc
    current_issues = sprint_artifact.frontmatter.get("issues", [])
    if isinstance(current_issues, str):
        current_issues = [current_issues] if current_issues else []
    else:
        current_issues = list(current_issues) if current_issues else []

    # Add newly linked filenames that aren't already in the list
    newly_to_add = [f for f in linked if f not in current_issues]
    if newly_to_add:
        merged = current_issues + newly_to_add
        sprint_artifact.update_frontmatter(issues=merged)

    return json.dumps(
        {
            "sprint_id": sprint_id,
            "linked": linked,
            "already_linked": already_linked,
            "not_found": not_found,
        },
        indent=2,
    )


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
    issue: str | list[str] | None = None,
) -> str:
    """Create a new ticket in a sprint's tickets/ directory.

    Auto-assigns the next ticket number within the sprint.
    Checks sprint phase if the state database exists.

    When ``issue`` is provided (a filename or list of filenames), the
    ticket's frontmatter ``issue`` field is set and the referenced issue
    files are updated with ``status: in-progress``, the sprint ID, and
    the ticket ID.

    When ``issue`` is omitted, the ticket is auto-linked to the sprint's
    issue **only if the sprint has exactly one linked issue** — that is
    the unambiguous case where "the sprint's issue" is a sensible default
    for "this ticket's issue". If the sprint has more than one linked
    issue, no auto-link is applied: the ticket's ``issue:`` frontmatter
    is left empty and no issue's ``tickets:`` backlink is touched. Callers
    working a multi-issue sprint must pass ``issue=`` explicitly per
    ticket (or attach one later with ``add_issue_ref``).

    Args:
        sprint_id: The sprint ID (e.g., '001')
        title: The ticket title
        issue: Optional issue filename or list of filenames that this
               ticket addresses (e.g., 'my-idea.md' or
               ['idea-a.md', 'idea-b.md'])
    """
    _check_sprint_phase_for_ticketing(sprint_id)
    project = get_project()
    sprint = project.get_sprint(sprint_id)

    # Auto-link to the sprint's issue only in the unambiguous single-issue
    # case. With 2+ linked issues, "the sprint's issues" is not a sensible
    # default for "this ticket's issue" — leave issue: empty rather than
    # silently linking every issue to every ticket.
    if issue is None:
        sprint_issues = (
            sprint.sprint_doc.frontmatter.get("issues")
            or sprint.sprint_doc.frontmatter.get("todos")
        )
        if (
            sprint_issues
            and isinstance(sprint_issues, list)
            and len(sprint_issues) == 1
        ):
            issue = sprint_issues

    # Determine issue_arg for Sprint.create_ticket (single string or None)
    issue_list: list[str] | None = None
    issue_arg: str | None = None
    if issue is not None:
        issue_list = [issue] if isinstance(issue, str) else list(issue)
        if len(issue_list) == 1:
            issue_arg = issue_list[0]

    ticket = sprint.create_ticket(title, issue=issue_arg)

    # If multiple issues, set the issue field to a list
    if issue_list and len(issue_list) > 1:
        ticket._artifact.update_frontmatter(issue=issue_list)

    # Update each referenced issue file and move to in-progress
    if issue_list:
        full_ticket_id = f"{sprint_id}-{ticket.id}"
        for issue_filename in issue_list:
            try:
                issue_obj = project.get_issue(issue_filename)
            except ValueError:
                continue  # Skip missing issues gracefully
            issue_obj.move_to_in_progress(sprint_id, full_ticket_id)

    result = ticket.to_dict()
    result["template_content"] = TICKET_TEMPLATE.format(id=ticket.id, title=title)
    return json.dumps(result, indent=2)


@server.tool()
def add_issue_ref(ticket_path: str, issue_filename: str) -> str:
    """Add a bidirectional link between a ticket and an issue post-creation.

    Idempotent: if the link already exists, returns current state without error.

    The ticket's ``issue:`` frontmatter field is updated (absent/empty → string;
    string → list; list → append). The issue's ``tickets:`` frontmatter is
    updated via ``Issue.add_ticket_ref`` (already idempotent).

    Args:
        ticket_path: Path to the ticket file (absolute or sprint-relative).
        issue_filename: Filename of the issue (e.g., 'my-idea.md').

    Returns JSON with {ticket_path, issue_filename, ticket_issue_refs, issue_ticket_refs}.
    """
    try:
        resolved_path = resolve_artifact_path(ticket_path)
    except FileNotFoundError:
        raise ValueError(f"Ticket not found: {ticket_path}")

    # Derive sprint directory from ticket path (handles tickets/done/ too)
    tickets_dir = resolved_path.parent
    if tickets_dir.name == "done":
        tickets_dir = tickets_dir.parent
    sprint_dir = tickets_dir.parent

    project = get_project()
    sprint = Sprint(sprint_dir, project)
    ticket = Ticket(resolved_path, sprint)

    # Build the full ticket ID: "<sprint_id>-<ticket.id>"
    full_ticket_id = f"{sprint.id}-{ticket.id}"

    # Read current issue: field and handle all three cases
    current_issue = ticket._artifact.frontmatter.get("issue", "")
    if not current_issue:
        # absent or empty — set to single filename
        new_issue_value: str | list[str] = issue_filename
    elif isinstance(current_issue, str):
        if current_issue == issue_filename:
            # already present — idempotent, no change
            new_issue_value = current_issue
        else:
            new_issue_value = [current_issue, issue_filename]
    else:
        # list
        issue_list = list(current_issue)
        if issue_filename in issue_list:
            # already present — idempotent, no change
            new_issue_value = issue_list
        else:
            issue_list.append(issue_filename)
            new_issue_value = issue_list

    # Only write if something changed
    if new_issue_value != current_issue:
        ticket._artifact.update_frontmatter(issue=new_issue_value)

    # Write the reverse link on the issue
    issue_obj = project.get_issue(issue_filename)
    issue_obj.add_ticket_ref(full_ticket_id)

    # Re-read updated ticket issue refs
    updated_issue_refs = ticket._artifact.frontmatter.get("issue", "")

    return json.dumps({
        "ticket_path": str(resolved_path),
        "issue_filename": issue_filename,
        "ticket_issue_refs": updated_issue_refs,
        "issue_ticket_refs": issue_obj.tickets,
    }, indent=2)


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
        status: Optional status filter (open, in-progress, done)

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

    Returns JSON with {id, title, status, branch, worktree,
    tickets: {open, in_progress, done}}.
    """
    sprint = get_project().get_sprint(sprint_id)

    return json.dumps({
        "id": sprint.id,
        "title": sprint.title,
        "status": sprint.status,
        "branch": sprint.branch,
        "worktree": sprint.worktree,
        "tickets": sprint.ticket_counts(),
    }, indent=2)


# --- Update tools (ticket 010) ---


@server.tool()
def update_ticket_status(path: str, status: str) -> str:
    """Update a ticket's status in its YAML frontmatter.

    Args:
        path: Path to the ticket file
        status: New status (open, in-progress, done)

    Returns JSON with {path, old_status, new_status}.
    """
    valid_statuses = {"open", "in-progress", "done", "exception"}
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
def throw_ticket_exception(
    path: str,
    thrown_by: str,
    attempted: str,
    conflict: str,
    surface: str,
) -> str:
    """Atomically write an exception block to a ticket and set its status to 'exception'.

    Args:
        path: Path to the ticket file.
        thrown_by: Who is throwing the exception ("programmer" or "sprint-planner").
        attempted: What was tried before hitting the blocker.
        conflict: The upstream decision or constraint that is blocked.
        surface: Visibility of the exception ("user-visible" or "internal").

    Returns JSON: {path, old_status, new_status, thrown_at}.
    """
    valid_thrown_by = {"programmer", "sprint-planner"}
    if thrown_by not in valid_thrown_by:
        raise ValueError(
            f"Invalid thrown_by '{thrown_by}'. Must be one of: {', '.join(sorted(valid_thrown_by))}"
        )

    valid_surfaces = {"user-visible", "internal"}
    if surface not in valid_surfaces:
        raise ValueError(
            f"Invalid surface '{surface}'. Must be one of: {', '.join(sorted(valid_surfaces))}"
        )

    for field_name, field_value in [
        ("attempted", attempted),
        ("conflict", conflict),
    ]:
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError(f"'{field_name}' must be a non-empty string.")

    try:
        ticket_path = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"Ticket not found: {path}")

    artifact = Artifact(ticket_path)
    old_status = artifact.frontmatter.get("status", "unknown")
    thrown_at = datetime.now(timezone.utc).isoformat()

    artifact.update_frontmatter(
        exception={
            "thrown_by": thrown_by,
            "thrown_at": thrown_at,
            "attempted": attempted,
            "conflict": conflict,
            "surface": surface,
        }
    )
    artifact.update_frontmatter(status="exception")

    return json.dumps(
        {
            "path": str(ticket_path),
            "old_status": old_status,
            "new_status": "exception",
            "thrown_at": thrown_at,
        },
        indent=2,
    )


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

    # Determine the tickets_dir (go up from done/ if already there)
    tickets_dir = ticket_path.parent
    if tickets_dir.name == "done":
        tickets_dir = tickets_dir.parent
    sprint_dir = tickets_dir.parent

    # Create domain objects
    project = get_project()
    sprint = Sprint(sprint_dir, project)
    ticket = Ticket(ticket_path, sprint)

    # Move the ticket and its plan file
    result = ticket.move_to_done_with_plan()

    # Sweep all sprint issues and auto-complete any whose tickets are all done
    completed = _sweep_done_issues(sprint)
    if completed:
        result["completed_issues"] = completed

    return json.dumps(result, indent=2)


@server.tool()
def reopen_ticket(path: str) -> str:
    """Reopen a completed ticket by moving it from done/ back to the sprint's tickets/ directory.

    Behaviour:
    - If the ticket is in tickets/done/, move it back to tickets/ and reset status to "open".
    - If the ticket exists but is NOT in done/, just reset status to "open".
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

    # Determine the sprint directory
    tickets_dir = ticket_path.parent
    if tickets_dir.name == "done":
        tickets_dir = tickets_dir.parent
    sprint_dir = tickets_dir.parent

    project = get_project()
    sprint = Sprint(sprint_dir, project)
    ticket = Ticket(ticket_path, sprint)

    result = ticket.reopen()
    return json.dumps(result, indent=2)


def _detect_sprint_from_branch() -> tuple[str, str] | None:
    """Detect sprint_id and branch_name from the current git branch.

    Returns (sprint_id, branch_name) if the current branch matches
    sprint/NNN-*, or None if not on a sprint branch (including detached HEAD).
    """
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
    )
    branch = result.stdout.strip()
    if not branch:
        return None
    m = re.match(r"^sprint/(\d+)-", branch)
    if m is None:
        return None
    return (m.group(1), branch)


@server.tool()
def close_sprint(
    sprint_id: Optional[str] = None,
    branch_name: Optional[str] = None,
    main_branch: str = "master",
    push_tags: bool = True,
    delete_branch: bool = True,
    test_command: Optional[str] = None,
    test_timeout: Optional[float] = None,
) -> str:
    """Close a sprint by updating its status and moving it to sprints/done/.

    When sprint_id is omitted or empty, auto-detects it from the current git
    branch (must be on a sprint/NNN-* branch).

    When branch_name is provided (or auto-detected), executes the full
    lifecycle including pre-condition verification with self-repair, test run,
    archive, state DB update, version bump, git merge, push tags, and branch
    deletion.

    When branch_name is omitted, falls back to legacy behavior (archive
    + state only, no git operations).

    Args:
        sprint_id: The sprint ID (e.g., '001'). When omitted or empty,
            auto-detected from the current git branch (sprint/NNN-*).
        branch_name: Sprint branch name (e.g., 'sprint/001-my-sprint').
            When provided, enables full lifecycle with git operations.
        main_branch: Target branch for merge (default: 'master')
        push_tags: Whether to push tags after tagging (default: True)
        delete_branch: Whether to delete the sprint branch after merge (default: True)
        test_command: Shell command to run tests. Defaults to 'uv run pytest'.
            Pass empty string to skip tests entirely (for non-Python projects).
        test_timeout: Seconds to allow the test command to run before it is
            considered hung and killed. Resolution order (highest priority
            first): (1) this parameter, if not None; (2) a top-level
            `test_timeout:` key in `.clasi/config.yaml`; (3) the default of
            900 seconds (chosen to comfortably fit this project's own
            ~460-525s suite runtime — the old 300s default was too short and
            produced false timeout failures on a healthy suite). Pass `0` to
            disable the timeout entirely (unlimited). When a timeout does
            occur, the error message names the effective timeout value that
            was used, so a false-timeout report is self-diagnosing.

    Returns JSON with structured result (success or error).
    """
    if not sprint_id:
        detected = _detect_sprint_from_branch()
        if detected is None:
            current = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
            ).stdout.strip() or "(detached HEAD)"
            return json.dumps({
                "status": "error",
                "error": {
                    "step": "auto-detect",
                    "message": (
                        "Not on a sprint branch. Provide sprint_id explicitly"
                        " or check out the sprint branch."
                    ),
                    "current_branch": current,
                },
            }, indent=2)
        sprint_id, branch_name = detected

    if branch_name is not None:
        return _close_sprint_full(
            sprint_id, branch_name, main_branch, push_tags, delete_branch,
            test_command=test_command, test_timeout=test_timeout,
        )
    return _close_sprint_legacy(sprint_id)


def _close_sprint_legacy(sprint_id: str) -> str:
    """Original close_sprint behavior: archive + state, no git."""
    project = get_project()
    sprint = project.get_sprint(sprint_id)

    # Check in-progress issues — they should already be resolved individually.
    # Sprint-scoped issues live in <sprint>/issues/; status is stored in frontmatter.
    unresolved_issues: list[str] = []

    # Part 1: scan <sprint>/issues/ top-level
    sprint_issues_dir = sprint.path / "issues"
    if sprint_issues_dir.exists():
        for issue_file in sorted(sprint_issues_dir.glob("*.md")):
            issue = Issue(issue_file, project)
            if issue.sprint == sprint_id:
                if issue.status in ("done", "complete", "completed"):
                    # Self-repair: move to done/ (physically relocates file)
                    issue.move_to_done()
                else:
                    # Check if intentionally deferred by a ticket in this sprint
                    if not _issue_is_deferred(sprint, issue_file.name):
                        unresolved_issues.append(issue_file.name)

    # Part 2: scan <sprint>/issues/done/ — already relocated, pass cleanly
    sprint_issues_done_dir = sprint.path / "issues" / "done"
    if sprint_issues_done_dir.exists():
        for _issue_file in sorted(sprint_issues_done_dir.glob("*.md")):
            pass  # Already in done/ — no action needed

    # Check pending pool issues tagged with this sprint
    pending_dir = project.issues_dir
    moved_issues: list[str] = []
    if pending_dir.exists():
        for issue_file in sorted(pending_dir.glob("*.md")):
            issue = Issue(issue_file, project)
            if issue.sprint == sprint_id:
                if issue.status in ("done", "complete", "completed"):
                    # Relocate directly to <sprint>/issues/done/ (not pool/done/)
                    target_dir = sprint.path / "issues" / "done"
                    target_dir.mkdir(parents=True, exist_ok=True)
                    target_path = target_dir / issue_file.name
                    issue_file.rename(target_path)
                    from clasi.artifact import Artifact as _Artifact
                    issue._artifact = _Artifact(target_path)
                    # Update frontmatter only (file is now in done/ — idempotent move)
                    issue.move_to_done(sprint_id=sprint_id)
                    moved_issues.append(issue_file.name)

    # Archive sprint directory (updates status, copies architecture-update, moves dir)
    archive_result = sprint.archive()

    # Update state database: advance to done and release lock
    db = project.db
    if db.path.exists():
        try:
            state = db.get_sprint_state(sprint_id)
            phase_idx = _PHASES.index(state["phase"])
            done_idx = _PHASES.index("done")
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
        "old_path": archive_result["old_path"],
        "new_path": archive_result["new_path"],
    }
    if moved_issues:
        result["moved_issues"] = moved_issues
    if unresolved_issues:
        result["unresolved_issues"] = unresolved_issues
    if version:
        result["version"] = version
        result["tag"] = f"v{version}"

    return json.dumps(result, indent=2)


def _prune_sprint_worktrees(
    branch_name: str,
    repo_root: Optional[Path] = None,
    sprint_dir: Optional[Path] = None,
) -> tuple[list[str], list[str], list[dict]]:
    """Prune git worktrees associated with the closing sprint.

    Two independent sweeps are performed:

    1. **Sprint branch's own worktree** (pre-existing behavior, unchanged):
       parses ``git worktree list --porcelain`` output and removes any
       worktree whose ``branch`` field matches ``refs/heads/<branch_name>``.
       This sweep always runs and never touches the main worktree (the first
       entry in the porcelain output, which has no ``branch`` field when in
       detached-HEAD state, or whose path matches the repo root).

    2. **Orphaned ticket worktrees** (``ticket/<sprint-id>-*`` branches left
       behind by parallel ticket execution): only runs when both
       ``repo_root`` and ``sprint_dir`` are provided. Delegates
       classification to ``worktree.reconcile_worktrees`` so there is one
       code path for ticket-worktree classification. Cleanup policy at
       sprint close is conservative:

       - ``merged``/``cleaned_up`` (reconcile's ``cleaned`` list): both the
         worktree directory and the branch are already removed by
         ``reconcile_worktrees`` itself.
       - ``failed``/``conflict`` (a subset of reconcile's ``escalated``
         list): the worktree *directory* is force-removed here, but the
         branch is retained so a human can inspect the partial work. These
         are reported back distinctly (see the third return element) rather
         than silently dropped.
       - Any other ambiguous case reconcile reports (dirty tree, "merged"
         audit state not yet an actual ancestor, rogue worktrees, etc.) is
         left untouched, matching reconcile's own safety contract.

    Returns a 3-tuple ``(pruned_paths, failed_paths, retained)``:

    - ``pruned_paths``: absolute worktree paths that were fully removed
      (both sweeps contribute).
    - ``failed_paths``: absolute worktree paths whose removal command
      failed (sprint-branch sweep only; unchanged from prior behavior).
    - ``retained``: list of dicts describing ticket worktrees whose
      directory was removed but whose branch was retained because the
      audit state was ``failed``/``conflict``. Each dict has
      ``ticket_id``, ``path``, ``branch``, and ``reason`` keys.
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )

    target_ref = f"refs/heads/{branch_name}"
    pruned: list[str] = []
    failed: list[str] = []
    retained: list[dict] = []

    # Parse porcelain blocks separated by blank lines.
    # Each block looks like:
    #   worktree /path/to/wt
    #   HEAD <sha>
    #   branch refs/heads/sprint/NNN-slug
    current_path: Optional[str] = None
    is_main: bool = True  # first block is always the main worktree

    for line in result.stdout.splitlines():
        line = line.rstrip()
        if line.startswith("worktree "):
            current_path = line[len("worktree "):]
        elif line == "":
            # Blank line separates blocks; reset is_main after first block.
            if is_main:
                is_main = False
            current_path = None
        elif line.startswith("branch ") and not is_main and current_path is not None:
            ref = line[len("branch "):]
            if ref == target_ref:
                # Remove this worktree.
                rm_result = subprocess.run(
                    ["git", "worktree", "remove", "--force", current_path],
                    capture_output=True,
                    text=True,
                )
                if rm_result.returncode == 0:
                    pruned.append(current_path)
                else:
                    failed.append(current_path)

    # Sweep 2: orphaned ticket/<sprint-id>-* worktrees, via reconcile_worktrees.
    if repo_root is not None and sprint_dir is not None:
        from clasi import worktree as worktree_module

        reconciliation = worktree_module.reconcile_worktrees(repo_root, sprint_dir)

        for entry in reconciliation.get("cleaned", []):
            path = entry.get("path")
            if path:
                pruned.append(path)

        for entry in reconciliation.get("escalated", []):
            reason = entry.get("reason", "")
            if reason.startswith("ambiguous audit state: failed") or reason.startswith(
                "ambiguous audit state: conflict"
            ):
                path = entry.get("path")
                branch = entry.get("branch")
                if path:
                    worktree_module.cleanup_worktree(
                        repo_root, Path(path), branch, keep_branch=True
                    )
                retained.append(
                    {
                        "ticket_id": entry.get("ticket_id"),
                        "path": path,
                        "branch": branch,
                        "reason": reason,
                    }
                )

    return pruned, failed, retained


@server.tool()
def reconcile_worktrees(sprint_id: str) -> str:
    """Reconcile worktree state for a sprint on demand.

    Resolves the sprint's directory and repo root, calls
    clasi.worktree.reconcile_worktrees, and returns the
    cleaned/escalated/rogue summary as JSON. Read-mostly: auto-cleans
    the two safe classes (merged-not-cleaned, clean-but-abandoned) and
    returns ambiguous cases for the caller to act on. Safe to call at
    any time, from any session — not only from within execute-sprint.

    Args:
        sprint_id: The sprint ID (e.g., '018')

    Returns JSON with {cleaned, escalated, rogue} (see
    clasi.worktree.reconcile_worktrees for the shape of each entry).
    """
    from clasi import worktree as worktree_module

    try:
        project = get_project()
        sprint = project.get_sprint(sprint_id)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)

    result = worktree_module.reconcile_worktrees(project.root, sprint.path)
    return json.dumps(result, indent=2)


def _find_sprint_frontmatter_path(project: Project, sprint_id: str) -> Optional[Path]:
    """Locate the sprint.md path for the candidate sprint directory matching
    *sprint_id*, without parsing its frontmatter.

    Mirrors ``Project.get_sprint``'s own candidate-selection logic (a
    directory whose name equals *sprint_id* or starts with
    ``"{sprint_id}-"``) so it finds the exact same file that caused
    ``get_sprint`` to raise ``SprintFrontmatterError`` or
    ``SprintIdMismatchError`` — those errors are raised precisely because
    the frontmatter of this candidate is malformed or mismatched, so it
    cannot be relied on to recover the path. Returns None only if no
    candidate directory with an existing sprint.md can be found (should not
    happen when called right after one of those errors was raised).
    """
    for location in [project.sprints_dir, project.sprints_dir / "done"]:
        if not location.exists():
            continue
        for d in sorted(location.iterdir()):
            if not d.is_dir():
                continue
            sprint_file = d / "sprint.md"
            if not sprint_file.exists():
                continue
            dir_name = d.name
            if dir_name == sprint_id or dir_name.startswith(f"{sprint_id}-"):
                return sprint_file
    return None


def _close_sprint_full(
    sprint_id: str,
    branch_name: str,
    main_branch: str,
    push_tags_flag: bool,
    delete_branch_flag: bool,
    test_command: Optional[str] = None,
    test_timeout: Optional[float] = None,
) -> str:
    """Full lifecycle close: preconditions, tests, archive, git ops."""
    project = get_project()
    db = project.db
    completed_steps: list[str] = []
    repairs: list[str] = []

    # ── Step 1: Pre-condition verification with self-repair ──

    # 1a. Check tickets — all should be in tickets/done/ with status done
    try:
        sprint = project.get_sprint(sprint_id)
        sprint_dir = sprint.path
    except SprintFrontmatterError as e:
        sprint_file_path = _find_sprint_frontmatter_path(project, sprint_id)
        allowed_paths = [str(sprint_file_path)] if sprint_file_path else []
        recorded = False
        if allowed_paths and db.path.exists():
            db.write_recovery_state(
                sprint_id, "precondition", allowed_paths, str(e),
            )
            recorded = True
        return json.dumps({
            "status": "error",
            "error": {
                "step": "precondition",
                "message": str(e),
                "recovery": {
                    "recorded": recorded,
                    "allowed_paths": allowed_paths,
                    "instruction": (
                        "The sprint.md file has malformed frontmatter. "
                        "Fix the opening '---' fence in the file named in "
                        "the message, then call close_sprint again."
                    ),
                },
            },
            "completed_steps": [],
            "remaining_steps": ["precondition", "tests", "archive", "db_update", "version_bump", "merge", "push_tags", "delete_branch", "prune_worktrees"],
        }, indent=2)
    except SprintIdMismatchError as e:
        sprint_file_path = _find_sprint_frontmatter_path(project, sprint_id)
        allowed_paths = [str(sprint_file_path)] if sprint_file_path else []
        recorded = False
        if allowed_paths and db.path.exists():
            db.write_recovery_state(
                sprint_id, "precondition", allowed_paths, str(e),
            )
            recorded = True
        return json.dumps({
            "status": "error",
            "error": {
                "step": "precondition",
                "message": str(e),
                "recovery": {
                    "recorded": recorded,
                    "allowed_paths": allowed_paths,
                    "instruction": (
                        "The sprint.md file has a missing or incorrect 'id:' field. "
                        "Correct the id field in the file named in the message, "
                        "then call close_sprint again."
                    ),
                },
            },
            "completed_steps": [],
            "remaining_steps": ["precondition", "tests", "archive", "db_update", "version_bump", "merge", "push_tags", "delete_branch", "prune_worktrees"],
        }, indent=2)
    except (SprintNotFoundError, ValueError):
        # Sprint dir might already be archived (idempotent retry), or an
        # unanticipated ValueError sub-class.
        return json.dumps({
            "status": "error",
            "error": {
                "step": "precondition",
                "message": f"Sprint '{sprint_id}' not found in active or done",
                "recovery": {"recorded": False, "allowed_paths": [], "instruction": "Create or restore the sprint directory."},
            },
            "completed_steps": [],
            "remaining_steps": ["precondition", "tests", "archive", "db_update", "version_bump", "merge", "push_tags", "delete_branch", "prune_worktrees"],
        }, indent=2)

    if sprint.tickets_dir.exists():
        for ticket_file in sorted(sprint.tickets_dir.glob("*.md")):
            if ticket_file.name == "done":
                continue
            ticket = Ticket(ticket_file, sprint)
            if ticket.status == "done":
                # Self-repair: move to done/
                ticket.move_to_done()
                # Also move plan file if exists
                plan_file = ticket_file.with_suffix("").with_name(ticket_file.stem + "-plan.md")
                if plan_file.exists():
                    sprint.tickets_done_dir.mkdir(parents=True, exist_ok=True)
                    plan_file.rename(sprint.tickets_done_dir / plan_file.name)
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
                    "remaining_steps": ["precondition", "tests", "archive", "db_update", "version_bump", "merge", "push_tags", "delete_branch", "prune_worktrees"],
                }, indent=2)

    # 1b. Check TODOs — in-progress TODOs for this sprint must be resolved.
    # Sprint-scoped issues live in <sprint>/issues/; status is stored in frontmatter.
    unresolved_issues: list[str] = []

    # Self-repair: sweep any issues whose tickets are all done before hard-fail check
    _sweep_done_issues(sprint)

    # Part 1: scan <sprint>/issues/ top-level
    sprint_issues_dir_full = sprint.path / "issues"
    if sprint_issues_dir_full.exists():
        for issue_file in sorted(sprint_issues_dir_full.glob("*.md")):
            issue = Issue(issue_file, project)
            if issue.sprint == sprint_id:
                if issue.status in ("done", "complete", "completed"):
                    # Self-repair: move to done/ (physically relocates file)
                    issue.move_to_done()
                    repairs.append(f"moved issue {issue_file.name} to done/")
                else:
                    # Issue still in-progress — check if intentionally deferred
                    if _issue_is_deferred(sprint, issue_file.name):
                        # At least one ticket in this sprint has completes_issue: false
                        # for this issue — it spans future sprints; allow close to proceed
                        continue
                    # Issue is unresolved and not deferred — collect, do not block
                    unresolved_issues.append(issue_file.name)

    # Part 2: scan <sprint>/issues/done/ — already relocated, pass cleanly
    sprint_issues_done_dir_full = sprint.path / "issues" / "done"
    if sprint_issues_done_dir_full.exists():
        for _issue_file in sorted(sprint_issues_done_dir_full.glob("*.md")):
            pass  # Already in done/ — no action needed

    # Also check pending pool issues that are tagged with this sprint
    pending_pool = project.issues_dir
    if pending_pool.exists():
        for issue_file in sorted(pending_pool.glob("*.md")):
            issue = Issue(issue_file, project)
            if issue.sprint == sprint_id:
                if issue.status in ("done", "complete", "completed"):
                    # Relocate directly to <sprint>/issues/done/ (not pool/done/)
                    target_dir = sprint.path / "issues" / "done"
                    target_dir.mkdir(parents=True, exist_ok=True)
                    target_path = target_dir / issue_file.name
                    issue_file.rename(target_path)
                    from clasi.artifact import Artifact as _Artifact
                    issue._artifact = _Artifact(target_path)
                    # Update frontmatter only (file is now in done/ — idempotent move)
                    issue.move_to_done(sprint_id=sprint_id)
                    repairs.append(f"moved issue {issue_file.name} to done/")

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
    all_steps = ["precondition_verification", "tests", "archive", "db_update", "design_overlay_apply", "version_bump", "merge", "push_tags", "delete_branch", "prune_worktrees"]

    if test_command == "":
        # Explicitly skip tests (non-Python projects, etc.)
        repairs.append("skipped tests (test_command is empty)")
    else:
        # Determine the command to run
        if test_command is not None:
            test_cmd = test_command.split()
        else:
            test_cmd = ["uv", "run", "pytest"]

        # Resolve the effective test timeout. Priority: explicit parameter,
        # then .clasi/config.yaml's top-level `test_timeout:` key, then the
        # 900s default (raised from the old 300s, which was too short for
        # this project's own ~460-525s suite runtime). `0` means unlimited.
        if test_timeout is not None:
            effective_timeout = test_timeout
        else:
            config_timeout = _load_config(project.root).get("test_timeout")
            if isinstance(config_timeout, (int, float)) and not isinstance(config_timeout, bool):
                effective_timeout = config_timeout
            else:
                effective_timeout = 900

        subprocess_timeout = None if effective_timeout == 0 else effective_timeout

        try:
            test_result = subprocess.run(
                test_cmd,
                capture_output=True,
                text=True,
                timeout=subprocess_timeout,
            )
            # Pytest exit codes: 0=all passed, 1=some failed, 2=interrupted,
            # 3=internal error, 4=usage error, 5=no tests collected.
            # Exit code 5 is not a failure — repos with no test suite are fine.
            if test_result.returncode not in (0, 5):
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
            # Test command not available — skip tests
            repairs.append(f"skipped tests ({test_cmd[0]} not found)")
        except subprocess.TimeoutExpired:
            error_msg = f"Test suite timed out after {effective_timeout} seconds"
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
    already_archived = sprint_dir.parent.name == "done"

    if already_archived:
        new_path = sprint_dir
        old_path_str = str(new_path)
    else:
        # NOTE: TODOs are not bulk-moved at sprint close.
        # They are moved individually by move_ticket_to_done when all
        # referencing tickets are done. The precondition check (step 1b)
        # already verified that no in-progress TODOs remain for this sprint.

        # Archive sprint directory (updates status, copies architecture-update, moves dir)
        archive_result = sprint.archive()
        new_path = sprint.path  # Sprint.archive() updates self._path
        old_path_str = archive_result["old_path"]

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

    # ── Step 4b: Apply design overlay to canonical docs (sprint 021) ──
    # Gated on opt-in; no-op (and no-op silently) when unset/off or the
    # sprint carries no design/ dir (trivial/compact sprint, or opted-out
    # project). Must run — and succeed — before the version-bump/tag step,
    # per sprint.md's Migration Concerns: a failed apply blocks tag/merge
    # exactly like a failed test run does today.
    if project.design_docs_opt_in and sprint.design_dir.exists():
        from clasi.design import DesignError, apply as apply_design_overlay, validate as validate_design_docs
        from clasi.design.overlay import OverlayError

        try:
            applied = apply_design_overlay(sprint.design_dir)
            validation = validate_design_docs(project)
            if not validation.ok:
                raise DesignError("\n".join(validation.messages))
        except (OverlayError, DesignError) as e:
            error_msg = f"Design overlay apply/validation failed: {e}"
            if db.path.exists():
                db.write_recovery_state(sprint_id, "design_overlay_apply", [], error_msg)
            return json.dumps({
                "status": "error",
                "error": {
                    "step": "design_overlay_apply",
                    "message": error_msg,
                    "recovery": {
                        "recorded": db.path.exists(),
                        "allowed_paths": [str(project.design_dir), str(sprint.design_dir)],
                        "instruction": (
                            "Fix the design overlay or canonical docs/design/ "
                            "content, then call close_sprint again."
                        ),
                    },
                },
                "completed_steps": completed_steps,
                "remaining_steps": [s for s in all_steps if s not in completed_steps],
            }, indent=2)

    completed_steps.append("design_overlay_apply")

    # ── Step 5: Version bump ──
    version = None
    try:
        trigger = load_version_trigger()
        if should_version(trigger, "sprint_close"):
            version = compute_next_version()
            detected = detect_version_file(project.root)
            if detected:
                update_version_file(detected[0], detected[1], version)
            # Commit the version bump so the working tree is clean for merge
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(project.root), capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "commit", "-m", f"chore: bump version to {version}"],
                cwd=str(project.root), capture_output=True, text=True,
            )
            create_version_tag(version)
    except Exception as exc:
        import sys
        print(f"[CLASI] Versioning failed: {exc}", file=sys.stderr)

    completed_steps.append("version_bump")

    # ── Step 5b: Commit .clasi.db if still dirty after version_bump ──
    db_file = project.db_path
    if db_file.exists():
        status_result = subprocess.run(
            ["git", "status", "--porcelain", str(db_file)],
            capture_output=True, text=True, cwd=str(project.root),
        )
        if status_result.stdout.strip():  # non-empty means dirty/staged
            # Verify we're on the sprint branch before committing
            head_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True, text=True, cwd=str(project.root),
            )
            head_branch = head_result.stdout.strip()
            if head_branch == branch_name:
                subprocess.run(
                    ["git", "add", str(db_file)],
                    cwd=str(project.root), capture_output=True, text=True,
                )
                subprocess.run(
                    ["git", "commit", "-m", "chore: update .clasi.db"],
                    cwd=str(project.root), capture_output=True, text=True,
                )

    # ── Step 6: Git merge ──
    merged = False
    branch_exists = False
    # Use a Sprint wrapper pointing to the archived location for git operations
    archived_sprint = Sprint(new_path, project)
    merge_error_result: Optional[str] = None
    try:
        merge_result = archived_sprint.merge_branch(main_branch)
        branch_exists = merge_result["branch_exists"]
        merged = merge_result["merged"]
    except RuntimeError as e:
        error_msg = str(e)
        conflicted: list[str] = (
            e.conflicted_files if isinstance(e, MergeConflictError) else []
        )
        if db.path.exists():
            db.write_recovery_state(sprint_id, "merge", conflicted, error_msg)
        merge_error_result = json.dumps({
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
    finally:
        # Release lock regardless of merge outcome (idempotent: no-op if already released)
        if db.path.exists():
            try:
                db.release_lock(sprint_id)
            except ValueError:
                pass  # Already released (success path releases in db_update)

    if merge_error_result is not None:
        return merge_error_result

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
    if delete_branch_flag:
        try:
            branch_deleted = archived_sprint.delete_branch()
        except RuntimeError:
            branch_deleted = False

    completed_steps.append("delete_branch")

    # ── Step 9: Prune sprint worktrees ──
    worktrees_pruned: list[str] = []
    worktrees_failed: list[str] = []
    worktrees_retained: list[dict] = []
    pruned, failed, retained = _prune_sprint_worktrees(
        branch_name, repo_root=project.root, sprint_dir=new_path
    )
    worktrees_pruned = pruned
    worktrees_failed = failed
    worktrees_retained = retained
    if worktrees_failed:
        for wt_path in worktrees_failed:
            repairs.append(f"failed to remove worktree: {wt_path}")
    if worktrees_retained:
        for entry in worktrees_retained:
            repairs.append(
                f"retained branch '{entry.get('branch')}' for ticket "
                f"{entry.get('ticket_id')} ({entry.get('reason')})"
            )
    if worktrees_pruned:
        completed_steps.append("prune_worktrees")

    # ── Step 10: Clear recovery state ──
    if db.path.exists():
        try:
            db.clear_recovery_state()
        except Exception:
            pass

    # ── Step 11: Return structured result ──
    result: dict = {
        "status": "success",
        "old_path": old_path_str,
        "new_path": str(new_path),
        "repairs": repairs,
        "worktrees_pruned": worktrees_pruned,
    }
    if worktrees_failed:
        result["worktrees_failed"] = worktrees_failed
    if worktrees_retained:
        result["worktrees_retained"] = worktrees_retained
    if unresolved_issues:
        result["unresolved_issues"] = unresolved_issues
    if version:
        result["version"] = version
        result["tag"] = f"v{version}"
    result["git"] = {
        "merged": merged,
        "merge_strategy": "rebase + --no-ff",
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
        result: 'passed', 'failed', or 'skipped' (skipped is treated as
            satisfying the gate, same as passed, for changes with no
            architectural impact)
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
            try:
                branch_name = sprint.create_branch()
            except RuntimeError as e:
                return json.dumps({
                    "error": str(e),
                    "lock": lock,
                }, indent=2)
            lock["branch"] = branch_name
        else:
            # Re-entrant: look up existing branch
            lock["branch"] = sprint.branch

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


# --- Issue management tools ---



@server.tool()
def list_issues() -> str:
    """List all active issue files with sprint/ticket linkage.

    Scans .clasi/issues/*.md (pending) and sprint-scoped issues directories.
    Excludes the done/ subdirectory.

    Returns JSON array of {filename, title, status, sprint, tickets}.
    The sprint and tickets fields are present only for in-progress issues.
    """
    project = get_project()
    results = []

    for issue in project.list_issues():
        entry: dict = {"filename": issue.path.name, "title": issue.title}
        entry["status"] = issue.status
        if issue.status == "in-progress":
            if issue.sprint:
                entry["sprint"] = issue.sprint
            if issue.tickets:
                entry["tickets"] = issue.tickets
        results.append(entry)

    return json.dumps(results, indent=2)


@server.tool()
def move_issue_to_done(
    filename: str,
    sprint_id: str | None = None,
    ticket_ids: list[str] | None = None,
) -> str:
    """Mark an issue as done by updating its frontmatter (no file move).

    When ``sprint_id`` is provided the issue must reside in
    ``<sprint_id>/issues/`` (i.e. it must have been moved there by
    ``move_todo_to_in_progress`` first).  Passing a ``sprint_id`` for an
    issue that lives elsewhere is an error.

    Args:
        filename: The issue filename (e.g., 'my-idea.md')
        sprint_id: Optional sprint ID that consumed this issue
        ticket_ids: Optional list of ticket IDs that address this issue

    Returns JSON with {path, status}.
    """
    project = get_project()
    try:
        issue_obj = project.get_issue(filename)
    except ValueError:
        raise ValueError(f"Issue not found: {filename}")

    # Validate sprint-scoped location when sprint_id is given
    if sprint_id is not None:
        try:
            sprint = project.get_sprint(sprint_id)
        except ValueError:
            raise ValueError(f"Sprint not found: {sprint_id}")
        expected_dirs = {
            (sprint.path / "issues").resolve(),
            (sprint.path / "issues" / "done").resolve(),
        }
        if issue_obj.path.parent.resolve() not in expected_dirs:
            raise ValueError(
                f"Issue '{filename}' is not in the expected sprint issues "
                f"directory or its done/ subdirectory. "
                f"Current location: '{issue_obj.path.parent}'. "
                "Run move_todo_to_in_progress first."
            )

    issue_obj.move_to_done(sprint_id=sprint_id, ticket_ids=ticket_ids)

    return json.dumps({
        "path": str(issue_obj.path),
        "status": issue_obj.status,
    }, indent=2)


@server.tool()
def split_issue(
    filename: str,
    new_filename: str,
    new_title: str,
    new_body: str,
    updated_body: str | None = None,
) -> str:
    """Split an issue into two sibling files with cross-link frontmatter.

    Creates a new issue file as a sibling of the original (same directory).
    Adds split_from to the new file and split_into to the original.

    When splitting a sprint-scoped in-progress issue, the new file inherits
    the sprint context (status: in-progress, sprint: <id>). Otherwise the
    new file starts as pending with no sprint set.

    Args:
        filename: The original issue filename (resolved via project.get_issue).
        new_filename: Filename for the new split-off issue (e.g., 'my-idea-part2.md').
        new_title: Title heading for the new issue.
        new_body: Body content for the new issue (after the heading).
        updated_body: Optional replacement body for the original issue.

    Returns JSON with {original_path, new_path}.
    """
    project = get_project()
    try:
        original = project.get_issue(filename)
    except ValueError:
        raise ValueError(f"Issue not found: {filename}")

    new_path = original.path.parent / new_filename
    if new_path.exists():
        raise ValueError(f"Target file already exists: {new_path}")

    # Determine frontmatter for the new file
    new_fm: dict = {"status": "pending"}
    if original.status == "in-progress" and original.sprint:
        new_fm["status"] = "in-progress"
        new_fm["sprint"] = original.sprint
    if original.source:
        new_fm["source"] = original.source
    new_fm["split_from"] = filename

    # Write the new file using Artifact.write (handles parent dir creation)
    from clasi.artifact import Artifact as _Artifact

    new_artifact = _Artifact(new_path)
    new_artifact.write(new_fm, f"\n# {new_title}\n\n{new_body}")

    # Update the original's split_into list
    orig_fm, orig_body = original._artifact.read_document()
    existing_split_into = orig_fm.get("split_into", [])
    if isinstance(existing_split_into, str):
        existing_split_into = [existing_split_into] if existing_split_into else []
    else:
        existing_split_into = list(existing_split_into)
    if new_filename not in existing_split_into:
        existing_split_into.append(new_filename)
    orig_fm["split_into"] = existing_split_into

    # Optionally replace the original body
    if updated_body is not None:
        orig_body = updated_body

    original._artifact.write(orig_fm, orig_body)

    return json.dumps({
        "original_path": str(original.path),
        "new_path": str(new_path),
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
    and tickets exist in open status.

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
    planning_docs = [
        ("sprint.md", sprint.sprint_md, SPRINT_TEMPLATE),
    ]

    for filename, filepath, template in planning_docs:
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
    if not sprint.tickets_dir.exists():
        issues.append({
            "severity": "error",
            "check": "tickets_dir_exists",
            "message": "tickets/ directory does not exist",
            "fix": "Create tickets using create_ticket(sprint_id, title)",
            "path": str(sprint.tickets_dir),
        })
    else:
        tickets = _collect_tickets(sprint_dir)
        if not tickets:
            issues.append({
                "severity": "error",
                "check": "tickets_exist",
                "message": "No tickets found in the sprint",
                "fix": "Create tickets using create_ticket(sprint_id, title)",
                "path": str(sprint.tickets_dir),
            })
        else:
            for t in tickets:
                if t["status"] not in ("open", "in-progress"):
                    issues.append({
                        "severity": "warning",
                        "check": "ticket_status_pre_execution",
                        "message": f"Ticket #{t['id']} has unexpected status"
                                   f" '{t['status']}' before execution",
                        "fix": f"Verify ticket #{t['id']} status is correct",
                        "path": t["path"],
                    })

    passed = not any(i["severity"] == "error" for i in issues)

    # ── Design overlay: commit edited copies (sprint 021, opt-in only) ──
    # Runs only after all existing checks above have passed — a sprint
    # that fails precondition checks (wrong branch, tickets not ready,
    # etc.) must not get a design commit either.
    project = get_project()
    design_overlay: dict = {"opted_in": bool(project.design_docs_opt_in)}
    if passed and design_overlay["opted_in"] and sprint.design_dir.exists():
        from clasi.design.overlay import OverlayError, commit_edits, generate_diffs

        try:
            diffs_written = generate_diffs(sprint.design_dir, repo_root=project.root)
            committed = commit_edits(
                sprint.design_dir,
                repo_root=project.root,
                commit_message=f"chore: commit sprint {sprint_id} design overlay edits",
            )
            design_overlay["diffs_written"] = [str(p) for p in diffs_written]
            design_overlay["committed"] = committed
        except OverlayError as e:
            issues.append({
                "severity": "error",
                "check": "design_overlay_commit",
                "message": f"Failed to commit sprint design overlay edits: {e}",
                "fix": "Resolve the git error and re-run review_sprint_pre_execution.",
                "path": str(sprint.design_dir),
            })
            passed = False
            design_overlay["error"] = str(e)

    return json.dumps({
        "passed": passed,
        "issues": issues,
        "design_overlay": design_overlay,
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
            "path": str(sprint.tickets_dir),
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
    planning_docs_pre_close = [
        ("sprint.md", sprint.sprint_md, SPRINT_TEMPLATE),
    ]

    for filename, filepath, template in planning_docs_pre_close:
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
        post_close_docs = [
            ("sprint.md", sprint.sprint_md),
            ("usecases.md", sprint.usecases_md),
            ("architecture-update.md", sprint.architecture_update_md),
        ]
        for filename, filepath in post_close_docs:
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
