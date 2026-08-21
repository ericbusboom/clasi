"""Tests for _prune_sprint_worktrees and its integration with _close_sprint_full."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from clasi.tools.artifact_tools import _prune_sprint_worktrees


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_run(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


_MAIN_ONLY_PORCELAIN = (
    "worktree /repo/root\n"
    "HEAD abc123\n"
    "branch refs/heads/master\n"
    "\n"
)

_ONE_SPRINT_PORCELAIN = (
    "worktree /repo/root\n"
    "HEAD abc123\n"
    "branch refs/heads/master\n"
    "\n"
    "worktree /repo/.git/worktrees/sprint-015-ticket-001\n"
    "HEAD def456\n"
    "branch refs/heads/sprint/015-close-sprint-and-sprint-lifecycle-hardening\n"
    "\n"
)

_TWO_SPRINT_PORCELAIN = (
    "worktree /repo/root\n"
    "HEAD abc123\n"
    "branch refs/heads/master\n"
    "\n"
    "worktree /repo/.git/worktrees/sprint-015-ticket-001\n"
    "HEAD def456\n"
    "branch refs/heads/sprint/015-close-sprint-and-sprint-lifecycle-hardening\n"
    "\n"
    "worktree /repo/.git/worktrees/sprint-015-ticket-002\n"
    "HEAD ghi789\n"
    "branch refs/heads/sprint/015-close-sprint-and-sprint-lifecycle-hardening\n"
    "\n"
)

_MIXED_PORCELAIN = (
    "worktree /repo/root\n"
    "HEAD abc123\n"
    "branch refs/heads/master\n"
    "\n"
    "worktree /repo/.git/worktrees/sprint-015-ticket-001\n"
    "HEAD def456\n"
    "branch refs/heads/sprint/015-close-sprint-and-sprint-lifecycle-hardening\n"
    "\n"
    "worktree /repo/.git/worktrees/other-sprint\n"
    "HEAD zzz000\n"
    "branch refs/heads/sprint/014-some-other-sprint\n"
    "\n"
)


# ---------------------------------------------------------------------------
# Unit tests for _prune_sprint_worktrees
# ---------------------------------------------------------------------------

class TestPruneSprintWorktrees:
    """Tests for the _prune_sprint_worktrees private helper."""

    def test_prune_worktrees_no_worktrees(self):
        """When only the main worktree exists, no removals are attempted."""
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(0, _MAIN_ONLY_PORCELAIN)
            pruned, failed, _retained = _prune_sprint_worktrees(
                "sprint/015-close-sprint-and-sprint-lifecycle-hardening"
            )

        # Only the list call should have been made — no remove calls.
        # Anchored to an explicit root (029/005), so the exact cwd value
        # (which falls back to the active project singleton here since no
        # repo_root was passed) is not asserted, only its presence.
        mock_run.assert_called_once()
        call_args, call_kwargs = mock_run.call_args
        assert call_args == (["git", "worktree", "list", "--porcelain"],)
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True
        assert "cwd" in call_kwargs
        assert pruned == []
        assert failed == []

    def test_prune_worktrees_matching_branch(self):
        """A worktree on the sprint branch is removed and path is in pruned list."""
        expected_path = "/repo/.git/worktrees/sprint-015-ticket-001"

        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            # First call: list; second call: remove
            mock_run.side_effect = [
                _mock_run(0, _ONE_SPRINT_PORCELAIN),
                _mock_run(0),
            ]
            pruned, failed, _retained = _prune_sprint_worktrees(
                "sprint/015-close-sprint-and-sprint-lifecycle-hardening"
            )

        assert pruned == [expected_path]
        assert failed == []

        # Anchored to an explicit root (029/005) -- assert the git args
        # and standard kwargs without pinning the exact cwd value.
        matching_calls = [
            c
            for c in mock_run.call_args_list
            if c.args == (["git", "worktree", "remove", "--force", expected_path],)
        ]
        assert len(matching_calls) == 1, mock_run.call_args_list
        remove_call = matching_calls[0]
        assert remove_call.kwargs["capture_output"] is True
        assert remove_call.kwargs["text"] is True
        assert "cwd" in remove_call.kwargs

    def test_prune_worktrees_non_blocking_failure(self):
        """A failed removal populates failed_paths but does not raise."""
        expected_path = "/repo/.git/worktrees/sprint-015-ticket-001"

        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _mock_run(0, _ONE_SPRINT_PORCELAIN),
                _mock_run(1, stderr="error: Unable to remove worktree"),
            ]
            pruned, failed, _retained = _prune_sprint_worktrees(
                "sprint/015-close-sprint-and-sprint-lifecycle-hardening"
            )

        assert pruned == []
        assert failed == [expected_path]

    def test_prune_worktrees_multiple(self):
        """Two worktrees on the sprint branch are both pruned."""
        path1 = "/repo/.git/worktrees/sprint-015-ticket-001"
        path2 = "/repo/.git/worktrees/sprint-015-ticket-002"

        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _mock_run(0, _TWO_SPRINT_PORCELAIN),
                _mock_run(0),  # remove path1
                _mock_run(0),  # remove path2
            ]
            pruned, failed, _retained = _prune_sprint_worktrees(
                "sprint/015-close-sprint-and-sprint-lifecycle-hardening"
            )

        assert pruned == [path1, path2]
        assert failed == []

    def test_prune_worktrees_does_not_touch_other_sprint(self):
        """Only worktrees for the closing sprint are removed; others are untouched."""
        sprint_015_path = "/repo/.git/worktrees/sprint-015-ticket-001"

        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.side_effect = [
                _mock_run(0, _MIXED_PORCELAIN),
                _mock_run(0),  # remove sprint-015 worktree only
            ]
            pruned, failed, _retained = _prune_sprint_worktrees(
                "sprint/015-close-sprint-and-sprint-lifecycle-hardening"
            )

        assert pruned == [sprint_015_path]
        assert failed == []
        # Confirm only two subprocess calls total (list + one remove).
        assert mock_run.call_count == 2

    def test_prune_worktrees_main_worktree_never_removed(self):
        """The main worktree is never removed even if it were on the sprint branch."""
        # Construct a porcelain where the MAIN worktree is on the sprint branch.
        # (This is an unusual situation but must be handled safely.)
        porcelain = (
            "worktree /repo/root\n"
            "HEAD abc123\n"
            "branch refs/heads/sprint/015-close-sprint-and-sprint-lifecycle-hardening\n"
            "\n"
        )

        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = _mock_run(0, porcelain)
            pruned, failed, _retained = _prune_sprint_worktrees(
                "sprint/015-close-sprint-and-sprint-lifecycle-hardening"
            )

        # Only the list call; no remove attempted for the main worktree.
        mock_run.assert_called_once()
        assert pruned == []
        assert failed == []


# ---------------------------------------------------------------------------
# Unit tests: orphaned ticket/<sprint-id>-* worktree sweep (ticket 018-008)
# ---------------------------------------------------------------------------

class TestPruneSprintWorktreesTicketSweep:
    """Tests for the second sweep in _prune_sprint_worktrees: orphaned
    ticket/<sprint-id>-* worktrees, classified via worktree.reconcile_worktrees.
    """

    def test_sprint_branch_only_path_unaffected_when_repo_root_omitted(self):
        """Regression: omitting repo_root/sprint_dir preserves the exact
        pre-existing sprint-branch-only pruning behavior (no ticket sweep,
        no call to reconcile_worktrees, retained is always []).
        """
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run, \
                patch("clasi.worktree.reconcile_worktrees") as mock_reconcile:
            mock_run.side_effect = [
                _mock_run(0, _ONE_SPRINT_PORCELAIN),
                _mock_run(0),
            ]
            pruned, failed, retained = _prune_sprint_worktrees(
                "sprint/015-close-sprint-and-sprint-lifecycle-hardening"
            )

        mock_reconcile.assert_not_called()
        assert pruned == ["/repo/.git/worktrees/sprint-015-ticket-001"]
        assert failed == []
        assert retained == []

    def test_merged_ticket_worktree_pruned_and_failed_worktree_retained(self):
        """One merged-not-cleaned ticket worktree (reconcile already cleaned
        it up: directory AND branch gone) is reported as pruned; one
        failed/conflict ticket worktree has its directory force-removed here
        (branch retained) and is reported distinctly in `retained`.
        """
        repo_root = Path("/repo/root")
        sprint_dir = Path("/repo/root/clasi/sprints/done/018-some-sprint")

        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run, \
                patch("clasi.worktree.reconcile_worktrees") as mock_reconcile, \
                patch("clasi.worktree.cleanup_worktree") as mock_cleanup:
            # Sprint-branch sweep: only the main worktree, no sprint-branch
            # worktree present.
            mock_run.return_value = _mock_run(0, _MAIN_ONLY_PORCELAIN)

            mock_reconcile.return_value = {
                "cleaned": [
                    {
                        "ticket_id": "001",
                        "path": "/repo/../worktree-018-001",
                        "branch": "ticket/018-001-merged-slug",
                        "reason": "merged-not-cleaned",
                    }
                ],
                "escalated": [
                    {
                        "ticket_id": "002",
                        "path": "/repo/../worktree-018-002",
                        "branch": "ticket/018-002-failed-slug",
                        "reason": "ambiguous audit state: failed",
                    }
                ],
                "rogue": [],
            }

            pruned, failed, retained = _prune_sprint_worktrees(
                "sprint/018-some-sprint",
                repo_root=repo_root,
                sprint_dir=sprint_dir,
            )

        mock_reconcile.assert_called_once_with(repo_root, sprint_dir)

        # Merged-not-cleaned worktree: already fully removed by
        # reconcile_worktrees; reported as pruned.
        assert "/repo/../worktree-018-001" in pruned
        assert failed == []

        # Failed/conflict worktree: directory force-removed via
        # cleanup_worktree(..., keep_branch=True); branch retained.
        mock_cleanup.assert_called_once_with(
            repo_root,
            Path("/repo/../worktree-018-002"),
            "ticket/018-002-failed-slug",
            keep_branch=True,
        )
        assert len(retained) == 1
        assert retained[0]["ticket_id"] == "002"
        assert retained[0]["path"] == "/repo/../worktree-018-002"
        assert retained[0]["branch"] == "ticket/018-002-failed-slug"
        assert "/repo/../worktree-018-002" not in pruned

    def test_conflict_state_also_retained(self):
        """A 'conflict' audit state (not just 'failed') is also retained
        distinctly, not silently dropped or treated as pruned."""
        repo_root = Path("/repo/root")
        sprint_dir = Path("/repo/root/clasi/sprints/done/018-some-sprint")

        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run, \
                patch("clasi.worktree.reconcile_worktrees") as mock_reconcile, \
                patch("clasi.worktree.cleanup_worktree") as mock_cleanup:
            mock_run.return_value = _mock_run(0, _MAIN_ONLY_PORCELAIN)
            mock_reconcile.return_value = {
                "cleaned": [],
                "escalated": [
                    {
                        "ticket_id": "003",
                        "path": "/repo/../worktree-018-003",
                        "branch": "ticket/018-003-conflict-slug",
                        "reason": "ambiguous audit state: conflict",
                    }
                ],
                "rogue": [],
            }

            pruned, failed, retained = _prune_sprint_worktrees(
                "sprint/018-some-sprint",
                repo_root=repo_root,
                sprint_dir=sprint_dir,
            )

        mock_cleanup.assert_called_once_with(
            repo_root,
            Path("/repo/../worktree-018-003"),
            "ticket/018-003-conflict-slug",
            keep_branch=True,
        )
        assert pruned == []
        assert len(retained) == 1
        assert retained[0]["ticket_id"] == "003"

    def test_other_escalated_reasons_left_untouched(self):
        """Escalated entries that are neither failed nor conflict (e.g. a
        dirty working tree) are not force-cleaned and not reported as
        retained -- matching reconcile_worktrees' own safety contract.
        """
        repo_root = Path("/repo/root")
        sprint_dir = Path("/repo/root/clasi/sprints/done/018-some-sprint")

        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run, \
                patch("clasi.worktree.reconcile_worktrees") as mock_reconcile, \
                patch("clasi.worktree.cleanup_worktree") as mock_cleanup:
            mock_run.return_value = _mock_run(0, _MAIN_ONLY_PORCELAIN)
            mock_reconcile.return_value = {
                "cleaned": [],
                "escalated": [
                    {
                        "ticket_id": "004",
                        "path": "/repo/../worktree-018-004",
                        "branch": "ticket/018-004-dirty-slug",
                        "reason": "dirty working tree",
                    }
                ],
                "rogue": [],
            }

            pruned, failed, retained = _prune_sprint_worktrees(
                "sprint/018-some-sprint",
                repo_root=repo_root,
                sprint_dir=sprint_dir,
            )

        mock_cleanup.assert_not_called()
        assert pruned == []
        assert retained == []


# ---------------------------------------------------------------------------
# Integration tests: result JSON shape via close_sprint
# ---------------------------------------------------------------------------

class TestCloseSSprintWorktreeResultJSON:
    """Verify worktrees_pruned appears in close_sprint result JSON."""

    @pytest.fixture
    def work_dir(self, tmp_path, monkeypatch):
        """Bootstrap a minimal project directory with a sprint in executing phase."""
        from clasi.mcp_server import set_project
        from clasi.tools.artifact_tools import create_sprint
        from clasi.state_db import (
            advance_phase,
            acquire_lock,
            StateDB,
        )

        # Write legacy pin so close_sprint uses _close_sprint_full.
        (tmp_path / ".clasi").mkdir(parents=True, exist_ok=True)
        (tmp_path / ".clasi" / ".version-pin").write_text("legacy", encoding="utf-8")

        monkeypatch.chdir(tmp_path)
        set_project(tmp_path)

        create_sprint("Sprint")

        db_path = tmp_path / ".clasi" / ".clasi.db"
        db = StateDB(db_path)
        # planning -> ticketing
        db.advance_phase("001")
        # Acquire lock (required for ticketing -> executing)
        db.acquire_lock("001")
        # ticketing -> executing
        db.advance_phase("001")

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "test"\nversion = "0.0.0"\n', encoding="utf-8"
        )
        return tmp_path

    def _mock_ok(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
        r = MagicMock()
        r.returncode = returncode
        r.stdout = stdout
        r.stderr = stderr
        return r

    def _subprocess_side_effects(self, worktree_stdout: str) -> list:
        return [
            self._mock_ok(0, "all tests passed"),  # pytest
            self._mock_ok(0, "# branch.oid deadbeef0000\n# branch.head master\n"),
                                                      # git status --porcelain=v2 --branch (031/008 marker write)
            self._mock_ok(0),                       # git config rebase.autoStash (version bump prep)
            self._mock_ok(0),                       # git add <archive paths + version file> (version bump)
            self._mock_ok(0),                       # git commit (version bump)
            self._mock_ok(0, ""),                   # git status --porcelain (clean)
            self._mock_ok(0),                       # git rev-parse --verify branch
            self._mock_ok(0),                       # git merge-base --is-ancestor
            self._mock_ok(0),                       # git push --tags
            self._mock_ok(0),                       # git rev-parse --verify branch (delete)
            self._mock_ok(0),                       # git branch -d
            self._mock_ok(0, worktree_stdout),      # git worktree list --porcelain
        ]

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260627.1")
    @patch("subprocess.run")
    def test_result_includes_worktrees_pruned_empty(
        self, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """Result JSON includes worktrees_pruned: [] when no sprint worktrees exist."""
        from clasi.tools.artifact_tools import close_sprint

        mock_run.side_effect = self._subprocess_side_effects(_MAIN_ONLY_PORCELAIN)
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))

        assert result.get("status") == "success", f"Expected success, got: {result}"
        assert result.get("worktrees_pruned") == [], (
            f"Expected worktrees_pruned: [] but got: {result.get('worktrees_pruned')}"
        )
        assert "worktrees_failed" not in result, (
            "worktrees_failed should be absent when no failures occurred"
        )

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260627.2")
    @patch("subprocess.run")
    def test_result_includes_worktrees_pruned_with_path(
        self, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """Result JSON lists pruned worktree path when one sprint worktree exists."""
        from clasi.tools.artifact_tools import close_sprint

        side_effects = self._subprocess_side_effects(
            "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"
            "worktree /repo/.git/worktrees/sprint-001-ticket-001\n"
            "HEAD def456\n"
            "branch refs/heads/sprint/001-sprint\n\n"
        )
        # Add the actual worktree remove call after the list call.
        side_effects.append(self._mock_ok(0))

        mock_run.side_effect = side_effects
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))

        assert result.get("status") == "success", f"Expected success, got: {result}"
        assert "/repo/.git/worktrees/sprint-001-ticket-001" in result.get(
            "worktrees_pruned", []
        ), f"Expected pruned path in worktrees_pruned: {result}"

    @patch("clasi.worktree.reconcile_worktrees")
    @patch("clasi.tools.artifact_tools.create_version_tag")
    @patch("clasi.tools.artifact_tools.compute_next_version", return_value="0.20260627.3")
    @patch("subprocess.run")
    def test_failed_worktree_removal_does_not_abort_close(
        self, mock_run, mock_ver, mock_tag, mock_reconcile, work_dir
    ):
        """A worktree removal failure still yields status: success and populates worktrees_failed."""
        from clasi.tools.artifact_tools import close_sprint

        side_effects = self._subprocess_side_effects(
            "worktree /repo/root\nHEAD abc123\nbranch refs/heads/master\n\n"
            "worktree /repo/.git/worktrees/sprint-001-ticket-001\n"
            "HEAD def456\n"
            "branch refs/heads/sprint/001-sprint\n\n"
        )
        # Simulate a failed worktree remove.
        side_effects.append(self._mock_ok(1, stderr="error: unable to remove"))

        mock_run.side_effect = side_effects
        mock_reconcile.return_value = {"cleaned": [], "escalated": [], "rogue": []}

        result = json.loads(close_sprint("001", branch_name="sprint/001-sprint"))

        assert result.get("status") == "success", (
            f"A failed worktree removal must not abort close; got: {result}"
        )
        assert result.get("worktrees_pruned") == [], (
            f"Pruned list must be empty on failure, got: {result}"
        )
        assert "/repo/.git/worktrees/sprint-001-ticket-001" in result.get(
            "worktrees_failed", []
        ), f"Failed path must be in worktrees_failed: {result}"
