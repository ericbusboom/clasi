"""Tests for the Project class."""

from pathlib import Path

from claude_agent_skills.project import Project


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
        from claude_agent_skills.state_db_class import StateDB
        assert isinstance(db, StateDB)
        assert db.path == proj.clasi_dir / ".clasi.db"

    def test_db_property_is_lazy_singleton(self, tmp_path):
        proj = Project(tmp_path)
        proj.clasi_dir.mkdir(parents=True, exist_ok=True)
        db1 = proj.db
        db2 = proj.db
        assert db1 is db2
