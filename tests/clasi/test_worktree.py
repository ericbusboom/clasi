"""Behavioral tests for clasi/worktree.py.

Covers:
- The audit pair (write_audit_record / read_audit_record).
- cleanup_worktree, including its idempotency and the `git worktree prune`
  fix (032/003) for the already-deleted-worktree branch.
- reconcile_worktrees: the standing cleanup engine that classifies live
  ticket worktrees against the audit record (merged-not-cleaned,
  clean-but-abandoned, ambiguous), plus the rogue/already-gone edge cases
  and idempotency.

`worktree.py`'s unreachable parallel-execution lifecycle
(create_worktree, create_ticket_branch, validate_worktree,
merge_ticket_branch, check_independence, and their parsing/topo-sort
helpers) was deleted in sprint 032 -- see worktree.py's module docstring.
The tests below still need *some* live git worktree to reconcile or
clean up, so this module keeps small local helpers (`_add_worktree`,
`_add_ticket_branch`, `_merge_branch`) that build one with raw git
commands, mirroring what the deleted production functions used to do.
These are test-only fixtures, not a reintroduction of the deleted API.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import clasi.worktree as worktree


# ---------------------------------------------------------------------------
# Git repo fixture (pattern reused from tests/unit/test_status/test_reader.py)
# ---------------------------------------------------------------------------


def _git_init(root: Path) -> None:
    """Initialise a throwaway git repo in *root*."""
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=root, check=True, capture_output=True,
    )


def _git_commit(root: Path, message: str = "init") -> None:
    """Stage everything and create a commit."""
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=root, check=True, capture_output=True,
    )


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A throwaway git repo with an initial commit and a sprint branch."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git_init(repo_root)
    (repo_root / "README.md").write_text("hello\n", encoding="utf-8")
    _git_commit(repo_root, "initial")
    # Rename current branch to a known name for predictability across
    # git config defaults (init.defaultBranch may be "main" or "master").
    subprocess.run(
        ["git", "branch", "-m", "sprint/999-test-sprint"],
        cwd=repo_root, check=True, capture_output=True,
    )
    return repo_root


# ---------------------------------------------------------------------------
# Test-only helpers standing in for the deleted create_worktree /
# create_ticket_branch / merge_ticket_branch production functions. The
# surviving functions under test (cleanup_worktree, reconcile_worktrees)
# operate on worktrees/branches that already exist; these helpers build
# that starting state with raw git commands.
# ---------------------------------------------------------------------------


def _add_worktree(repo: Path, sprint_id: str, ticket_id: str) -> Path:
    """Create a sibling detached worktree, mirroring the deleted
    `create_worktree` production function's behavior.
    """
    worktree_path = (repo / ".." / f"worktree-{sprint_id}-{ticket_id}").resolve()
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree_path), "HEAD"],
        cwd=repo, check=True, capture_output=True,
    )
    return worktree_path


def _add_ticket_branch(
    worktree_path: Path, sprint_id: str, ticket_id: str, slug: str
) -> str:
    """Create and check out a per-ticket branch inside a worktree,
    mirroring the deleted `create_ticket_branch` production function's
    naming (``ticket/<sprint_id>-<ticket_id>-<slug>``).
    """
    branch_name = f"ticket/{sprint_id}-{ticket_id}-{slug}"
    subprocess.run(
        ["git", "checkout", "-b", branch_name],
        cwd=worktree_path, check=True, capture_output=True,
    )
    return branch_name


def _merge_branch(repo: Path, sprint_branch: str, ticket_branch: str) -> None:
    """Merge a ticket branch into the sprint branch, mirroring the deleted
    `merge_ticket_branch` production function (fast-forward first, falling
    back to --no-ff). Conflict handling is intentionally omitted -- no
    surviving test exercises a merge conflict.
    """
    subprocess.run(
        ["git", "checkout", sprint_branch], cwd=repo, check=True, capture_output=True,
    )
    ff = subprocess.run(
        ["git", "merge", "--ff-only", ticket_branch],
        cwd=repo, capture_output=True, text=True,
    )
    if ff.returncode != 0:
        subprocess.run(
            ["git", "merge", "--no-ff", ticket_branch, "-m", f"Merge {ticket_branch}"],
            cwd=repo, check=True, capture_output=True,
        )


# ---------------------------------------------------------------------------
# Audit pair: write_audit_record / read_audit_record
# ---------------------------------------------------------------------------


class TestAuditRecord:
    def test_write_creates_new_record(self, tmp_path: Path) -> None:
        worktree.write_audit_record(
            tmp_path, {"ticket_id": "001", "state": "worktree_created"}
        )
        record = worktree.read_audit_record(tmp_path)
        assert record["worktrees"] == [
            {"ticket_id": "001", "state": "worktree_created"}
        ]

    def test_write_merges_by_ticket_id(self, tmp_path: Path) -> None:
        worktree.write_audit_record(
            tmp_path, {"ticket_id": "001", "state": "worktree_created", "path": "/a"}
        )
        worktree.write_audit_record(
            tmp_path, {"ticket_id": "001", "state": "branch_created"}
        )
        record = worktree.read_audit_record(tmp_path)
        assert len(record["worktrees"]) == 1
        entry = record["worktrees"][0]
        assert entry["ticket_id"] == "001"
        assert entry["state"] == "branch_created"
        assert entry["path"] == "/a"

    def test_write_appends_new_ticket(self, tmp_path: Path) -> None:
        worktree.write_audit_record(
            tmp_path, {"ticket_id": "001", "state": "worktree_created"}
        )
        worktree.write_audit_record(
            tmp_path, {"ticket_id": "002", "state": "worktree_created"}
        )
        record = worktree.read_audit_record(tmp_path)
        assert {e["ticket_id"] for e in record["worktrees"]} == {"001", "002"}

    def test_atomic_write_leaves_no_tmp_file(self, tmp_path: Path) -> None:
        worktree.write_audit_record(
            tmp_path, {"ticket_id": "001", "state": "worktree_created"}
        )
        assert not (tmp_path / ".worktree-audit.json.tmp").exists()
        assert (tmp_path / ".worktree-audit.json").exists()

    def test_missing_ticket_id_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            worktree.write_audit_record(tmp_path, {"state": "worktree_created"})

    def test_missing_state_raises_value_error(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            worktree.write_audit_record(tmp_path, {"ticket_id": "001"})

    def test_read_absent_file_returns_default(self, tmp_path: Path) -> None:
        record = worktree.read_audit_record(tmp_path)
        assert record == {"sprint_id": None, "worktrees": []}

    def test_read_malformed_json_propagates(self, tmp_path: Path) -> None:
        (tmp_path / ".worktree-audit.json").write_text("{not valid json", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            worktree.read_audit_record(tmp_path)


# ---------------------------------------------------------------------------
# cleanup_worktree
# ---------------------------------------------------------------------------


class TestCleanupWorktree:
    def test_removes_worktree_and_deletes_branch(self, repo: Path) -> None:
        wt_path = _add_worktree(repo, "999", "020")
        branch_name = _add_ticket_branch(wt_path, "999", "020", "slug")
        # Merge it so the branch is fully merged and -d succeeds.
        _merge_branch(repo, "sprint/999-test-sprint", branch_name)

        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=False)

        assert not wt_path.exists()
        branch_exists = _run(["git", "rev-parse", "--verify", branch_name], cwd=repo).returncode == 0
        assert branch_exists is False

    def test_keep_branch_true_retains_branch(self, repo: Path) -> None:
        wt_path = _add_worktree(repo, "999", "021")
        branch_name = _add_ticket_branch(wt_path, "999", "021", "slug")

        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=True)

        assert not wt_path.exists()
        branch_exists = _run(["git", "rev-parse", "--verify", branch_name], cwd=repo).returncode == 0
        assert branch_exists is True

        # Cleanup the branch ourselves since we asked to keep it.
        _run(["git", "branch", "-D", branch_name], cwd=repo)

    def test_idempotent_on_already_removed_worktree(self, repo: Path) -> None:
        wt_path = _add_worktree(repo, "999", "022")
        branch_name = _add_ticket_branch(wt_path, "999", "022", "slug")

        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=True)
        # Calling it again on the same (already-removed) worktree must not
        # raise.
        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=True)

        _run(["git", "branch", "-D", branch_name], cwd=repo)

    def test_already_removed_worktree_calls_prune_not_remove(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """032/003 fix: the already-deleted-worktree branch must call
        `git worktree prune` (which succeeds unconditionally) rather than
        re-running `git worktree remove --force <path>` on a path that no
        longer exists and silently swallowing the resulting error.
        """
        wt_path = _add_worktree(repo, "999", "023")
        branch_name = _add_ticket_branch(wt_path, "999", "023", "slug")
        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=True)
        assert not wt_path.exists()

        real_run = subprocess.run
        calls: list[list[str]] = []

        def _spy(args, *a, **kw):
            calls.append(list(args))
            return real_run(args, *a, **kw)

        monkeypatch.setattr(worktree.subprocess, "run", _spy)

        # Second call: worktree_path no longer exists on disk, so this
        # exercises the already-deleted-worktree branch.
        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=True)

        worktree_calls = [c for c in calls if c[:2] == ["git", "worktree"]]
        assert ["git", "worktree", "prune"] in worktree_calls
        assert not any(c[:3] == ["git", "worktree", "remove"] for c in worktree_calls)

        _run(["git", "branch", "-D", branch_name], cwd=repo)


# ---------------------------------------------------------------------------
# reconcile_worktrees: the standing cleanup engine
# ---------------------------------------------------------------------------


@pytest.fixture()
def sprint_dir(repo: Path) -> Path:
    """Sprint directory matching the `repo` fixture's sprint branch name.

    The `repo` fixture's sprint branch is `sprint/999-test-sprint`, so the
    sprint dir's basename must be `999-test-sprint` for
    `reconcile_worktrees` to derive the matching sprint branch name and
    sprint id ("999").
    """
    path = repo.parent / "sprint-artifacts" / "999-test-sprint"
    path.mkdir(parents=True)
    return path


def _make_ticket_worktree(
    repo: Path, ticket_id: str, slug: str = "slug"
) -> tuple[Path, str]:
    """Create a live worktree + ticket branch for `ticket_id` on `repo`."""
    wt_path = _add_worktree(repo, "999", ticket_id)
    branch_name = _add_ticket_branch(wt_path, "999", ticket_id, slug)
    return wt_path, branch_name


class TestReconcileWorktrees:
    def test_all_three_classes_plus_edge_cases_in_one_call(
        self, repo: Path, sprint_dir: Path
    ) -> None:
        """The single highest-value test: all three classifications plus
        both edge cases (rogue live worktree, already-gone audit entry)
        present simultaneously in one `reconcile_worktrees` call.
        """
        # --- merged-not-cleaned: audit says "merged", branch actually
        # merged into the sprint branch.
        merged_wt, merged_branch = _make_ticket_worktree(repo, "001", "merged-slug")
        (merged_wt / "merged.txt").write_text("merged\n", encoding="utf-8")
        _run(["git", "add", "-A"], cwd=merged_wt)
        _run(["git", "commit", "-m", "merged work"], cwd=merged_wt)
        _merge_branch(repo, "sprint/999-test-sprint", merged_branch)
        # _merge_branch checks out the sprint branch as a side effect;
        # switch back to it explicitly for clarity/robustness.
        _run(["git", "checkout", "sprint/999-test-sprint"], cwd=repo)
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "001",
                "state": "merged",
                "path": str(merged_wt),
                "branch": merged_branch,
            },
        )

        # --- clean-but-abandoned: worktree has no uncommitted changes,
        # audit state is some non-terminal, non-in_progress state (e.g.
        # "worktree_created" -- work was done and committed but the ticket
        # lifecycle was abandoned without marking merged).
        abandoned_wt, abandoned_branch = _make_ticket_worktree(
            repo, "002", "abandoned-slug"
        )
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "002",
                "state": "worktree_created",
                "path": str(abandoned_wt),
                "branch": abandoned_branch,
            },
        )

        # --- ambiguous (dirty tree): uncommitted changes present.
        dirty_wt, dirty_branch = _make_ticket_worktree(repo, "003", "dirty-slug")
        (dirty_wt / "untracked.txt").write_text("dirty\n", encoding="utf-8")
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "003",
                "state": "worktree_created",
                "path": str(dirty_wt),
                "branch": dirty_branch,
            },
        )

        # --- ambiguous (audit state failed): clean tree but audit says
        # failed -- must not be touched regardless of tree cleanliness.
        failed_wt, failed_branch = _make_ticket_worktree(repo, "004", "failed-slug")
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "004",
                "state": "failed",
                "path": str(failed_wt),
                "branch": failed_branch,
            },
        )

        # --- rogue: a live ticket/* worktree with no audit entry at all.
        rogue_wt, rogue_branch = _make_ticket_worktree(repo, "005", "rogue-slug")

        # --- already-gone: an audit entry whose worktree no longer exists
        # on disk / in `git worktree list` at all.
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "006",
                "state": "merged",
                "path": str(repo.parent / "worktree-999-006"),
                "branch": "ticket/999-006-gone-slug",
            },
        )

        result = worktree.reconcile_worktrees(repo, sprint_dir)

        # --- cleaned: 001 (merged-not-cleaned) and 002 (clean-but-abandoned).
        cleaned_ids = {c["ticket_id"] for c in result["cleaned"]}
        assert cleaned_ids == {"001", "002"}

        cleaned_by_id = {c["ticket_id"]: c for c in result["cleaned"]}
        assert cleaned_by_id["001"]["reason"] == "merged-not-cleaned"
        assert cleaned_by_id["002"]["reason"] == "clean-but-abandoned"

        # 001: worktree dir AND branch removed.
        assert not merged_wt.exists()
        assert (
            _run(["git", "rev-parse", "--verify", merged_branch], cwd=repo).returncode
            != 0
        )

        # 002: worktree dir removed, branch RETAINED.
        assert not abandoned_wt.exists()
        assert (
            _run(
                ["git", "rev-parse", "--verify", abandoned_branch], cwd=repo
            ).returncode
            == 0
        )

        # --- escalated: 003 (dirty) and 004 (failed audit state), untouched.
        escalated_ids = {e["ticket_id"] for e in result["escalated"]}
        assert escalated_ids == {"003", "004"}
        assert dirty_wt.exists()
        assert failed_wt.exists()
        assert (
            _run(["git", "rev-parse", "--verify", dirty_branch], cwd=repo).returncode
            == 0
        )
        assert (
            _run(["git", "rev-parse", "--verify", failed_branch], cwd=repo).returncode
            == 0
        )

        # --- rogue: 005 (live, no audit entry) and 006 (audit entry, no
        # live worktree -- already gone) both reported, neither raises.
        rogue_ids = {r["ticket_id"] for r in result["rogue"]}
        assert rogue_ids == {"005", "006"}
        # 005 is rogue but untouched -- reconcile_worktrees never deletes
        # a worktree it can't attribute to an audit trail.
        assert rogue_wt.exists()

        # Audit record for 006 (already-gone) reconciled to cleaned_up.
        audit = worktree.read_audit_record(sprint_dir)
        entry_006 = next(
            e for e in audit["worktrees"] if e["ticket_id"] == "006"
        )
        assert entry_006["state"] == "cleaned_up"

        # No ticket/999-* worktree survives except those in escalated (003,
        # 004) and the untouched rogue one (005), which is explicitly
        # reported and left alone by design.
        remaining = _run(
            ["git", "worktree", "list", "--porcelain"], cwd=repo
        ).stdout
        assert "ticket/999-001-" not in remaining
        assert "ticket/999-002-" not in remaining
        assert "ticket/999-003-" in remaining
        assert "ticket/999-004-" in remaining
        assert "ticket/999-005-" in remaining

        # --- idempotency: a second consecutive call with no state change
        # cleans nothing new. 003/004/005 are still present and ambiguous/
        # rogue on the second pass too.
        second_result = worktree.reconcile_worktrees(repo, sprint_dir)
        assert second_result["cleaned"] == []
        second_escalated_ids = {e["ticket_id"] for e in second_result["escalated"]}
        assert second_escalated_ids == {"003", "004"}
        second_rogue_ids = {r["ticket_id"] for r in second_result["rogue"]}
        assert second_rogue_ids == {"005"}

        # Cleanup: remove the still-live worktrees/branches so the test
        # doesn't leak state (they're outside the tmp_path fixture's repo
        # dir, as siblings, so pytest won't clean them automatically).
        for wt, branch in (
            (dirty_wt, dirty_branch),
            (failed_wt, failed_branch),
            (rogue_wt, rogue_branch),
        ):
            _run(["git", "worktree", "remove", "--force", str(wt)], cwd=repo)
            _run(["git", "branch", "-D", branch], cwd=repo)
        _run(["git", "branch", "-D", abandoned_branch], cwd=repo)

    def test_no_audit_entry_and_no_live_worktree_returns_empty(
        self, repo: Path, sprint_dir: Path
    ) -> None:
        """No worktrees at all -> everything empty, no raise."""
        result = worktree.reconcile_worktrees(repo, sprint_dir)
        assert result == {"cleaned": [], "escalated": [], "rogue": []}

    def test_idempotent_when_nothing_to_clean_from_the_start(
        self, repo: Path, sprint_dir: Path
    ) -> None:
        first = worktree.reconcile_worktrees(repo, sprint_dir)
        second = worktree.reconcile_worktrees(repo, sprint_dir)
        assert first == {"cleaned": [], "escalated": [], "rogue": []}
        assert second == {"cleaned": [], "escalated": [], "rogue": []}

    def test_merged_audit_state_but_not_actually_merged_is_escalated(
        self, repo: Path, sprint_dir: Path
    ) -> None:
        """Audit claims "merged" but the branch isn't actually an ancestor
        of the sprint branch -- must be treated as ambiguous, not
        force-cleaned.
        """
        wt_path, branch_name = _make_ticket_worktree(repo, "007", "unmerged-slug")
        (wt_path / "work.txt").write_text("unmerged work\n", encoding="utf-8")
        _run(["git", "add", "-A"], cwd=wt_path)
        _run(["git", "commit", "-m", "unmerged work"], cwd=wt_path)
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "007",
                "state": "merged",
                "path": str(wt_path),
                "branch": branch_name,
            },
        )

        result = worktree.reconcile_worktrees(repo, sprint_dir)

        assert result["cleaned"] == []
        escalated_ids = {e["ticket_id"] for e in result["escalated"]}
        assert "007" in escalated_ids
        assert wt_path.exists()

        _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)
        _run(["git", "branch", "-D", branch_name], cwd=repo)

    def test_in_progress_audit_state_is_escalated_even_if_clean(
        self, repo: Path, sprint_dir: Path
    ) -> None:
        """A clean tree with audit state in_progress must still be
        escalated, never auto-cleaned (work may still be underway).
        """
        wt_path, branch_name = _make_ticket_worktree(repo, "008", "inprogress-slug")
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "008",
                "state": "in_progress",
                "path": str(wt_path),
                "branch": branch_name,
            },
        )

        result = worktree.reconcile_worktrees(repo, sprint_dir)

        assert result["cleaned"] == []
        escalated_ids = {e["ticket_id"] for e in result["escalated"]}
        assert "008" in escalated_ids
        assert wt_path.exists()

        _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)
        _run(["git", "branch", "-D", branch_name], cwd=repo)

    def test_conflict_audit_state_is_escalated(
        self, repo: Path, sprint_dir: Path
    ) -> None:
        wt_path, branch_name = _make_ticket_worktree(repo, "009", "conflict-slug")
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "009",
                "state": "conflict",
                "path": str(wt_path),
                "branch": branch_name,
            },
        )

        result = worktree.reconcile_worktrees(repo, sprint_dir)

        assert result["cleaned"] == []
        escalated_ids = {e["ticket_id"] for e in result["escalated"]}
        assert "009" in escalated_ids
        assert wt_path.exists()

        _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)
        _run(["git", "branch", "-D", branch_name], cwd=repo)

    def test_never_raises_on_corrupt_state_is_not_expected_but_bad_json_propagates(
        self, repo: Path, sprint_dir: Path
    ) -> None:
        """Corrupt audit JSON is a genuine unexpected error and must
        propagate (via read_audit_record), unlike normal ambiguous cases.
        """
        (sprint_dir / ".worktree-audit.json").write_text(
            "{not valid json", encoding="utf-8"
        )
        with pytest.raises(json.JSONDecodeError):
            worktree.reconcile_worktrees(repo, sprint_dir)


# ---------------------------------------------------------------------------
# stdin-closed regression (031/008 follow-up)
# ---------------------------------------------------------------------------
#
# close_sprint's prune step calls reconcile_worktrees unconditionally on
# every close (see clasi.close._prune_sprint_worktrees). Its git
# subprocess calls -- and cleanup_worktree's, which it calls internally
# -- must not inherit the calling process's stdin, for the same reason
# the sibling fixes in clasi.gitutil.run_git and clasi.close's test-runner
# subprocess exist: through the MCP server, inherited stdin is a
# JSON-RPC pipe that never delivers input, so a git subcommand that
# unexpectedly tries to read it would hang the calling tool forever.


class TestGitSubprocessCallsCloseStdin:
    def test_cleanup_worktree_closes_stdin_on_every_git_call(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wt_path = _add_worktree(repo, "999", "030")
        branch_name = _add_ticket_branch(wt_path, "999", "030", "slug")

        real_run = subprocess.run
        calls: list[dict] = []

        def _spy(*args, **kwargs):
            calls.append(kwargs)
            return real_run(*args, **kwargs)

        monkeypatch.setattr(worktree.subprocess, "run", _spy)

        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=False)

        assert calls, "expected cleanup_worktree to make at least one git call"
        for kwargs in calls:
            assert kwargs.get("stdin") is subprocess.DEVNULL

    def test_reconcile_worktrees_closes_stdin_on_every_git_call(
        self, repo: Path, sprint_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        wt_path, branch_name = _make_ticket_worktree(repo, "031", "stdin-slug")
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "031",
                "state": "worktree_created",
                "path": str(wt_path),
                "branch": branch_name,
            },
        )

        real_run = subprocess.run
        calls: list[dict] = []

        def _spy(*args, **kwargs):
            calls.append(kwargs)
            return real_run(*args, **kwargs)

        monkeypatch.setattr(worktree.subprocess, "run", _spy)

        worktree.reconcile_worktrees(repo, sprint_dir)

        assert calls, "expected reconcile_worktrees to make at least one git call"
        for kwargs in calls:
            assert kwargs.get("stdin") is subprocess.DEVNULL

    def test_reconcile_worktrees_merged_state_closes_stdin_on_merge_base_check(
        self, repo: Path, sprint_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The "merged" audit-state branch runs a distinct git call
        (``git merge-base --is-ancestor``) that the other
        reconcile_worktrees test above never reaches -- covered
        separately here."""
        wt_path, branch_name = _make_ticket_worktree(repo, "032", "merged-slug")
        (wt_path / "merged.txt").write_text("merged\n", encoding="utf-8")
        _run(["git", "add", "-A"], cwd=wt_path)
        _run(["git", "commit", "-m", "merged work"], cwd=wt_path)
        _merge_branch(repo, "sprint/999-test-sprint", branch_name)
        _run(["git", "checkout", "sprint/999-test-sprint"], cwd=repo)
        worktree.write_audit_record(
            sprint_dir,
            {
                "ticket_id": "032",
                "state": "merged",
                "path": str(wt_path),
                "branch": branch_name,
            },
        )

        real_run = subprocess.run
        calls: list[dict] = []

        def _spy(*args, **kwargs):
            calls.append(kwargs)
            return real_run(*args, **kwargs)

        monkeypatch.setattr(worktree.subprocess, "run", _spy)

        result = worktree.reconcile_worktrees(repo, sprint_dir)

        assert any(e["ticket_id"] == "032" for e in result["cleaned"]), result
        assert calls, "expected reconcile_worktrees to make at least one git call"
        for kwargs in calls:
            assert kwargs.get("stdin") is subprocess.DEVNULL
