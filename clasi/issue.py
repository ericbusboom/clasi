"""Issue: OO wrapper around an issue markdown file."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from clasi.artifact import Artifact

if TYPE_CHECKING:
    from clasi.project import Project


class Issue:
    """An issue file in docs/clasi/todo/."""

    def __init__(self, path: Path, project: Project):
        self._artifact = Artifact(path)
        self._project = project

    @property
    def path(self) -> Path:
        return self._artifact.path

    @property
    def title(self) -> str:
        """From first markdown heading."""
        content = self._artifact.content
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return self.path.stem

    @property
    def status(self) -> str:
        """From frontmatter 'status' field."""
        return self.frontmatter.get("status", "pending")

    @property
    def sprint(self) -> str | None:
        """Sprint ID from frontmatter."""
        val = self.frontmatter.get("sprint")
        return str(val) if val else None

    @property
    def tickets(self) -> list[str]:
        """Ticket references from frontmatter."""
        val = self.frontmatter.get("tickets", [])
        if isinstance(val, str):
            return [val] if val else []
        return list(val) if val else []

    @property
    def source(self) -> str | None:
        """Source URL from frontmatter."""
        val = self.frontmatter.get("source")
        return str(val) if val else None

    @property
    def frontmatter(self) -> dict[str, Any]:
        return self._artifact.frontmatter

    @property
    def content(self) -> str:
        return self._artifact.content

    def move_to_in_progress(self, sprint_id: str, ticket_id: str) -> None:
        """Move to <sprint>/issues/, update frontmatter."""
        sprint = self._project.get_sprint(sprint_id)
        sprint_issues_dir = sprint.path / "issues"
        sprint_issues_dir.mkdir(parents=True, exist_ok=True)

        # Update frontmatter
        self._artifact.update_frontmatter(
            status="in-progress",
            sprint=sprint_id,
        )
        self.add_ticket_ref(ticket_id)

        # Move file if not already in sprint issues dir
        if self.path.parent != sprint_issues_dir:
            new_path = sprint_issues_dir / self.path.name
            self.path.rename(new_path)
            self._artifact = Artifact(new_path)

    def move_to_done(
        self,
        sprint_id: str | None = None,
        ticket_ids: list[str] | None = None,
    ) -> None:
        """Mark issue as done by updating frontmatter only; no file is moved.

        The issue file stays at its current location (typically
        ``<sprint>/issues/<filename>``). Physical relocation to an archive
        directory happens only when the sprint itself is closed/archived.

        Args:
            sprint_id: Optional sprint ID to record in frontmatter.
            ticket_ids: Optional list of ticket IDs to record in frontmatter.
        """
        if sprint_id is not None:
            self._artifact.update_frontmatter(sprint=sprint_id)
        if ticket_ids is not None:
            self._artifact.update_frontmatter(tickets=ticket_ids)
        self._artifact.update_frontmatter(status="done")

    def add_ticket_ref(self, ticket_id: str) -> None:
        """Append a ticket reference to the tickets list."""
        fm, body = self._artifact.read_document()
        existing = fm.get("tickets", [])
        if isinstance(existing, str):
            existing = [existing] if existing else []
        if ticket_id not in existing:
            existing.append(ticket_id)
        fm["tickets"] = existing
        self._artifact.write(fm, body)
