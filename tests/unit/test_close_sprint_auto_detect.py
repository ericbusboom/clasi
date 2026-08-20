"""Tests for close_sprint auto-detect sprint_id from branch behavior."""

import json
from unittest.mock import MagicMock, patch

import pytest

from clasi.tools.artifact_tools import _detect_sprint_from_branch, close_sprint


class TestDetectSprintFromBranch:
    """Unit tests for the _detect_sprint_from_branch helper."""

    def _make_run_result(self, stdout: str) -> MagicMock:
        result = MagicMock()
        result.stdout = stdout
        return result

    def test_sprint_branch_returns_sprint_id_and_branch_name(self):
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result("sprint/015-my-sprint\n")
            detected = _detect_sprint_from_branch()
        assert detected == ("015", "sprint/015-my-sprint")

    def test_sprint_branch_three_digit_id(self):
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result("sprint/007-close-sprint-hardening\n")
            detected = _detect_sprint_from_branch()
        assert detected == ("007", "sprint/007-close-sprint-hardening")

    def test_master_branch_returns_none(self):
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result("master\n")
            detected = _detect_sprint_from_branch()
        assert detected is None

    def test_non_sprint_branch_returns_none(self):
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result("feature/some-feature\n")
            detected = _detect_sprint_from_branch()
        assert detected is None

    def test_empty_output_detached_head_returns_none(self):
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result("")
            detected = _detect_sprint_from_branch()
        assert detected is None

    def test_calls_git_branch_show_current(self):
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result("sprint/001-test\n")
            _detect_sprint_from_branch()
        # Anchored to project.root (029/005: root-anchored git calls) --
        # never a bare, cwd-less git subprocess. The exact cwd value
        # depends on the active project singleton, so only its presence
        # (not its value) is asserted here.
        mock_run.assert_called_once()
        call_args, call_kwargs = mock_run.call_args
        assert call_args == (["git", "branch", "--show-current"],)
        assert call_kwargs["capture_output"] is True
        assert call_kwargs["text"] is True
        assert "cwd" in call_kwargs


class TestCloseSSprintAutoDetect:
    """Integration-level tests for auto-detect path in close_sprint."""

    def _make_run_result(self, stdout: str) -> MagicMock:
        result = MagicMock()
        result.stdout = stdout
        return result

    def test_auto_detect_sprint_branch_calls_full_close(self):
        """When sprint_id omitted and on sprint branch, calls _close_sprint_full."""
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run, \
             patch("clasi.tools.artifact_tools._close_sprint_full", return_value='{"status":"ok"}') as mock_full:
            mock_run.return_value = self._make_run_result("sprint/015-my-sprint\n")
            result = close_sprint()
        mock_full.assert_called_once_with(
            "015", "sprint/015-my-sprint", "master", True, True, test_command=None, test_timeout=None
        )

    def test_auto_detect_empty_string_sprint_id_also_triggers_auto_detect(self):
        """Empty-string sprint_id triggers auto-detect (the empty-args bug case)."""
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run, \
             patch("clasi.tools.artifact_tools._close_sprint_full", return_value='{"status":"ok"}') as mock_full:
            mock_run.return_value = self._make_run_result("sprint/012-foo\n")
            result = close_sprint(sprint_id="")
        mock_full.assert_called_once_with(
            "012", "sprint/012-foo", "master", True, True, test_command=None, test_timeout=None
        )

    def test_not_on_sprint_branch_returns_structured_error(self):
        """When not on a sprint branch, returns error JSON with step=auto-detect."""
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result("master\n")
            result = close_sprint()
        data = json.loads(result)
        assert data["status"] == "error"
        assert data["error"]["step"] == "auto-detect"
        assert "sprint branch" in data["error"]["message"]
        assert data["error"]["current_branch"] == "master"

    def test_detached_head_returns_structured_error(self):
        """Detached HEAD (empty branch output) returns structured error."""
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run:
            mock_run.return_value = self._make_run_result("")
            result = close_sprint()
        data = json.loads(result)
        assert data["status"] == "error"
        assert data["error"]["step"] == "auto-detect"
        assert data["error"]["current_branch"] == "(detached HEAD)"

    def test_explicit_sprint_id_bypasses_auto_detect(self):
        """When sprint_id provided explicitly, git branch is never called."""
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run, \
             patch("clasi.tools.artifact_tools._close_sprint_legacy", return_value='{"status":"ok"}') as mock_legacy:
            result = close_sprint(sprint_id="007")
        # subprocess.run should NOT be called for git branch detection
        mock_run.assert_not_called()
        mock_legacy.assert_called_once_with("007")

    def test_explicit_sprint_id_with_branch_calls_full_close(self):
        """Explicit sprint_id + branch_name calls _close_sprint_full (pre-015 behavior)."""
        with patch("clasi.tools.artifact_tools.subprocess.run") as mock_run, \
             patch("clasi.tools.artifact_tools._close_sprint_full", return_value='{"status":"ok"}') as mock_full:
            result = close_sprint(sprint_id="007", branch_name="sprint/007-foo")
        mock_run.assert_not_called()
        mock_full.assert_called_once_with(
            "007", "sprint/007-foo", "master", True, True, test_command=None, test_timeout=None
        )
