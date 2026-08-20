"""StateDB: SQLite-backed sprint lifecycle state database.

All database logic lives here. The module-level functions in state_db.py
are thin wrappers that instantiate StateDB and delegate to these methods.
"""

from __future__ import annotations

import importlib.resources as _res
import json as _json
import logging as _logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from clasi.schemas import loader as _loader
from clasi.schemas.graph import ArtifactGraph as _ArtifactGraph

_logger = _logging.getLogger(__name__)

_schema_path = _res.files("clasi.schemas").joinpath("se-process", "schema.yaml")
PHASES = _ArtifactGraph(_loader.load(_schema_path)).phases()

VALID_GATE_NAMES = {"architecture_review", "stakeholder_approval"}
VALID_GATE_RESULTS = {"passed", "failed", "skipped"}

# Gate results that satisfy an advance-phase gate requirement. "skipped" is
# treated as equivalent to "passed" for the purpose of unblocking phase
# advancement (e.g. an architecture review skipped for a trivial change);
# "failed" still blocks.
_SATISFYING_GATE_RESULTS = {"passed", "skipped"}

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS sprints (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'roadmap',
    branch TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sprint_gates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sprint_id TEXT NOT NULL REFERENCES sprints(id),
    gate_name TEXT NOT NULL,
    result TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    notes TEXT,
    UNIQUE(sprint_id, gate_name)
);

CREATE TABLE IF NOT EXISTS execution_locks (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    sprint_id TEXT NOT NULL REFERENCES sprints(id),
    acquired_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recovery_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    sprint_id TEXT NOT NULL,
    step TEXT NOT NULL,
    allowed_paths TEXT NOT NULL,
    reason TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS active_agents (
    agent_id TEXT PRIMARY KEY,
    agent_type TEXT NOT NULL,
    tier TEXT NOT NULL,
    log_file TEXT,
    started_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oop_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    set_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

# Gate requirements for each transition: {from_phase: required_gate_name or None}
_GATE_REQUIREMENTS: dict[str, Optional[str]] = {
    "roadmap": None,  # No gate to advance from roadmap
    "planning-docs": None,  # No gate to advance from planning-docs
    "architecture-review": "architecture_review",
    "stakeholder-review": "stakeholder_approval",
    "ticketing": None,  # Checked programmatically (needs tickets + lock)
    "executing": None,  # Checked programmatically (all tickets done)
    "closing": None,  # Checked programmatically (sprint archived)
}

_RECOVERY_TTL = timedelta(hours=24)
_OOP_DEFAULT_TTL_HOURS = 8.0


def _now() -> str:
    """Return the current time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection with WAL mode and foreign keys enabled."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class StateDB:
    """CLASI SQLite state database.

    Provides all sprint lifecycle tracking: phases, review gates,
    execution locks, and recovery state.
    """

    def __init__(self, db_path: str | Path):
        self._path = Path(db_path)

    @property
    def path(self) -> Path:
        return self._path

    def init(self) -> None:
        """Create the database file and all tables if they do not exist."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = _connect(self._path)
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    def connect(self) -> sqlite3.Connection:
        """Open a new connection to this database (WAL mode, foreign keys on).

        Does NOT call init() — callers needing schema guarantees should
        rely on the individual query methods' default (conn=None)
        behavior, which calls init() automatically, or call init()
        themselves first. This method exists for a caller that wants to
        share ONE connection across several StateDB method calls within
        a single short-lived process (see handle_role_guard's
        per-invocation cache in hook_handlers.py) instead of each method
        opening and closing its own. The caller owns the returned
        connection's lifecycle and must close it.
        """
        return _connect(self._path)

    def register_sprint(
        self,
        sprint_id: str,
        slug: str,
        branch: Optional[str] = None,
    ) -> dict[str, Any]:
        """Register a new sprint in the state database.

        Calls init() internally (lazy initialization).

        Raises ValueError if the sprint is already registered.
        """
        self.init()
        now = _now()
        conn = _connect(self._path)
        try:
            try:
                conn.execute(
                    "INSERT INTO sprints (id, slug, phase, branch, created_at, updated_at) "
                    "VALUES (?, ?, 'roadmap', ?, ?, ?)",
                    (sprint_id, slug, branch, now, now),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                raise ValueError(f"Sprint '{sprint_id}' is already registered")
            return {
                "id": sprint_id,
                "slug": slug,
                "phase": "roadmap",
                "branch": branch,
                "created_at": now,
                "updated_at": now,
            }
        finally:
            conn.close()

    def get_sprint_state(self, sprint_id: str) -> dict[str, Any]:
        """Return a dict with the sprint's phase, gates, and lock status.

        Raises ValueError if the sprint is not registered.
        """
        self.init()
        conn = _connect(self._path)
        try:
            row = conn.execute(
                "SELECT id, slug, phase, branch, created_at, updated_at "
                "FROM sprints WHERE id = ?",
                (sprint_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Sprint '{sprint_id}' is not registered")

            gates = []
            for g in conn.execute(
                "SELECT gate_name, result, recorded_at, notes "
                "FROM sprint_gates WHERE sprint_id = ? ORDER BY gate_name",
                (sprint_id,),
            ):
                gates.append({
                    "gate_name": g["gate_name"],
                    "result": g["result"],
                    "recorded_at": g["recorded_at"],
                    "notes": g["notes"],
                })

            lock_row = conn.execute(
                "SELECT sprint_id, acquired_at FROM execution_locks WHERE id = 1"
            ).fetchone()
            lock = None
            if lock_row and lock_row["sprint_id"] == sprint_id:
                lock = {
                    "sprint_id": lock_row["sprint_id"],
                    "acquired_at": lock_row["acquired_at"],
                }

            return {
                "id": row["id"],
                "slug": row["slug"],
                "phase": row["phase"],
                "branch": row["branch"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "gates": gates,
                "lock": lock,
            }
        finally:
            conn.close()

    def advance_phase(self, sprint_id: str) -> dict[str, Any]:
        """Advance a sprint to the next lifecycle phase.

        Validates that exit conditions for the current phase are met before
        advancing. Returns a dict with old_phase and new_phase.

        Raises ValueError if conditions are not met or the sprint is already done.
        """
        self.init()
        conn = _connect(self._path)
        try:
            row = conn.execute(
                "SELECT phase FROM sprints WHERE id = ?", (sprint_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Sprint '{sprint_id}' is not registered")

            current = row["phase"]
            if current == "done":
                raise ValueError(f"Sprint '{sprint_id}' is already done")

            idx = PHASES.index(current)
            next_phase = PHASES[idx + 1]

            # Check gate requirements
            required_gate = _GATE_REQUIREMENTS.get(current)
            if required_gate:
                gate_row = conn.execute(
                    "SELECT result FROM sprint_gates "
                    "WHERE sprint_id = ? AND gate_name = ?",
                    (sprint_id, required_gate),
                ).fetchone()
                if gate_row is None or gate_row["result"] not in _SATISFYING_GATE_RESULTS:
                    raise ValueError(
                        f"Cannot advance from '{current}': "
                        f"gate '{required_gate}' has not passed"
                    )

            # Special check: ticketing → executing requires lock
            if current == "ticketing":
                lock_row = conn.execute(
                    "SELECT sprint_id FROM execution_locks WHERE id = 1"
                ).fetchone()
                if lock_row is None or lock_row["sprint_id"] != sprint_id:
                    raise ValueError(
                        f"Cannot advance to 'executing': "
                        f"sprint '{sprint_id}' does not hold the execution lock"
                    )

            now = _now()
            conn.execute(
                "UPDATE sprints SET phase = ?, updated_at = ? WHERE id = ?",
                (next_phase, now, sprint_id),
            )
            conn.commit()

            return {"sprint_id": sprint_id, "old_phase": current, "new_phase": next_phase}
        finally:
            conn.close()

    def record_gate(
        self,
        sprint_id: str,
        gate: str,
        result: str,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record a review gate result for a sprint.

        Uses upsert semantics: re-recording a gate overwrites the previous result.

        Raises ValueError for invalid gate names or results, or if the sprint
        is not registered.
        """
        if gate not in VALID_GATE_NAMES:
            raise ValueError(
                f"Invalid gate name '{gate}'. "
                f"Must be one of: {', '.join(sorted(VALID_GATE_NAMES))}"
            )
        if result not in VALID_GATE_RESULTS:
            raise ValueError(
                f"Invalid result '{result}'. "
                f"Must be one of: {', '.join(sorted(VALID_GATE_RESULTS))}"
            )

        self.init()
        conn = _connect(self._path)
        try:
            # Verify sprint exists
            row = conn.execute(
                "SELECT id FROM sprints WHERE id = ?", (sprint_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Sprint '{sprint_id}' is not registered")

            now = _now()
            conn.execute(
                "INSERT INTO sprint_gates (sprint_id, gate_name, result, recorded_at, notes) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(sprint_id, gate_name) DO UPDATE SET "
                "result = excluded.result, recorded_at = excluded.recorded_at, "
                "notes = excluded.notes",
                (sprint_id, gate, result, now, notes),
            )
            conn.commit()

            return {
                "sprint_id": sprint_id,
                "gate_name": gate,
                "result": result,
                "recorded_at": now,
                "notes": notes,
            }
        finally:
            conn.close()

    def acquire_lock(self, sprint_id: str) -> dict[str, Any]:
        """Acquire the execution lock for a sprint.

        Only one sprint can hold the lock at a time (singleton table).
        Re-entrant: if the sprint already holds the lock, returns success.

        Raises ValueError if another sprint holds the lock.
        """
        self.init()
        conn = _connect(self._path)
        try:
            # Verify sprint exists
            row = conn.execute(
                "SELECT id FROM sprints WHERE id = ?", (sprint_id,)
            ).fetchone()
            if row is None:
                raise ValueError(f"Sprint '{sprint_id}' is not registered")

            lock_row = conn.execute(
                "SELECT sprint_id, acquired_at FROM execution_locks WHERE id = 1"
            ).fetchone()

            if lock_row is not None:
                if lock_row["sprint_id"] == sprint_id:
                    # Re-entrant: already holds lock
                    return {
                        "sprint_id": sprint_id,
                        "acquired_at": lock_row["acquired_at"],
                        "reentrant": True,
                    }
                raise ValueError(
                    f"Execution lock held by sprint '{lock_row['sprint_id']}' "
                    f"since {lock_row['acquired_at']}"
                )

            now = _now()
            conn.execute(
                "INSERT INTO execution_locks (id, sprint_id, acquired_at) "
                "VALUES (1, ?, ?)",
                (sprint_id, now),
            )
            conn.commit()

            return {"sprint_id": sprint_id, "acquired_at": now, "reentrant": False}
        finally:
            conn.close()

    def release_lock(self, sprint_id: str) -> dict[str, Any]:
        """Release the execution lock held by a sprint.

        Raises ValueError if the sprint does not hold the lock.
        """
        self.init()
        conn = _connect(self._path)
        try:
            lock_row = conn.execute(
                "SELECT sprint_id FROM execution_locks WHERE id = 1"
            ).fetchone()

            if lock_row is None:
                raise ValueError("No execution lock is currently held")
            if lock_row["sprint_id"] != sprint_id:
                raise ValueError(
                    f"Sprint '{sprint_id}' does not hold the lock "
                    f"(held by '{lock_row['sprint_id']}')"
                )

            conn.execute("DELETE FROM execution_locks WHERE id = 1")
            conn.commit()

            return {"sprint_id": sprint_id, "released": True}
        finally:
            conn.close()

    def rename_sprint(
        self,
        old_id: str,
        new_id: str,
        new_branch: Optional[str] = None,
    ) -> dict[str, Any]:
        """Rename a sprint's ID in the state database.

        Updates the sprints table and any references in sprint_gates.
        Does NOT touch execution_locks (only planning-docs sprints should
        be renamed, and they can't hold locks).

        Raises ValueError if old_id is not registered or new_id already exists.
        """
        self.init()
        conn = _connect(self._path)
        try:
            row = conn.execute(
                "SELECT id, slug, phase, branch FROM sprints WHERE id = ?",
                (old_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Sprint '{old_id}' is not registered")

            existing = conn.execute(
                "SELECT id FROM sprints WHERE id = ?", (new_id,)
            ).fetchone()
            if existing is not None:
                raise ValueError(f"Sprint '{new_id}' already exists in database")

            now = _now()
            branch = new_branch if new_branch is not None else row["branch"]

            # Update sprint_gates first (foreign key references)
            conn.execute("PRAGMA foreign_keys=OFF")
            conn.execute(
                "UPDATE sprint_gates SET sprint_id = ? WHERE sprint_id = ?",
                (new_id, old_id),
            )
            conn.execute(
                "UPDATE sprints SET id = ?, branch = ?, updated_at = ? WHERE id = ?",
                (new_id, branch, now, old_id),
            )
            conn.execute("PRAGMA foreign_keys=ON")
            conn.commit()

            return {
                "old_id": old_id,
                "new_id": new_id,
                "branch": branch,
            }
        finally:
            conn.close()

    def get_lock_holder(
        self, conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[dict[str, Any]]:
        """Return the current lock holder, or None if no lock is held.

        If *conn* is given, it is used directly and this method neither
        calls init() nor opens/closes its own connection — the caller
        owns the connection's lifecycle (see StateDB.connect()). Omitted
        (the default), behavior is unchanged: init() runs and a fresh
        connection is opened and closed internally.
        """
        _owns_conn = conn is None
        if _owns_conn:
            self.init()
            conn = _connect(self._path)
        try:
            lock_row = conn.execute(
                "SELECT sprint_id, acquired_at FROM execution_locks WHERE id = 1"
            ).fetchone()
            if lock_row is None:
                return None
            return {
                "sprint_id": lock_row["sprint_id"],
                "acquired_at": lock_row["acquired_at"],
            }
        finally:
            if _owns_conn:
                conn.close()

    def write_recovery_state(
        self,
        sprint_id: str,
        step: str,
        allowed_paths: list[str],
        reason: str,
    ) -> dict[str, Any]:
        """Write or overwrite the singleton recovery state record.

        Only one recovery record exists at a time (id=1). Calling this
        again replaces any previous record.
        """
        self.init()
        now = _now()
        conn = _connect(self._path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO recovery_state "
                "(id, sprint_id, step, allowed_paths, reason, recorded_at) "
                "VALUES (1, ?, ?, ?, ?, ?)",
                (sprint_id, step, _json.dumps(allowed_paths), reason, now),
            )
            conn.commit()
            return {
                "sprint_id": sprint_id,
                "step": step,
                "allowed_paths": allowed_paths,
                "reason": reason,
                "recorded_at": now,
            }
        finally:
            conn.close()

    def get_recovery_state(
        self, conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[dict[str, Any]]:
        """Read the recovery state record, auto-clearing stale entries.

        Returns a dict with sprint_id, step, allowed_paths, reason, and
        recorded_at -- or None if no record exists. Records older than 24
        hours are automatically deleted with a warning on stderr.

        If *conn* is given, it is used directly and this method neither
        calls init() nor opens/closes its own connection — the caller
        owns the connection's lifecycle (see StateDB.connect()). Omitted
        (the default), behavior is unchanged: init() runs and a fresh
        connection is opened and closed internally.
        """
        _owns_conn = conn is None
        if _owns_conn:
            self.init()
            conn = _connect(self._path)
        try:
            row = conn.execute(
                "SELECT sprint_id, step, allowed_paths, reason, recorded_at "
                "FROM recovery_state WHERE id = 1"
            ).fetchone()
            if row is None:
                return None

            recorded_at = datetime.fromisoformat(row["recorded_at"])
            if datetime.now(timezone.utc) - recorded_at > _RECOVERY_TTL:
                conn.execute("DELETE FROM recovery_state WHERE id = 1")
                conn.commit()
                print(
                    f"[CLASI] Stale recovery state for sprint '{row['sprint_id']}' "
                    f"(recorded {row['recorded_at']}) auto-cleared after 24h TTL",
                    file=sys.stderr,
                )
                return None

            return {
                "sprint_id": row["sprint_id"],
                "step": row["step"],
                "allowed_paths": _json.loads(row["allowed_paths"]),
                "reason": row["reason"],
                "recorded_at": row["recorded_at"],
            }
        finally:
            if _owns_conn:
                conn.close()

    def clear_recovery_state(self) -> dict[str, Any]:
        """Delete the recovery state record.

        Returns {"cleared": True} if a record was removed,
        {"cleared": False} if no record existed.
        """
        self.init()
        conn = _connect(self._path)
        try:
            cursor = conn.execute("DELETE FROM recovery_state WHERE id = 1")
            conn.commit()
            return {"cleared": cursor.rowcount > 0}
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Active agent tracking
    # ------------------------------------------------------------------

    def register_active_agent(
        self,
        agent_id: str,
        agent_type: str,
        tier: str,
        log_file: Optional[str] = None,
    ) -> dict[str, Any]:
        """Register an active agent in the database.

        Uses upsert semantics: re-registering the same agent_id overwrites
        the previous record.
        """
        self.init()
        now = _now()
        conn = _connect(self._path)
        try:
            conn.execute(
                "INSERT INTO active_agents (agent_id, agent_type, tier, log_file, started_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(agent_id) DO UPDATE SET "
                "agent_type = excluded.agent_type, tier = excluded.tier, "
                "log_file = excluded.log_file, started_at = excluded.started_at",
                (agent_id, agent_type, tier, log_file, now),
            )
            conn.commit()
            return {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "tier": tier,
                "log_file": log_file,
                "started_at": now,
            }
        finally:
            conn.close()

    def get_active_agent(
        self, agent_id: str, conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[dict[str, Any]]:
        """Return the active agent record for the given agent_id, or None.

        If *conn* is given, it is used directly and this method neither
        calls init() nor opens/closes its own connection — the caller
        owns the connection's lifecycle (see StateDB.connect()). Omitted
        (the default), behavior is unchanged: init() runs and a fresh
        connection is opened and closed internally.
        """
        _owns_conn = conn is None
        if _owns_conn:
            self.init()
            conn = _connect(self._path)
        try:
            row = conn.execute(
                "SELECT agent_id, agent_type, tier, log_file, started_at "
                "FROM active_agents WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "agent_id": row["agent_id"],
                "agent_type": row["agent_type"],
                "tier": row["tier"],
                "log_file": row["log_file"],
                "started_at": row["started_at"],
            }
        finally:
            if _owns_conn:
                conn.close()

    def remove_active_agent(self, agent_id: str) -> dict[str, Any]:
        """Remove the active agent record for the given agent_id.

        Returns {"removed": True} if a record was deleted,
        {"removed": False} if no record existed.
        """
        self.init()
        conn = _connect(self._path)
        try:
            cursor = conn.execute(
                "DELETE FROM active_agents WHERE agent_id = ?", (agent_id,)
            )
            conn.commit()
            return {"removed": cursor.rowcount > 0}
        finally:
            conn.close()

    def get_active_tier(
        self, agent_id: str, conn: Optional[sqlite3.Connection] = None,
    ) -> str:
        """Return the tier of the active agent identified by agent_id.

        Queries active_agents WHERE agent_id = ? — this answers "what
        tier is *this caller*?", not "what tier is somebody?". With
        concurrent agents (normal for this project), a filter-less
        lookup would return an arbitrary row. If no row matches
        agent_id, the tier is unresolvable: return the "unresolved"
        sentinel (empty string) rather than any other agent's tier.
        This replaces the .clasi-agent-tier file check.

        If *conn* is given, it is used directly and this method neither
        calls init() nor opens/closes its own connection — the caller
        owns the connection's lifecycle (see StateDB.connect()). Omitted
        (the default), behavior is unchanged: init() runs and a fresh
        connection is opened and closed internally.
        """
        _owns_conn = conn is None
        if _owns_conn:
            self.init()
            conn = _connect(self._path)
        try:
            row = conn.execute(
                "SELECT tier FROM active_agents WHERE agent_id = ?",
                (agent_id,),
            ).fetchone()
            if row is None:
                return ""
            return row["tier"]
        finally:
            if _owns_conn:
                conn.close()

    def clear_stale_agents(self, ttl_hours: int = 24) -> dict[str, Any]:
        """Delete active_agents records older than ttl_hours.

        Returns {"cleared": count} with the number of records removed.
        """
        self.init()
        cutoff = datetime.now(timezone.utc) - timedelta(hours=ttl_hours)
        cutoff_str = cutoff.isoformat()
        conn = _connect(self._path)
        try:
            cursor = conn.execute(
                "DELETE FROM active_agents WHERE started_at < ?", (cutoff_str,)
            )
            conn.commit()
            return {"cleared": cursor.rowcount}
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # OOP (out-of-process) bypass state
    # ------------------------------------------------------------------

    def set_oop(
        self, reason: str, ttl_hours: float = _OOP_DEFAULT_TTL_HOURS
    ) -> dict[str, Any]:
        """Write or overwrite the singleton OOP bypass record.

        Only one OOP record exists at a time (id=1). Calling this again
        replaces any previous record, resetting the TTL clock.
        """
        self.init()
        set_at = datetime.now(timezone.utc)
        expires_at = set_at + timedelta(hours=ttl_hours)
        set_at_str = set_at.isoformat()
        expires_at_str = expires_at.isoformat()
        conn = _connect(self._path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO oop_state "
                "(id, set_at, reason, expires_at) VALUES (1, ?, ?, ?)",
                (set_at_str, reason, expires_at_str),
            )
            conn.commit()
            return {
                "set_at": set_at_str,
                "reason": reason,
                "expires_at": expires_at_str,
            }
        finally:
            conn.close()

    def get_oop(
        self, conn: Optional[sqlite3.Connection] = None,
    ) -> Optional[dict[str, Any]]:
        """Read the OOP bypass record, auto-clearing it past expiry.

        Returns a dict with set_at, reason, and expires_at -- or None if
        no record exists. A record whose expires_at is in the past is
        automatically deleted, with a warning on stderr, and this
        returns None as if no record existed.

        If *conn* is given, it is used directly and this method neither
        calls init() nor opens/closes its own connection — the caller
        owns the connection's lifecycle (see StateDB.connect()). Omitted
        (the default), behavior is unchanged: init() runs and a fresh
        connection is opened and closed internally.
        """
        _owns_conn = conn is None
        if _owns_conn:
            self.init()
            conn = _connect(self._path)
        try:
            row = conn.execute(
                "SELECT set_at, reason, expires_at FROM oop_state WHERE id = 1"
            ).fetchone()
            if row is None:
                return None

            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now(timezone.utc) > expires_at:
                conn.execute("DELETE FROM oop_state WHERE id = 1")
                conn.commit()
                print(
                    f"[CLASI] Stale OOP bypass (reason '{row['reason']}', "
                    f"set {row['set_at']}) auto-cleared after expiry "
                    f"{row['expires_at']}",
                    file=sys.stderr,
                )
                return None

            return {
                "set_at": row["set_at"],
                "reason": row["reason"],
                "expires_at": row["expires_at"],
            }
        finally:
            if _owns_conn:
                conn.close()

    def clear_oop(self) -> dict[str, Any]:
        """Delete the OOP bypass record.

        Returns {"cleared": True} if a record was removed,
        {"cleared": False} if no record existed. Idempotent -- safe to
        call when no row exists.
        """
        self.init()
        conn = _connect(self._path)
        try:
            cursor = conn.execute("DELETE FROM oop_state WHERE id = 1")
            conn.commit()
            return {"cleared": cursor.rowcount > 0}
        finally:
            conn.close()
