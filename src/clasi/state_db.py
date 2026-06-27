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
    PHASES,
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
    "register_active_agent",
    "get_active_agent",
    "remove_active_agent",
    "get_active_tier",
    "clear_stale_agents",
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


def get_active_tier(db_path: str | Path) -> str:
    """Return the tier of any active agent, or empty string if none."""
    return StateDB(db_path).get_active_tier()


def clear_stale_agents(db_path: str | Path, ttl_hours: int = 24) -> dict[str, Any]:
    """Delete active_agents records older than ttl_hours."""
    return StateDB(db_path).clear_stale_agents(ttl_hours)
