"""Tests for claude_agent_skills.state_db module."""

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from claude_agent_skills.state_db import (
    PHASES,
    init_db,
    register_sprint,
    get_sprint_state,
    advance_phase,
    record_gate,
    acquire_lock,
    release_lock,
    get_lock_holder,
    write_recovery_state,
    get_recovery_state,
    clear_recovery_state,
)


@pytest.fixture
def db_path(tmp_path):
    """Return a temporary database path."""
    return tmp_path / "test.db"


class TestInitDb:
    def test_creates_database_file(self, db_path):
        init_db(db_path)
        assert db_path.exists()

    def test_creates_tables(self, db_path):
        init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        conn.close()
        assert "sprints" in tables
        assert "sprint_gates" in tables
        assert "execution_locks" in tables

    def test_idempotent(self, db_path):
        init_db(db_path)
        init_db(db_path)  # Should not raise
        assert db_path.exists()

    def test_enables_wal_mode(self, db_path):
        init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_creates_parent_directories(self, tmp_path):
        deep_path = tmp_path / "a" / "b" / "c" / "test.db"
        init_db(deep_path)
        assert deep_path.exists()


class TestRegisterSprint:
    def test_registers_sprint(self, db_path):
        result = register_sprint(db_path, "001", "test-sprint", "sprint/001-test-sprint")
        assert result["id"] == "001"
        assert result["slug"] == "test-sprint"
        assert result["phase"] == "planning-docs"
        assert result["branch"] == "sprint/001-test-sprint"
        assert result["created_at"] is not None
        assert result["updated_at"] is not None

    def test_lazy_init(self, db_path):
        """register_sprint creates the DB if it doesn't exist."""
        assert not db_path.exists()
        register_sprint(db_path, "001", "test", None)
        assert db_path.exists()

    def test_duplicate_raises(self, db_path):
        register_sprint(db_path, "001", "test", None)
        with pytest.raises(ValueError, match="already registered"):
            register_sprint(db_path, "001", "test", None)

    def test_multiple_sprints(self, db_path):
        r1 = register_sprint(db_path, "001", "first", None)
        r2 = register_sprint(db_path, "002", "second", None)
        assert r1["id"] == "001"
        assert r2["id"] == "002"

    def test_branch_optional(self, db_path):
        result = register_sprint(db_path, "001", "test")
        assert result["branch"] is None


class TestGetSprintState:
    def test_returns_state(self, db_path):
        register_sprint(db_path, "001", "test", "sprint/001-test")
        state = get_sprint_state(db_path, "001")
        assert state["id"] == "001"
        assert state["slug"] == "test"
        assert state["phase"] == "planning-docs"
        assert state["branch"] == "sprint/001-test"
        assert state["gates"] == []
        assert state["lock"] is None

    def test_not_registered_raises(self, db_path):
        init_db(db_path)
        with pytest.raises(ValueError, match="not registered"):
            get_sprint_state(db_path, "999")

    def test_lazy_init(self, db_path):
        """get_sprint_state initializes DB if needed, then raises for missing sprint."""
        assert not db_path.exists()
        with pytest.raises(ValueError, match="not registered"):
            get_sprint_state(db_path, "001")
        assert db_path.exists()


class TestAdvancePhase:
    def test_advance_from_planning_docs(self, db_path):
        register_sprint(db_path, "001", "test")
        result = advance_phase(db_path, "001")
        assert result["old_phase"] == "planning-docs"
        assert result["new_phase"] == "architecture-review"

    def test_advance_requires_gate(self, db_path):
        register_sprint(db_path, "001", "test")
        advance_phase(db_path, "001")  # → architecture-review
        with pytest.raises(ValueError, match="architecture_review.*not passed"):
            advance_phase(db_path, "001")  # needs gate

    def test_advance_after_gate_passes(self, db_path):
        register_sprint(db_path, "001", "test")
        advance_phase(db_path, "001")  # → architecture-review
        record_gate(db_path, "001", "architecture_review", "passed")
        result = advance_phase(db_path, "001")  # → stakeholder-review
        assert result["new_phase"] == "stakeholder-review"

    def test_advance_stakeholder_gate(self, db_path):
        register_sprint(db_path, "001", "test")
        advance_phase(db_path, "001")  # → architecture-review
        record_gate(db_path, "001", "architecture_review", "passed")
        advance_phase(db_path, "001")  # → stakeholder-review
        with pytest.raises(ValueError, match="stakeholder_approval.*not passed"):
            advance_phase(db_path, "001")

    def test_full_lifecycle(self, db_path):
        register_sprint(db_path, "001", "test")
        advance_phase(db_path, "001")  # → architecture-review
        record_gate(db_path, "001", "architecture_review", "passed")
        advance_phase(db_path, "001")  # → stakeholder-review
        record_gate(db_path, "001", "stakeholder_approval", "passed")
        advance_phase(db_path, "001")  # → ticketing
        acquire_lock(db_path, "001")
        advance_phase(db_path, "001")  # → executing
        advance_phase(db_path, "001")  # → closing
        advance_phase(db_path, "001")  # → done
        state = get_sprint_state(db_path, "001")
        assert state["phase"] == "done"

    def test_cannot_advance_past_done(self, db_path):
        register_sprint(db_path, "001", "test")
        advance_phase(db_path, "001")  # → architecture-review
        record_gate(db_path, "001", "architecture_review", "passed")
        advance_phase(db_path, "001")  # → stakeholder-review
        record_gate(db_path, "001", "stakeholder_approval", "passed")
        advance_phase(db_path, "001")  # → ticketing
        acquire_lock(db_path, "001")
        advance_phase(db_path, "001")  # → executing
        advance_phase(db_path, "001")  # → closing
        advance_phase(db_path, "001")  # → done
        with pytest.raises(ValueError, match="already done"):
            advance_phase(db_path, "001")

    def test_ticketing_to_executing_requires_lock(self, db_path):
        register_sprint(db_path, "001", "test")
        advance_phase(db_path, "001")
        record_gate(db_path, "001", "architecture_review", "passed")
        advance_phase(db_path, "001")
        record_gate(db_path, "001", "stakeholder_approval", "passed")
        advance_phase(db_path, "001")  # → ticketing
        with pytest.raises(ValueError, match="execution lock"):
            advance_phase(db_path, "001")

    def test_not_registered_raises(self, db_path):
        init_db(db_path)
        with pytest.raises(ValueError, match="not registered"):
            advance_phase(db_path, "999")

    def test_failed_gate_blocks(self, db_path):
        register_sprint(db_path, "001", "test")
        advance_phase(db_path, "001")  # → architecture-review
        record_gate(db_path, "001", "architecture_review", "failed")
        with pytest.raises(ValueError, match="not passed"):
            advance_phase(db_path, "001")


class TestRecordGate:
    def test_records_gate(self, db_path):
        register_sprint(db_path, "001", "test")
        result = record_gate(db_path, "001", "architecture_review", "passed")
        assert result["gate_name"] == "architecture_review"
        assert result["result"] == "passed"
        assert result["recorded_at"] is not None

    def test_with_notes(self, db_path):
        register_sprint(db_path, "001", "test")
        result = record_gate(db_path, "001", "architecture_review", "passed", "Looks good")
        assert result["notes"] == "Looks good"

    def test_upsert_overwrites(self, db_path):
        register_sprint(db_path, "001", "test")
        record_gate(db_path, "001", "architecture_review", "failed", "Issues found")
        result = record_gate(db_path, "001", "architecture_review", "passed", "Fixed")
        assert result["result"] == "passed"
        assert result["notes"] == "Fixed"
        state = get_sprint_state(db_path, "001")
        assert len(state["gates"]) == 1
        assert state["gates"][0]["result"] == "passed"

    def test_invalid_gate_name(self, db_path):
        register_sprint(db_path, "001", "test")
        with pytest.raises(ValueError, match="Invalid gate name"):
            record_gate(db_path, "001", "bogus", "passed")

    def test_invalid_result(self, db_path):
        register_sprint(db_path, "001", "test")
        with pytest.raises(ValueError, match="Invalid result"):
            record_gate(db_path, "001", "architecture_review", "maybe")

    def test_not_registered_raises(self, db_path):
        init_db(db_path)
        with pytest.raises(ValueError, match="not registered"):
            record_gate(db_path, "999", "architecture_review", "passed")

    def test_visible_in_state(self, db_path):
        register_sprint(db_path, "001", "test")
        record_gate(db_path, "001", "architecture_review", "passed")
        record_gate(db_path, "001", "stakeholder_approval", "passed")
        state = get_sprint_state(db_path, "001")
        assert len(state["gates"]) == 2
        names = {g["gate_name"] for g in state["gates"]}
        assert names == {"architecture_review", "stakeholder_approval"}


class TestExecutionLocks:
    def test_acquire_lock(self, db_path):
        register_sprint(db_path, "001", "test")
        result = acquire_lock(db_path, "001")
        assert result["sprint_id"] == "001"
        assert result["reentrant"] is False

    def test_reentrant_acquire(self, db_path):
        register_sprint(db_path, "001", "test")
        acquire_lock(db_path, "001")
        result = acquire_lock(db_path, "001")
        assert result["reentrant"] is True

    def test_conflict(self, db_path):
        register_sprint(db_path, "001", "first")
        register_sprint(db_path, "002", "second")
        acquire_lock(db_path, "001")
        with pytest.raises(ValueError, match="held by sprint '001'"):
            acquire_lock(db_path, "002")

    def test_release_lock(self, db_path):
        register_sprint(db_path, "001", "test")
        acquire_lock(db_path, "001")
        result = release_lock(db_path, "001")
        assert result["released"] is True

    def test_release_when_not_held(self, db_path):
        init_db(db_path)
        with pytest.raises(ValueError, match="No execution lock"):
            release_lock(db_path, "001")

    def test_release_wrong_sprint(self, db_path):
        register_sprint(db_path, "001", "first")
        register_sprint(db_path, "002", "second")
        acquire_lock(db_path, "001")
        with pytest.raises(ValueError, match="does not hold"):
            release_lock(db_path, "002")

    def test_get_lock_holder(self, db_path):
        register_sprint(db_path, "001", "test")
        assert get_lock_holder(db_path) is None
        acquire_lock(db_path, "001")
        holder = get_lock_holder(db_path)
        assert holder["sprint_id"] == "001"

    def test_acquire_after_release(self, db_path):
        register_sprint(db_path, "001", "first")
        register_sprint(db_path, "002", "second")
        acquire_lock(db_path, "001")
        release_lock(db_path, "001")
        result = acquire_lock(db_path, "002")
        assert result["sprint_id"] == "002"
        assert result["reentrant"] is False

    def test_not_registered_raises(self, db_path):
        init_db(db_path)
        with pytest.raises(ValueError, match="not registered"):
            acquire_lock(db_path, "999")

    def test_visible_in_state(self, db_path):
        register_sprint(db_path, "001", "test")
        acquire_lock(db_path, "001")
        state = get_sprint_state(db_path, "001")
        assert state["lock"] is not None
        assert state["lock"]["sprint_id"] == "001"


class TestPhaseConstants:
    def test_phase_order(self):
        assert PHASES[0] == "planning-docs"
        assert PHASES[-1] == "done"
        assert len(PHASES) == 7

    def test_all_phases_present(self):
        expected = {
            "planning-docs", "architecture-review", "stakeholder-review",
            "ticketing", "executing", "closing", "done",
        }
        assert set(PHASES) == expected


class TestRecoveryState:
    def test_write_creates_record(self, db_path):
        result = write_recovery_state(
            db_path, "001", "merge", ["/path/a.py"], "conflict in a.py"
        )
        assert result["sprint_id"] == "001"
        assert result["step"] == "merge"
        assert result["allowed_paths"] == ["/path/a.py"]
        assert result["reason"] == "conflict in a.py"
        assert result["recorded_at"] is not None

    def test_get_returns_record(self, db_path):
        write_recovery_state(db_path, "001", "tests", [], "tests failed")
        record = get_recovery_state(db_path)
        assert record is not None
        assert record["sprint_id"] == "001"
        assert record["step"] == "tests"
        assert record["allowed_paths"] == []
        assert record["reason"] == "tests failed"

    def test_get_returns_none_when_empty(self, db_path):
        init_db(db_path)
        assert get_recovery_state(db_path) is None

    def test_ttl_clears_stale_record(self, db_path):
        write_recovery_state(db_path, "001", "merge", [], "conflict")
        # Manually set recorded_at to >24h ago
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "UPDATE recovery_state SET recorded_at = ? WHERE id = 1",
            (old_time,),
        )
        conn.commit()
        conn.close()

        result = get_recovery_state(db_path)
        assert result is None

        # Verify record was actually deleted
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT COUNT(*) FROM recovery_state").fetchone()
        conn.close()
        assert row[0] == 0

    def test_clear_removes_record(self, db_path):
        write_recovery_state(db_path, "001", "merge", [], "conflict")
        result = clear_recovery_state(db_path)
        assert result["cleared"] is True
        assert get_recovery_state(db_path) is None

    def test_clear_when_no_record(self, db_path):
        init_db(db_path)
        result = clear_recovery_state(db_path)
        assert result["cleared"] is False

    def test_singleton_constraint(self, db_path):
        """Writing twice should overwrite, not create two records."""
        write_recovery_state(db_path, "001", "merge", ["/a.py"], "first")
        write_recovery_state(db_path, "002", "tests", ["/b.py"], "second")

        record = get_recovery_state(db_path)
        assert record["sprint_id"] == "002"
        assert record["step"] == "tests"

        # Verify only one row
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM recovery_state").fetchone()[0]
        conn.close()
        assert count == 1

    def test_table_in_schema(self, db_path):
        """recovery_state table should be created by init_db."""
        init_db(db_path)
        conn = sqlite3.connect(str(db_path))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        conn.close()
        assert "recovery_state" in tables
