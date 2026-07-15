"""Tests for the StateDB class wrapper."""

import pytest

from clasi.state_db_class import PHASES, StateDB
from clasi.project import Project


class TestPhases:
    """Tests for the PHASES constant."""

    def test_roadmap_is_first_phase(self):
        """PHASES[0] must be 'roadmap' — the lightweight planning phase."""
        assert PHASES[0] == "roadmap"

    def test_planning_docs_follows_roadmap(self):
        """Advancing from roadmap lands on planning-docs."""
        idx = PHASES.index("roadmap")
        assert PHASES[idx + 1] == "planning-docs"

    def test_phases_is_complete_list_derived_from_schema(self):
        """PHASES contains all expected lifecycle phases, unconditionally from schema."""
        expected = [
            "roadmap",
            "planning-docs",
            "architecture-review",
            "stakeholder-review",
            "ticketing",
            "executing",
            "closing",
            "done",
        ]
        assert PHASES == expected

    def test_phases_is_non_empty_list(self):
        """PHASES is a non-empty list loaded from the schema at module import."""
        assert isinstance(PHASES, list)
        assert len(PHASES) > 0


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
        assert state["phase"] == "roadmap"
        assert state["branch"] == "sprint/025"

    def test_register_duplicate_raises(self, db):
        db.register_sprint("001", "first")
        with pytest.raises(ValueError, match="already registered"):
            db.register_sprint("001", "first")

    def test_get_sprint_state_missing_raises(self, db):
        with pytest.raises(ValueError, match="not registered"):
            db.get_sprint_state("999")

    def test_advance_phase_from_roadmap(self, db):
        db.register_sprint("010", "test-sprint")
        result = db.advance_phase("010")
        assert result["old_phase"] == "roadmap"
        assert result["new_phase"] == "planning-docs"

    def test_advance_phase_from_planning_docs(self, db):
        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")  # roadmap -> planning-docs
        result = db.advance_phase("010")  # planning-docs -> architecture-review
        assert result["old_phase"] == "planning-docs"
        assert result["new_phase"] == "architecture-review"

    def test_advance_phase_requires_gate(self, db):
        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")  # roadmap -> planning-docs
        db.advance_phase("010")  # planning-docs -> architecture-review
        # architecture-review -> stakeholder-review requires architecture_review gate
        with pytest.raises(ValueError, match="gate.*architecture_review.*not passed"):
            db.advance_phase("010")

    def test_record_gate_and_advance(self, db):
        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")  # roadmap -> planning-docs
        db.advance_phase("010")  # planning-docs -> architecture-review
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


class TestActiveAgents:
    """Test active_agents table methods."""

    @pytest.fixture()
    def db(self, tmp_path):
        sdb = StateDB(tmp_path / ".clasi.db")
        sdb.init()
        return sdb

    def test_register_and_get_active_agent(self, db):
        result = db.register_active_agent("agent-abc", "programmer", "2", "/tmp/log.md")
        assert result["agent_id"] == "agent-abc"
        assert result["agent_type"] == "programmer"
        assert result["tier"] == "2"
        assert result["log_file"] == "/tmp/log.md"
        assert "started_at" in result

        record = db.get_active_agent("agent-abc")
        assert record is not None
        assert record["agent_id"] == "agent-abc"
        assert record["agent_type"] == "programmer"
        assert record["tier"] == "2"
        assert record["log_file"] == "/tmp/log.md"

    def test_get_active_agent_returns_none_when_missing(self, db):
        result = db.get_active_agent("nonexistent")
        assert result is None

    def test_register_active_agent_upserts(self, db):
        db.register_active_agent("agent-abc", "programmer", "2", "/tmp/old.md")
        db.register_active_agent("agent-abc", "sprint-planner", "1", "/tmp/new.md")
        record = db.get_active_agent("agent-abc")
        assert record["agent_type"] == "sprint-planner"
        assert record["tier"] == "1"
        assert record["log_file"] == "/tmp/new.md"

    def test_remove_active_agent(self, db):
        db.register_active_agent("agent-abc", "programmer", "2")
        result = db.remove_active_agent("agent-abc")
        assert result["removed"] is True
        assert db.get_active_agent("agent-abc") is None

    def test_remove_active_agent_missing(self, db):
        result = db.remove_active_agent("nonexistent")
        assert result["removed"] is False

    def test_get_active_tier_returns_empty_when_no_agents(self, db):
        tier = db.get_active_tier("agent-001")
        assert tier == ""

    def test_get_active_tier_returns_tier_when_agent_present(self, db):
        db.register_active_agent("agent-001", "programmer", "2")
        tier = db.get_active_tier("agent-001")
        assert tier == "2"

    def test_get_active_tier_unknown_agent_id_returns_unresolved_sentinel(self, db):
        """A caller whose agent_id has no matching row gets the empty-string
        sentinel — never another agent's tier, even though other agents
        are registered."""
        db.register_active_agent("agent-001", "programmer", "2")
        tier = db.get_active_tier("agent-999-no-such-agent")
        assert tier == ""

    def test_get_active_tier_concurrent_agents_each_get_own_tier(self, db):
        """Non-negotiable regression test (ticket 019-003): register two
        agents with DIFFERENT tiers simultaneously, then assert each
        caller — identified by its own agent_id — gets back its OWN
        tier, not the other's and not whichever row sorts first.

        Before this fix, get_active_tier() ran `SELECT tier FROM
        active_agents LIMIT 1` with no WHERE clause, so which tier came
        back was arbitrary once more than one agent was registered. A
        single-agent test (as above) passes trivially against both the
        old and new implementation and would not have caught the bug.
        """
        db.register_active_agent("agent-tier1", "sprint-planner", "1")
        db.register_active_agent("agent-tier2", "programmer", "2")

        assert db.get_active_tier("agent-tier1") == "1"
        assert db.get_active_tier("agent-tier2") == "2"

        # Re-check in reverse order to rule out any ordering/caching
        # dependence between the two lookups.
        assert db.get_active_tier("agent-tier2") == "2"
        assert db.get_active_tier("agent-tier1") == "1"

    def test_register_active_agent_without_log_file(self, db):
        result = db.register_active_agent("agent-xyz", "programmer", "2")
        assert result["log_file"] is None
        record = db.get_active_agent("agent-xyz")
        assert record["log_file"] is None

    def test_clear_stale_agents(self, db):
        import sqlite3
        from datetime import datetime, timedelta, timezone

        # Insert a stale record directly
        stale_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        conn = sqlite3.connect(str(db.path))
        conn.execute(
            "INSERT INTO active_agents (agent_id, agent_type, tier, log_file, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("stale-agent", "programmer", "2", None, stale_time),
        )
        conn.commit()
        conn.close()

        # Insert a fresh record via API
        db.register_active_agent("fresh-agent", "programmer", "2")

        result = db.clear_stale_agents(ttl_hours=24)
        assert result["cleared"] == 1
        assert db.get_active_agent("stale-agent") is None
        assert db.get_active_agent("fresh-agent") is not None


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
        assert state["phase"] == "roadmap"
