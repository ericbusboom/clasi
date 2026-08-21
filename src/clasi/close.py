"""Resumable, transactional sprint close orchestration (030/004).

Holds :class:`SprintCloser`, the ordered step sequence
``tools.artifact_tools.close_sprint`` (via its thin ``_close_sprint_full``
wrapper) delegates to for the full-lifecycle close path. Ported from the
pre-existing ~950-line ``_close_sprint_full`` function step-by-step (most
of the git-call/archive/merge logic was already correct — root-anchored
since sprint 029 — and moves here unchanged) with four defects fixed, per
the reliability review (``docs/reviews/2026-08-reliability/00-review.md``
C3-C5, ``02-mcp-tools.md`` F1/F2/F9):

1. The state-DB phase advance + lock release (``StateDB.force_close``,
   ``state_db_class.py``) is transactional and never swallows a failure —
   no bare ``except: pass``.
2. Self-repair (moving a ticket/issue that is done but not yet relocated,
   catching the DB phase up) now runs only *after* the test gate passes,
   not before it — a test failure can no longer leave the repo in a state
   that never existed before the call.
3. The version-bump step checks git's own tag list before minting a new
   tag when resuming after a later step's failure, so a retry never mints
   a second tag for an unchanged HEAD.
4. The tag-push step pushes the sprint's own tag by name
   (``git push origin v{version}``), not ``git push --tags``.

Step model
----------
``ALL_STEPS`` names the ten steps, in order: ``precondition_verification``,
``tests``, ``archive``, ``db_update``, ``design_overlay_apply``,
``version_bump``, ``merge``, ``push_tags``, ``delete_branch``,
``prune_worktrees``. This is unchanged from the pre-existing
``_close_sprint_full``'s own ``all_steps`` list — the same names appear
in ``completed_steps``/``remaining_steps`` in the tool's JSON result, and
existing tests pin several of them (e.g. ``"precondition_verification"``,
``"archive"``) so they are kept exactly as before.

Resumability is achieved via per-step idempotency against ground truth,
not a new "completed steps" ledger column (see sprint.md's Design
Rationale) — ``recovery_state`` already stores exactly one failed
``step`` name; that is reused here as a coarse "resume from here"
pointer:

- Every step except ``tests`` and ``version_bump`` already carries its
  own unconditional ground-truth check that makes it safe to run again
  regardless of whether this is a fresh call or a retry: ``archive``
  checks whether the sprint directory is already under ``sprints/done/``;
  ``db_update`` delegates to ``StateDB.force_close``, itself idempotent;
  ``merge`` delegates to ``Sprint.merge_branch``, which checks
  ``is_ancestor`` before doing anything; ``push_tags``/``delete_branch``/
  ``prune_worktrees`` were already tolerant of "nothing to do" before
  this ticket. These steps need no resume-path branching at all.
- ``tests`` has no independent ground truth for "did the tests already
  pass" from the resume pointer alone (sprint 030/002 removes the
  writer-less test-cache marker predicate this codebase used to
  half-rely on) — so when the recorded recovery step is *after*
  ``tests`` in ``ALL_STEPS`` (meaning a later step failed on a prior
  attempt, so tests must already have passed to reach it), the tests
  step is skipped rather than re-run. Sprint 031/008 adds one narrow,
  independently-verified ground truth back on top of that: a
  ``test_pass_markers`` DB row (sprint_id, head_sha, test_cmd) written
  only immediately after a real, successful subprocess test run, and
  consulted only when the *current* HEAD sha and test command still
  match the stored row **and** the working tree is clean right now
  (``_valid_test_pass_marker``). Unlike the removed predicate, this
  marker always has both a writer and a reader landing in the same
  change, and re-validates against live git state on every read rather
  than trusting a stored fact indefinitely — a dirty working tree at a
  matching sha is treated as unverified, not as a pass.
- ``version_bump`` is the one step whose own idempotency check needs a
  live git call: does the version currently recorded in the project's
  version file already have a matching tag in git (``_get_existing_tags``)?
  That check only runs when resuming from a recorded step at or after
  ``version_bump``, so an ordinary (non-retried) close never pays for the
  extra ``git tag -l`` call. It reads the file rather than recomputing,
  because ``compute_next_version`` can never answer this question by
  construction — it always returns a version whose tag does not yet
  exist — and checks tag *existence* rather than "is this tag on HEAD"
  so a later, unrelated commit (e.g. the ``.clasi.db`` commit) moving
  HEAD past the tagged commit does not make the check false-negative.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from clasi.artifact import Artifact
from clasi.gitutil import run_git
from clasi.issue import Issue
from clasi.mcp_server import get_project
from clasi.project import (
    Project,
    SprintFrontmatterError,
    SprintIdMismatchError,
    SprintNotFoundError,
    _load_config,
)
from clasi.sprint import MergeConflictError, Sprint
from clasi.state_db_class import PHASES as _PHASES
from clasi.ticket import Ticket
from clasi.versioning import (
    _get_existing_tags,
    compute_next_version,
    create_version_tag,
    detect_version_file,
    load_version_trigger,
    read_current_version,
    should_version,
    update_version_file,
)

ALL_STEPS = [
    "precondition_verification",
    "tests",
    "archive",
    "db_update",
    "design_overlay_apply",
    "version_bump",
    "merge",
    "push_tags",
    "delete_branch",
    "prune_worktrees",
]

# write_recovery_state's "step" argument has historically used
# "precondition" (not "precondition_verification") for the
# precondition-stage failure cases below -- pinned by existing tests
# asserting both result["error"]["step"] == "precondition" and a
# recorded recovery_state["step"] == "precondition". This alias lets a
# recorded recovery pointer resolve against ALL_STEPS for resume-index
# purposes without renaming that externally-observed string.
_RECOVERY_STEP_ALIASES = {"precondition": "precondition_verification"}


# ---------------------------------------------------------------------
# Shared helpers ported from tools/artifact_tools.py (030/004) -- these
# were tools-layer functions used only by the close-sprint machinery
# (plus _sweep_done_issues, also used by tools.artifact_tools._mark_ticket_done
# for the unrelated update_ticket_status/move_ticket_to_done tools, which
# import it back from here). Moving them here keeps the dependency
# direction correct (tools wraps clasi-core, never the reverse) without
# duplicating the logic.
# ---------------------------------------------------------------------


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
    suppresses completion (via ``_any_ticket_suppresses_issue``), the issue
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
            issue = Issue(issue_file, project)
            if issue.sprint != sprint.id:
                continue
            if _try_complete(issue, issue_file.name):
                issue.move_to_done()
                completed.append(issue_file.name)

    # Source 2: pending-pool issues tagged with this sprint
    pending_pool = project.issues_dir
    if pending_pool.exists():
        for issue_file in sorted(pending_pool.glob("*.md")):
            issue = Issue(issue_file, project)
            if issue.sprint != sprint.id:
                continue
            if _try_complete(issue, issue_file.name):
                # Relocate to <sprint>/issues/done/ before calling move_to_done
                target_dir = sprint.path / "issues" / "done"
                target_dir.mkdir(parents=True, exist_ok=True)
                target_path = target_dir / issue_file.name
                issue_file.rename(target_path)
                issue._artifact = Artifact(target_path)
                # File is already in done/; move_to_done() just updates frontmatter
                issue.move_to_done()
                completed.append(issue_file.name)

    return completed


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
    # Anchor every git call to an explicit root: repo_root when the caller
    # supplied one (the production call site always does), else fall back
    # to the active project's root rather than the process's own cwd.
    effective_root = repo_root if repo_root is not None else get_project().root

    result = run_git(["worktree", "list", "--porcelain"], cwd=effective_root)

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
                rm_result = run_git(
                    ["worktree", "remove", "--force", current_path],
                    cwd=effective_root,
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


def _recovery(recorded: bool, allowed_paths: list[str], instruction: str) -> dict:
    return {"recorded": recorded, "allowed_paths": allowed_paths, "instruction": instruction}


class SprintCloser:
    """Orchestrates the full-lifecycle close for one sprint.

    Constructed with the already-resolved ``project`` and the raw
    parameters ``tools.artifact_tools.close_sprint`` receives; ``run()``
    executes the ten-step sequence (see module docstring) and returns the
    same JSON string shape ``_close_sprint_full`` has always returned.

    The six versioning-module functions the version-bump step calls
    (``compute_next_version``, ``create_version_tag``,
    ``detect_version_file``, ``update_version_file``,
    ``load_version_trigger``, ``should_version``) are accepted as
    constructor overrides, defaulting to the real functions imported at
    module level. This is not speculative DI -- a substantial slice of
    the pre-existing test suite patches these at
    ``clasi.tools.artifact_tools.<name>`` (e.g.
    ``@patch("clasi.tools.artifact_tools.compute_next_version", ...)``),
    which only intercepts the name binding in *that* module's namespace.
    ``tools.artifact_tools._close_sprint_full`` (the thin wrapper that
    constructs this class) references the bare names in its own body, so
    they resolve through its own patchable module globals at call time
    and get threaded through here explicitly -- the same mechanism that
    made these patches work when this logic lived directly in that
    function, before this ticket moved it here.
    """

    def __init__(
        self,
        project: Project,
        sprint_id: str,
        branch_name: str,
        main_branch: str,
        push_tags_flag: bool,
        delete_branch_flag: bool,
        test_command: Optional[str] = None,
        test_timeout: Optional[float] = None,
        compute_next_version_fn=None,
        create_version_tag_fn=None,
        detect_version_file_fn=None,
        update_version_file_fn=None,
        load_version_trigger_fn=None,
        should_version_fn=None,
    ) -> None:
        self.project = project
        self.sprint_id = sprint_id
        self.branch_name = branch_name
        self.main_branch = main_branch
        self.push_tags_flag = push_tags_flag
        self.delete_branch_flag = delete_branch_flag
        self.test_command = test_command
        self.test_timeout = test_timeout
        self.db = project.db
        self.completed_steps: list[str] = []
        self.repairs: list[str] = []
        self._compute_next_version = compute_next_version_fn or compute_next_version
        self._create_version_tag = create_version_tag_fn or create_version_tag
        self._detect_version_file = detect_version_file_fn or detect_version_file
        self._update_version_file = update_version_file_fn or update_version_file
        self._load_version_trigger = load_version_trigger_fn or load_version_trigger
        self._should_version = should_version_fn or should_version

    def _error(self, step: str, message: str, recovery: dict, extra: Optional[dict] = None) -> str:
        error: dict[str, Any] = {"step": step, "message": message}
        if extra:
            error.update(extra)
        error["recovery"] = recovery
        return json.dumps(
            {
                "status": "error",
                "error": error,
                "completed_steps": self.completed_steps,
                "remaining_steps": [s for s in ALL_STEPS if s not in self.completed_steps],
            },
            indent=2,
        )

    def _write_recovery(self, step: str, allowed_paths: list[str], reason: str) -> bool:
        if self.db.path.exists():
            self.db.write_recovery_state(self.sprint_id, step, allowed_paths, reason)
            return True
        return False

    # ------------------------------------------------------------------
    # Test-pass marker helpers (031/008)
    # ------------------------------------------------------------------

    def _git_head_and_cleanliness(self) -> tuple[Optional[str], bool]:
        """Return (head_sha, is_clean) from a single git call.

        Uses ``git status --porcelain=v2 --branch``, which prints a
        ``# branch.oid <sha>`` header line (the current HEAD commit)
        followed by zero or more porcelain entry lines -- any entry line
        means the tree is dirty, matching plain ``--porcelain``'s
        untracked-files-included default (a stray untracked file is
        still "not the same code" as what a marker's test run covered).
        One subprocess call instead of two (``rev-parse HEAD`` plus a
        separate ``status --porcelain``) keeps this marker's overhead to
        the single git call it actually needs, at both the write site
        (right after a real test pass) and the read site
        (``_valid_test_pass_marker``).

        Returns ``(None, False)`` on any git failure or on a repo with
        no commits yet (``branch.oid (initial)``) -- callers treat that
        as "cannot verify," failing closed toward running tests for real
        rather than trusting or writing a marker.
        """
        result = run_git(["status", "--porcelain=v2", "--branch"], cwd=self.project.root)
        if result.returncode != 0:
            return None, False
        sha: Optional[str] = None
        is_clean = True
        for line in result.stdout.splitlines():
            if line.startswith("# branch.oid "):
                sha = line[len("# branch.oid "):].strip()
            elif line.startswith("#"):
                continue
            elif line.strip():
                is_clean = False
        if sha == "(initial)":
            sha = None
        return sha, is_clean

    def _valid_test_pass_marker(self, sprint_id: str, test_cmd_str: str) -> Optional[str]:
        """Return the marker's head_sha if it is still safe to trust, else None.

        All three of the following must hold, checked in cheapest-first
        order to avoid spawning a git subprocess when there is no marker
        to begin with:

        1. A marker row exists for *sprint_id*.
        2. Its recorded ``test_cmd`` matches *test_cmd_str* exactly --
           a marker written for one test command must never license
           skipping a *different* command a later call asks for.
        3. Its recorded ``head_sha`` equals the repository's current
           HEAD sha, AND the working tree is clean right now. Both are
           re-checked live on every call; nothing is cached beyond the
           single DB row itself. A dirty tree at a matching sha is
           explicitly not trusted -- see the module docstring and
           close.md's design note for why (uncommitted edits present
           now are not reflected in the sha either way).
        """
        if not self.db.path.exists():
            return None
        marker = self.db.get_test_pass_marker(sprint_id)
        if marker is None or marker["test_cmd"] != test_cmd_str:
            return None
        current_sha, is_clean = self._git_head_and_cleanliness()
        if current_sha is None or current_sha != marker["head_sha"]:
            return None
        if not is_clean:
            return None
        return marker["head_sha"]

    def run(self) -> str:
        project = self.project
        sprint_id = self.sprint_id
        branch_name = self.branch_name
        db = self.db

        # ── Resume-state: read any existing recovery pointer for this sprint ──
        # See module docstring -- this is a coarse "resume from here" signal,
        # not an exhaustive completed-steps ledger. Every step except
        # "tests" and "version_bump" has its own unconditional ground-truth
        # check and needs no branching on this at all.
        resume_index = -1
        if db.path.exists():
            recovery = db.get_recovery_state()
            if recovery is not None and recovery.get("sprint_id") == sprint_id:
                resume_step = _RECOVERY_STEP_ALIASES.get(recovery["step"], recovery["step"])
                if resume_step in ALL_STEPS:
                    resume_index = ALL_STEPS.index(resume_step)

        # ── Step: Precondition verification (read-only) ──
        try:
            sprint = project.get_sprint(sprint_id)
            sprint_dir = sprint.path
        except SprintFrontmatterError as e:
            sprint_file_path = _find_sprint_frontmatter_path(project, sprint_id)
            allowed_paths = [str(sprint_file_path)] if sprint_file_path else []
            recorded = self._write_recovery("precondition", allowed_paths, str(e)) if allowed_paths else False
            return self._error(
                "precondition",
                str(e),
                _recovery(
                    recorded,
                    allowed_paths,
                    "The sprint.md file has malformed frontmatter. "
                    "Fix the opening '---' fence in the file named in "
                    "the message, then call close_sprint again.",
                ),
            )
        except SprintIdMismatchError as e:
            sprint_file_path = _find_sprint_frontmatter_path(project, sprint_id)
            allowed_paths = [str(sprint_file_path)] if sprint_file_path else []
            recorded = self._write_recovery("precondition", allowed_paths, str(e)) if allowed_paths else False
            return self._error(
                "precondition",
                str(e),
                _recovery(
                    recorded,
                    allowed_paths,
                    "The sprint.md file has a missing or incorrect 'id:' field. "
                    "Correct the id field in the file named in the message, "
                    "then call close_sprint again.",
                ),
            )
        except (SprintNotFoundError, ValueError):
            # Sprint dir might already be archived (idempotent retry), or an
            # unanticipated ValueError sub-class.
            return self._error(
                "precondition",
                f"Sprint '{sprint_id}' not found in active or done",
                _recovery(False, [], "Create or restore the sprint directory."),
            )

        if sprint.tickets_dir.exists():
            for ticket_file in sorted(sprint.tickets_dir.glob("*.md")):
                if ticket_file.name == "done":
                    continue
                ticket = Ticket(ticket_file, sprint)
                if ticket.status != "done":
                    # Not repairable -- a genuinely incomplete ticket blocks
                    # close, same as always. (A ticket that IS done but not
                    # yet moved to tickets/done/ is not an error here -- it
                    # is handled by the post-test self-repair step below,
                    # not reported or mutated at precondition time.)
                    error_msg = f"Ticket {ticket.id or ticket_file.stem} has status '{ticket.status}', not 'done'"
                    self._write_recovery("precondition", [str(ticket_file)], error_msg)
                    return self._error(
                        "precondition",
                        error_msg,
                        _recovery(
                            db.path.exists(),
                            [str(ticket_file)],
                            f"Complete ticket {ticket.id or ticket_file.stem} and set status to 'done', then call close_sprint again.",
                        ),
                    )

        self.completed_steps.append("precondition_verification")

        # ── Step: Run tests ──
        skip_tests = resume_index > ALL_STEPS.index("tests")

        # Resolved unconditionally (cheap: a string split, no subprocess)
        # so both the marker check below and the real-run branch use the
        # exact same command -- a marker recorded for one test_cmd must
        # never license skipping a different one.
        if self.test_command is not None:
            test_cmd = self.test_command.split()
        else:
            test_cmd = ["uv", "run", "pytest"]
        test_cmd_str = " ".join(test_cmd)

        marker_sha: Optional[str] = None
        if not skip_tests and self.test_command != "SKIP":
            marker_sha = self._valid_test_pass_marker(sprint_id, test_cmd_str)

        if skip_tests:
            self.repairs.append(
                "skipped tests (already passed on a prior attempt at this close)"
            )
        elif self.test_command == "SKIP":
            # Explicitly skip tests (non-Python projects, etc.) -- the
            # "SKIP" sentinel replaces the old test_command="" mechanism,
            # which was unreachable through the Claude Code harness bug
            # that motivates the "NONE" sentinel elsewhere: an empty-string
            # argument drops *all* call arguments before this function ever
            # sees them (sprint 030 ticket 005; see
            # .claude/rules/tool-call-empty-args.md).
            self.repairs.append('skipped tests (test_command is "SKIP")')
        elif marker_sha is not None:
            # 031/008: a real prior run already passed for this exact
            # HEAD sha and test command, and the working tree is clean
            # right now -- skip the redundant re-run without the operator
            # reaching for a fake test_command. See _valid_test_pass_marker.
            self.repairs.append(
                f"skipped tests (already passed for HEAD {marker_sha[:12]} "
                f'with "{test_cmd_str}", working tree clean)'
            )
        else:
            if self.test_timeout is not None:
                effective_timeout = self.test_timeout
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
                # Exit code 5 is not a failure -- repos with no test suite are fine.
                if test_result.returncode not in (0, 5):
                    error_msg = f"Tests failed (exit code {test_result.returncode})"
                    test_output = test_result.stdout[-2000:] if test_result.stdout else ""
                    if test_result.stderr:
                        test_output += "\n" + test_result.stderr[-500:]
                    self._write_recovery("tests", [], error_msg)
                    return self._error(
                        "tests",
                        error_msg,
                        _recovery(db.path.exists(), [], "Fix failing tests, then call close_sprint again."),
                        extra={"output": test_output.strip()},
                    )
            except FileNotFoundError:
                self.repairs.append(f"skipped tests ({test_cmd[0]} not found)")
            except subprocess.TimeoutExpired:
                error_msg = f"Test suite timed out after {effective_timeout} seconds"
                self._write_recovery("tests", [], error_msg)
                return self._error(
                    "tests",
                    error_msg,
                    _recovery(db.path.exists(), [], "Investigate slow tests, then call close_sprint again."),
                )
            else:
                # Tests genuinely ran and passed (no exception, no early
                # return above) -- record the HEAD-sha marker so a
                # subsequent close_sprint call against this exact,
                # still-clean commit can skip a redundant re-run (031/008).
                # Only recorded when the tree is clean *right now*: a
                # marker written while the tree was dirty would certify
                # code that was never actually isolated at this sha (the
                # uncommitted edits present during this run are not part
                # of head_sha either way).
                if db.path.exists():
                    current_sha, is_clean = self._git_head_and_cleanliness()
                    if current_sha is not None and is_clean:
                        db.record_test_pass_marker(sprint_id, current_sha, test_cmd_str)

        self.completed_steps.append("tests")

        # ── Step: Self-repair (mutations; runs only after the test gate) ──
        # Ticket 003 landed: update_ticket_status(path, "done") now keeps
        # frontmatter and location in sync going forward, so this has
        # materially less to do than the pre-004 code's precondition step --
        # it remains a safety net for a ticket/issue moved by a legacy call
        # path, or hand-edited directly, not something removable.
        if sprint.tickets_dir.exists():
            for ticket_file in sorted(sprint.tickets_dir.glob("*.md")):
                if ticket_file.name == "done":
                    continue
                ticket = Ticket(ticket_file, sprint)
                if ticket.status == "done":
                    ticket.mark_done()
                    label = f"moved ticket {ticket.id or ticket_file.stem} to done/"
                    self.repairs.append(label)
                    self._write_recovery("self_repair", [str(ticket_file)], label)

        # Self-repair: sweep any issues whose tickets are all done before the
        # unresolved-issue check below.
        _sweep_done_issues(sprint)

        unresolved_issues: list[str] = []
        sprint_issues_dir_full = sprint.path / "issues"
        if sprint_issues_dir_full.exists():
            for issue_file in sorted(sprint_issues_dir_full.glob("*.md")):
                issue = Issue(issue_file, project)
                if issue.sprint == sprint_id:
                    if issue.status in ("done", "complete", "completed"):
                        issue.move_to_done()
                        label = f"moved issue {issue_file.name} to done/"
                        self.repairs.append(label)
                        self._write_recovery("self_repair", [str(issue_file)], label)
                    else:
                        if _issue_is_deferred(sprint, issue_file.name):
                            continue
                        unresolved_issues.append(issue_file.name)

        pending_pool = project.issues_dir
        if pending_pool.exists():
            for issue_file in sorted(pending_pool.glob("*.md")):
                issue = Issue(issue_file, project)
                if issue.sprint == sprint_id:
                    if issue.status in ("done", "complete", "completed"):
                        target_dir = sprint.path / "issues" / "done"
                        target_dir.mkdir(parents=True, exist_ok=True)
                        target_path = target_dir / issue_file.name
                        issue_file.rename(target_path)
                        issue._artifact = Artifact(target_path)
                        issue.move_to_done(sprint_id=sprint_id)
                        label = f"moved issue {issue_file.name} to done/"
                        self.repairs.append(label)
                        self._write_recovery("self_repair", [str(target_path)], label)

        # ── Step: Archive sprint directory ──
        already_archived = sprint_dir.parent.name == "done"

        if already_archived:
            new_path = sprint_dir
            old_path_str = str(new_path)
        else:
            archive_result = sprint.archive()
            new_path = sprint.path  # Sprint.archive() updates self._path
            old_path_str = archive_result["old_path"]

        self.completed_steps.append("archive")

        # ── Step: Update state DB (transactional; never swallowed) ──
        # Matches the pre-existing "no db at all" graceful-degradation
        # guard: a project with no state database has nothing to update
        # and close proceeds without it. Once the db file exists, any
        # failure from force_close() propagates -- never a bare
        # `except: pass` (that was defect #1 this ticket exists to fix).
        if db.path.exists():
            try:
                db.force_close(sprint_id)
            except Exception as e:
                error_msg = f"State DB update failed: {e}"
                self._write_recovery("db_update", [], error_msg)
                return self._error(
                    "db_update",
                    error_msg,
                    _recovery(db.path.exists(), [], "Investigate the state database, then call close_sprint again."),
                )

        self.completed_steps.append("db_update")

        # ── Step: Apply design overlay to canonical docs (sprint 021) ──
        # Gated on opt-in; no-op (and no-op silently) when unset/off or the
        # sprint carries no design/ dir. Must run -- and succeed -- before
        # the version-bump/tag step, per sprint.md's Migration Concerns.
        applied: list = []
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
                self._write_recovery("design_overlay_apply", [], error_msg)
                return self._error(
                    "design_overlay_apply",
                    error_msg,
                    _recovery(
                        db.path.exists(),
                        [str(project.design_dir), str(sprint.design_dir)],
                        "Fix the design overlay or canonical docs/design/ content, then call close_sprint again.",
                    ),
                )

        self.completed_steps.append("design_overlay_apply")

        # ── Step: Version bump (idempotent; every git call checked) ──
        version = None
        try:
            trigger = self._load_version_trigger()
            if self._should_version(trigger, "sprint_close"):
                reused_existing = False
                if resume_index >= ALL_STEPS.index("version_bump"):
                    # Resuming from a point at/after this step in a prior
                    # attempt at this same close -- verify against ground
                    # truth before minting a new tag, so an unchanged HEAD
                    # never gets a second one. The check is: does the
                    # version currently recorded in the project's version
                    # file (persisted by the earlier attempt's commit,
                    # independent of how many commits have landed on top
                    # of it since -- e.g. a later .clasi.db commit moves
                    # HEAD without touching this) already have a matching
                    # tag in git? compute_next_version() itself can never
                    # answer this question (by construction it always
                    # returns a version whose tag does NOT yet exist), so
                    # the check has to read the file directly rather than
                    # recompute. Both calls are skipped entirely on a
                    # fresh (non-resumed) run -- see module docstring.
                    current_file_version = read_current_version(project.root)
                    if current_file_version:
                        candidate_tag = f"v{current_file_version}"
                        if candidate_tag in _get_existing_tags(project.root):
                            version = current_file_version
                            reused_existing = True

                if not reused_existing:
                    version = self._compute_next_version(project_root=project.root)
                    detected = self._detect_version_file(project.root)
                    if detected:
                        self._update_version_file(detected[0], detected[1], version)
                    # Commit the version bump together with the paths this
                    # run's own earlier steps already produced -- see
                    # 027/002 (never a blanket `git add -A`).
                    bump_paths = [old_path_str, str(new_path)]
                    bump_paths.extend(str(p) for p in applied)
                    if detected:
                        bump_paths.append(str(detected[0]))

                    r = run_git(["config", "rebase.autoStash", "true"], cwd=project.root)
                    if r.returncode != 0:
                        raise RuntimeError(
                            f"git config rebase.autoStash failed: {r.stderr.strip()}"
                        )
                    r = run_git(["add", *bump_paths], cwd=project.root)
                    if r.returncode != 0:
                        raise RuntimeError(f"git add (version bump) failed: {r.stderr.strip()}")
                    r = run_git(
                        [
                            "commit", "-m", f"chore: bump version to {version}",
                            "--", *bump_paths,
                        ],
                        cwd=project.root,
                    )
                    if r.returncode != 0:
                        raise RuntimeError(f"git commit (version bump) failed: {r.stderr.strip()}")
                    self._create_version_tag(version)  # raises RuntimeError with git output on failure
        except Exception as exc:
            error_msg = f"Version bump failed: {exc}"
            self._write_recovery("version_bump", [], error_msg)
            return self._error(
                "version_bump",
                error_msg,
                _recovery(db.path.exists(), [], "Investigate the version bump failure, then call close_sprint again."),
            )

        self.completed_steps.append("version_bump")

        # ── Step: Commit .clasi.db if still dirty after version_bump ──
        db_file = project.db_path
        if db_file.exists():
            status_result = run_git(["status", "--porcelain", str(db_file)], cwd=project.root)
            if status_result.stdout.strip():
                head_result = run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=project.root)
                head_branch = head_result.stdout.strip()
                if head_branch == branch_name:
                    r = run_git(["add", str(db_file)], cwd=project.root)
                    if r.returncode != 0:
                        error_msg = f"git add .clasi.db failed: {r.stderr.strip()}"
                        self._write_recovery("version_bump", [str(db_file)], error_msg)
                        return self._error(
                            "version_bump",
                            error_msg,
                            _recovery(db.path.exists(), [str(db_file)], "Investigate the git failure, then call close_sprint again."),
                        )
                    r = run_git(
                        ["commit", "-m", "chore: update .clasi.db", "--", str(db_file)],
                        cwd=project.root,
                    )
                    if r.returncode != 0:
                        error_msg = f"git commit .clasi.db failed: {r.stderr.strip()}"
                        self._write_recovery("version_bump", [str(db_file)], error_msg)
                        return self._error(
                            "version_bump",
                            error_msg,
                            _recovery(db.path.exists(), [str(db_file)], "Investigate the git failure, then call close_sprint again."),
                        )

        # ── Step: Git merge ──
        merged = False
        archived_sprint = Sprint(new_path, project)
        merge_error_result: Optional[str] = None
        try:
            merge_result = archived_sprint.merge_branch(self.main_branch)
            merged = merge_result["merged"]
        except RuntimeError as e:
            error_msg = str(e)
            conflicted: list[str] = e.conflicted_files if isinstance(e, MergeConflictError) else []
            self._write_recovery("merge", conflicted, error_msg)
            merge_error_result = self._error(
                "merge",
                error_msg,
                _recovery(db.path.exists(), conflicted, "Resolve the merge conflicts in the listed files, then call close_sprint again."),
            )
        finally:
            # Release lock regardless of merge outcome (idempotent: no-op if
            # already released by force_close above).
            if db.path.exists():
                try:
                    db.release_lock(sprint_id)
                except ValueError:
                    pass

        if merge_error_result is not None:
            return merge_error_result

        self.completed_steps.append("merge")

        # ── Step: Push tags ──
        tags_pushed = False
        if self.push_tags_flag and version:
            tag_name = f"v{version}"
            push_result = run_git(["push", "origin", tag_name], cwd=project.root)
            tags_pushed = push_result.returncode == 0

        self.completed_steps.append("push_tags")

        # ── Step: Delete branch ──
        branch_deleted = False
        if self.delete_branch_flag:
            try:
                branch_deleted = archived_sprint.delete_branch()
            except RuntimeError:
                branch_deleted = False

        self.completed_steps.append("delete_branch")

        # ── Step: Prune sprint worktrees ──
        pruned, worktrees_failed, worktrees_retained = _prune_sprint_worktrees(
            branch_name, repo_root=project.root, sprint_dir=new_path
        )
        worktrees_pruned = pruned
        if worktrees_failed:
            for wt_path in worktrees_failed:
                self.repairs.append(f"failed to remove worktree: {wt_path}")
        if worktrees_retained:
            for entry in worktrees_retained:
                self.repairs.append(
                    f"retained branch '{entry.get('branch')}' for ticket "
                    f"{entry.get('ticket_id')} ({entry.get('reason')})"
                )
        if worktrees_pruned:
            self.completed_steps.append("prune_worktrees")

        # ── Step: Clear recovery state ──
        if db.path.exists():
            try:
                db.clear_recovery_state()
            except Exception:
                pass
            try:
                db.clear_test_pass_marker(sprint_id)
            except Exception:
                pass

        # ── Return structured result ──
        result: dict = {
            "status": "success",
            "old_path": old_path_str,
            "new_path": str(new_path),
            "repairs": self.repairs,
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
            "merge_target": self.main_branch,
            "tags_pushed": tags_pushed,
            "branch_deleted": branch_deleted,
            "branch_name": branch_name,
        }

        return json.dumps(result, indent=2)
