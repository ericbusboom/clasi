"""Sprint lifecycle state database — module-level API.

These functions are thin wrappers around the StateDB class in
state_db_class.py. They exist for backward compatibility: all existing
callers use the module-level functions with a db_path first argument.

The real logic lives in clasi/state_db_class.py.
"""

from pathlib import Path
from typing import Any, Optional

from clasi.state_db_class import (
    StateDB,
    VALID_GATE_NAMES,
    VALID_GATE_RESULTS,
    _SCHEMA,
    _GATE_REQUIREMENTS,
    _RECOVERY_TTL,
    _now,
    _connect,
)

__all__ = [
    "PHASES",
    "VALID_GATE_NAMES",
    "VALID_GATE_RESULTS",
    "init_db",
    "register_sprint",
    "get_sprint_state",
    "advance_phase",
    "record_gate",
    "acquire_lock",
    "release_lock",
    "rename_sprint",
    "get_lock_holder",
    "write_recovery_state",
    "get_recovery_state",
    "clear_recovery_state",
    "record_test_pass_marker",
    "get_test_pass_marker",
    "clear_test_pass_marker",
    "register_active_agent",
    "get_active_agent",
    "remove_active_agent",
    "get_active_tier",
    "clear_stale_agents",
    "set_oop",
    "clear_oop",
    "get_oop",
]


def init_db(db_path: str | Path) -> None:
    """Create the database file and all tables if they do not exist."""
    StateDB(db_path).init()


def register_sprint(
    db_path: str | Path,
    sprint_id: str,
    slug: str,
    branch: Optional[str] = None,
) -> dict[str, Any]:
    """Register a new sprint in the state database."""
    return StateDB(db_path).register_sprint(sprint_id, slug, branch)


def get_sprint_state(db_path: str | Path, sprint_id: str) -> dict[str, Any]:
    """Return a dict with the sprint's phase, gates, and lock status."""
    return StateDB(db_path).get_sprint_state(sprint_id)


def advance_phase(db_path: str | Path, sprint_id: str) -> dict[str, Any]:
    """Advance a sprint to the next lifecycle phase."""
    return StateDB(db_path).advance_phase(sprint_id)


def record_gate(
    db_path: str | Path,
    sprint_id: str,
    gate_name: str,
    result: str,
    notes: Optional[str] = None,
) -> dict[str, Any]:
    """Record a review gate result for a sprint."""
    return StateDB(db_path).record_gate(sprint_id, gate_name, result, notes)


def acquire_lock(db_path: str | Path, sprint_id: str) -> dict[str, Any]:
    """Acquire the execution lock for a sprint."""
    return StateDB(db_path).acquire_lock(sprint_id)


def release_lock(db_path: str | Path, sprint_id: str) -> dict[str, Any]:
    """Release the execution lock held by a sprint."""
    return StateDB(db_path).release_lock(sprint_id)


def rename_sprint(
    db_path: str | Path,
    old_id: str,
    new_id: str,
    new_branch: Optional[str] = None,
) -> dict[str, Any]:
    """Rename a sprint's ID in the state database."""
    return StateDB(db_path).rename_sprint(old_id, new_id, new_branch)


def get_lock_holder(db_path: str | Path) -> Optional[dict[str, Any]]:
    """Return the current lock holder, or None if no lock is held."""
    return StateDB(db_path).get_lock_holder()


def write_recovery_state(
    db_path: str | Path,
    sprint_id: str,
    step: str,
    allowed_paths: list[str],
    reason: str,
) -> dict[str, Any]:
    """Write or overwrite the singleton recovery state record."""
    return StateDB(db_path).write_recovery_state(sprint_id, step, allowed_paths, reason)


def get_recovery_state(db_path: str | Path) -> Optional[dict[str, Any]]:
    """Read the recovery state record, auto-clearing stale entries."""
    return StateDB(db_path).get_recovery_state()


def clear_recovery_state(db_path: str | Path) -> dict[str, Any]:
    """Delete the recovery state record."""
    return StateDB(db_path).clear_recovery_state()


def record_test_pass_marker(
    db_path: str | Path, sprint_id: str, head_sha: str, test_cmd: str,
) -> dict[str, Any]:
    """Record that the full suite passed for sprint_id at head_sha."""
    return StateDB(db_path).record_test_pass_marker(sprint_id, head_sha, test_cmd)


def get_test_pass_marker(db_path: str | Path, sprint_id: str) -> Optional[dict[str, Any]]:
    """Read the test-pass marker for sprint_id, or None if absent."""
    return StateDB(db_path).get_test_pass_marker(sprint_id)


def clear_test_pass_marker(db_path: str | Path, sprint_id: str) -> dict[str, Any]:
    """Delete the test-pass marker for sprint_id, if any."""
    return StateDB(db_path).clear_test_pass_marker(sprint_id)


def register_active_agent(
    db_path: str | Path,
    agent_id: str,
    agent_type: str,
    tier: str,
    log_file: Optional[str] = None,
) -> dict[str, Any]:
    """Register an active agent in the database."""
    return StateDB(db_path).register_active_agent(agent_id, agent_type, tier, log_file)


def get_active_agent(db_path: str | Path, agent_id: str) -> Optional[dict[str, Any]]:
    """Return the active agent record for the given agent_id, or None."""
    return StateDB(db_path).get_active_agent(agent_id)


def remove_active_agent(db_path: str | Path, agent_id: str) -> dict[str, Any]:
    """Remove the active agent record for the given agent_id."""
    return StateDB(db_path).remove_active_agent(agent_id)


def get_active_tier(db_path: str | Path, agent_id: str) -> str:
    """Return the tier of the active agent identified by agent_id.

    Returns the "unresolved" sentinel (empty string) if no row matches
    agent_id — never another agent's tier.
    """
    return StateDB(db_path).get_active_tier(agent_id)


def clear_stale_agents(db_path: str | Path, ttl_hours: int = 24) -> dict[str, Any]:
    """Delete active_agents records older than ttl_hours."""
    return StateDB(db_path).clear_stale_agents(ttl_hours)


def set_oop(
    db_path: str | Path,
    reason: str,
    ttl_hours: float = 8.0,
    auto_clear_on_commit: bool = True,
) -> dict[str, Any]:
    """Write or overwrite the singleton OOP bypass record.

    See ``StateDB.set_oop`` for ``auto_clear_on_commit``'s semantics --
    it auto-clears the bypass once its permitted change is committed
    (HEAD advances past the commit captured at set-time). Pass False for
    a deliberately long-running, multi-commit bypass.
    """
    return StateDB(db_path).set_oop(reason, ttl_hours, auto_clear_on_commit)


def clear_oop(db_path: str | Path) -> dict[str, Any]:
    """Delete the OOP bypass record."""
    return StateDB(db_path).clear_oop()


def get_oop(db_path: str | Path) -> Optional[dict[str, Any]]:
    """Read the OOP bypass record, auto-clearing it past expiry."""
    return StateDB(db_path).get_oop()


def __getattr__(name: str):
    """PEP 562 lazy resolution for :data:`PHASES` (sprint 027 / ticket 003).

    Mirrors ``state_db_class``'s own lazy ``PHASES`` -- re-exporting it
    here via a plain module-level ``from clasi.state_db_class import
    PHASES`` would immediately force the underlying Pydantic-backed
    schema-graph computation on every import of THIS module, undoing
    that laziness for any caller of the wrapper API instead of the
    class directly. Deferred the same way so both entry points share
    one computation, cached the first time either is actually accessed.
    """
    if name == "PHASES":
        from clasi.state_db_class import PHASES as _phases

        return _phases
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
