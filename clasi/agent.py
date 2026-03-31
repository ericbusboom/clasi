"""Agent class hierarchy for CLASI.

## Class Hierarchy

The module defines four classes that form a three-tier agent architecture:

- **Agent** -- Base class. Loads an agent definition from a directory on
  disk, resolves its contract, renders its dispatch template, and runs the
  full dispatch lifecycle.

- **MainController** (tier 0) -- Orchestrates the entire project. Dispatches
  to domain controllers only. Never writes files directly.

- **DomainController** (tier 1) -- Orchestrates work within one domain (e.g.
  sprint execution, architecture). Dispatches to task workers. Never writes
  files directly.

- **TaskWorker** (tier 2) -- Performs concrete work: writes code, produces
  architecture documents, reviews pull requests, etc. Does not dispatch to
  other agents.

Tier is determined from the parent directory name inside the agents tree
(``main-controller/``, ``domain-controllers/``, ``task-workers/``). The
concrete subclasses override ``tier`` to hard-code the value so callers
never need to inspect the directory layout directly.

## Contracts and Templates

Each agent directory contains two key files:

- **agent.md** -- The agent's system prompt / role definition. Read as the
  ``definition`` property and passed as ``system_prompt`` when dispatching.

- **contract.yaml** -- Machine-readable contract that specifies the agent's
  allowed tools, delegation edges (``delegates_to``), expected return schema,
  and optional MCP server list. Loaded lazily by the ``contract`` property
  via ``clasi.contracts.load_contract``.

- **dispatch-template.md.j2** (optional) -- Jinja2 template rendered by
  ``render_prompt()`` to produce the user-turn prompt for a subagent
  dispatch. Agents without this file cannot be dispatched via
  ``render_prompt()`` and raise ``ValueError`` if called.

## Dispatch Lifecycle

``Agent.dispatch()`` runs the full dispatch lifecycle in seven steps:

1. **Log (pre-execution)** -- Write a dispatch log entry via
   ``clasi.dispatch_log.log_dispatch``. This always happens, even if the
   subagent call later fails.

2. **Resolve working directory** -- Always use the project root as ``cwd``
   for subagents. Using a sprint subdirectory causes path-nesting bugs in
   the MCP server.

3. **Import SDK** -- Import ``claude_agent_sdk``. If the SDK is not
   installed, return an error dict immediately.

4. **Execute** -- Call ``claude_agent_sdk.query()`` with a
   ``ClaudeAgentOptions`` built from the contract. Tier 0-1 agents receive a
   role-guard hook (via ``_build_role_guard_hooks``) that blocks direct file
   writes and redirects the agent to use dispatch tools instead. Tier 2
   agents have no such restriction.

5. **Validate** -- Pass the raw result text through
   ``clasi.contracts.validate_return`` which checks the return schema
   defined in the contract.

6. **Log (post-execution)** -- Update the dispatch log with the final status
   and list of modified files.

7. **Return** -- Return a dict with ``status``, ``result``, ``log_path``,
   and ``validations``.

If the SDK call raises an exception the lifecycle short-circuits after step
4, logs an error, and returns a ``fatal`` error dict instructing the caller
to stop and report the failure rather than attempting the work inline.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clasi.project import Project

logger = logging.getLogger("clasi.dispatch")

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

    def _build_role_guard_hooks(self) -> dict:
        """Build SDK hooks dict that blocks dispatchers from writing files.

        Returns a hooks dict suitable for ClaudeAgentOptions.hooks.
        The hook blocks Edit/Write/MultiEdit for tier 0-1 agents,
        directing them to dispatch to task workers instead.
        """
        from claude_agent_sdk import HookMatcher, PreToolUseHookInput, HookContext

        agent_name = self.name

        async def role_guard_hook(
            hook_input: PreToolUseHookInput,
            context: HookContext,
        ):
            """Block dispatchers from writing files directly."""
            from claude_agent_sdk import HookJSONOutput

            # Extract file path from tool input
            tool_input = hook_input.tool_input or {}
            file_path = (
                tool_input.get("file_path")
                or tool_input.get("path")
                or tool_input.get("new_path")
                or ""
            )
            if not file_path:
                return None  # Allow — can't determine path

            # Allow safe list
            for prefix in [".claude/", "CLAUDE.md", "AGENTS.md"]:
                if file_path == prefix or file_path.startswith(prefix):
                    return None  # Allow

            # Block
            return HookJSONOutput(
                decision="block",
                reason=(
                    f"CLASI ROLE VIOLATION: {agent_name} attempted direct "
                    f"file write to: {file_path}. "
                    f"Dispatchers must use dispatch_to_code_monkey or "
                    f"dispatch_to_architect instead of writing files directly."
                ),
            )

        return {
            "PreToolUse": [
                HookMatcher(
                    matcher="Edit|Write|MultiEdit",
                    hooks=[role_guard_hook],
                ),
            ],
        }

    async def dispatch(
        self,
        prompt: str,
        cwd: str,
        parent: str = "team-lead",
        mode: str | None = None,
        sprint_name: str | None = None,
        ticket_id: str | None = None,
    ) -> dict:
        """Full dispatch lifecycle: log, query(), validate, log result, return dict.

        This replaces the _dispatch() function in dispatch_tools.py.

        Args:
            prompt: The rendered prompt text to send to the subagent.
            cwd: Working directory for the subagent.
            parent: Name of the dispatching agent.
            mode: Mode name for multi-mode agents (e.g., 'roadmap', 'detail').
            sprint_name: Sprint name for log routing.
            ticket_id: Ticket ID for log routing.

        Returns:
            A dict with status, result, log_path, and validations.
        """
        from clasi.dispatch_log import (
            log_dispatch,
            update_dispatch_result,
        )
        from clasi.contracts import validate_return

        child = self.name
        contract = self.contract

        # 1. LOG (pre-execution -- always happens)
        log_path = log_dispatch(
            parent=parent,
            child=child,
            scope=cwd,
            prompt=prompt,
            sprint_name=sprint_name,
            ticket_id=ticket_id,
            template_used="dispatch-template.md.j2",
        )

        # 2. Resolve working directory
        # ALWAYS use the project root as cwd for subagents. The sprint
        # directory or other scope is passed as a parameter in the prompt.
        # Using the sprint directory as cwd causes the MCP server inside
        # the subagent to create nested docs/clasi/ directories (the
        # path nesting bug). The project root ensures all MCP tool calls
        # resolve paths correctly.
        work_dir = str(self._project.root)

        # 3. Try to import the SDK
        try:
            from claude_agent_sdk import (  # type: ignore[import-not-found]
                query,
                ClaudeAgentOptions,
                ResultMessage,
            )
        except ImportError:
            error_msg = (
                "claude-agent-sdk is not installed. "
                "Install it to enable subagent dispatch."
            )
            update_dispatch_result(
                log_path,
                result="error",
                files_modified=[],
                response=error_msg,
            )
            return {
                "status": "error",
                "message": error_msg,
                "log_path": str(log_path),
            }

        # Build options from contract
        env = {k: v for k, v in os.environ.items()}
        env.pop("CLAUDECODE", None)

        # Write stderr to a file for error diagnostics
        stderr_log = Path(work_dir) / ".dispatch-stderr.log"
        try:
            stderr_file = open(stderr_log, "w", encoding="utf-8")
        except OSError:
            stderr_file = None

        # Resolve MCP server config: use the project's .mcp.json
        mcp_servers_config = contract.get("mcp_servers", [])
        if isinstance(mcp_servers_config, list) and mcp_servers_config:
            mcp_json = self._project.mcp_config_path
            mcp_servers_config = str(mcp_json) if mcp_json.exists() else {}

        # Enforcement configuration:
        #
        # We do NOT use setting_sources=["project"] because that loads
        # CLAUDE.md which says "You are the team-lead" — wrong for
        # subagents. Instead we:
        #
        # 1. Pass the agent.md as system_prompt (already done above)
        # 2. Pass hooks programmatically via the SDK hooks parameter
        #    so the role guard fires for dispatchers (tier 0-1) but
        #    allows task workers (tier 2) to write files.
        # 3. Use acceptEdits so hooks actually fire (bypassPermissions
        #    skips them entirely).

        env["CLASI_AGENT_TIER"] = str(self.tier)
        env["CLASI_AGENT_NAME"] = self.name

        # Build hooks: for dispatchers (tier 0-1), add role guard.
        # Task workers (tier 2) don't need hooks — they write files.
        sdk_hooks = None
        if self.tier < 2:
            try:
                sdk_hooks = self._build_role_guard_hooks()
            except Exception:
                logger.warning("Failed to build role guard hooks for %s", self.name)

        options = ClaudeAgentOptions(
            system_prompt=self.definition,
            cwd=work_dir,
            allowed_tools=self.allowed_tools,
            mcp_servers=mcp_servers_config,
            model=self.model,
            env=env,
            permission_mode="acceptEdits",
            hooks=sdk_hooks,
            debug_stderr=stderr_file,
        )

        # 4. EXECUTE
        result_text = ""
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, ResultMessage):
                    result_text = message.result
        except Exception as e:
            error_msg = str(e)
            if stderr_file:
                stderr_file.close()
            stderr_from_file = ""
            try:
                stderr_from_file = stderr_log.read_text(encoding="utf-8").strip()
            except OSError:
                pass
            stderr_output = stderr_from_file or getattr(e, "stderr", None) or ""
            exit_code = getattr(e, "exit_code", None)
            detail = error_msg
            if stderr_output:
                detail = f"{error_msg}\nSTDERR: {stderr_output}"
            logger.error("dispatch %s -> %s FAILED: %s", parent, child, detail)

            update_dispatch_result(
                log_path,
                result="error",
                files_modified=[],
                response=detail,
            )
            return {
                "status": "error",
                "fatal": True,
                "message": error_msg,
                "stderr": stderr_output,
                "exit_code": exit_code,
                "log_path": str(log_path),
                "instruction": (
                    "DISPATCH FAILED. DO NOT attempt to do this work yourself. "
                    "DO NOT proceed without the subagent. STOP and report this "
                    "error to the stakeholder. The dispatch infrastructure must "
                    "be fixed before work can continue."
                ),
            }

        # Close stderr file on success
        if stderr_file:
            stderr_file.close()

        # 5. VALIDATE
        validation = validate_return(contract, mode, result_text, work_dir)

        # 6. LOG (post-execution -- always happens)
        files_modified = []
        if validation.get("result_json") and isinstance(
            validation["result_json"].get("files_changed"), list
        ):
            files_modified = validation["result_json"]["files_changed"]
        elif validation.get("result_json") and isinstance(
            validation["result_json"].get("files_created"), list
        ):
            files_modified = validation["result_json"]["files_created"]

        update_dispatch_result(
            log_path,
            result=validation["status"],
            files_modified=files_modified,
            response=result_text,
        )

        # 7. RETURN
        return {
            "status": validation["status"],
            "result": result_text,
            "log_path": str(log_path),
            "validations": validation,
        }


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
