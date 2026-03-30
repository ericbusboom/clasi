"""Sprint lifecycle state database.

Provides SQLite-backed tracking of sprint phases, review gates, and
execution locks. All functions take a db_path parameter and return
results — no MCP decorators. The MCP tool layer calls these functions.
"""

import json as _json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional


PHASES = [
    "planning-docs",
    "architecture-review",
    "stakeholder-review",
    "ticketing",
    "executing",
    "closing",
    "done",
]

VALID_GATE_NAMES = {"architecture_review", "stakeholder_approval"}
VALID_GATE_RESULTS = {"passed", "failed"}

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS sprints (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'planning-docs',
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
"""


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


def init_db(db_path: str | Path) -> None:
    """Create the database file and all tables if they do not exist."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _connect(path)
    try:
        conn.executescript(_SCHEMA)
    finally:
        conn.close()


def register_sprint(
    db_path: str | Path,
    sprint_id: str,
    slug: str,
    branch: Optional[str] = None,
) -> dict[str, Any]:
    """Register a new sprint in the state database.

    Calls init_db internally (lazy initialization).

    Raises ValueError if the sprint is already registered.
    """
    init_db(db_path)
    now = _now()
    conn = _connect(db_path)
    try:
        try:
            conn.execute(
                "INSERT INTO sprints (id, slug, phase, branch, created_at, updated_at) "
                "VALUES (?, ?, 'planning-docs', ?, ?, ?)",
                (sprint_id, slug, branch, now, now),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Sprint '{sprint_id}' is already registered")
        return {
            "id": sprint_id,
            "slug": slug,
            "phase": "planning-docs",
            "branch": branch,
            "created_at": now,
            "updated_at": now,
        }
    finally:
        conn.close()


def get_sprint_state(db_path: str | Path, sprint_id: str) -> dict[str, Any]:
    """Return a dict with the sprint's phase, gates, and lock status.

    Raises ValueError if the sprint is not registered.
    """
    init_db(db_path)
    conn = _connect(db_path)
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


# --- Phase transitions (ticket 002) ---


# Gate requirements for each transition: {from_phase: required_gate_name or None}
_GATE_REQUIREMENTS: dict[str, Optional[str]] = {
    "planning-docs": None,  # No gate to advance from planning-docs
    "architecture-review": "architecture_review",
    "stakeholder-review": "stakeholder_approval",
    "ticketing": None,  # Checked programmatically (needs tickets + lock)
    "executing": None,  # Checked programmatically (all tickets done)
    "closing": None,  # Checked programmatically (sprint archived)
}


def advance_phase(db_path: str | Path, sprint_id: str) -> dict[str, Any]:
    """Advance a sprint to the next lifecycle phase.

    Validates that exit conditions for the current phase are met before
    advancing. Returns a dict with old_phase and new_phase.

    Raises ValueError if conditions are not met or the sprint is already done.
    """
    init_db(db_path)
    conn = _connect(db_path)
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
            if gate_row is None or gate_row["result"] != "passed":
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


# --- Gate recording (ticket 003) ---


def record_gate(
    db_path: str | Path,
    sprint_id: str,
    gate_name: str,
    result: str,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Record a review gate result for a sprint.

    Uses upsert semantics: re-recording a gate overwrites the previous result.

    Raises ValueError for invalid gate names or results, or if the sprint
    is not registered.
    """
    if gate_name not in VALID_GATE_NAMES:
        raise ValueError(
            f"Invalid gate name '{gate_name}'. "
            f"Must be one of: {', '.join(sorted(VALID_GATE_NAMES))}"
        )
    if result not in VALID_GATE_RESULTS:
        raise ValueError(
            f"Invalid result '{result}'. "
            f"Must be one of: {', '.join(sorted(VALID_GATE_RESULTS))}"
        )

    init_db(db_path)
    conn = _connect(db_path)
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
            (sprint_id, gate_name, result, now, notes),
        )
        conn.commit()

        return {
            "sprint_id": sprint_id,
            "gate_name": gate_name,
            "result": result,
            "recorded_at": now,
            "notes": notes,
        }
    finally:
        conn.close()


# --- Execution locks (ticket 004) ---


def acquire_lock(db_path: str | Path, sprint_id: str) -> dict[str, Any]:
    """Acquire the execution lock for a sprint.

    Only one sprint can hold the lock at a time (singleton table).
    Re-entrant: if the sprint already holds the lock, returns success.

    Raises ValueError if another sprint holds the lock.
    """
    init_db(db_path)
    conn = _connect(db_path)
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


def release_lock(db_path: str | Path, sprint_id: str) -> dict[str, Any]:
    """Release the execution lock held by a sprint.

    Raises ValueError if the sprint does not hold the lock.
    """
    init_db(db_path)
    conn = _connect(db_path)
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
    db_path: str | Path,
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
    init_db(db_path)
    conn = _connect(db_path)
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


def get_lock_holder(db_path: str | Path) -> Optional[dict[str, Any]]:
    """Return the current lock holder, or None if no lock is held."""
    init_db(db_path)
    conn = _connect(db_path)
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
        conn.close()


# --- Recovery state (ticket 003) ---

_RECOVERY_TTL = timedelta(hours=24)


def write_recovery_state(
    db_path: str | Path,
    sprint_id: str,
    step: str,
    allowed_paths: list[str],
    reason: str,
) -> dict[str, Any]:
    """Write or overwrite the singleton recovery state record.

    Only one recovery record exists at a time (id=1).  Calling this
    again replaces any previous record.
    """
    init_db(db_path)
    now = _now()
    conn = _connect(db_path)
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


def get_recovery_state(db_path: str | Path) -> Optional[dict[str, Any]]:
    """Read the recovery state record, auto-clearing stale entries.

    Returns a dict with sprint_id, step, allowed_paths, reason, and
    recorded_at -- or None if no record exists.  Records older than 24
    hours are automatically deleted with a warning on stderr.
    """
    init_db(db_path)
    conn = _connect(db_path)
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
        conn.close()


def clear_recovery_state(db_path: str | Path) -> dict[str, Any]:
    """Delete the recovery state record.

    Returns {"cleared": True} if a record was removed,
    {"cleared": False} if no record existed.
    """
    init_db(db_path)
    conn = _connect(db_path)
    try:
        cursor = conn.execute("DELETE FROM recovery_state WHERE id = 1")
        conn.commit()
        return {"cleared": cursor.rowcount > 0}
    finally:
        conn.close()
