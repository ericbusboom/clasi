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
from pathlib import Path

logger = logging.getLogger("clasi.dispatch")

from clasi.mcp_server import server, content_path, get_project


# ---------------------------------------------------------------------------
# Legacy helpers (kept for backward compatibility with existing imports)
# ---------------------------------------------------------------------------

def _load_jinja2_template(agent_name: str):
    """Load the Jinja2 dispatch template for the named agent.

    Searches for ``dispatch-template.md.j2`` in the agent's directory
    under the content tree.

    Raises:
        ValueError: If no template is found for the agent.
    """
    from jinja2 import Template

    agents_dir = content_path("agents")
    for template_path in agents_dir.rglob("dispatch-template.md.j2"):
        if template_path.parent.name == agent_name:
            return Template(template_path.read_text(encoding="utf-8"))

    raise ValueError(
        f"No dispatch template found for agent '{agent_name}'. "
        f"Only agents with a dispatch-template.md.j2 file in their "
        f"directory have templates."
    )


def _load_agent_system_prompt(agent_name: str) -> str:
    """Load the agent.md content as a system prompt.

    Reads the agent.md file from the agent's directory and returns
    its content as a string suitable for a system prompt.
    """
    agents_dir = content_path("agents")
    for agent_md in agents_dir.rglob("agent.md"):
        if agent_md.parent.name == agent_name:
            return agent_md.read_text(encoding="utf-8")

    raise ValueError(
        f"No agent.md found for agent '{agent_name}'."
    )


async def _dispatch(
    *,
    parent: str,
    child: str,
    template_params: dict,
    scope: str,
    sprint_name: str | None = None,
    ticket_id: str | None = None,
    mode: str | None = None,
    cwd_override: str | None = None,
) -> str:
    """Shared 7-step dispatch pattern.

    Now delegates to Agent.dispatch(). Kept for backward compatibility.

    Returns a JSON string with status, result, log_path, and validations.
    """
    agent = get_project().get_agent(child)
    prompt = agent.render_prompt(**template_params)

    work_dir = cwd_override or scope
    result = await agent.dispatch(
        prompt=prompt,
        cwd=work_dir,
        parent=parent,
        mode=mode,
        sprint_name=sprint_name,
        ticket_id=ticket_id,
    )
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Dispatch tools
# ---------------------------------------------------------------------------

@server.tool()
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


@server.tool()
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
    agent = get_project().get_agent("project-architect")
    prompt = agent.render_prompt(todo_files=todo_files)
    result = await agent.dispatch(
        prompt=prompt,
        cwd=str(get_project().root),
        parent="team-lead",
    )
    return json.dumps(result, indent=2)


@server.tool()
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
    agent = get_project().get_agent("todo-worker")
    prompt = agent.render_prompt(todo_ids=todo_ids, action=action)
    result = await agent.dispatch(
        prompt=prompt,
        cwd=str(get_project().root),
        parent="team-lead",
    )
    return json.dumps(result, indent=2)


@server.tool()
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


@server.tool()
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


@server.tool()
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


@server.tool()
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


@server.tool()
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


@server.tool()
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


@server.tool()
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


@server.tool()
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


@server.tool()
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
