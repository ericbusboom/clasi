"""Behavioral tests for clasi/worktree.py lifecycle functions.

Covers:
- The audit pair (write_audit_record / read_audit_record).
- check_independence's static file-set overlap algorithm, including the
  src/ normalization regression called out explicitly as a footgun.
- Real-git-backed tests (a tmp_path repo with an initial commit) driving
  create_worktree, create_ticket_branch, validate_worktree, and
  merge_ticket_branch (fast-forward, --no-ff fallback, conflict-abort),
  plus cleanup_worktree idempotency.
- reconcile_worktrees: the standing cleanup engine that classifies live
  ticket worktrees against the audit record (merged-not-cleaned,
  clean-but-abandoned, ambiguous), plus the rogue/already-gone edge cases
  and idempotency.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import clasi.worktree as worktree
from clasi.sprint import MergeConflictError


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
# check_independence
# ---------------------------------------------------------------------------


class TestCheckIndependenceFileSets:
    def test_disjoint_file_sets_are_independent(self) -> None:
        tickets = [
            {"id": "001", "files_to_create": ["clasi/foo.py"], "files_to_modify": []},
            {"id": "002", "files_to_create": ["clasi/bar.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        assert groups == [["001", "002"]]

    def test_overlapping_file_sets_are_dependent(self) -> None:
        tickets = [
            {"id": "001", "files_to_create": ["clasi/foo.py"], "files_to_modify": []},
            {"id": "002", "files_to_create": [], "files_to_modify": ["clasi/foo.py"]},
        ]
        groups = worktree.check_independence(tickets)
        # Dependent tickets must never share a group -> two serial groups.
        assert groups == [["001"], ["002"]]

    def test_src_prefix_normalization_regression(self) -> None:
        """src/clasi/foo.py and clasi/foo.py must be treated as the same file."""
        tickets = [
            {"id": "001", "files_to_create": ["src/clasi/foo.py"], "files_to_modify": []},
            {"id": "002", "files_to_create": ["clasi/foo.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        # The normalized paths collide, so the tickets are dependent and
        # must be split into separate groups (proves the normalization
        # actually took effect -- an unnormalized comparison would have
        # incorrectly treated them as independent and merged them).
        assert groups == [["001"], ["002"]]

    def test_shared_derived_test_module_is_dependent(self) -> None:
        """Disjoint source files but the same derived test_<stem>.py -> dependent."""
        tickets = [
            {"id": "001", "files_to_create": ["clasi/foo.py"], "files_to_modify": []},
            {"id": "002", "files_to_create": ["tests/clasi/test_foo.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        assert groups == [["001"], ["002"]]

    def test_missing_file_info_dependent_on_all(self) -> None:
        tickets = [
            {"id": "001", "files_to_create": ["clasi/foo.py"], "files_to_modify": []},
            {"id": "002"},
            {"id": "003", "files_to_create": ["clasi/bar.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        # Ticket 002 has no discoverable files -> the "unknown" sentinel
        # makes it dependent on everything, so it can never share a group
        # with 001 or 003. 001 and 003 are independent of each other and
        # do share a group.
        assert groups == [["001", "003"], ["002"]]

    def test_three_independent_tickets(self) -> None:
        tickets = [
            {"id": "001", "files_to_create": ["clasi/a.py"], "files_to_modify": []},
            {"id": "002", "files_to_create": ["clasi/b.py"], "files_to_modify": []},
            {"id": "003", "files_to_create": ["clasi/c.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        assert groups == [["001", "002", "003"]]


class TestCheckIndependenceBodyParsing:
    def _body(self, heading: str, create_items: list[str] | None = None, modify_items: list[str] | None = None) -> str:
        lines = [f"{heading}", ""]
        for item in (create_items or []):
            lines.append(f"- `{item}` — create.")
        for item in (modify_items or []):
            lines.append(f"- `{item}` — modify.")
        lines.append("")
        lines.append("## Testing")
        lines.append("- run pytest")
        return "\n".join(lines)

    def test_h2_combined_heading(self) -> None:
        body = self._body("## Files to create or modify", create_items=["clasi/foo.py"])
        tickets = [
            {"id": "001", "body": body},
            {"id": "002", "files_to_create": ["clasi/foo.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        # Both tickets touch clasi/foo.py -> the ## heading was parsed
        # correctly (proven by the resulting dependence being detected).
        assert groups == [["001"], ["002"]]

    def test_h3_combined_heading(self) -> None:
        body = self._body("### Files to create or modify", create_items=["clasi/foo.py"])
        tickets = [
            {"id": "001", "body": body},
            {"id": "002", "files_to_create": ["clasi/bar.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        assert groups == [["001", "002"]]

    def test_separate_create_and_modify_headings(self) -> None:
        lines = [
            "## Files to create",
            "",
            "- `clasi/new_thing.py`",
            "",
            "## Files to modify",
            "",
            "- `clasi/existing.py`",
            "",
            "## Testing",
            "- run pytest",
        ]
        body = "\n".join(lines)
        tickets = [
            {"id": "001", "body": body},
            {"id": "002", "files_to_create": ["clasi/existing.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        # Ticket 001's "Files to modify" section includes clasi/existing.py,
        # which ticket 002 also touches -> dependent, proving both the
        # "Files to create" and "Files to modify" headings were parsed.
        assert groups == [["001"], ["002"]]

    def test_body_parsing_stops_at_next_heading(self) -> None:
        body = self._body("## Files to create or modify", create_items=["clasi/foo.py"])
        tickets = [
            {"id": "001", "body": body},
            {"id": "002", "files_to_create": ["clasi/unrelated.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        # "run pytest" under ## Testing must not be picked up as a file,
        # so ticket 001's file set is exactly {clasi/foo.py} — independent
        # of ticket 002's unrelated file.
        assert groups == [["001", "002"]]

    def test_body_src_prefix_normalization(self) -> None:
        body = self._body("## Files to create or modify", create_items=["src/clasi/foo.py"])
        tickets = [
            {"id": "001", "body": body},
            {"id": "002", "files_to_create": ["clasi/foo.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        # src/clasi/foo.py (parsed from the body) normalizes to the same
        # path as clasi/foo.py -> dependent, proving normalization applies
        # to body-parsed paths too.
        assert groups == [["001"], ["002"]]


class TestCheckIndependenceGroupOrdering:
    def test_depends_on_orders_groups(self) -> None:
        tickets = [
            {"id": "001", "files_to_create": ["clasi/a.py"], "files_to_modify": []},
            {
                "id": "002",
                "files_to_create": ["clasi/b.py"],
                "files_to_modify": [],
                "depends-on": ["001"],
            },
        ]
        groups = worktree.check_independence(tickets)
        assert groups == [["001"], ["002"]]

    def test_tie_break_by_ticket_id_ascending(self) -> None:
        # No dependency relationship between the two independent tickets'
        # components (each is a singleton) -> ties broken by ticket id.
        tickets = [
            {"id": "003", "files_to_create": ["clasi/c.py"], "files_to_modify": []},
            {"id": "001", "files_to_create": ["clasi/a.py"], "files_to_modify": []},
            {"id": "002", "files_to_create": ["clasi/b.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        # All three are mutually independent -> single parallel group,
        # sorted ascending within the group.
        assert groups == [["001", "002", "003"]]

    def test_two_conflicting_pairs_are_colored_across_groups(self) -> None:
        # 001/002 conflict on y.py; 003/004 conflict on x.py. 001 and 003
        # are independent of each other (disjoint files), as are 002 and
        # 004. Greedy first-fit coloring (processed in id-ascending order,
        # no depends-on) places 001 in group 0, 002 can't join group 0
        # (conflicts with 001) so opens group 1, 003 joins group 0 (no
        # conflict with 001), 004 joins group 1 (no conflict with 002).
        # This also proves two tickets that individually conflict with a
        # third ticket are never merged transitively into one group.
        tickets = [
            {"id": "004", "files_to_create": ["clasi/x.py"], "files_to_modify": []},
            {"id": "003", "files_to_create": ["clasi/x.py"], "files_to_modify": []},
            {"id": "002", "files_to_create": ["clasi/y.py"], "files_to_modify": []},
            {"id": "001", "files_to_create": ["clasi/y.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        assert groups == [["001", "003"], ["002", "004"]]

    def test_transitivity_trap_conflicting_tickets_never_share_a_group(self) -> None:
        # A(001)={x.py} conflicts with C(003)={x.py}. B(002)={y.py} is
        # independent of both A and C. A naive connected-components
        # approach over an "independence" adjacency (union A-B since
        # independent, union B-C since independent) would incorrectly
        # merge A and C into the same group via the B chain. Greedy
        # first-fit coloring must not do this: A and C must never appear
        # together.
        tickets = [
            {"id": "001", "files_to_create": ["clasi/x.py"], "files_to_modify": []},
            {"id": "002", "files_to_create": ["clasi/y.py"], "files_to_modify": []},
            {"id": "003", "files_to_create": ["clasi/x.py"], "files_to_modify": []},
        ]
        groups = worktree.check_independence(tickets)
        for group in groups:
            assert not ("001" in group and "003" in group), (
                f"001 and 003 conflict on clasi/x.py but were grouped together: {groups}"
            )
        assert groups == [["001", "002"], ["003"]]


# ---------------------------------------------------------------------------
# Real-git fixture: create_worktree / create_ticket_branch / validate_worktree
# / merge_ticket_branch / cleanup_worktree
# ---------------------------------------------------------------------------


class TestCreateWorktree:
    def test_creates_sibling_detached_worktree(self, repo: Path) -> None:
        wt_path = worktree.create_worktree(repo, "999", "001")
        try:
            assert wt_path.parent == repo.parent
            assert wt_path.name == "worktree-999-001"
            assert wt_path.exists()

            head_result = _run(["git", "symbolic-ref", "-q", "HEAD"], cwd=wt_path)
            # A detached HEAD means symbolic-ref fails (non-zero exit).
            assert head_result.returncode != 0
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)

    def test_raises_on_failure(self, repo: Path) -> None:
        # git worktree add fails if the target path already exists as a
        # non-empty directory.
        target = (repo / ".." / "worktree-999-002").resolve()
        target.mkdir(parents=True)
        (target / "occupied.txt").write_text("taken\n", encoding="utf-8")
        try:
            with pytest.raises(RuntimeError):
                worktree.create_worktree(repo, "999", "002")
        finally:
            import shutil

            shutil.rmtree(target, ignore_errors=True)


class TestCreateTicketBranch:
    def test_creates_and_checks_out_branch(self, repo: Path) -> None:
        wt_path = worktree.create_worktree(repo, "999", "003")
        try:
            branch_name = worktree.create_ticket_branch(
                wt_path, "999", "003", "some-slug"
            )
            assert branch_name == "ticket/999-003-some-slug"

            current = _run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt_path
            ).stdout.strip()
            assert current == branch_name
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)
            _run(["git", "branch", "-D", "ticket/999-003-some-slug"], cwd=repo)


class TestValidateWorktree:
    def _make_ticket_file(self, path: Path, status: str = "done") -> Path:
        """Write and commit a ticket file so the worktree stays clean."""
        ticket_path = path / "ticket.md"
        ticket_path.write_text(f"---\nstatus: {status}\n---\n# Ticket\n", encoding="utf-8")
        _run(["git", "add", "-A"], cwd=path)
        _run(["git", "commit", "-m", "add ticket file"], cwd=path)
        return ticket_path

    def test_all_checks_pass(self, repo: Path) -> None:
        wt_path = worktree.create_worktree(repo, "999", "004")
        try:
            ticket_path = self._make_ticket_file(wt_path, status="done")
            result = worktree.validate_worktree(
                wt_path, ticket_path, test_command=["true"]
            )
            assert result is True
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)

    def test_test_failure_returns_false(self, repo: Path) -> None:
        wt_path = worktree.create_worktree(repo, "999", "005")
        try:
            ticket_path = self._make_ticket_file(wt_path, status="done")
            result = worktree.validate_worktree(
                wt_path, ticket_path, test_command=["false"]
            )
            assert result is False
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)

    def test_dirty_tree_returns_false(self, repo: Path) -> None:
        wt_path = worktree.create_worktree(repo, "999", "006")
        try:
            ticket_path = self._make_ticket_file(wt_path, status="done")
            (wt_path / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            result = worktree.validate_worktree(
                wt_path, ticket_path, test_command=["true"]
            )
            assert result is False
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)

    def test_status_not_done_returns_false(self, repo: Path) -> None:
        wt_path = worktree.create_worktree(repo, "999", "007")
        try:
            ticket_path = self._make_ticket_file(wt_path, status="open")
            result = worktree.validate_worktree(
                wt_path, ticket_path, test_command=["true"]
            )
            assert result is False
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)

    def test_never_raises_default_command_missing(self, tmp_path: Path) -> None:
        # Not a git repo at all and a nonexistent test_command binary should
        # not raise -- validate_worktree returns False, never propagates.
        ticket_path = tmp_path / "ticket.md"
        ticket_path.write_text("---\nstatus: done\n---\n", encoding="utf-8")
        result = worktree.validate_worktree(
            tmp_path, ticket_path, test_command=["false"]
        )
        assert result is False


class TestMergeTicketBranch:
    def _make_ticket_branch(self, repo: Path, ticket_id: str, filename: str, content: str) -> tuple[Path, str]:
        wt_path = worktree.create_worktree(repo, "999", ticket_id)
        branch_name = worktree.create_ticket_branch(wt_path, "999", ticket_id, "slug")
        (wt_path / filename).write_text(content, encoding="utf-8")
        _run(["git", "add", "-A"], cwd=wt_path)
        _run(["git", "commit", "-m", f"add {filename}"], cwd=wt_path)
        return wt_path, branch_name

    def test_fast_forward_merge(self, repo: Path) -> None:
        wt_path, branch_name = self._make_ticket_branch(repo, "010", "a.txt", "a\n")
        try:
            worktree.merge_ticket_branch(repo, "sprint/999-test-sprint", branch_name)
            log = _run(["git", "log", "--oneline", "-1"], cwd=repo).stdout
            assert "add a.txt" in log
            # Fast-forward: no merge commit, so parent count is 1.
            parents = _run(["git", "rev-list", "--parents", "-n", "1", "HEAD"], cwd=repo).stdout.split()
            assert len(parents) == 2  # commit hash + exactly one parent
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)

    def test_no_ff_fallback_when_sprint_branch_advanced(self, repo: Path) -> None:
        wt_path, branch_name = self._make_ticket_branch(repo, "011", "b.txt", "b\n")
        try:
            # Advance the sprint branch after the worktree was branched off,
            # so a fast-forward is no longer possible.
            _run(["git", "checkout", "sprint/999-test-sprint"], cwd=repo)
            (repo / "advance.txt").write_text("advance\n", encoding="utf-8")
            _run(["git", "add", "-A"], cwd=repo)
            _run(["git", "commit", "-m", "advance sprint branch"], cwd=repo)

            worktree.merge_ticket_branch(repo, "sprint/999-test-sprint", branch_name)

            parents = _run(["git", "rev-list", "--parents", "-n", "1", "HEAD"], cwd=repo).stdout.split()
            assert len(parents) == 3  # commit hash + two parents = merge commit
            assert (repo / "b.txt").exists()
            assert (repo / "advance.txt").exists()
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)

    def test_conflict_aborts_and_leaves_clean_tree(self, repo: Path) -> None:
        # Create a ticket branch that modifies README.md.
        wt_path = worktree.create_worktree(repo, "999", "012")
        branch_name = worktree.create_ticket_branch(wt_path, "999", "012", "slug")
        (wt_path / "README.md").write_text("ticket branch change\n", encoding="utf-8")
        _run(["git", "add", "-A"], cwd=wt_path)
        _run(["git", "commit", "-m", "modify README on ticket branch"], cwd=wt_path)

        try:
            # Advance the sprint branch with a conflicting change to the
            # same file.
            _run(["git", "checkout", "sprint/999-test-sprint"], cwd=repo)
            (repo / "README.md").write_text("sprint branch change\n", encoding="utf-8")
            _run(["git", "add", "-A"], cwd=repo)
            _run(["git", "commit", "-m", "modify README on sprint branch"], cwd=repo)

            with pytest.raises(MergeConflictError) as excinfo:
                worktree.merge_ticket_branch(repo, "sprint/999-test-sprint", branch_name)

            assert "README.md" in excinfo.value.conflicted_files

            status = _run(["git", "status", "--porcelain"], cwd=repo).stdout
            assert status.strip() == ""
        finally:
            _run(["git", "worktree", "remove", "--force", str(wt_path)], cwd=repo)
            _run(["git", "branch", "-D", branch_name], cwd=repo)

    def test_checkout_failure_raises_runtime_error(self, repo: Path) -> None:
        with pytest.raises(RuntimeError):
            worktree.merge_ticket_branch(repo, "no-such-branch", "also-no-such-branch")


class TestCleanupWorktree:
    def test_removes_worktree_and_deletes_branch(self, repo: Path) -> None:
        wt_path = worktree.create_worktree(repo, "999", "020")
        branch_name = worktree.create_ticket_branch(wt_path, "999", "020", "slug")
        # Merge it so the branch is fully merged and -d succeeds.
        worktree.merge_ticket_branch(repo, "sprint/999-test-sprint", branch_name)

        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=False)

        assert not wt_path.exists()
        branch_exists = _run(["git", "rev-parse", "--verify", branch_name], cwd=repo).returncode == 0
        assert branch_exists is False

    def test_keep_branch_true_retains_branch(self, repo: Path) -> None:
        wt_path = worktree.create_worktree(repo, "999", "021")
        branch_name = worktree.create_ticket_branch(wt_path, "999", "021", "slug")

        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=True)

        assert not wt_path.exists()
        branch_exists = _run(["git", "rev-parse", "--verify", branch_name], cwd=repo).returncode == 0
        assert branch_exists is True

        # Cleanup the branch ourselves since we asked to keep it.
        _run(["git", "branch", "-D", branch_name], cwd=repo)

    def test_idempotent_on_already_removed_worktree(self, repo: Path) -> None:
        wt_path = worktree.create_worktree(repo, "999", "022")
        branch_name = worktree.create_ticket_branch(wt_path, "999", "022", "slug")

        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=True)
        # Calling it again on the same (already-removed) worktree must not
        # raise.
        worktree.cleanup_worktree(repo, wt_path, branch_name, keep_branch=True)

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
    wt_path = worktree.create_worktree(repo, "999", ticket_id)
    branch_name = worktree.create_ticket_branch(wt_path, "999", ticket_id, slug)
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
        worktree.merge_ticket_branch(repo, "sprint/999-test-sprint", merged_branch)
        # merge_ticket_branch checks out the sprint branch as a side effect;
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
