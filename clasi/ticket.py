"""Ticket: OO wrapper around a ticket markdown file."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from clasi.artifact import Artifact

if TYPE_CHECKING:
    from clasi.sprint import Sprint


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

    def to_dict(self) -> dict:
        """Serialize ticket to a plain dict suitable for JSON return.

        All Path objects are converted to strings.
        Returns keys: id, path, title, status.
        """
        return {
            "id": self.id,
            "path": str(self.path),
            "title": self.title,
            "status": self.status,
        }

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

    def move_to_done_with_plan(self) -> dict:
        """Move ticket and its plan file (if any) to tickets/done/.

        Also moves <ticket-stem>-plan.md if it exists alongside the ticket.

        Returns a dict with keys: old_path, new_path, and optionally
        plan_old_path / plan_new_path if a plan file was moved.
        """
        old_path = self.path
        tickets_dir = old_path.parent
        if tickets_dir.name == "done":
            tickets_dir = tickets_dir.parent

        new_path = self.move_to_done()
        result: dict = {"old_path": str(old_path), "new_path": str(new_path)}

        # Also move the plan file if it exists
        plan_name = old_path.stem + "-plan.md"
        plan_path = tickets_dir / plan_name
        if plan_path.exists():
            done_dir = tickets_dir / "done"
            done_dir.mkdir(parents=True, exist_ok=True)
            new_plan_path = done_dir / plan_name
            plan_path.rename(new_plan_path)
            result["plan_old_path"] = str(plan_path)
            result["plan_new_path"] = str(new_plan_path)

        return result

    def reopen(self) -> dict:
        """Reopen this ticket by moving it from done/ back to tickets/ and resetting status to 'todo'.

        If the ticket is in tickets/done/, moves it back to tickets/.
        If the ticket exists but is not in done/, just resets the status.
        Also moves the plan file back if one exists in done/.

        Returns a dict with keys: old_path, new_path, old_status, new_status.
        Also includes plan_old_path / plan_new_path if a plan file was moved.
        """
        old_path = self.path
        old_status = self.status
        in_done = old_path.parent.name == "done"

        if in_done:
            # Move from tickets/done/ back to tickets/
            tickets_dir = old_path.parent.parent
            new_path = tickets_dir / old_path.name
            old_path.rename(new_path)

            result: dict = {"old_path": str(old_path), "new_path": str(new_path)}

            # Also move plan file if it exists in done/
            plan_name = old_path.stem + "-plan.md"
            plan_path = old_path.parent / plan_name
            if plan_path.exists():
                new_plan_path = tickets_dir / plan_name
                plan_path.rename(new_plan_path)
                result["plan_old_path"] = str(plan_path)
                result["plan_new_path"] = str(new_plan_path)

            # Update frontmatter on the moved file
            self._artifact = Artifact(new_path)
            self._artifact.update_frontmatter(status="todo")
        else:
            # Ticket exists but not in done/ — just reset status
            new_path = old_path
            self._artifact.update_frontmatter(status="todo")
            result = {"old_path": str(old_path), "new_path": str(new_path)}

        result["old_status"] = old_status
        result["new_status"] = "todo"
        return result
