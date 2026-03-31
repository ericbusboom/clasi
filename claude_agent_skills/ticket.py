"""Ticket: OO wrapper around a ticket markdown file."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from claude_agent_skills.artifact import Artifact

if TYPE_CHECKING:
    from claude_agent_skills.sprint import Sprint


class Ticket:
    """A ticket file within a sprint's tickets/ directory."""

    def __init__(self, path: Path, sprint: Sprint):
        self._artifact = Artifact(path)
        self._sprint = sprint

    @property
    def path(self) -> Path:
        return self._artifact.path

    @property
    def id(self) -> str:
        """From frontmatter 'id' field."""
        return self.frontmatter.get("id", "")

    @property
    def title(self) -> str:
        """From frontmatter 'title' field. Set once at creation."""
        return self.frontmatter.get("title", "")

    @property
    def status(self) -> str:
        """From frontmatter 'status' field."""
        return self.frontmatter.get("status", "todo")

    @status.setter
    def status(self, value: str) -> None:
        self._artifact.update_frontmatter(status=value)

    @property
    def depends_on(self) -> list[str]:
        """From frontmatter 'depends-on' field."""
        val = self.frontmatter.get("depends-on", [])
        if isinstance(val, str):
            return [val] if val else []
        return list(val) if val else []

    @property
    def todo_ref(self) -> str | None:
        """From frontmatter 'todo' field."""
        val = self.frontmatter.get("todo", "")
        return val if val else None

    @property
    def use_cases(self) -> list[str]:
        """From frontmatter 'use-cases' field."""
        val = self.frontmatter.get("use-cases", [])
        if isinstance(val, str):
            return [val] if val else []
        return list(val) if val else []

    @property
    def sprint(self) -> Sprint:
        return self._sprint

    @property
    def frontmatter(self) -> dict[str, Any]:
        return self._artifact.frontmatter

    @property
    def content(self) -> str:
        return self._artifact.content

    def set_status(self, status: str) -> None:
        """Update status in frontmatter."""
        self._artifact.update_frontmatter(status=status)

    def move_to_done(self) -> Path:
        """Move ticket file to tickets/done/ subdirectory.

        Returns the new path.
        """
        tickets_dir = self.path.parent
        if tickets_dir.name == "done":
            # Already in done/
            return self.path
        done_dir = tickets_dir / "done"
        done_dir.mkdir(parents=True, exist_ok=True)
        new_path = done_dir / self.path.name
        self.path.rename(new_path)
        self._artifact = Artifact(new_path)
        return new_path
