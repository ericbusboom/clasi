"""Sprint: OO wrapper around a sprint directory."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from claude_agent_skills.artifact import Artifact
from claude_agent_skills.templates import (
    SPRINT_TEMPLATE,
    SPRINT_USECASES_TEMPLATE,
    SPRINT_ARCHITECTURE_UPDATE_TEMPLATE,
    TICKET_TEMPLATE,
    slugify,
)

if TYPE_CHECKING:
    from claude_agent_skills.project import Project
    from claude_agent_skills.ticket import Ticket


class Sprint:
    """A sprint directory with its planning artifacts and tickets."""

    def __init__(self, path: Path, project: Project):
        self._path = Path(path)
        self._project = project

    @property
    def path(self) -> Path:
        return self._path

    @property
    def project(self) -> Project:
        return self._project

    @property
    def id(self) -> str:
        """From sprint.md frontmatter 'id' field."""
        return self.sprint_doc.frontmatter.get("id", "")

    @property
    def title(self) -> str:
        """From sprint.md frontmatter 'title' field."""
        return self.sprint_doc.frontmatter.get("title", "")

    @property
    def slug(self) -> str:
        """Directory name without the ID prefix."""
        name = self._path.name
        sid = self.id
        if sid and name.startswith(sid + "-"):
            return name[len(sid) + 1 :]
        return name

    @property
    def branch(self) -> str:
        """From sprint.md frontmatter 'branch' field."""
        return self.sprint_doc.frontmatter.get("branch", "")

    @property
    def status(self) -> str:
        """From sprint.md frontmatter 'status' field."""
        return self.sprint_doc.frontmatter.get("status", "unknown")

    @property
    def phase(self) -> str:
        """From StateDB if available, else inferred from directory location."""
        sid = self.id
        if sid:
            try:
                state = self._project.db.get_sprint_state(sid)
                return state.get("phase", "unknown")
            except Exception:
                pass
        # Fallback: if under done/, phase is "done"
        if self._path.parent.name == "done":
            return "done"
        return "unknown"

    # --- Named artifacts ---

    @property
    def sprint_doc(self) -> Artifact:
        """sprint.md artifact."""
        return Artifact(self._path / "sprint.md")

    @property
    def usecases(self) -> Artifact:
        """usecases.md artifact."""
        return Artifact(self._path / "usecases.md")

    @property
    def technical_plan(self) -> Artifact:
        """technical-plan.md artifact."""
        return Artifact(self._path / "technical-plan.md")

    @property
    def architecture(self) -> Artifact:
        """architecture-update.md artifact."""
        return Artifact(self._path / "architecture-update.md")

    # --- Ticket management ---

    def list_tickets(self, status: str | None = None) -> list[Ticket]:
        """List tickets in this sprint, optionally filtered by status."""
        from claude_agent_skills.ticket import Ticket
        from claude_agent_skills.frontmatter import read_frontmatter

        tickets_dir = self._path / "tickets"
        results: list[Ticket] = []

        for location in [tickets_dir, tickets_dir / "done"]:
            if not location.exists():
                continue
            for f in sorted(location.glob("*.md")):
                fm = read_frontmatter(f)
                if status and fm.get("status") != status:
                    continue
                results.append(Ticket(f, self))

        return results

    def get_ticket(self, ticket_id: str) -> Ticket:
        """Get a ticket by its ID."""
        from claude_agent_skills.ticket import Ticket
        from claude_agent_skills.frontmatter import read_frontmatter

        tickets_dir = self._path / "tickets"
        for location in [tickets_dir, tickets_dir / "done"]:
            if not location.exists():
                continue
            for f in sorted(location.glob("*.md")):
                fm = read_frontmatter(f)
                if fm.get("id") == ticket_id:
                    return Ticket(f, self)
        raise ValueError(f"Ticket '{ticket_id}' not found in sprint {self.id}")

    def create_ticket(self, title: str, todo: str | None = None) -> Ticket:
        """Create a new ticket in this sprint's tickets/ directory."""
        from claude_agent_skills.ticket import Ticket
        from claude_agent_skills.frontmatter import read_frontmatter

        tickets_dir = self._path / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)
        (tickets_dir / "done").mkdir(exist_ok=True)

        ticket_id = self._next_ticket_id()
        ticket_slug = slugify(title)
        path = tickets_dir / f"{ticket_id}-{ticket_slug}.md"

        content = TICKET_TEMPLATE.format(id=ticket_id, title=title)
        path.write_text(content, encoding="utf-8")

        if todo is not None:
            fm = read_frontmatter(path)
            fm["todo"] = todo
            Artifact(path).write(fm, Artifact(path).content)

        return Ticket(path, self)

    def _next_ticket_id(self) -> str:
        """Determine the next ticket number within this sprint."""
        from claude_agent_skills.frontmatter import read_frontmatter

        tickets_dir = self._path / "tickets"
        max_id = 0
        for location in [tickets_dir, tickets_dir / "done"]:
            if not location.exists():
                continue
            for f in location.glob("*.md"):
                fm = read_frontmatter(f)
                try:
                    num = int(fm.get("id", "0"))
                    max_id = max(max_id, num)
                except (ValueError, TypeError):
                    pass
        return f"{max_id + 1:03d}"

    # --- Phase management (delegates to project.db) ---

    def advance_phase(self) -> dict:
        """Advance this sprint's phase in the state DB."""
        return self._project.db.advance_phase(self.id)

    def record_gate(self, gate: str, result: str, notes: str | None = None) -> dict:
        """Record a gate result for this sprint."""
        return self._project.db.record_gate(self.id, gate, result, notes)

    def acquire_lock(self) -> dict:
        """Acquire the execution lock for this sprint."""
        return self._project.db.acquire_lock(self.id)

    def release_lock(self) -> dict:
        """Release the execution lock for this sprint."""
        return self._project.db.release_lock(self.id)
