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
from clasi.close import (
    SprintCloser,
    _issue_is_deferred,
    _prune_sprint_worktrees,
    _sweep_done_issues,
)
from clasi.frontmatter import read_document, read_frontmatter
from clasi.gitutil import run_git
from clasi.mcp_server import server, get_project
from clasi.project import Project
from clasi.sprint import Sprint
from clasi.state_db import (
    PHASES as _PHASES,
    rename_sprint as _rename_sprint,
)
from clasi.state_db_class import _SATISFYING_GATE_RESULTS
from clasi.templates import (
    slugify,
    SPRINT_TEMPLATE,
    TICKET_TEMPLATE,
)
from clasi.ticket import Ticket
from clasi.issue import Issue
from clasi.tools._common import clasi_tool, resolve_artifact_path
from clasi.versioning import (
    compute_next_version,
    create_version_tag,
    detect_version_file,
    load_version_trigger,
    should_version,
    update_version_file,
)

logger = logging.getLogger("clasi.artifact")

# resolve_artifact_path moved to clasi.tools._common (sprint 030 ticket
# 005), imported above -- re-exported here so `from
# clasi.tools.artifact_tools import resolve_artifact_path` (existing
# callers, existing tests) keeps working unchanged.



# _is_ticket_done, _any_ticket_suppresses_issue, _issue_is_deferred, and
# _sweep_done_issues moved to clasi.close (030/004) -- they are
# close-sprint domain logic (Ticket/Issue/Sprint objects only, no
# MCP/JSON concern), and close.py, a core module, cannot import back
# from this tools-layer module without inverting the tools->core
# dependency direction. _issue_is_deferred and _sweep_done_issues are
# re-imported below (see the top-of-file import block): the former is
# still used by _close_sprint_legacy (unchanged, out of this ticket's
# scope), the latter by both _close_sprint_legacy and _mark_ticket_done
# (the update_ticket_status/move_ticket_to_done primitive, unrelated to
# close_sprint).

# --- Create tools (ticket 008) ---


@server.tool()
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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


def _check_architecture_review_gate(sprint_id: str) -> None:
    """Check that a sprint's ``architecture_review`` gate has recorded a
    satisfying (``passed``/``skipped``) result (031/002).

    Replaces the old phase-index check (was
    ``_check_sprint_phase_for_ticketing``): the real precondition for
    ticket creation is the gate result itself, not which phase the
    sprint's ``sprints.phase`` row happens to say -- checking the gate
    directly is what lets a sprint's *first* ``create_ticket`` call
    succeed the moment the gate passes, with no separate
    ``advance_sprint_phase`` call in between (the gate-order bug this
    ticket exists to fix).

    Degrades gracefully: if the DB doesn't exist or the sprint isn't
    registered, the check is skipped (backward compatibility) -- the
    same graceful-degradation contract the check this replaces had.
    """
    project = get_project()
    if not project.db.path.exists():
        return
    try:
        state = project.db.get_sprint_state(sprint_id)
    except ValueError as e:
        if "not registered" in str(e):
            return  # Sprint not in DB — allow (backward compat)
        raise

    gates = {g["gate_name"]: g["result"] for g in state["gates"]}
    result = gates.get("architecture_review")
    if result not in _SATISFYING_GATE_RESULTS:
        raise ValueError(
            f"Cannot create tickets: sprint '{sprint_id}' has not "
            "recorded a passing 'architecture_review' gate result "
            f"(current: {result!r}). Record the gate result first via "
            "record_gate_result."
        )


@server.tool()
@clasi_tool
def create_ticket(
    sprint_id: str,
    title: str,
    issue: str | list[str] | None = None,
) -> str:
    """Create a new ticket in a sprint's tickets/ directory.

    Auto-assigns the next ticket number within the sprint.
    Checks the sprint's recorded ``architecture_review`` gate result (not
    its phase) if the state database exists; on a sprint's first
    ``create_ticket`` call, this also auto-advances the sprint's phase to
    ``"ticketing"`` (031/002) -- no separate ``advance_sprint_phase`` call
    is needed. Later calls are unaffected (the auto-advance is idempotent).

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
    _check_architecture_review_gate(sprint_id)
    project = get_project()
    sprint = project.get_sprint(sprint_id)

    # 031/002: auto-advance to 'ticketing' as a side effect of the first
    # create_ticket call, instead of requiring a separate
    # advance_sprint_phase call in between recording architecture_review
    # and creating tickets. Guarded by the same "DB doesn't exist / sprint
    # not registered" backward-compat skip _check_architecture_review_gate
    # above already applies -- advance_to() calls self.init(), which would
    # otherwise create a state DB file as a side effect of ticket creation
    # for a project/sprint that isn't using one.
    if project.db.path.exists():
        try:
            sprint.advance_to("ticketing", "architecture_review")
        except ValueError as e:
            if "not registered" not in str(e):
                raise

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
@clasi_tool
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
@clasi_tool
def list_sprints(status: Optional[str] = None) -> str:
    """List all sprints with their metadata.

    Args:
        status: Optional filter by status — one of the DB-phase values
            Sprint.set_sprint_stage()/Sprint.advance_to() mirror into
            frontmatter status: (roadmap, planning-docs,
            architecture-review, ticketing, executing, closing, done).

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
@clasi_tool
def list_tickets(sprint_id: Optional[str] = None, status: Optional[str] = None) -> str:
    """List tickets, optionally filtered by sprint and/or status.

    Args:
        sprint_id: Optional sprint ID to filter by
        status: Optional status filter (open, in-progress, done)

    Returns JSON array of {id, title, status, sprint_id, path}.

    Raises ValueError if sprint_id is given but does not match any known
    sprint (e.g. a typo'd ID) -- previously this silently returned `[]`,
    indistinguishable from "sprint exists, has no tickets".
    """
    project = get_project()
    results = []

    if sprint_id:
        sprints_to_scan = [project.get_sprint(sprint_id)]
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
@clasi_tool
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


def _mark_ticket_done(ticket_path: Path) -> dict:
    """Combined frontmatter-write + directory-move for a ticket's "done"
    transition — the single primitive both ``update_ticket_status(path,
    "done")`` and ``move_ticket_to_done`` delegate to (sprint 030 ticket
    003), so the two stores can no longer be set independently.

    Idempotent: if *ticket_path* (after ``resolve_artifact_path``) is
    already in ``tickets/done/`` with ``status: done``, ``Ticket.mark_done()``
    re-writes the same status and finds nothing left to move — it returns
    successfully rather than raising. This tolerates a stale caller
    invoking ``move_ticket_to_done`` on the pre-move path after
    ``update_ticket_status(path, "done")`` already moved the file.

    Returns the dict from ``Ticket.mark_done()`` (old_path, new_path,
    old_status, new_status, and optionally plan_old_path/plan_new_path),
    plus ``completed_issues`` if the post-move issue sweep auto-completed
    any sprint issues.
    """
    tickets_dir = ticket_path.parent
    if tickets_dir.name == "done":
        tickets_dir = tickets_dir.parent
    sprint_dir = tickets_dir.parent

    project = get_project()
    sprint = Sprint(sprint_dir, project)
    ticket = Ticket(ticket_path, sprint)

    result = ticket.mark_done()

    completed = _sweep_done_issues(sprint)
    if completed:
        result["completed_issues"] = completed

    return result


@server.tool()
@clasi_tool
def update_ticket_status(path: str, status: str) -> str:
    """Update a ticket's status in its YAML frontmatter.

    For ``status="done"``, this performs both the frontmatter write and
    the ``tickets/done/`` move in one call (sprint 030 ticket 003) —
    internally delegating to ``Ticket.mark_done()``, the same combined
    primitive ``move_ticket_to_done`` uses, rather than requiring a
    separate ``move_ticket_to_done`` call afterward. For any other status
    value, behavior is unchanged: a frontmatter write only — there is
    nothing to move for open/in-progress/exception.

    Args:
        path: Path to the ticket file
        status: New status (open, in-progress, done, exception)

    Returns JSON with {path, old_status, new_status} for a non-"done"
    status, or {old_path, new_path, old_status, new_status, ...} (see
    ``Ticket.mark_done()``) when status is "done".
    """
    valid_statuses = {"open", "in-progress", "done", "exception"}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(valid_statuses))}")

    try:
        ticket_path = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"Ticket not found: {path}")

    if status == "done":
        return json.dumps(_mark_ticket_done(ticket_path), indent=2)

    artifact = Artifact(ticket_path)
    old_status = artifact.frontmatter.get("status", "unknown")
    artifact.update_frontmatter(status=status)

    return json.dumps({
        "path": str(ticket_path),
        "old_status": old_status,
        "new_status": status,
    }, indent=2)


@server.tool()
@clasi_tool
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
@clasi_tool
def move_ticket_to_done(path: str) -> str:
    """Move a ticket (and its plan file if exists) to the sprint's
    tickets/done/ directory, setting status to "done" in the same call.

    Thin alias for ``update_ticket_status(path, "done")`` — both delegate
    to the same ``_mark_ticket_done`` / ``Ticket.mark_done()`` primitive
    (sprint 030 ticket 003), so there is no behavior divergence between
    the two entry points for a ticket already in the expected pre-state.
    Tolerant of running after ``update_ticket_status(path, "done")``
    already moved the file: ``resolve_artifact_path`` finds the ticket at
    its new ``tickets/done/`` location, and re-marking an already-done
    ticket is a no-op rather than an error.

    Args:
        path: Path to the ticket file

    Returns JSON with {old_path, new_path, old_status, new_status, ...}.
    """
    try:
        ticket_path = resolve_artifact_path(path)
    except FileNotFoundError:
        raise ValueError(f"Ticket not found: {path}")

    return json.dumps(_mark_ticket_done(ticket_path), indent=2)


@server.tool()
@clasi_tool
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
    result = run_git(["branch", "--show-current"], cwd=get_project().root)
    branch = result.stdout.strip()
    if not branch:
        return None
    m = re.match(r"^sprint/(\d+)-", branch)
    if m is None:
        return None
    return (m.group(1), branch)


@server.tool()
@clasi_tool
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
        test_command: Shell command to run tests. Defaults to the full
            suite with coverage -- the same invocation as `just test-all`
            (`uv run pytest -m 'slow or not slow' --cov=src/clasi
            --cov-report=term-missing --cov-report=lcov:lcov.info`), not
            the fast-loop `uv run pytest` a developer runs while
            iterating (032/008: default `addopts` now filters out
            `@pytest.mark.slow` tests and carries no coverage flags, so a
            *bare* `uv run pytest` is deliberately not this tool's
            default -- see close.py's SprintCloser.run for the exact
            command). Pass the literal string "SKIP" to skip tests
            entirely (for non-Python projects or a deliberate no-test
            close). This is the only supported skip mechanism -- an empty
            string is unreachable in practice (the Claude Code harness bug
            documented in .claude/rules/tool-call-empty-args.md drops
            *all* arguments when any one argument is empty or null, so
            `test_command=""` never arrives) and "NONE" maps to `None`
            (the full-suite-with-coverage default above), not to "skip".
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
            current = run_git(
                ["branch", "--show-current"], cwd=get_project().root
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
            version = compute_next_version(project_root=project.root)
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



@server.tool()
@clasi_tool
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


def _close_sprint_full(
    sprint_id: str,
    branch_name: str,
    main_branch: str,
    push_tags_flag: bool,
    delete_branch_flag: bool,
    test_command: Optional[str] = None,
    test_timeout: Optional[float] = None,
) -> str:
    """Full lifecycle close: preconditions, tests, archive, git ops.

    Thin wrapper (030/004) delegating to close.SprintCloser -- the
    ~950-line body that used to live directly in this function moved to
    close.py step-by-step (see that module's docstring), reordering
    self-repair to run only after the test gate and fixing the
    transactional-DB-update, version-bump-idempotency,
    checked-git-call, and tag-push-by-name defects the reliability
    review named (C3-C5 / F1, F2, F9). Kept as a named module-level
    function here, not inlined into the close_sprint tool below,
    because existing tests patch it directly at this module path
    (clasi.tools.artifact_tools._close_sprint_full) to intercept the
    full lifecycle without exercising SprintCloser itself.

    The versioning-function names below (``compute_next_version`` etc.)
    are passed through explicitly rather than left for SprintCloser to
    import on its own: many existing tests patch them at
    ``clasi.tools.artifact_tools.<name>``, which only replaces the name
    binding in *this* module's globals. Referencing the bare names here
    resolves them through this module's own (patchable) namespace at
    call time and threads whatever is currently bound -- real or mocked
    -- into SprintCloser, exactly as when this logic lived inline here.
    """
    project = get_project()
    return SprintCloser(
        project,
        sprint_id,
        branch_name,
        main_branch,
        push_tags_flag,
        delete_branch_flag,
        test_command=test_command,
        test_timeout=test_timeout,
        compute_next_version_fn=compute_next_version,
        create_version_tag_fn=create_version_tag,
        detect_version_file_fn=detect_version_file,
        update_version_file_fn=update_version_file,
        load_version_trigger_fn=load_version_trigger,
        should_version_fn=should_version,
    ).run()


@server.tool()
@clasi_tool
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
@clasi_tool
def get_sprint_phase(sprint_id: str) -> str:
    """Get a sprint's current lifecycle phase and gate status.

    Args:
        sprint_id: The sprint ID (e.g., '002')

    Returns JSON with {id, phase, gates, lock, phase_transitions}, where
    phase_transitions is an ordered (oldest-first) list of
    {from_phase, to_phase, at} recording every phase advance this sprint
    has made, written transactionally by advance_sprint_phase. Empty list
    for a sprint that has never advanced past its initial phase.
    """
    try:
        state = get_project().db.get_sprint_state(sprint_id)
        return json.dumps(state, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


@server.tool()
@clasi_tool
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
@clasi_tool
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


def _check_stakeholder_approval_gate(project, sprint_id: str) -> None:
    """Check that a sprint's ``stakeholder_approval`` gate has recorded a
    satisfying (``passed``/``skipped``) result (031/002).

    No DB-absent / not-registered graceful degradation here, unlike
    ``_check_architecture_review_gate``: ``acquire_execution_lock``'s own
    ``sprint.acquire_lock()`` call already requires the sprint to be
    registered (it raises 'not registered' itself, unchanged by this
    ticket) -- there is no pre-existing backward-compat path for an
    unregistered sprint to preserve here.
    """
    state = project.db.get_sprint_state(sprint_id)
    gates = {g["gate_name"]: g["result"] for g in state["gates"]}
    result = gates.get("stakeholder_approval")
    if result not in _SATISFYING_GATE_RESULTS:
        raise ValueError(
            f"Cannot acquire execution lock: sprint '{sprint_id}' has "
            "not recorded a passing 'stakeholder_approval' gate result "
            f"(current: {result!r}). Record the gate result first via "
            "record_gate_result."
        )


@server.tool()
@clasi_tool
def acquire_execution_lock(sprint_id: str) -> str:
    """Acquire the execution lock for a sprint and create the sprint branch.

    Only one sprint can hold the lock at a time. Prevents concurrent
    sprint execution in the same repository.

    Checks the sprint's recorded ``stakeholder_approval`` gate result
    *before* granting the lock (031/002) -- no lock is granted without a
    recorded ``passed``/``skipped`` result. Once the lock is granted,
    auto-advances the sprint's phase to ``"executing"``; no separate
    ``advance_sprint_phase`` call is needed.

    Failure-mode contract: the gate check and the lock acquisition are
    the safety-critical steps; the phase-advance that follows is a
    status-display convenience, not a second safety gate. If the
    phase-advance fails after the lock has already been granted, the
    lock is **not** rolled back -- the lock, not the phase string, is
    what every other consumer (the tier-2 ticket-state gate,
    ``close_sprint``'s precondition check) treats as authoritative. The
    failure still surfaces to the caller (in the returned ``{"error":
    ...}`` JSON, this function's existing error-reporting shape) rather
    than being swallowed. A retried call is safe: ``acquire_lock()``'s
    existing re-entrant path returns success immediately for a lock this
    sprint already holds, and the phase-advance is independently
    idempotent, so the retry's only real work is completing whatever
    failed the first time.

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

        _check_stakeholder_approval_gate(project, sprint_id)

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

        # 031/002: auto-advance to 'executing' now that the lock is
        # granted. Per the failure-mode contract above, a failure here
        # propagates to the outer except ValueError -- the lock acquired
        # above is not rolled back.
        sprint.advance_to("executing", "stakeholder_approval")

        return json.dumps(lock, indent=2)
    except ValueError as e:
        return json.dumps({"error": str(e)}, indent=2)


@server.tool()
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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
@clasi_tool
def tag_version(major: int = 0) -> str:
    """Compute the next version, update pyproject.toml, and create a git tag.

    Version format: <major>.<YYYYMMDD>.<build>
    Build auto-increments within the same date, resets to 1 on new date.

    Args:
        major: Major version number (default 0)

    Returns JSON with {version, tag}.
    """

    project = get_project()
    version = compute_next_version(major, project_root=project.root)
    detected = detect_version_file(project.root)
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
@clasi_tool
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
@clasi_tool
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
@clasi_tool
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
