"""SDK-based dispatch tools for the CLASI MCP server.

Orchestration tools that render dispatch templates, log dispatches,
execute subagents via the Claude Agent SDK ``query()`` function,
validate results against agent contracts, and return structured JSON.

Each dispatch tool follows the 7-step pattern:
1. RENDER   -- Jinja2 template + parameters -> prompt text
2. LOG      -- log_dispatch() -> pre-execution dispatch log entry
3. LOAD     -- contract.yaml -> ClaudeAgentOptions config
4. EXECUTE  -- query(prompt, options) -> subagent session
5. VALIDATE -- validate_return() on result JSON + file checks
6. LOG      -- update_dispatch_result() -> post-execution log entry
7. RETURN   -- structured JSON to caller

All dispatch is now handled by ``Agent.dispatch()`` in
``clasi.agent``. The dispatch tool functions are thin
wrappers that look up the agent, render the prompt, and call dispatch.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("clasi.dispatch")


def _check_delegation_edge(
    tool_name: str,
    allowed_callers: frozenset[str],
) -> None:
    """Warn if the calling agent is not an allowed caller for this dispatch tool.

    Reads ``CLASI_AGENT_NAME`` from the environment (set by Agent.dispatch()).
    If the environment variable is not set, defaults to ``"team-lead"`` because
    interactive sessions run as the team-lead without an explicit env var.

    Emits a WARNING log on violation — does not block the call. Blocking would
    break interactive sessions where the team-lead doesn't have
    ``CLASI_AGENT_NAME`` set correctly.

    Args:
        tool_name: The name of the dispatch tool being called (for logging).
        allowed_callers: Set of agent names permitted to call this tool.
    """
    caller = os.environ.get("CLASI_AGENT_NAME", "team-lead")
    if caller not in allowed_callers:
        logger.warning(
            "DELEGATION VIOLATION: %s called %s (expected one of: %s)",
            caller,
            tool_name,
            sorted(allowed_callers),
        )

from clasi.mcp_server import server, content_path, get_project


# ---------------------------------------------------------------------------
# Dispatch tools
# ---------------------------------------------------------------------------

async def dispatch_to_project_manager(
    mode: str,
    spec_file: str = "",
    todo_assessments: list[str] | None = None,
    sprint_goals: str = "",
) -> str:
    """Dispatch to the project-manager agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        mode: Operating mode -- 'initiation' (process spec into project
              docs) or 'roadmap' (group assessed TODOs into sprints)
        spec_file: Path to the stakeholder's specification file
                   (required for initiation mode)
        todo_assessments: List of TODO assessment file paths
                         (required for roadmap mode)
        sprint_goals: High-level goals for the sprint roadmap
                      (used in roadmap mode)
    """
    _check_delegation_edge("dispatch_to_project_manager", frozenset({"team-lead"}))
    agent = get_project().get_agent("project-manager")
    prompt = agent.render_prompt(
        mode=mode,
        spec_file=spec_file,
        todo_assessments=todo_assessments or [],
        sprint_goals=sprint_goals,
    )
    result = await agent.dispatch(
        prompt=prompt,
        cwd=str(get_project().root),
        parent="team-lead",
        mode=mode,
    )
    return json.dumps(result, indent=2)


async def dispatch_to_project_architect(
    todo_files: list[str],
) -> str:
    """Dispatch to the project-architect agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        todo_files: List of TODO file paths to assess
    """
    _check_delegation_edge("dispatch_to_project_architect", frozenset({"team-lead"}))
    agent = get_project().get_agent("project-architect")
    prompt = agent.render_prompt(todo_files=todo_files)
    result = await agent.dispatch(
        prompt=prompt,
        cwd=str(get_project().root),
        parent="team-lead",
    )
    return json.dumps(result, indent=2)


async def dispatch_to_todo_worker(
    todo_ids: list[str],
    action: str,
) -> str:
    """Dispatch to the todo-worker agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        todo_ids: List of TODO IDs to operate on
        action: What to do (create, import, list, summarize, prioritize)
    """
    _check_delegation_edge("dispatch_to_todo_worker", frozenset({"team-lead"}))
    agent = get_project().get_agent("todo-worker")
    prompt = agent.render_prompt(todo_ids=todo_ids, action=action)
    result = await agent.dispatch(
        prompt=prompt,
        cwd=str(get_project().root),
        parent="team-lead",
    )
    return json.dumps(result, indent=2)


async def dispatch_to_sprint_planner(
    sprint_id: str,
    sprint_directory: str,
    todo_ids: list[str],
    goals: str,
    mode: str = "detail",
) -> str:
    """Dispatch to the sprint-planner agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        sprint_id: The sprint ID (e.g., '001')
        sprint_directory: Path to the sprint directory
        todo_ids: List of TODO IDs to address
        goals: High-level goals for the sprint
        mode: Planning mode -- 'roadmap' (lightweight) or 'detail' (full)
    """
    _check_delegation_edge("dispatch_to_sprint_planner", frozenset({"team-lead"}))
    agent = get_project().get_agent("sprint-planner")
    prompt = agent.render_prompt(
        sprint_id=sprint_id,
        sprint_directory=sprint_directory,
        todo_ids=todo_ids,
        goals=goals,
        mode=mode,
    )
    sprint_name = Path(sprint_directory).name
    result = await agent.dispatch(
        prompt=prompt,
        cwd=sprint_directory,
        parent="team-lead",
        mode=mode,
        sprint_name=sprint_name,
    )
    return json.dumps(result, indent=2)


async def dispatch_to_sprint_executor(
    sprint_id: str,
    sprint_directory: str,
    branch_name: str,
    tickets: list[str],
) -> str:
    """Dispatch to the sprint-executor agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        sprint_id: The sprint ID (e.g., '001')
        sprint_directory: Path to the sprint directory
        branch_name: Git branch name for the sprint
        tickets: List of ticket references to execute
    """
    _check_delegation_edge("dispatch_to_sprint_executor", frozenset({"team-lead"}))
    agent = get_project().get_agent("sprint-executor")
    prompt = agent.render_prompt(
        sprint_id=sprint_id,
        sprint_directory=sprint_directory,
        branch_name=branch_name,
        tickets=tickets,
    )
    sprint_name = Path(sprint_directory).name
    result = await agent.dispatch(
        prompt=prompt,
        cwd=sprint_directory,
        parent="team-lead",
        sprint_name=sprint_name,
    )
    return json.dumps(result, indent=2)


async def dispatch_to_ad_hoc_executor(
    task_description: str,
    scope_directory: str,
) -> str:
    """Dispatch to the ad-hoc-executor agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        task_description: Description of the change to make
        scope_directory: Directory scope for the change
    """
    _check_delegation_edge("dispatch_to_ad_hoc_executor", frozenset({"team-lead"}))
    agent = get_project().get_agent("ad-hoc-executor")
    prompt = agent.render_prompt(
        task_description=task_description,
        scope_directory=scope_directory,
    )
    result = await agent.dispatch(
        prompt=prompt,
        cwd=scope_directory,
        parent="team-lead",
    )
    return json.dumps(result, indent=2)


async def dispatch_to_sprint_reviewer(
    sprint_id: str,
    sprint_directory: str,
) -> str:
    """Dispatch to the sprint-reviewer agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        sprint_id: The sprint ID to review
        sprint_directory: Path to the sprint directory
    """
    _check_delegation_edge("dispatch_to_sprint_reviewer", frozenset({"team-lead"}))
    agent = get_project().get_agent("sprint-reviewer")
    prompt = agent.render_prompt(
        sprint_id=sprint_id,
        sprint_directory=sprint_directory,
    )
    sprint_name = Path(sprint_directory).name
    result = await agent.dispatch(
        prompt=prompt,
        cwd=sprint_directory,
        parent="team-lead",
        sprint_name=sprint_name,
    )
    return json.dumps(result, indent=2)


async def dispatch_to_architect(
    sprint_id: str,
    sprint_directory: str,
) -> str:
    """Dispatch to the architect agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        sprint_id: The sprint ID for the architecture update
        sprint_directory: Path to the sprint directory
    """
    _check_delegation_edge("dispatch_to_architect", frozenset({"sprint-planner"}))
    agent = get_project().get_agent("architect")
    prompt = agent.render_prompt(
        sprint_id=sprint_id,
        sprint_directory=sprint_directory,
    )
    sprint_name = Path(sprint_directory).name
    result = await agent.dispatch(
        prompt=prompt,
        cwd=sprint_directory,
        parent="sprint-planner",
        sprint_name=sprint_name,
    )
    return json.dumps(result, indent=2)


async def dispatch_to_architecture_reviewer(
    sprint_id: str,
    sprint_directory: str,
) -> str:
    """Dispatch to the architecture-reviewer agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        sprint_id: The sprint ID whose architecture to review
        sprint_directory: Path to the sprint directory
    """
    _check_delegation_edge(
        "dispatch_to_architecture_reviewer", frozenset({"sprint-planner"})
    )
    agent = get_project().get_agent("architecture-reviewer")
    prompt = agent.render_prompt(
        sprint_id=sprint_id,
        sprint_directory=sprint_directory,
    )
    sprint_name = Path(sprint_directory).name
    result = await agent.dispatch(
        prompt=prompt,
        cwd=sprint_directory,
        parent="sprint-planner",
        sprint_name=sprint_name,
    )
    return json.dumps(result, indent=2)


async def dispatch_to_technical_lead(
    sprint_id: str,
    sprint_directory: str,
) -> str:
    """Dispatch to the technical-lead agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        sprint_id: The sprint ID to create tickets for
        sprint_directory: Path to the sprint directory
    """
    _check_delegation_edge("dispatch_to_technical_lead", frozenset({"sprint-planner"}))
    agent = get_project().get_agent("technical-lead")
    prompt = agent.render_prompt(
        sprint_id=sprint_id,
        sprint_directory=sprint_directory,
    )
    sprint_name = Path(sprint_directory).name
    result = await agent.dispatch(
        prompt=prompt,
        cwd=sprint_directory,
        parent="sprint-planner",
        sprint_name=sprint_name,
    )
    return json.dumps(result, indent=2)


async def dispatch_to_code_monkey(
    ticket_path: str,
    ticket_plan_path: str,
    scope_directory: str,
    sprint_name: str,
    ticket_id: str,
) -> str:
    """Dispatch to the code-monkey agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        ticket_path: Path to the ticket file
        ticket_plan_path: Path to the ticket plan file
        scope_directory: Directory scope for the implementation
        sprint_name: Sprint name (e.g., '001-feature-name')
        ticket_id: Ticket ID (e.g., '001')
    """
    _check_delegation_edge(
        "dispatch_to_code_monkey", frozenset({"sprint-executor", "ad-hoc-executor"})
    )
    agent = get_project().get_agent("code-monkey")
    prompt = agent.render_prompt(
        ticket_path=ticket_path,
        ticket_plan_path=ticket_plan_path,
        scope_directory=scope_directory,
        sprint_name=sprint_name,
        ticket_id=ticket_id,
    )
    result = await agent.dispatch(
        prompt=prompt,
        cwd=scope_directory,
        parent="sprint-executor",
        sprint_name=sprint_name,
        ticket_id=ticket_id,
    )
    return json.dumps(result, indent=2)


async def dispatch_to_code_reviewer(
    file_paths: list[str],
    review_scope: str,
) -> str:
    """Dispatch to the code-reviewer agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        file_paths: List of file paths to review
        review_scope: Description of what to review and the acceptance criteria
    """
    _check_delegation_edge("dispatch_to_code_reviewer", frozenset({"ad-hoc-executor"}))
    agent = get_project().get_agent("code-reviewer")
    prompt = agent.render_prompt(
        file_paths=file_paths,
        review_scope=review_scope,
    )
    result = await agent.dispatch(
        prompt=prompt,
        cwd=str(get_project().root),
        parent="ad-hoc-executor",
    )
    return json.dumps(result, indent=2)
