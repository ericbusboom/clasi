"""Tests for the StateDB class wrapper."""

import pytest

from claude_agent_skills.state_db_class import StateDB
from claude_agent_skills.project import Project


class TestStateDB:
    """Test StateDB wrapper methods."""

    @pytest.fixture()
    def db(self, tmp_path):
        sdb = StateDB(tmp_path / ".clasi.db")
        sdb.init()
        return sdb

    def test_init_creates_tables(self, tmp_path):
        sdb = StateDB(tmp_path / ".clasi.db")
        sdb.init()
        assert sdb.path.exists()

    def test_path_property(self, tmp_path):
        p = tmp_path / "test.db"
        sdb = StateDB(p)
        assert sdb.path == p

    def test_register_and_get_sprint_state(self, db):
        result = db.register_sprint("025", "oo-refactoring", branch="sprint/025")
        assert result["id"] == "025"
        assert result["slug"] == "oo-refactoring"

        state = db.get_sprint_state("025")
        assert state["id"] == "025"
        assert state["phase"] == "planning-docs"
        assert state["branch"] == "sprint/025"

    def test_register_duplicate_raises(self, db):
        db.register_sprint("001", "first")
        with pytest.raises(ValueError, match="already registered"):
            db.register_sprint("001", "first")

    def test_get_sprint_state_missing_raises(self, db):
        with pytest.raises(ValueError, match="not registered"):
            db.get_sprint_state("999")

    def test_advance_phase(self, db):
        db.register_sprint("010", "test-sprint")
        result = db.advance_phase("010")
        assert result["old_phase"] == "planning-docs"
        assert result["new_phase"] == "architecture-review"

    def test_advance_phase_requires_gate(self, db):
        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")  # planning-docs -> architecture-review
        # architecture-review -> stakeholder-review requires architecture_review gate
        with pytest.raises(ValueError, match="gate.*architecture_review.*not passed"):
            db.advance_phase("010")

    def test_record_gate_and_advance(self, db):
        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")  # -> architecture-review
        db.record_gate("010", "architecture_review", "passed")
        result = db.advance_phase("010")  # -> stakeholder-review
        assert result["new_phase"] == "stakeholder-review"

    def test_acquire_and_release_lock(self, db):
        db.register_sprint("010", "test-sprint")
        result = db.acquire_lock("010")
        assert result["sprint_id"] == "010"
        assert result["reentrant"] is False

        # Re-entrant acquire
        result2 = db.acquire_lock("010")
        assert result2["reentrant"] is True

        # Release
        result3 = db.release_lock("010")
        assert result3["released"] is True

    def test_release_lock_without_holding_raises(self, db):
        db.register_sprint("010", "test-sprint")
        with pytest.raises(ValueError, match="No execution lock"):
            db.release_lock("010")

    def test_recovery_state_crud(self, db):
        # Initially none
        assert db.get_recovery_state() is None

        # Write
        result = db.write_recovery_state(
            "010", "create-branch", ["docs/"], "testing recovery"
        )
        assert result["sprint_id"] == "010"
        assert result["step"] == "create-branch"

        # Read back
        state = db.get_recovery_state()
        assert state is not None
        assert state["sprint_id"] == "010"
        assert state["allowed_paths"] == ["docs/"]

        # Clear
        cleared = db.clear_recovery_state()
        assert cleared["cleared"] is True
        assert db.get_recovery_state() is None

    def test_clear_recovery_state_when_empty(self, db):
        result = db.clear_recovery_state()
        assert result["cleared"] is False


class TestProjectDbIntegration:
    """Test that Project.db returns a working StateDB."""

    def test_project_db_returns_state_db(self, tmp_path):
        proj = Project(tmp_path)
        proj.clasi_dir.mkdir(parents=True)
        db = proj.db
        assert isinstance(db, StateDB)
        assert db.path == proj.clasi_dir / ".clasi.db"

    def test_project_db_is_functional(self, tmp_path):
        proj = Project(tmp_path)
        proj.clasi_dir.mkdir(parents=True)
        db = proj.db
        db.init()
        db.register_sprint("001", "test")
        state = db.get_sprint_state("001")
        assert state["phase"] == "planning-docs"
