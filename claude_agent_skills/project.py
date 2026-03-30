"""Project root object for CLASI. All path resolution flows through here."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claude_agent_skills.state_db_class import StateDB


class Project:
    """Root object for a CLASI project. All path resolution flows through here."""

    def __init__(self, root: str | Path):
        self._root = Path(root).resolve()
        self._db: StateDB | None = None

    @property
    def root(self) -> Path:
        return self._root

    @property
    def clasi_dir(self) -> Path:
        """docs/clasi/ directory."""
        return self._root / "docs" / "clasi"

    @property
    def sprints_dir(self) -> Path:
        """docs/clasi/sprints/ directory."""
        return self.clasi_dir / "sprints"

    @property
    def todo_dir(self) -> Path:
        """docs/clasi/todo/ directory."""
        return self.clasi_dir / "todo"

    @property
    def log_dir(self) -> Path:
        """docs/clasi/log/ directory."""
        return self.clasi_dir / "log"

    @property
    def architecture_dir(self) -> Path:
        """docs/clasi/architecture/ directory."""
        return self.clasi_dir / "architecture"

    @property
    def mcp_config_path(self) -> Path:
        """Path to .mcp.json in the project root."""
        return self._root / ".mcp.json"

    @property
    def db(self) -> StateDB:
        """Lazily-initialized StateDB instance."""
        if self._db is None:
            from claude_agent_skills.state_db_class import StateDB

            self._db = StateDB(self.clasi_dir / ".clasi.db")
        return self._db
