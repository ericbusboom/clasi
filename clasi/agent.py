"""Agent class hierarchy for CLASI.

This module loads agent definitions, contracts, and dispatch templates from
disk. It does not execute dispatches — it is a pure content-loading and
template-rendering module.

## Class Hierarchy

- **Agent** -- Base class. Loads an agent definition directory, resolves its
  contract, and renders its dispatch template.

- **MainController** (tier 0) -- Orchestrates the entire project.

- **DomainController** (tier 1) -- Orchestrates work within one domain.

- **TaskWorker** (tier 2) -- Performs concrete work (code, docs, review).

## Contracts and Templates

Each agent directory contains:

- **agent.md** -- The agent's system prompt / role definition (``definition``
  property).

- **contract.yaml** -- Machine-readable contract: allowed tools, delegation
  edges, return schema, optional MCP server list (``contract`` property via
  ``clasi.contracts.load_contract``).

- **dispatch-template.md.j2** (optional) -- Jinja2 template rendered by
  ``render_prompt()`` to produce the user-turn prompt for a subagent dispatch.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clasi.project import Project

# Tier directory names mapped to tier numbers
_TIER_DIRS = {
    "main-controller": 0,
    "domain-controllers": 1,
    "task-workers": 2,
}


class Agent:
    """Represents an agent definition with its contract and dispatch template."""

    def __init__(self, agent_dir: str | Path, project: "Project"):
        self._dir = Path(agent_dir)
        self._project = project
        self._contract: dict | None = None  # lazy

    @property
    def name(self) -> str:
        """Agent name (directory name)."""
        return self._dir.name

    @property
    def tier(self) -> int:
        """0=main-controller, 1=domain-controller, 2=task-worker.

        Derived from the parent directory name.
        """
        parent_name = self._dir.parent.name
        if parent_name in _TIER_DIRS:
            return _TIER_DIRS[parent_name]
        # Fallback: check contract
        return self.contract.get("tier", -1)

    @property
    def model(self) -> str:
        """Model from contract, defaults to 'sonnet'."""
        return self.contract.get("model", "sonnet")

    @property
    def definition(self) -> str:
        """Content of agent.md."""
        agent_md = self._dir / "agent.md"
        if not agent_md.exists():
            raise ValueError(f"No agent.md found for agent '{self.name}'.")
        return agent_md.read_text(encoding="utf-8")

    @property
    def contract(self) -> dict:
        """Parsed and validated contract.yaml (lazy-loaded)."""
        if self._contract is None:
            from clasi.contracts import load_contract

            self._contract = load_contract(self.name)
        return self._contract

    @property
    def allowed_tools(self) -> list[str]:
        """From contract."""
        return self.contract.get("allowed_tools", [])

    @property
    def delegates_to(self) -> list[dict]:
        """Delegation edges from contract."""
        return self.contract.get("delegates_to", [])

    @property
    def has_dispatch_template(self) -> bool:
        """Whether a dispatch-template.md.j2 exists for this agent."""
        return (self._dir / "dispatch-template.md.j2").exists()

    def render_prompt(self, **params) -> str:
        """Render the Jinja2 dispatch template with parameters.

        Raises:
            ValueError: If no dispatch template exists for this agent.
        """
        from jinja2 import Template

        template_path = self._dir / "dispatch-template.md.j2"
        if not template_path.exists():
            raise ValueError(
                f"No dispatch template found for agent '{self.name}'. "
                f"Only agents with a dispatch-template.md.j2 file in their "
                f"directory have templates."
            )
        template = Template(template_path.read_text(encoding="utf-8"))
        return template.render(**params)


class MainController(Agent):
    """Tier 0 agent -- dispatches only, no file writes."""

    @property
    def tier(self) -> int:
        return 0


class DomainController(Agent):
    """Tier 1 agent -- orchestrates within a domain."""

    @property
    def tier(self) -> int:
        return 1


class TaskWorker(Agent):
    """Tier 2 agent -- does actual work (code, architecture, review)."""

    @property
    def tier(self) -> int:
        return 2
