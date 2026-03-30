"""StateDB: OO wrapper around the state_db module functions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from claude_agent_skills import state_db as _sdb


class StateDB:
    """Wraps the CLASI SQLite state database.

    Each method delegates to the corresponding module-level function in
    state_db.py, passing self._path as the db_path argument.
    """

    def __init__(self, db_path: str | Path):
        self._path = Path(db_path)

    @property
    def path(self) -> Path:
        return self._path

    def init(self) -> None:
        """Create tables if they don't exist."""
        _sdb.init_db(self._path)

    def register_sprint(
        self,
        sprint_id: str,
        slug: str,
        branch: Optional[str] = None,
    ) -> dict[str, Any]:
        return _sdb.register_sprint(self._path, sprint_id, slug, branch)

    def get_sprint_state(self, sprint_id: str) -> dict[str, Any]:
        return _sdb.get_sprint_state(self._path, sprint_id)

    def advance_phase(self, sprint_id: str) -> dict[str, Any]:
        return _sdb.advance_phase(self._path, sprint_id)

    def record_gate(
        self,
        sprint_id: str,
        gate: str,
        result: str,
        notes: Optional[str] = None,
    ) -> dict[str, Any]:
        return _sdb.record_gate(self._path, sprint_id, gate, result, notes)

    def acquire_lock(self, sprint_id: str) -> dict[str, Any]:
        return _sdb.acquire_lock(self._path, sprint_id)

    def release_lock(self, sprint_id: str) -> dict[str, Any]:
        return _sdb.release_lock(self._path, sprint_id)

    def write_recovery_state(
        self,
        sprint_id: str,
        step: str,
        allowed_paths: list[str],
        reason: str,
    ) -> dict[str, Any]:
        return _sdb.write_recovery_state(
            self._path, sprint_id, step, allowed_paths, reason
        )

    def get_recovery_state(self) -> Optional[dict[str, Any]]:
        return _sdb.get_recovery_state(self._path)

    def clear_recovery_state(self) -> dict[str, Any]:
        return _sdb.clear_recovery_state(self._path)
