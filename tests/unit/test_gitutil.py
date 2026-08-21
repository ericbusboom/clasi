"""Unit tests for clasi.gitutil.run_git (ticket 029/005).

Covers the shared git subprocess helper itself -- that it runs the given
git subcommand, is anchored to the *cwd* argument rather than the calling
process's own working directory, and does not raise on a non-zero exit
code. Also proves the explicit-pathspec commit pattern CLASI's own
generated commits use (artifact_tools.py's version-bump and .clasi.db
commit steps) does not sweep a stakeholder's own pre-staged, unrelated
file into a CLASI chore commit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from clasi.gitutil import run_git

# 032/008: this module is the git subprocess helper's own test suite --
# all but one test drive a real git repo via _git()/run_git (real-git
# tier by definition, not a raw-duration outlier).
pytestmark = [pytest.mark.slow]


def _git(repo: Path, *args: str) -> None:
    """Set up a fixture repo using a plain subprocess call (not run_git
    itself, so the fixture doesn't depend on the code under test)."""
    result = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "master")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "base.txt").write_text("base\n", encoding="utf-8")
    _git(tmp_path, "add", "base.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


class TestRunGit:
    """Direct tests of the run_git(args, cwd) helper."""

    def test_runs_git_with_given_args(self, repo):
        result = run_git(["status", "--porcelain"], cwd=repo)
        assert result.returncode == 0
        assert result.stdout == ""

    def test_returns_completed_process_with_captured_output(self, repo):
        result = run_git(["log", "--oneline"], cwd=repo)
        assert result.returncode == 0
        assert "init" in result.stdout

    def test_nonzero_exit_does_not_raise(self, repo):
        """Callers inspect .returncode themselves -- run_git never raises
        on a failing git invocation (no `check=True`)."""
        result = run_git(["not-a-real-git-subcommand"], cwd=repo)
        assert result.returncode != 0
        assert result.stderr

    def test_anchored_to_cwd_argument_not_process_cwd(self, tmp_path, monkeypatch):
        """The defining behavior this ticket introduces: run_git must
        operate on *cwd*, never on the calling process's own working
        directory (docs/reviews/2026-08-reliability/02-mcp-tools.md F3/F4).
        """
        repo_a = tmp_path / "repo_a"
        repo_b = tmp_path / "repo_b"
        repo_a.mkdir()
        repo_b.mkdir()  # deliberately not a git repo at all
        _git(repo_a, "init", "-q", "-b", "master")
        _git(repo_a, "config", "user.email", "a@example.com")
        _git(repo_a, "config", "user.name", "A")
        (repo_a / "a.txt").write_text("a\n", encoding="utf-8")
        _git(repo_a, "add", "a.txt")
        _git(repo_a, "commit", "-q", "-m", "repo a commit")

        # Process cwd points at repo_b (not even a git repo). If run_git
        # ever fell back to the process cwd instead of the explicit cwd
        # argument, this would fail (no git repo at repo_b).
        monkeypatch.chdir(repo_b)
        result = run_git(["log", "--oneline"], cwd=repo_a)
        assert result.returncode == 0
        assert "repo a commit" in result.stdout

    def test_stdin_is_devnull(self, repo):
        """031/008 follow-up: run_git must never inherit the calling
        process's stdin. When invoked from CLASI's MCP server, that
        inherited stdin is the JSON-RPC pipe from the client -- a git
        subcommand that unexpectedly tries to read it (a credential
        prompt, a merge driver) would hang the calling tool forever
        instead of failing fast. Asserted on the real subprocess.run
        call (mocked) rather than trying to provoke an actual git
        stdin-read, matching the same "assert on call arguments" style
        used for the analogous close.py fix.
        """
        with patch("clasi.gitutil.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
            run_git(["status", "--porcelain"], cwd=repo)

        mock_run.assert_called_once()
        _, call_kwargs = mock_run.call_args
        assert call_kwargs["stdin"] is subprocess.DEVNULL


class TestExplicitPathspecCommit:
    """Proves the stage-then-commit-with-pathspec pattern CLASI's own
    generated commits use (artifact_tools.py's version-bump and
    .clasi.db commit steps, ticket 029/005) does not sweep a
    stakeholder's own pre-staged, unrelated file into the commit.
    """

    def test_pathspec_commit_excludes_pre_staged_unrelated_file(self, repo):
        # Simulate a stakeholder who already had an unrelated file staged
        # before CLASI's own close_sprint git sequence ran (the F7
        # scenario this ticket fixes).
        (repo / "unrelated.txt").write_text(
            "stakeholder's own work\n", encoding="utf-8"
        )
        run_git(["add", "unrelated.txt"], cwd=repo)

        # CLASI's own change: modify an existing tracked file AND add a
        # brand new one -- mirrors bump_paths in artifact_tools.py, which
        # mixes both kinds of paths.
        (repo / "base.txt").write_text("base\nmodified\n", encoding="utf-8")
        (repo / "clasi-new.txt").write_text("new\n", encoding="utf-8")

        clasi_paths = ["base.txt", "clasi-new.txt"]
        # Exact production pattern: explicit `git add` of CLASI's own
        # paths, then `git commit -- <paths>`.
        add_result = run_git(["add", *clasi_paths], cwd=repo)
        assert add_result.returncode == 0
        commit_result = run_git(
            ["commit", "-m", "chore: clasi commit", "--", *clasi_paths],
            cwd=repo,
        )
        assert commit_result.returncode == 0, commit_result.stderr

        # The commit contains only CLASI's own paths.
        show = run_git(["show", "--stat", "--format=", "HEAD"], cwd=repo)
        assert "base.txt" in show.stdout
        assert "clasi-new.txt" in show.stdout
        assert "unrelated.txt" not in show.stdout

        # The unrelated file is still staged (in the index) but was never
        # swept into the CLASI commit -- it survives untouched.
        status = run_git(["status", "--porcelain"], cwd=repo)
        assert "A  unrelated.txt" in status.stdout.splitlines()

    def test_pathspec_commit_fails_for_untracked_path_without_prior_add(self, repo):
        """Documents the exact nuance the ticket flagged: `git commit --
        <path>` alone does NOT stage a brand new (never `git add`-ed)
        file -- production code must keep the explicit `git add` call
        before the pathspec commit, which is exactly what both commit
        sites in artifact_tools.py do.
        """
        (repo / "brandnew.txt").write_text("new\n", encoding="utf-8")
        # No `git add` first.
        result = run_git(
            ["commit", "-m", "no prior add", "--", "brandnew.txt"], cwd=repo
        )
        assert result.returncode != 0
        assert "did not match any file" in (result.stderr + result.stdout)
