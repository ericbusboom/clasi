"""Tests for tests.e2e.verify module — _check_dispatch_logs."""

import pytest
from pathlib import Path

from tests.e2e.verify import _check_dispatch_logs


@pytest.fixture
def project(tmp_path):
    """Create a minimal project directory with log structure."""
    log_dir = tmp_path / "docs" / "clasi" / "log" / "sprints"
    log_dir.mkdir(parents=True)
    return tmp_path


def _make_log(directory: Path, name: str, content: str = "---\nchild: x\n---\nbody\n"):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(content, encoding="utf-8")


class TestCheckDispatchLogs:
    def test_passes_when_ticket_and_planner_logs_present(self, project):
        sprint_dir = project / "docs" / "clasi" / "log" / "sprints" / "001-sprint"
        _make_log(sprint_dir, "ticket-001-001.md")
        _make_log(sprint_dir, "architect-001.md")
        result = _check_dispatch_logs(project)
        assert result.passed, result.detail

    def test_fails_when_no_ticket_logs(self, project):
        sprint_dir = project / "docs" / "clasi" / "log" / "sprints" / "001-sprint"
        # Only planner-level logs, no ticket-* files
        _make_log(sprint_dir, "sprint-planner-001.md")
        _make_log(sprint_dir, "architect-001.md")
        result = _check_dispatch_logs(project)
        assert not result.passed
        assert "no ticket-* log files" in result.detail

    def test_fails_when_no_planner_sub_dispatch_logs(self, project):
        sprint_dir = project / "docs" / "clasi" / "log" / "sprints" / "001-sprint"
        # Has ticket logs and sprint-planner logs, but no architect/reviewer logs
        _make_log(sprint_dir, "ticket-001-001.md")
        _make_log(sprint_dir, "sprint-planner-001.md")
        result = _check_dispatch_logs(project)
        assert not result.passed
        assert "no planner sub-dispatch logs" in result.detail

    def test_fails_when_log_dir_missing(self, tmp_path):
        result = _check_dispatch_logs(tmp_path)
        assert not result.passed
        assert "log/ directory does not exist" in result.detail

    def test_fails_when_no_log_files(self, project):
        # sprints dir exists but is empty
        result = _check_dispatch_logs(project)
        assert not result.passed
        assert "no log files found" in result.detail

    def test_passes_with_multiple_sprints(self, project):
        for sprint_name in ["001-first", "002-second"]:
            sprint_dir = project / "docs" / "clasi" / "log" / "sprints" / sprint_name
            _make_log(sprint_dir, "ticket-001-001.md")
            _make_log(sprint_dir, "architect-001.md")
        result = _check_dispatch_logs(project)
        assert result.passed, result.detail

    def test_fails_when_empty_log_files(self, project):
        sprint_dir = project / "docs" / "clasi" / "log" / "sprints" / "001-sprint"
        _make_log(sprint_dir, "ticket-001-001.md", content="tiny")
        _make_log(sprint_dir, "architect-001.md", content="")
        result = _check_dispatch_logs(project)
        assert not result.passed
        assert "empty logs" in result.detail
