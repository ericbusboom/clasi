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
        assert proj.clasi_dir == tmp_path / "docs" / "clasi"

    def test_sprints_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.sprints_dir == tmp_path / "docs" / "clasi" / "sprints"

    def test_todo_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.todo_dir == tmp_path / "docs" / "clasi" / "todo"

    def test_log_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.log_dir == tmp_path / "docs" / "clasi" / "log"

    def test_architecture_dir(self, tmp_path):
        proj = Project(tmp_path)
        assert proj.architecture_dir == tmp_path / "docs" / "clasi" / "architecture"

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
