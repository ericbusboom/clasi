"""Tests for the Project class."""

from pathlib import Path

import pytest

from clasi.project import Project


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
        assert proj.sprints_dir == tmp_path / ".clasi" / "sprints"

    def test_issues_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.issues_dir == tmp_path / ".clasi" / "issues"

    def test_log_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.log_dir == tmp_path / ".clasi" / "log"

    def test_architecture_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.architecture_dir == tmp_path / ".clasi" / "architecture"

    def test_mcp_config_path(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.mcp_config_path == tmp_path / ".mcp.json"

    def test_root_resolves_relative_path(self, tmp_path):
        # Create a subdirectory and use a relative-style path
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        proj = Project(sub)
        assert proj.root == sub.resolve()

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
