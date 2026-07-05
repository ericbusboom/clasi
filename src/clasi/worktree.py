"""Worktree lifecycle API for parallel ticket execution.

This module implements the worktree lifecycle used by the CLASI
execute-sprint controller when parallel execution is enabled.

Authoritative specification:
    docs/design/worktree-process.md

Current state:
    Parallel execution is disabled. The serial-only mandate in
    ``clasi/schemas/se-process/instructions/execution.md`` is in effect.
    These implementations satisfy the contracts described here and in the
    spec document above, but are not yet wired into the controller
    (see the reconciliation/controller-wiring tickets for that work).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from clasi.frontmatter import read_frontmatter
from clasi.sprint import MergeConflictError

__all__ = [
    "create_worktree",
    "create_ticket_branch",
    "validate_worktree",
    "merge_ticket_branch",
    "cleanup_worktree",
    "write_audit_record",
    "read_audit_record",
    "check_independence",
    "reconcile_worktrees",
]

# Sentinel used by check_independence when a ticket's file set cannot be
# determined from either frontmatter or the plan body. A ticket carrying
# this sentinel is treated as dependent on every other ticket.
_UNKNOWN_FILES = frozenset({"__unknown__"})

_DEFAULT_TEST_COMMAND = ["uv", "run", "pytest"]


def create_worktree(
    repo_root: Path,
    sprint_id: str,
    ticket_id: str,
) -> Path:
    """Create a git worktree for a single ticket's parallel execution.

    The worktree is placed at ``../worktree-<sprint_id>-<ticket_id>/``
    relative to ``repo_root`` (i.e., a sibling of the repo root directory).
    This placement prevents the worktree directory from appearing as an
    untracked entry in the main repo's ``git status``.

    The worktree is checked out at the current HEAD of the sprint branch
    held by ``repo_root``. The controller subsequently calls
    ``create_ticket_branch`` to create the per-ticket branch inside the
    worktree.

    Parameters:
        repo_root: Absolute path to the repository root (the main working
            tree, not an existing worktree).
        sprint_id: Sprint identifier string (e.g. ``"022"``).
        ticket_id: Ticket identifier string (e.g. ``"003"``).

    Returns:
        Absolute ``Path`` to the newly created worktree directory.

    Raises:
        RuntimeError: If ``git worktree add`` fails.

    See: worktree-process.md §5 (Naming Conventions), §6 (Lifecycle State
    Machine)
    """
    repo_root = Path(repo_root)
    worktree_path = (repo_root / ".." / f"worktree-{sprint_id}-{ticket_id}").resolve()

    result = subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree_path), "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create worktree at '{worktree_path}': "
            f"{result.stderr.strip()}"
        )

    return worktree_path


def create_ticket_branch(
    worktree_path: Path,
    sprint_id: str,
    ticket_id: str,
    slug: str,
) -> str:
    """Create and check out a per-ticket branch inside an existing worktree.

    The branch name follows the pattern
    ``ticket/<sprint_id>-<ticket_id>-<slug>`` where ``slug`` is derived
    from the ticket title (lowercased, non-alphanumeric characters replaced
    with hyphens, truncated to 40 characters). The branch is created from
    the current HEAD of ``worktree_path``.

    Parameters:
        worktree_path: Absolute path to an existing git worktree directory
            created by ``create_worktree``.
        sprint_id: Sprint identifier string (e.g. ``"022"``).
        ticket_id: Ticket identifier string (e.g. ``"003"``).
        slug: URL-safe slug derived from the ticket title
            (e.g. ``"stub-worktree-module"``). Caller is responsible for
            deriving the slug; this function does not transform it.

    Returns:
        Full branch name string
        (e.g. ``"ticket/022-003-stub-worktree-module"``).

    Raises:
        RuntimeError: If ``git checkout -b`` fails.

    See: worktree-process.md §5 (Naming Conventions), §6 (Lifecycle State
    Machine)
    """
    branch_name = f"ticket/{sprint_id}-{ticket_id}-{slug}"

    result = subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to create branch '{branch_name}' in '{worktree_path}': "
            f"{result.stderr.strip()}"
        )

    return branch_name


def validate_worktree(
    worktree_path: Path,
    ticket_path: Path,
    test_command: list[str] | None = None,
) -> bool:
    """Validate a worktree before the controller initiates a merge-back.

    Performs three checks as specified in the design document:

    1. **Tests pass**: runs the project's test suite (``uv run pytest`` by
       default) from within ``worktree_path``.
    2. **Clean working tree**: verifies ``git status --porcelain`` returns
       empty output (no untracked files or staged-but-uncommitted changes).
    3. **Ticket status is ``done``**: reads ``ticket_path`` and verifies
       the YAML frontmatter ``status`` field equals ``"done"``.

    Parameters:
        worktree_path: Absolute path to the worktree directory to validate.
        ticket_path: Absolute path to the ticket markdown file. The path
            must be within ``worktree_path`` (the programmer agent writes
            to the copy inside the worktree).
        test_command: Command (as an argv list) used to run the test suite.
            Defaults to ``["uv", "run", "pytest"]``. Callers (e.g. tests)
            may inject a fast stub command such as ``["true"]``.

    Returns:
        ``True`` if all three checks pass, ``False`` otherwise. The caller
        is responsible for deciding whether to retry or escalate. This
        function never raises for a failed check — only truly unexpected
        errors (which are not expected in normal operation) would
        propagate.

    See: worktree-process.md §7 (Pre-Completion Validation)
    """
    command = test_command if test_command is not None else _DEFAULT_TEST_COMMAND

    tests_result = subprocess.run(
        command,
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if tests_result.returncode != 0:
        return False

    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
    )
    if status_result.stdout.strip() != "":
        return False

    try:
        fm = read_frontmatter(ticket_path)
    except OSError:
        return False

    return fm.get("status") == "done"


def merge_ticket_branch(
    repo_root: Path,
    sprint_branch: str,
    ticket_branch: str,
) -> None:
    """Merge a completed ticket branch into the sprint branch.

    Checks out ``sprint_branch`` in ``repo_root``, then attempts a
    fast-forward merge first. If the sprint branch has advanced since the
    worktree was created, falls back to a standard merge commit
    (``--no-ff``). Rebase is explicitly prohibited — it destroys the
    per-ticket branch history.

    If ``git merge`` reports a conflict, this function aborts the merge and
    raises ``MergeConflictError``. This function does not have a
    ``sprint_dir`` parameter and does not write any audit state itself —
    the caller (the controller) is responsible for catching
    ``MergeConflictError``, writing a ``conflict`` state to the audit
    record, retaining the worktree, and escalating to the stakeholder.

    Parameters:
        repo_root: Absolute path to the repository root (main working tree).
        sprint_branch: Name of the sprint branch to merge into
            (e.g. ``"sprint/022-worktree-process-for-parallel-ticket-execution"``).
        ticket_branch: Name of the ticket branch to merge from
            (e.g. ``"ticket/022-003-stub-worktree-module"``).

    Returns:
        ``None`` on successful merge.

    Raises:
        RuntimeError: If checkout or the merge command fails for any
            reason other than a conflict.
        MergeConflictError: If a merge conflict is detected. The merge is
            aborted (working tree left clean) before this is raised.

    See: worktree-process.md §8 (Merge Strategy and Conflict Resolution)
    """
    checkout = subprocess.run(
        ["git", "checkout", sprint_branch],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if checkout.returncode != 0:
        raise RuntimeError(
            f"Failed to checkout '{sprint_branch}': {checkout.stderr.strip()}"
        )

    ff_merge = subprocess.run(
        ["git", "merge", "--ff-only", ticket_branch],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if ff_merge.returncode == 0:
        return

    merge = subprocess.run(
        ["git", "merge", "--no-ff", ticket_branch, "-m", f"Merge {ticket_branch}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if merge.returncode != 0:
        conflict_result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        conflicted = [
            f.strip()
            for f in conflict_result.stdout.strip().split("\n")
            if f.strip()
        ]
        subprocess.run(
            ["git", "merge", "--abort"], cwd=repo_root, capture_output=True
        )
        raise MergeConflictError(
            f"Merge conflict merging '{ticket_branch}' into '{sprint_branch}': "
            f"{merge.stderr.strip()}",
            conflicted_files=conflicted,
        )


def cleanup_worktree(
    repo_root: Path,
    worktree_path: Path,
    ticket_branch: str,
    keep_branch: bool = False,
) -> None:
    """Remove a worktree and optionally delete its ticket branch.

    Runs ``git worktree remove --force <worktree_path>`` from ``repo_root``.
    The ``--force`` flag handles lingering lock files.

    If ``keep_branch`` is ``False`` (the default, used after a successful
    merge), also runs ``git branch -d <ticket_branch>`` to delete the now-
    merged branch.

    If ``keep_branch`` is ``True`` (used on failure or conflict), the branch
    is retained so a human can inspect the partial work.

    Parameters:
        repo_root: Absolute path to the repository root (main working tree).
        worktree_path: Absolute path to the worktree directory to remove.
        ticket_branch: Name of the per-ticket branch
            (e.g. ``"ticket/022-003-stub-worktree-module"``).
        keep_branch: When ``True``, skip the ``git branch -d`` step and
            retain the branch. Default is ``False`` (delete the branch).

    Returns:
        ``None``.

    Raises:
        RuntimeError: If ``git worktree remove`` fails for a reason other
            than the worktree already being gone, or if ``git branch -d``
            fails (e.g. the branch is not fully merged).

    See: worktree-process.md §9 (Cleanup Rules)

    Idempotent: calling this function again after the worktree has already
    been removed does not raise — a missing ``worktree_path`` or a
    "not a working tree" error from git is treated as success.
    """
    worktree_path = Path(worktree_path)

    if worktree_path.exists():
        result = subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "is not a working tree" not in stderr and "not a working tree" not in stderr:
                raise RuntimeError(
                    f"Failed to remove worktree '{worktree_path}': {stderr}"
                )
    else:
        # Worktree directory is already gone. Still ask git to prune/remove
        # its registration in case metadata lingers; ignore failures since
        # the desired end state (no worktree) is already achieved.
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )

    if not keep_branch:
        branch_exists = subprocess.run(
            ["git", "rev-parse", "--verify", ticket_branch],
            cwd=repo_root,
            capture_output=True,
            text=True,
        ).returncode == 0

        if branch_exists:
            delete_result = subprocess.run(
                ["git", "branch", "-d", ticket_branch],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if delete_result.returncode != 0:
                raise RuntimeError(
                    f"Failed to delete branch '{ticket_branch}': "
                    f"{delete_result.stderr.strip()}"
                )


def _parse_ticket_worktrees(repo_root: Path, sprint_id: str) -> dict[str, dict]:
    """Parse ``git worktree list --porcelain`` for live ticket worktrees.

    Reuses the block-parsing technique from
    ``clasi.tools.artifact_tools._prune_sprint_worktrees``, but matches
    branches of the form ``refs/heads/ticket/<sprint_id>-*`` rather than a
    single sprint branch.

    Returns a dict keyed by branch name (e.g.
    ``"ticket/018-007-some-slug"``), each value a dict with ``path`` and
    ``branch`` keys.
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    branch_prefix = f"refs/heads/ticket/{sprint_id}-"
    live: dict[str, dict] = {}

    current_path: str | None = None
    is_main = True  # first block is always the main worktree

    for line in result.stdout.splitlines():
        line = line.rstrip()
        if line.startswith("worktree "):
            current_path = line[len("worktree "):]
        elif line == "":
            if is_main:
                is_main = False
            current_path = None
        elif line.startswith("branch ") and not is_main and current_path is not None:
            ref = line[len("branch "):]
            if ref.startswith(branch_prefix):
                branch_name = ref[len("refs/heads/"):]
                live[branch_name] = {
                    "path": current_path,
                    "branch": branch_name,
                }

    return live


def _ticket_id_from_branch(branch: str, sprint_id: str) -> str:
    """Extract the ticket id from a ``ticket/<sprint_id>-<ticket_id>-<slug>``
    branch name.
    """
    remainder = branch[len(f"ticket/{sprint_id}-"):]
    return remainder.split("-", 1)[0]


def reconcile_worktrees(repo_root: Path, sprint_dir: Path) -> dict:
    """Reconcile live ticket worktrees against the audit record.

    This is the standing cleanup engine that prevents worktree-directory
    accumulation. It reads the sprint's audit record (via
    ``read_audit_record``) and the live output of
    ``git worktree list --porcelain`` (from ``cwd=repo_root``), matching
    branches of the form ``ticket/<sprint_id>-*`` (``sprint_id`` is derived
    from ``sprint_dir``'s directory name, e.g.
    ``018-worktree-...`` -> ``018``). Each live ticket worktree is
    classified using the audit state plus live git state:

    - **merged-not-cleaned**: audit state is ``merged`` and the ticket
      branch is an ancestor of the sprint branch (fully merged). Cleaned up
      via ``cleanup_worktree(..., keep_branch=False)`` (worktree AND branch
      removed); audit updated to ``cleaned_up``.
    - **clean-but-abandoned**: ``git status --porcelain`` in the worktree
      is empty and the audit state is not ``in_progress``. Cleaned up via
      ``cleanup_worktree(..., keep_branch=True)`` (worktree removed, branch
      retained); audit updated to ``cleaned_up``.
    - **ambiguous**: the worktree has a dirty tree, or the audit state is
      ``failed``/``conflict``/``in_progress``. Left untouched and reported
      in ``escalated``.

    Two edge cases are detected and reported in ``rogue`` without
    triggering any cleanup action:

    - An audit entry whose worktree path no longer appears in
      ``git worktree list`` (already gone). The audit record is reconciled
      (marked ``cleaned_up`` if not already) and the entry is noted.
    - A live ``ticket/<sprint_id>-*`` worktree with no matching audit entry
      (created outside the tracked lifecycle).

    This function is pure of any prompting or interactive decision-making:
    it classifies, safely auto-cleans the unambiguous cases, and returns
    the rest for the caller (a human or the controller) to decide. It is
    idempotent — calling it twice in a row with no intervening state
    change returns ``{"cleaned": [], "escalated": [...], "rogue": []}`` on
    the second call, since the first call already cleaned or reconciled
    everything it safely could.

    Parameters:
        repo_root: Absolute path to the repository root (main working
            tree).
        sprint_dir: Absolute path to the sprint directory. Its final path
            component's leading ``<digits>`` segment (e.g. ``"018"`` from
            ``018-worktree-...``) is used as the sprint id for both branch
            matching and audit lookups, and its basename is used as the
            sprint branch name prefix (``sprint/<sprint_dir_name>``).

    Returns:
        A dict with three keys: ``cleaned``, ``escalated``, and ``rogue``.
        Each is a list of dicts describing the ticket_id/path/branch/reason
        sufficient for a human or the controller to act on.

    Raises:
        json.JSONDecodeError: If the audit file exists but is malformed
            (propagated from ``read_audit_record``). No other exceptions
            are expected in normal operation.

    See: worktree-process.md §10 (Audit and Recovery State), and the
    "Cleanup Discipline" table in the originating issue.
    """
    repo_root = Path(repo_root)
    sprint_dir = Path(sprint_dir)
    sprint_dir_name = sprint_dir.name
    sprint_id_match = re.match(r"(\d+)", sprint_dir_name)
    sprint_id = sprint_id_match.group(1) if sprint_id_match else sprint_dir_name
    sprint_branch = f"sprint/{sprint_dir_name}"

    audit = read_audit_record(sprint_dir)
    audit_entries = audit.get("worktrees", [])
    audit_by_ticket = {str(e.get("ticket_id")): e for e in audit_entries}

    live_by_branch = _parse_ticket_worktrees(repo_root, sprint_id)
    live_ticket_ids = {
        _ticket_id_from_branch(branch, sprint_id): info
        for branch, info in live_by_branch.items()
    }

    cleaned: list[dict] = []
    escalated: list[dict] = []
    rogue: list[dict] = []

    handled_ticket_ids: set[str] = set()

    # Pass 1: audit entries with a live worktree -- classify and act.
    for ticket_id, entry in audit_by_ticket.items():
        live_info = live_ticket_ids.get(ticket_id)
        if live_info is None:
            handled_ticket_ids.add(ticket_id)
            if entry.get("state") == "cleaned_up":
                # Already reconciled on a prior call -- nothing new to
                # report. This branch is what makes the function
                # idempotent across repeated calls.
                continue
            # Edge case: audit entry present but no live worktree. Already
            # gone -- reconcile the audit record and report it once.
            write_audit_record(
                sprint_dir, {"ticket_id": ticket_id, "state": "cleaned_up"}
            )
            rogue.append(
                {
                    "ticket_id": ticket_id,
                    "path": entry.get("path"),
                    "branch": entry.get("branch"),
                    "reason": "audit entry with no live worktree (already gone)",
                }
            )
            continue

        handled_ticket_ids.add(ticket_id)
        path = live_info["path"]
        branch = live_info["branch"]
        state = entry.get("state")

        if state == "merged":
            merged_check = subprocess.run(
                ["git", "merge-base", "--is-ancestor", branch, sprint_branch],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if merged_check.returncode == 0:
                cleanup_worktree(repo_root, Path(path), branch, keep_branch=False)
                write_audit_record(
                    sprint_dir, {"ticket_id": ticket_id, "state": "cleaned_up"}
                )
                cleaned.append(
                    {
                        "ticket_id": ticket_id,
                        "path": path,
                        "branch": branch,
                        "reason": "merged-not-cleaned",
                    }
                )
                continue
            # Audit says "merged" but the branch isn't actually an
            # ancestor of the sprint branch yet -- ambiguous, don't touch.
            escalated.append(
                {
                    "ticket_id": ticket_id,
                    "path": path,
                    "branch": branch,
                    "reason": "audit state merged but branch not yet an "
                    "ancestor of the sprint branch",
                }
            )
            continue

        if state in ("failed", "conflict", "in_progress"):
            escalated.append(
                {
                    "ticket_id": ticket_id,
                    "path": path,
                    "branch": branch,
                    "reason": f"ambiguous audit state: {state}",
                }
            )
            continue

        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path,
            capture_output=True,
            text=True,
        )
        if status_result.stdout.strip() == "":
            cleanup_worktree(repo_root, Path(path), branch, keep_branch=True)
            write_audit_record(
                sprint_dir, {"ticket_id": ticket_id, "state": "cleaned_up"}
            )
            cleaned.append(
                {
                    "ticket_id": ticket_id,
                    "path": path,
                    "branch": branch,
                    "reason": "clean-but-abandoned",
                }
            )
        else:
            escalated.append(
                {
                    "ticket_id": ticket_id,
                    "path": path,
                    "branch": branch,
                    "reason": "dirty working tree",
                }
            )

    # Pass 2: live worktrees with no audit entry at all -- rogue.
    for ticket_id, live_info in live_ticket_ids.items():
        if ticket_id in handled_ticket_ids:
            continue
        rogue.append(
            {
                "ticket_id": ticket_id,
                "path": live_info["path"],
                "branch": live_info["branch"],
                "reason": "live worktree with no audit entry (rogue)",
            }
        )

    return {"cleaned": cleaned, "escalated": escalated, "rogue": rogue}


def write_audit_record(sprint_dir: Path, event: dict) -> None:
    """Write or update the sprint-local worktree audit record.

    The audit file is located at
    ``<sprint_dir>/.worktree-audit.json``. Uses an atomic write
    (write to a temp file, then rename) to prevent partial writes from
    corrupting the audit file.

    If the audit file does not exist, it is created. If it exists, the
    ``event`` dict is merged into the appropriate entry in the
    ``worktrees`` array, matched by ``ticket_id``. If no existing entry
    matches, a new entry is appended.

    The ``event`` dict must contain at minimum a ``ticket_id`` key and a
    ``state`` key. Additional keys (``path``, ``branch``, ``created_at``,
    ``merged_at``, ``failed_at``, ``error``) are written as provided.

    Parameters:
        sprint_dir: Absolute path to the sprint directory
            (e.g. ``docs/clasi/sprints/022-worktree-process-for-parallel-ticket-execution``).
        event: Dictionary describing the state transition. Must contain
            ``ticket_id`` and ``state``. See the audit schema in the spec.

    Returns:
        ``None``.

    Raises:
        ValueError: If ``event`` is missing the ``ticket_id`` or ``state``
            key.
        OSError: If the audit file cannot be written.

    See: worktree-process.md §10 (Audit and Recovery State)
    """
    if "ticket_id" not in event or "state" not in event:
        raise ValueError(
            "write_audit_record: event must contain 'ticket_id' and 'state' keys"
        )

    sprint_dir = Path(sprint_dir)
    final_path = sprint_dir / ".worktree-audit.json"
    tmp_path = sprint_dir / ".worktree-audit.json.tmp"

    record = read_audit_record(sprint_dir)

    worktrees = record.setdefault("worktrees", [])
    ticket_id = event["ticket_id"]

    for entry in worktrees:
        if entry.get("ticket_id") == ticket_id:
            entry.update(event)
            break
    else:
        worktrees.append(dict(event))

    sprint_dir.mkdir(parents=True, exist_ok=True)
    tmp_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    os.replace(tmp_path, final_path)


def read_audit_record(sprint_dir: Path) -> dict:
    """Read the sprint-local worktree audit record.

    Reads ``<sprint_dir>/.worktree-audit.json`` and returns its contents
    as a Python dict. Used by the controller on session start to discover
    any worktrees that were not cleaned up after a crash.

    If the audit file does not exist, returns an empty dict with a
    ``worktrees`` key set to an empty list (not an error — the file is
    created lazily on the first ``write_audit_record`` call).

    Parameters:
        sprint_dir: Absolute path to the sprint directory
            (e.g. ``docs/clasi/sprints/022-worktree-process-for-parallel-ticket-execution``).

    Returns:
        A dict with the structure described in the spec's audit schema,
        or ``{"sprint_id": None, "worktrees": []}`` if the file does not
        exist.

    Raises:
        json.JSONDecodeError: If the audit file exists but is malformed.

    See: worktree-process.md §10 (Audit and Recovery State)
    """
    audit_path = Path(sprint_dir) / ".worktree-audit.json"

    if not audit_path.exists():
        return {"sprint_id": None, "worktrees": []}

    content = audit_path.read_text(encoding="utf-8")
    return json.loads(content)


def check_independence(tickets: list[dict]) -> list[list[str]]:
    """Partition tickets into groups of mutually independent tickets.

    Applies the static file-set overlap algorithm described in the spec:

    1. For each ticket, extract the set of files it plans to create or
       modify from ``files_to_create`` / ``files_to_modify`` frontmatter
       keys, or by parsing a ``## Files to create or modify`` heading (or
       the equivalent ``###`` level, or separate "Files to create" /
       "Files to modify" headings) in the ticket body, collecting list
       items until the next heading of equal or higher level. If neither
       source yields any files, the ticket is treated as dependent on all
       others via an "unknown" sentinel.
    2. Two tickets are dependent if their file sets overlap (source file
       overlap) or if the derived test-module paths for their source files
       overlap (test module overlap).
    3. Tickets within each returned group are pairwise independent (every
       pair in a group has no file/test overlap and no unknown sentinel)
       and may run in parallel. Groups themselves run in the serial order
       implied by their ``depends-on`` frontmatter — a ticket is placed no
       earlier than the group immediately after any ticket it depends on.
       Grouping uses greedy first-fit assignment (a ticket joins the
       earliest existing group with no conflicting member) rather than
       naive connected components, since dependence is not transitive for
       grouping purposes: if A conflicts with C but B conflicts with
       neither, B must not be forced apart from both merely because A and
       C are each independent of B.

    Precision note: Static extraction is low-precision. False positives
    (spurious dependence) cause a fallback to serial execution — a safe
    degradation. False negatives (missed dependence) cause merge conflicts,
    which the controller escalates to the stakeholder (see merge strategy
    in the spec). See also: Q3 in the Open Questions section of the spec.

    Parameters:
        tickets: List of ticket dicts, each containing at minimum:
            - ``id``: ticket identifier string.
            - ``files_to_create``: (optional) list of file path strings.
            - ``files_to_modify``: (optional) list of file path strings.
            - ``body``: (optional) full markdown body string, parsed for
              file lists if frontmatter keys are absent.

    Returns:
        A list of groups, where each group is a list of ticket ID strings.
        Tickets within a group are independent and may run in parallel.
        Example: ``[["001", "003"], ["002"]]`` means tickets 001 and 003
        can run in parallel, then ticket 002 runs serially.

    See: worktree-process.md §3 (Ticket Independence Determination)
    """
    ids = [str(t.get("id", "")) for t in tickets]
    id_set = set(ids)
    file_sets: dict[str, frozenset[str]] = {}
    test_sets: dict[str, frozenset[str]] = {}
    depends_on: dict[str, list[str]] = {}

    for ticket in tickets:
        ticket_id = str(ticket.get("id", ""))
        files = _extract_ticket_files(ticket)
        file_sets[ticket_id] = files
        if files == _UNKNOWN_FILES:
            test_sets[ticket_id] = _UNKNOWN_FILES
        else:
            # Compare against both the derived test_<stem>.py basename for
            # each source file AND the source files' own basenames, so
            # that a ticket directly touching tests/test_foo.py is
            # correctly detected as overlapping with another ticket's
            # derived test_foo.py for clasi/foo.py.
            test_sets[ticket_id] = frozenset(
                {_derive_test_basename(f) for f in files}
                | {Path(f).name for f in files}
            )

        dep = ticket.get("depends-on") or ticket.get("depends_on") or []
        if isinstance(dep, str):
            dep = [dep] if dep else []
        depends_on[ticket_id] = [str(d) for d in dep if str(d) in id_set]

    # Deterministic processing order: topological sort over depends-on,
    # tie-broken by ticket id ascending (Kahn's algorithm with a
    # min-by-id frontier).
    order = _topo_sort_tickets(ids, depends_on)

    # Greedy first-fit graph coloring over the *conflict* (dependence)
    # relation: assign each ticket, in `order`, to the earliest existing
    # group with no conflicting member, subject to the floor imposed by
    # its own dependencies (a ticket may not be placed in a group at or
    # before any of its dependencies' groups — depends-on is a hard
    # sequencing requirement, not just a file-conflict signal). This is
    # NOT the same as connected components of the dependence graph:
    # dependence is not transitive for grouping purposes (A conflicts
    # with C does not mean B, which is independent of both A and C,
    # must be split away from both), so first-fit coloring is used
    # instead to guarantee every returned group is pairwise independent.
    groups: list[list[str]] = []
    group_index_of: dict[str, int] = {}

    for tid in order:
        min_allowed_index = 0
        for dep_id in depends_on[tid]:
            dep_index = group_index_of.get(dep_id)
            if dep_index is not None:
                min_allowed_index = max(min_allowed_index, dep_index + 1)

        placed_index: int | None = None
        for idx in range(min_allowed_index, len(groups)):
            if all(
                not _tickets_dependent(tid, member, file_sets, test_sets)
                for member in groups[idx]
            ):
                groups[idx].append(tid)
                placed_index = idx
                break

        if placed_index is None:
            groups.append([tid])
            placed_index = len(groups) - 1

        group_index_of[tid] = placed_index

    return [sorted(group) for group in groups]


def _tickets_dependent(
    a: str,
    b: str,
    file_sets: dict[str, frozenset[str]],
    test_sets: dict[str, frozenset[str]],
) -> bool:
    """Return True if tickets a and b are dependent per the spec's rules."""
    files_a = file_sets[a]
    files_b = file_sets[b]
    if files_a == _UNKNOWN_FILES or files_b == _UNKNOWN_FILES:
        return True
    if files_a & files_b:
        return True
    if test_sets[a] & test_sets[b]:
        return True
    return False


def _topo_sort_tickets(ids: list[str], depends_on: dict[str, list[str]]) -> list[str]:
    """Topologically sort ticket ids by depends-on, tie-break id ascending.

    Uses Kahn's algorithm with a sorted frontier so that, among all
    tickets whose dependencies are already satisfied at each step, the
    lowest ticket id is emitted next. Callers must pre-filter
    ``depends_on`` values to only reference ids present in ``ids``. Falls
    back to remaining ids in ascending order if a dependency cycle is
    present (defensive; should not occur with well-formed ticket data).
    """
    remaining = set(ids)
    emitted: set[str] = set()
    ordered: list[str] = []

    while remaining:
        ready = sorted(
            tid
            for tid in remaining
            if all(dep in emitted for dep in depends_on.get(tid, []))
        )
        if not ready:
            # Cycle guard: emit remaining ids in ascending order rather
            # than looping forever.
            ready = sorted(remaining)

        chosen = ready[0]
        ordered.append(chosen)
        emitted.add(chosen)
        remaining.discard(chosen)

    return ordered


def _extract_ticket_files(ticket: dict) -> frozenset[str]:
    """Extract a ticket's normalized file set per the priority order.

    Priority: (a) files_to_create/files_to_modify frontmatter keys,
    (b) parsed "Files to create or modify" section of the ticket body,
    (c) the "unknown" sentinel if neither source yields any files.
    """
    raw_files: list[str] = []

    files_to_create = ticket.get("files_to_create")
    files_to_modify = ticket.get("files_to_modify")
    if files_to_create or files_to_modify:
        raw_files.extend(files_to_create or [])
        raw_files.extend(files_to_modify or [])
    else:
        body = ticket.get("body") or ""
        raw_files = _parse_files_from_body(body)

    if not raw_files:
        return _UNKNOWN_FILES

    normalized = {_normalize_path(f) for f in raw_files}
    normalized.discard("")
    if not normalized:
        return _UNKNOWN_FILES

    return frozenset(normalized)


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def _parse_files_from_body(body: str) -> list[str]:
    """Parse file paths out of "Files to create/modify" headings in a
    ticket's markdown body.

    Accepts heading levels ``##`` or ``###``, and accepts a combined
    heading ("Files to create or modify") or separate headings ("Files to
    create" / "Files to modify"). Collects markdown list items until the
    next heading of equal or higher level.
    """
    lines = body.splitlines()
    files: list[str] = []
    in_section = False
    section_level = 0

    file_heading_re = re.compile(r"files to (create|modify)", re.IGNORECASE)

    for line in lines:
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2)
            if in_section and level <= section_level:
                in_section = False
            if file_heading_re.search(title):
                in_section = True
                section_level = level
                continue
            continue

        if in_section:
            item = _parse_list_item(line)
            if item is not None:
                files.append(item)

    return files


_LIST_ITEM_RE = re.compile(r"^\s*[-*]\s+(.*)$")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def _parse_list_item(line: str) -> str | None:
    """Extract a file path from a markdown list-item line, or None."""
    match = _LIST_ITEM_RE.match(line)
    if not match:
        return None
    rest = match.group(1).strip()
    if not rest:
        return None

    # Prefer an inline-code span (`path/to/file.py`) if present, since list
    # items often carry trailing prose ("— create.").
    code_match = _INLINE_CODE_RE.search(rest)
    if code_match:
        return code_match.group(1).strip()

    # Otherwise take the leading token up to whitespace or punctuation
    # commonly used to separate the path from trailing prose.
    token = re.split(r"\s+[-—]\s+|\s+\(", rest, maxsplit=1)[0].strip()
    token = token.rstrip(".,;:")
    return token or None


def _normalize_path(raw: str) -> str:
    """Normalize a file path to repo-relative POSIX form.

    Strips a leading ``src/`` so that ``src/clasi/foo.py`` and
    ``clasi/foo.py`` are treated as the same file (a footgun called out
    explicitly in the spec).
    """
    path = raw.strip().strip("`").strip()
    if not path:
        return ""
    # Normalize to POSIX separators.
    path = path.replace("\\", "/")
    # Collapse any leading "./" and repeated slashes.
    while path.startswith("./"):
        path = path[2:]
    path = re.sub(r"/+", "/", path).strip("/")
    if path.startswith("src/"):
        path = path[len("src/") :]
    return path


def _derive_test_basename(source_path: str) -> str:
    """Derive the expected test-module basename for a source file path.

    E.g. ``clasi/foo.py`` -> ``test_foo.py``. Non-``.py`` files derive a
    basename from their stem the same way, which is sufficient for
    overlap detection purposes even though such files have no real test
    module.
    """
    stem = Path(source_path).stem
    return f"test_{stem}.py"
