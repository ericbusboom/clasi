"""Project root object for CLASI. All path resolution flows through here."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clasi.agent import Agent
    from clasi.sprint import Sprint
    from clasi.state_db_class import StateDB
    from clasi.issue import Issue


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
        """.clasi/ directory — root for all CLASI artifacts."""
        return self._root / ".clasi"

    @property
    def design_dir(self) -> Path:
        """docs/design/ directory — overview, specification, usecases."""
        return self._root / "docs" / "design"

    @property
    def sprints_dir(self) -> Path:
        """.clasi/sprints/ directory."""
        return self.clasi_dir / "sprints"

    @property
    def issues_dir(self) -> Path:
        """.clasi/issues/ pending pool directory."""
        return self.clasi_dir / "issues"

    @property
    def log_dir(self) -> Path:
        """.clasi/log/ directory."""
        return self.clasi_dir / "log"

    @property
    def architecture_dir(self) -> Path:
        """.clasi/architecture/ directory."""
        return self.clasi_dir / "architecture"

    @property
    def mcp_config_path(self) -> Path:
        """Path to .mcp.json in the project root."""
        return self._root / ".mcp.json"

    @property
    def db(self) -> StateDB:
        """Lazily-initialized StateDB instance."""
        if self._db is None:
            from clasi.state_db_class import StateDB

            self._db = StateDB(self.clasi_dir / ".clasi.db")
        return self._db

    # --- Sprint management ---

    def get_sprint(self, sprint_id: str) -> Sprint:
        """Find a sprint by its ID (checks active and done directories)."""
        from clasi.sprint import Sprint
        from clasi.frontmatter import read_frontmatter

        for location in [self.sprints_dir, self.sprints_dir / "done"]:
            if not location.exists():
                continue
            for d in sorted(location.iterdir()):
                if not d.is_dir():
                    continue
                sprint_file = d / "sprint.md"
                if not sprint_file.exists():
                    continue
                fm = read_frontmatter(sprint_file)
                if fm.get("id") == sprint_id:
                    return Sprint(d, self)
        raise ValueError(f"Sprint '{sprint_id}' not found")

    def list_sprints(self, status: str | None = None) -> list[Sprint]:
        """List all sprints, optionally filtered by status."""
        from clasi.sprint import Sprint
        from clasi.frontmatter import read_frontmatter

        results: list[Sprint] = []
        for location in [self.sprints_dir, self.sprints_dir / "done"]:
            if not location.exists():
                continue
            for d in sorted(location.iterdir()):
                if not d.is_dir():
                    continue
                sprint_file = d / "sprint.md"
                if not sprint_file.exists():
                    continue
                fm = read_frontmatter(sprint_file)
                sprint_status = fm.get("status", "unknown")
                if status and sprint_status != status:
                    continue
                results.append(Sprint(d, self))
        return results

    def create_sprint(self, title: str) -> Sprint:
        """Create a new sprint directory with template planning documents."""
        from clasi.sprint import Sprint
        from clasi.templates import (
            SPRINT_TEMPLATE,
            SPRINT_USECASES_TEMPLATE,
            SPRINT_ARCHITECTURE_UPDATE_TEMPLATE,
            slugify,
        )

        sprint_id = self._next_sprint_id()
        slug = slugify(title)
        sprint_dir = self.sprints_dir / f"{sprint_id}-{slug}"

        if sprint_dir.exists():
            raise ValueError(f"Sprint directory already exists: {sprint_dir}")

        sprint_dir.mkdir(parents=True, exist_ok=True)
        sprint = Sprint(sprint_dir, self)
        sprint.tickets_dir.mkdir()
        sprint.tickets_done_dir.mkdir()

        fmt = {"id": sprint_id, "title": title, "slug": slug}
        sprint.sprint_md.write_text(
            SPRINT_TEMPLATE.format(**fmt), encoding="utf-8"
        )
        sprint.usecases_md.write_text(
            SPRINT_USECASES_TEMPLATE.format(**fmt), encoding="utf-8"
        )
        sprint.architecture_update_md.write_text(
            SPRINT_ARCHITECTURE_UPDATE_TEMPLATE.format(**fmt), encoding="utf-8"
        )

        return sprint

    def _next_sprint_id(self) -> str:
        """Determine the next sprint number (NNN format)."""
        from clasi.frontmatter import read_frontmatter

        max_id = 0
        for location in [self.sprints_dir, self.sprints_dir / "done"]:
            if not location.exists():
                continue
            for d in location.iterdir():
                if d.is_dir() and (d / "sprint.md").exists():
                    fm = read_frontmatter(d / "sprint.md")
                    try:
                        num = int(fm.get("id", "0"))
                        max_id = max(max_id, num)
                    except (ValueError, TypeError):
                        pass
        return f"{max_id + 1:03d}"

    # --- Agent management ---

    @property
    def _agents_dir(self) -> Path:
        """Path to the agents directory inside the package."""
        return Path(__file__).parent.resolve() / "plugin" / "agents"

    def get_agent(self, name: str) -> Agent:
        """Find agent by name in the flat clasi/plugin/agents/ directory.

        Only active agents are searched. Archived agents in ``old/`` are not
        accessible by name; use the directory directly if needed.

        Raises:
            ValueError: If no agent with the given name is found.
        """
        from clasi.agent import Agent

        agents_dir = self._agents_dir
        if not agents_dir.exists():
            raise ValueError(f"Agents directory not found: {agents_dir}")

        agent_dir = agents_dir / name
        if agent_dir.is_dir():
            return Agent(agent_dir, self)

        # Build available list for error message
        available = sorted(
            d.name for d in agents_dir.iterdir() if d.is_dir() and d.name != "old"
        )
        raise ValueError(
            f"No agent found with name '{name}'. "
            f"Available: {', '.join(available)}"
        )

    def list_agents(self) -> list[Agent]:
        """List all agents in the flat clasi/plugin/agents/ directory."""
        from clasi.agent import Agent

        agents_dir = self._agents_dir
        if not agents_dir.exists():
            return []

        results: list[Agent] = []
        for agent_dir in sorted(agents_dir.iterdir()):
            if agent_dir.is_dir() and agent_dir.name != "old":
                results.append(Agent(agent_dir, self))
        return results

    # --- Issue management ---

    def get_issue(self, filename: str) -> Issue:
        """Get an issue by its filename.

        Search order:
        1. Pending pool: ``.clasi/issues/<filename>``
        2. Sprint-scoped issues: ``<sprint>/issues/<filename>`` for every sprint
        """
        from clasi.issue import Issue

        # Check pending pool
        path = self.issues_dir / filename
        if path.exists():
            return Issue(path, self)

        # Check sprint-scoped issues directories (<sprint>/issues/<filename>)
        for sprint in self.list_sprints():
            path = sprint.path / "issues" / filename
            if path.exists():
                return Issue(path, self)

        raise ValueError(f"Issue '{filename}' not found")

    def list_issues(self) -> list[Issue]:
        """List all pending pool issues (``.clasi/issues/*.md``).

        Returns only files in the top-level pending pool directory.
        Sprint-scoped in-progress issues are retrieved via ``Sprint.list_issues()``.
        """
        from clasi.issue import Issue

        if not self.issues_dir.exists():
            return []
        return [Issue(f, self) for f in sorted(self.issues_dir.glob("*.md"))]
