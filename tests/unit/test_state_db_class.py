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


class TestPhaseTransitions:
    """Test the phase_transitions history table and its exposure."""

    @pytest.fixture()
    def db(self, tmp_path):
        sdb = StateDB(tmp_path / ".clasi.db")
        sdb.init()
        return sdb

    def test_init_creates_phase_transitions_table(self, tmp_path):
        import sqlite3

        sdb = StateDB(tmp_path / ".clasi.db")
        sdb.init()
        conn = sqlite3.connect(str(sdb.path))
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        conn.close()
        assert "phase_transitions" in tables

    def test_get_sprint_state_has_empty_phase_transitions_initially(self, db):
        db.register_sprint("010", "test-sprint")
        state = db.get_sprint_state("010")
        assert state["phase_transitions"] == []

    def test_advance_phase_writes_one_transition_row(self, db):
        import sqlite3

        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")  # roadmap -> planning-docs

        conn = sqlite3.connect(str(db.path))
        rows = conn.execute(
            "SELECT sprint_id, from_phase, to_phase, at "
            "FROM phase_transitions WHERE sprint_id = ?",
            ("010",),
        ).fetchall()
        conn.close()

        assert len(rows) == 1
        sprint_id, from_phase, to_phase, at = rows[0]
        assert sprint_id == "010"
        assert from_phase == "roadmap"
        assert to_phase == "planning-docs"
        assert at  # non-empty timestamp

    def test_advance_phase_transition_is_atomic_with_sprints_update(self, db):
        """The phase_transitions row and the sprints.phase update are
        written in the same transaction (same conn.commit()) -- assert
        both are visible together after advance_phase returns, which is
        the externally observable evidence of atomicity."""
        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")

        state = db.get_sprint_state("010")
        assert state["phase"] == "planning-docs"
        assert len(state["phase_transitions"]) == 1
        assert state["phase_transitions"][0]["from_phase"] == "roadmap"
        assert state["phase_transitions"][0]["to_phase"] == "planning-docs"

    def test_get_sprint_state_returns_transitions_in_order(self, db):
        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")  # roadmap -> planning-docs
        db.advance_phase("010")  # planning-docs -> architecture-review

        state = db.get_sprint_state("010")
        transitions = state["phase_transitions"]
        assert len(transitions) == 2
        assert transitions[0]["from_phase"] == "roadmap"
        assert transitions[0]["to_phase"] == "planning-docs"
        assert transitions[1]["from_phase"] == "planning-docs"
        assert transitions[1]["to_phase"] == "architecture-review"
        # Chronological order: first transition's timestamp <= second's.
        assert transitions[0]["at"] <= transitions[1]["at"]

    def test_advance_phase_failure_writes_no_transition_row(self, db):
        """If advance_phase raises (gate not satisfied), no
        phase_transitions row is written -- the UPDATE and the INSERT
        both happen only on the successful path, inside one transaction."""
        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")  # roadmap -> planning-docs
        db.advance_phase("010")  # planning-docs -> architecture-review
        with pytest.raises(ValueError, match="gate.*architecture_review.*not passed"):
            db.advance_phase("010")  # blocked: gate not passed

        state = db.get_sprint_state("010")
        assert state["phase"] == "architecture-review"
        assert len(state["phase_transitions"]) == 2


class TestOopState:
    """Test oop_state table methods (StateDB class level)."""

    @pytest.fixture()
    def db(self, tmp_path):
        sdb = StateDB(tmp_path / ".clasi.db")
        sdb.init()
        return sdb

    def test_get_oop_returns_none_when_unset(self, db):
        assert db.get_oop() is None

    def test_set_and_get_oop_round_trip(self, db):
        result = db.set_oop("testing oop", ttl_hours=8.0)
        assert result["reason"] == "testing oop"
        assert "set_at" in result
        assert "expires_at" in result

        state = db.get_oop()
        assert state is not None
        assert state["reason"] == "testing oop"
        assert state["set_at"] == result["set_at"]
        assert state["expires_at"] == result["expires_at"]

    def test_clear_oop_removes_record(self, db):
        db.set_oop("testing oop")
        cleared = db.clear_oop()
        assert cleared["cleared"] is True
        assert db.get_oop() is None

    def test_clear_oop_when_empty_is_noop(self, db):
        result = db.clear_oop()
        assert result["cleared"] is False

    def test_set_oop_overwrites_previous_record(self, db):
        db.set_oop("first reason")
        db.set_oop("second reason")

        state = db.get_oop()
        assert state["reason"] == "second reason"

    def test_get_oop_expires_and_clears_row(self, db, tmp_path):
        import sqlite3
        from datetime import datetime, timedelta, timezone

        db.set_oop("about to expire", ttl_hours=8.0)

        # Force expires_at into the past, matching get_recovery_state's
        # existing TTL test pattern.
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        conn = sqlite3.connect(str(db.path))
        conn.execute(
            "UPDATE oop_state SET expires_at = ? WHERE id = 1", (past,)
        )
        conn.commit()
        conn.close()

        assert db.get_oop() is None

        # Verify the row was actually deleted, not just masked.
        conn = sqlite3.connect(str(db.path))
        count = conn.execute("SELECT COUNT(*) FROM oop_state").fetchone()[0]
        conn.close()
        assert count == 0


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


class TestReadsDoNotCreateDatabase:
    """Ticket 029/004: a read against a nonexistent DB path must not
    create the file, and must return the method's own documented
    "absent"/default value instead.

    Covers the five methods that share the ``_owns_conn = conn is
    None`` pattern (default-connection entry points): get_lock_holder,
    get_recovery_state, get_active_agent, get_active_tier, get_oop.
    These are also exactly the reads guards (role-guard, mcp-guard)
    depend on for OOP state, the execution lock, and agent tier.
    """

    def test_get_lock_holder_creates_no_file(self, tmp_path):
        db_path = tmp_path / ".clasi.db"
        sdb = StateDB(db_path)
        assert not db_path.exists()

        result = sdb.get_lock_holder()

        assert result is None
        assert not db_path.exists()

    def test_get_oop_creates_no_file(self, tmp_path):
        db_path = tmp_path / ".clasi.db"
        sdb = StateDB(db_path)
        assert not db_path.exists()

        result = sdb.get_oop()

        assert result is None
        assert not db_path.exists()

    def test_get_active_tier_creates_no_file(self, tmp_path):
        db_path = tmp_path / ".clasi.db"
        sdb = StateDB(db_path)
        assert not db_path.exists()

        result = sdb.get_active_tier("agent-001")

        assert result == ""
        assert not db_path.exists()

    def test_get_active_agent_creates_no_file(self, tmp_path):
        db_path = tmp_path / ".clasi.db"
        sdb = StateDB(db_path)
        assert not db_path.exists()

        result = sdb.get_active_agent("agent-001")

        assert result is None
        assert not db_path.exists()

    def test_get_recovery_state_creates_no_file(self, tmp_path):
        db_path = tmp_path / ".clasi.db"
        sdb = StateDB(db_path)
        assert not db_path.exists()

        result = sdb.get_recovery_state()

        assert result is None
        assert not db_path.exists()

    def test_reads_creates_no_parent_directory_either(self, tmp_path):
        """A guard-level read against a project whose .clasi/ directory
        doesn't exist yet must not even create that parent directory --
        only init() (a real write path) does the mkdir."""
        db_path = tmp_path / ".clasi" / ".clasi.db"
        sdb = StateDB(db_path)
        assert not db_path.parent.exists()

        sdb.get_oop()
        sdb.get_lock_holder()
        sdb.get_active_tier("agent-001")

        assert not db_path.parent.exists()

    def test_write_path_still_creates_schema_on_fresh_db(self, tmp_path):
        """Sanity check for the acceptance criterion that legitimate
        write paths are unaffected: an explicit write against a
        nonexistent path still creates the file and its schema."""
        db_path = tmp_path / ".clasi.db"
        sdb = StateDB(db_path)
        assert not db_path.exists()

        sdb.set_oop("testing", ttl_hours=1.0)

        assert db_path.exists()
        assert sdb.get_oop()["reason"] == "testing"


class TestConnectBusyTimeout:
    """Ticket 029/004: sqlite3.connect must use a short busy timeout
    instead of sqlite3's own 5s default, so lock contention under
    parallel agents fails fast (a catchable OperationalError) rather
    than silently eating a hook's entire harness budget.
    """

    def test_connect_default_timeout_is_one_second(self):
        """Verified via the _connect call site itself (its default
        parameter value), not just behaviorally -- per the ticket's
        explicit instruction not to rely on a timing-based test."""
        import inspect

        from clasi.state_db_class import _connect

        default = inspect.signature(_connect).parameters["timeout"].default
        assert default == 1.0
        assert default < 5.0  # well under sqlite3's own default

    def test_connect_passes_timeout_kwarg_to_sqlite3_connect(self, tmp_path, monkeypatch):
        """The default timeout actually reaches sqlite3.connect (not just
        declared and ignored)."""
        import sqlite3

        from clasi.state_db_class import _connect

        captured = {}
        real_connect = sqlite3.connect

        def spy_connect(path, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return real_connect(path, *args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", spy_connect)

        conn = _connect(tmp_path / "t.db")
        conn.close()

        assert captured["timeout"] == 1.0

    def test_state_db_methods_use_the_short_timeout(self, tmp_path, monkeypatch):
        """A real StateDB call site (init(), which every method funnels
        through at least once) opens its connection with the short
        timeout, not sqlite3's 5s default."""
        import sqlite3

        captured = {}
        real_connect = sqlite3.connect

        def spy_connect(path, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return real_connect(path, *args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", spy_connect)

        sdb = StateDB(tmp_path / ".clasi.db")
        sdb.init()

        assert captured["timeout"] == 1.0


class TestInitRunsAtMostOncePerInstance:
    """Ticket 029/004: init() must run at most once per StateDB
    instance, tracked by an instance-level flag, instead of re-running
    executescript(_SCHEMA) (a write transaction) on every call."""

    def test_direct_repeated_init_calls_execute_schema_once(self, tmp_path, monkeypatch):
        # sqlite3.Connection is an immutable C type -- its methods can't be
        # monkeypatched directly (setattr raises TypeError). Instead, count
        # calls via a Connection *subclass* (subclasses are plain, mutable
        # Python classes) installed as sqlite3.connect's `factory`.
        import sqlite3

        calls = []

        class _CountingConnection(sqlite3.Connection):
            def executescript(self, script):
                calls.append(script)
                return super().executescript(script)

        real_connect = sqlite3.connect

        def spy_connect(path, *args, **kwargs):
            kwargs.setdefault("factory", _CountingConnection)
            return real_connect(path, *args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", spy_connect)

        sdb = StateDB(tmp_path / ".clasi.db")
        sdb.init()
        sdb.init()
        sdb.init()

        assert len(calls) == 1

    def test_init_flag_is_set_after_first_call(self, tmp_path):
        sdb = StateDB(tmp_path / ".clasi.db")
        assert sdb._initialized is False
        sdb.init()
        assert sdb._initialized is True

    def test_schema_executed_once_across_multiple_different_methods(
        self, tmp_path, monkeypatch
    ):
        """Every write method (register_sprint, acquire_lock, ...) and
        every default-conn read method (get_active_tier,
        get_lock_holder, ...) calls self.init() at its own entry point.
        On one shared StateDB instance (e.g. Project.db, cached per
        Project), only the FIRST of those calls should actually run
        executescript."""
        import sqlite3

        calls = []

        class _CountingConnection(sqlite3.Connection):
            def executescript(self, script):
                calls.append(script)
                return super().executescript(script)

        real_connect = sqlite3.connect

        def spy_connect(path, *args, **kwargs):
            kwargs.setdefault("factory", _CountingConnection)
            return real_connect(path, *args, **kwargs)

        monkeypatch.setattr(sqlite3, "connect", spy_connect)

        sdb = StateDB(tmp_path / ".clasi.db")
        sdb.register_sprint("001", "test-sprint")
        sdb.get_active_tier("agent-001")
        sdb.get_lock_holder()
        sdb.acquire_lock("001")
        sdb.get_oop()

        assert len(calls) == 1

    def test_new_instance_against_same_file_still_runs_schema(self, tmp_path):
        """The once-per-instance guard must not be mistaken for
        once-per-file: a fresh StateDB instance against a
        pre-populated database file still runs init()'s
        CREATE TABLE IF NOT EXISTS script, which is what makes
        additive migration (e.g. sprint 028's phase_transitions table)
        safe on a database created before that table existed."""
        db_path = tmp_path / ".clasi.db"

        sdb1 = StateDB(db_path)
        sdb1.init()
        sdb1.register_sprint("001", "test-sprint")

        # Simulate a database created before phase_transitions existed
        # by dropping the table, then confirm a fresh instance's init()
        # re-adds it.
        import sqlite3

        conn = sqlite3.connect(str(db_path))
        conn.execute("DROP TABLE phase_transitions")
        conn.commit()
        conn.close()

        sdb2 = StateDB(db_path)
        sdb2.init()
        state = sdb2.get_sprint_state("001")
        assert state["phase_transitions"] == []


class TestForceClose:
    """Tests for StateDB.force_close (030/004) -- transactional phase->done
    + lock release, replacing close_sprint's old ``except (ValueError,
    Exception): pass`` phase-advance loop."""

    @pytest.fixture()
    def db(self, tmp_path):
        sdb = StateDB(tmp_path / ".clasi.db")
        sdb.init()
        return sdb

    def test_sets_phase_done_and_releases_lock(self, db):
        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")  # roadmap -> planning-docs
        db.acquire_lock("010")

        result = db.force_close("010")

        assert result["phase"] == "done"
        assert result["phase_changed"] is True
        assert result["lock_released"] is True

        state = db.get_sprint_state("010")
        assert state["phase"] == "done"
        assert state["lock"] is None
        # Recorded in phase_transitions history, like advance_phase does.
        transitions = state["phase_transitions"]
        assert transitions[-1]["from_phase"] == "planning-docs"
        assert transitions[-1]["to_phase"] == "done"

    def test_jumps_directly_from_any_phase_no_gate_checks(self, db):
        """Unlike advance_phase, force_close does not step through the
        phase list one gate at a time -- it works from an early phase
        with none of the later gates satisfied (e.g. no architecture_review
        gate recorded, no execution lock held)."""
        db.register_sprint("010", "test-sprint")
        # Still at 'roadmap' -- no gates recorded, no lock acquired. A
        # plain advance_phase() loop would hit the architecture_review
        # gate requirement and raise; force_close must not.
        result = db.force_close("010")
        assert result["phase"] == "done"
        assert db.get_sprint_state("010")["phase"] == "done"

    def test_idempotent_noop_when_already_done(self, db):
        db.register_sprint("010", "test-sprint")
        db.force_close("010")

        # Second call: cheap no-op, not an error.
        result = db.force_close("010")
        assert result["phase"] == "done"
        assert result["phase_changed"] is False
        assert result["lock_released"] is False

    def test_lock_released_only_if_held_by_this_sprint(self, db):
        """force_close on sprint A must not release a lock held by a
        different sprint B."""
        db.register_sprint("010", "sprint-a")
        db.register_sprint("011", "sprint-b")
        db.acquire_lock("011")  # sprint B holds the lock

        result = db.force_close("010")

        assert result["phase"] == "done"
        assert result["lock_released"] is False
        # Lock is untouched -- still held by sprint B.
        lock = db.get_lock_holder()
        assert lock is not None
        assert lock["sprint_id"] == "011"

    def test_raises_for_unregistered_sprint(self, db):
        with pytest.raises(ValueError, match="not registered"):
            db.force_close("999")

    def test_is_transactional_no_partial_write_on_mid_transaction_failure(self, db, monkeypatch):
        """If something fails between the phase UPDATE and the final
        commit, neither write should be visible afterward -- both halves
        live in the one implicit transaction force_close's single
        conn.commit() closes, so an interrupted call leaves ground truth
        exactly where it started, not half-advanced.

        sqlite3.Connection is a C-level immutable type (its methods
        cannot be monkeypatched directly), so the failure is injected via
        a thin proxy in place of clasi.state_db_class._connect's return
        value instead.
        """
        import sqlite3

        import clasi.state_db_class as state_db_class_module

        db.register_sprint("010", "test-sprint")
        db.advance_phase("010")  # roadmap -> planning-docs
        db.acquire_lock("010")

        real_connect = state_db_class_module._connect

        class _FailingConnProxy:
            """Delegates everything to a real connection except execute(),
            which raises once the phase_transitions history INSERT runs --
            i.e. right after the phase UPDATE succeeds but before
            force_close reaches its lock DELETE or its one conn.commit()."""

            def __init__(self, real_conn):
                self._real = real_conn

            def execute(self, sql, *args, **kwargs):
                if sql.strip().upper().startswith("INSERT INTO PHASE_TRANSITIONS"):
                    raise sqlite3.OperationalError("simulated mid-transaction failure")
                return self._real.execute(sql, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._real, name)

        def _patched_connect(db_path, timeout: float = 1.0):
            return _FailingConnProxy(real_connect(db_path, timeout=timeout))

        monkeypatch.setattr(state_db_class_module, "_connect", _patched_connect)

        with pytest.raises(sqlite3.OperationalError):
            db.force_close("010")

        monkeypatch.undo()

        # Re-read with the real (unpatched) connect: neither the phase
        # UPDATE nor the lock DELETE survived -- force_close's
        # finally: conn.close() discards the uncommitted transaction.
        state = db.get_sprint_state("010")
        assert state["phase"] == "planning-docs"
        assert state["lock"] is not None
        assert state["lock"]["sprint_id"] == "010"
