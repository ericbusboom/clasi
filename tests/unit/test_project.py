"""Tests for the Project class."""

import logging
from pathlib import Path

import pytest

from clasi.project import (
    Project,
    SprintFrontmatterError,
    SprintIdMismatchError,
    SprintNotFoundError,
)


class TestProject:
    """Test Project path resolution."""

    def test_root_is_resolved(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.root == tmp_path.resolve()
        assert proj.root.is_absolute()

    def test_clasi_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.clasi_dir == tmp_path / ".clasi"

    def test_design_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.design_dir == tmp_path / "docs" / "design"

    def test_sprints_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.sprints_dir == tmp_path / "clasi" / "sprints"

    def test_issues_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.issues_dir == tmp_path / "clasi" / "issues"

    def test_log_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.log_dir == tmp_path / ".clasi" / "log"

    def test_mcp_config_path(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.mcp_config_path == tmp_path / ".mcp.json"

    def test_root_resolves_relative_path(self, tmp_path):
        # Create a subdirectory and use a relative-style path
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        proj = Project(sub)
        assert proj.root == sub.resolve()

    def test_protected_paths_empty_when_unconfigured(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.protected_paths == []

    def test_protected_paths_reads_config(self, tmp_path):
        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir(parents=True)
        (clasi_dir / "config.yaml").write_text(
            "protected_paths:\n  - src\n  - tests\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        assert proj.protected_paths == ["src/", "tests/"]

    def test_protected_paths_normalizes_trailing_slash(self, tmp_path):
        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir(parents=True)
        (clasi_dir / "config.yaml").write_text(
            "protected_paths:\n  - src/\n  - tests/\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        assert proj.protected_paths == ["src/", "tests/"]

    def test_protected_paths_ignores_non_list_value(self, tmp_path):
        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir(parents=True)
        (clasi_dir / "config.yaml").write_text(
            "protected_paths: not-a-list\n", encoding="utf-8"
        )
        proj = Project(tmp_path)
        assert proj.protected_paths == []

    def test_excluded_paths_empty_when_unconfigured(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.excluded_paths == []

    def test_excluded_paths_reads_config(self, tmp_path):
        clasi_dir = tmp_path / ".clasi"
        clasi_dir.mkdir(parents=True)
        (clasi_dir / "config.yaml").write_text(
            "protected_paths:\n  - tests\nexcluded_paths:\n  - tests/e2e\n",
            encoding="utf-8",
        )
        proj = Project(tmp_path)
        assert proj.excluded_paths == ["tests/e2e/"]

    def test_db_property_returns_state_db(self, tmp_path):
        proj = Project(tmp_path)
        # Ensure the clasi dir exists so db can initialize
        proj.clasi_dir.mkdir(parents=True, exist_ok=True)
        db = proj.db
        from clasi.state_db_class import StateDB
        assert isinstance(db, StateDB)
        assert db.path == proj.clasi_dir / ".clasi.db"

    def test_db_property_is_lazy_singleton(self, tmp_path):
        proj = Project(tmp_path)
        proj.clasi_dir.mkdir(parents=True, exist_ok=True)
        db1 = proj.db
        db2 = proj.db
        assert db1 is db2


class TestListIssues:
    """Test Project.list_issues() — pending pool only."""

    def _make_pending_issue(self, proj: "Project", filename: str) -> None:
        proj.issues_dir.mkdir(parents=True, exist_ok=True)
        (proj.issues_dir / filename).write_text(
            "---\nstatus: pending\n---\n# Title\n", encoding="utf-8"
        )

    def test_list_issues_returns_pending_pool_files(self, tmp_path):
        proj = Project(tmp_path)
        self._make_pending_issue(proj, "a.md")
        self._make_pending_issue(proj, "b.md")
        issues = proj.list_issues()
        names = [i.path.name for i in issues]
        assert names == ["a.md", "b.md"]

    def test_list_issues_empty_when_dir_missing(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.list_issues() == []

    def test_list_issues_does_not_scan_sprint_issues(self, tmp_path):
        """Sprint-scoped issues are NOT included in Project.list_issues()."""
        proj = Project(tmp_path)
        # Create a sprint with an issue
        sprint_dir = proj.sprints_dir / "001-test-sprint"
        sprint_dir.mkdir(parents=True, exist_ok=True)
        (sprint_dir / "sprint.md").write_text(
            '---\nid: "001"\ntitle: "Test"\nstatus: executing\n---\n',
            encoding="utf-8",
        )
        (sprint_dir / "issues").mkdir()
        (sprint_dir / "issues" / "sprint-issue.md").write_text(
            "---\nstatus: in-progress\n---\n# Sprint Issue\n", encoding="utf-8"
        )
        # Only pending pool should be returned (empty here)
        assert proj.list_issues() == []


class TestGetIssue:
    """Test Project.get_issue() — pending pool and sprint-scoped search."""

    def test_get_issue_finds_pending_issue(self, tmp_path):
        proj = Project(tmp_path)
        proj.issues_dir.mkdir(parents=True, exist_ok=True)
        (proj.issues_dir / "foo.md").write_text(
            "---\nstatus: pending\n---\n# Foo\n", encoding="utf-8"
        )
        issue = proj.get_issue("foo.md")
        assert issue.path.name == "foo.md"

    def test_get_issue_finds_sprint_scoped_issue(self, tmp_path):
        proj = Project(tmp_path)
        # Create a sprint
        sprint_dir = proj.sprints_dir / "001-test-sprint"
        sprint_dir.mkdir(parents=True, exist_ok=True)
        (sprint_dir / "sprint.md").write_text(
            '---\nid: "001"\ntitle: "Test"\nstatus: executing\n---\n',
            encoding="utf-8",
        )
        issues_dir = sprint_dir / "issues"
        issues_dir.mkdir()
        (issues_dir / "bar.md").write_text(
            "---\nstatus: in-progress\n---\n# Bar\n", encoding="utf-8"
        )
        issue = proj.get_issue("bar.md")
        assert issue.path.name == "bar.md"

    def test_get_issue_raises_for_missing(self, tmp_path):
        import pytest
        proj = Project(tmp_path)
        proj.issues_dir.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError, match="not found"):
            proj.get_issue("nonexistent.md")

    def test_get_issue_does_not_search_in_progress_subdir(self, tmp_path):
        """in-progress/ subdir under issues_dir is no longer searched."""
        import pytest
        proj = Project(tmp_path)
        # Put a file in what used to be the in-progress subdirectory
        old_in_progress = proj.issues_dir / "in-progress"
        old_in_progress.mkdir(parents=True, exist_ok=True)
        (old_in_progress / "legacy.md").write_text(
            "---\nstatus: in-progress\n---\n# Legacy\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match="not found"):
            proj.get_issue("legacy.md")


class TestGetAgent:
    """Test Project.get_agent() fallback removal."""

    def test_get_agent_architect_raises_value_error(self, tmp_path):
        """architect lives in old/ and must not be returned by get_agent."""
        proj = Project(tmp_path)
        with pytest.raises(ValueError):
            proj.get_agent("architect")

    def test_get_agent_error_message_lists_active_agents(self, tmp_path):
        """ValueError for an unknown agent names the active agents."""
        proj = Project(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            proj.get_agent("architect")
        msg = str(exc_info.value)
        assert "programmer" in msg
        assert "sprint-planner" in msg
        assert "team-lead" in msg


def _make_sprint_dir(
    proj: Project,
    dir_name: str,
    sprint_md_content: str,
) -> Path:
    """Helper: create a sprint directory with the given sprint.md content."""
    sprint_dir = proj.sprints_dir / dir_name
    sprint_dir.mkdir(parents=True, exist_ok=True)
    (sprint_dir / "sprint.md").write_text(sprint_md_content, encoding="utf-8")
    return sprint_dir


class TestGetSprintTypedExceptions:
    """Test that Project.get_sprint raises typed exceptions for each failure mode."""

    def test_get_sprint_not_found_raises(self, tmp_path):
        """No sprint directories → SprintNotFoundError."""
        proj = Project(tmp_path)
        proj.sprints_dir.mkdir(parents=True, exist_ok=True)
        with pytest.raises(SprintNotFoundError, match="001"):
            proj.get_sprint("001")

    def test_get_sprint_not_found_is_value_error(self, tmp_path):
        """SprintNotFoundError is a subclass of ValueError."""
        proj = Project(tmp_path)
        proj.sprints_dir.mkdir(parents=True, exist_ok=True)
        with pytest.raises(ValueError):
            proj.get_sprint("001")

    def test_get_sprint_malformed_frontmatter_raises(self, tmp_path):
        """Candidate directory with corrupted sprint.md → SprintFrontmatterError."""
        proj = Project(tmp_path)
        _make_sprint_dir(proj, "001-bad-sprint", "---bad\nmalformed content\n")
        with pytest.raises(SprintFrontmatterError) as exc_info:
            proj.get_sprint("001")
        assert "sprint.md" in str(exc_info.value)

    def test_get_sprint_frontmatter_error_is_value_error(self, tmp_path):
        """SprintFrontmatterError is a subclass of ValueError."""
        proj = Project(tmp_path)
        _make_sprint_dir(proj, "001-bad-sprint", "---bad-fence\nmalformed\n")
        with pytest.raises(ValueError):
            proj.get_sprint("001")

    def test_get_sprint_id_mismatch_raises(self, tmp_path):
        """Candidate directory with valid frontmatter but wrong id → SprintIdMismatchError."""
        proj = Project(tmp_path)
        _make_sprint_dir(
            proj,
            "001-wrong-id",
            '---\nid: "999"\ntitle: "Wrong"\nstatus: draft\n---\n',
        )
        with pytest.raises(SprintIdMismatchError) as exc_info:
            proj.get_sprint("001")
        msg = str(exc_info.value)
        assert "999" in msg
        assert "001" in msg

    def test_get_sprint_id_absent_raises(self, tmp_path):
        """Candidate directory whose frontmatter has no id field → SprintIdMismatchError."""
        proj = Project(tmp_path)
        _make_sprint_dir(
            proj,
            "001-no-id",
            '---\ntitle: "No ID"\nstatus: draft\n---\n',
        )
        with pytest.raises(SprintIdMismatchError, match="no 'id' field"):
            proj.get_sprint("001")

    def test_get_sprint_id_mismatch_is_value_error(self, tmp_path):
        """SprintIdMismatchError is a subclass of ValueError."""
        proj = Project(tmp_path)
        _make_sprint_dir(
            proj,
            "001-wrong-id",
            '---\nid: "999"\ntitle: "Wrong"\nstatus: draft\n---\n',
        )
        with pytest.raises(ValueError):
            proj.get_sprint("001")

    def test_get_sprint_success_with_multiple_dirs(self, tmp_path):
        """Correct sprint is found among multiple directories."""
        proj = Project(tmp_path)
        _make_sprint_dir(
            proj,
            "001-first",
            '---\nid: "001"\ntitle: "First"\nstatus: done\n---\n',
        )
        _make_sprint_dir(
            proj,
            "002-second",
            '---\nid: "002"\ntitle: "Second"\nstatus: active\n---\n',
        )
        sprint = proj.get_sprint("002")
        assert sprint.path.name == "002-second"


class TestListSprintsCorruptFile:
    """Test that list_sprints skips corrupt files with a warning."""

    def test_list_sprints_continues_past_corrupt_file(self, tmp_path, caplog):
        """One corrupt sprint dir and one valid: only valid sprint is returned."""
        proj = Project(tmp_path)
        _make_sprint_dir(proj, "001-corrupt", "---bad-fence\nmalformed fence\n")
        _make_sprint_dir(
            proj,
            "002-valid",
            '---\nid: "002"\ntitle: "Valid"\nstatus: active\n---\n',
        )
        with caplog.at_level(logging.WARNING, logger="clasi.project"):
            results = proj.list_sprints()

        assert len(results) == 1
        assert results[0].path.name == "002-valid"
        # Warning was logged naming the corrupt file
        assert any("001-corrupt" in r.message for r in caplog.records)

    def test_list_sprints_no_exception_propagates(self, tmp_path):
        """Corrupt sprint files do not raise — iteration completes."""
        proj = Project(tmp_path)
        _make_sprint_dir(proj, "001-corrupt", "---xyz\nbad content\n")
        # Should not raise
        results = proj.list_sprints()
        assert results == []
