"""Worktree reconciliation, cleanup, and audit-record I/O for CLASI.

This module cleans up git worktrees left behind by other tooling and
tracks their lifecycle state in a sprint-local audit record
(``<sprint_dir>/.worktree-audit.json``). It is used by
``close_sprint``'s worktree-pruning step (``clasi.close``) and by the
``reconcile_worktrees`` MCP tool (``clasi.tools.artifact_tools``).

Historical note: earlier revisions of this module also implemented an
unreachable parallel ticket-execution lifecycle (``create_worktree``,
``create_ticket_branch``, ``validate_worktree``, ``merge_ticket_branch``,
``check_independence``, and their parsing/topo-sort helpers) that no MCP
tool ever exposed. It was deleted as dead code in sprint 032 — see
``docs/design/worktree-process.md`` (retired) for that design's history,
and this module's git history at the sprint 032 tag for the removed
implementation.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

__all__ = [
    "cleanup_worktree",
    "write_audit_record",
    "read_audit_record",
    "reconcile_worktrees",
]


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
            stdin=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "is not a working tree" not in stderr and "not a working tree" not in stderr:
                raise RuntimeError(
                    f"Failed to remove worktree '{worktree_path}': {stderr}"
                )
    else:
        # Worktree directory is already gone. Ask git to prune the stale
        # administrative files for it, rather than re-running `git worktree
        # remove --force <path>` on a path that no longer exists (which
        # errors, and whose error was previously silently ignored). `git
        # worktree prune` takes no path argument -- it sweeps all stale
        # worktree registrations at once -- and succeeds unconditionally,
        # so the desired end state (no worktree, no stale metadata) is
        # achieved either way.
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )

    if not keep_branch:
        branch_exists = subprocess.run(
            ["git", "rev-parse", "--verify", ticket_branch],
            cwd=repo_root,
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        ).returncode == 0

        if branch_exists:
            delete_result = subprocess.run(
                ["git", "branch", "-d", ticket_branch],
                cwd=repo_root,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
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
        stdin=subprocess.DEVNULL,
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
                stdin=subprocess.DEVNULL,
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
            stdin=subprocess.DEVNULL,
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
