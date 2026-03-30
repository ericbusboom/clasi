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
"""

from __future__ import annotations

import json
from pathlib import Path

from claude_agent_skills.mcp_server import server, content_path


# ---------------------------------------------------------------------------
# Shared helpers
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

    Returns a JSON string with status, result, log_path, and validations.
    """
    from claude_agent_skills.dispatch_log import (
        log_dispatch,
        update_dispatch_result,
    )
    from claude_agent_skills.contracts import load_contract, validate_return

    # 1. RENDER
    template = _load_jinja2_template(child)
    rendered = template.render(**template_params)

    # 2. LOG (pre-execution -- always happens)
    log_path = log_dispatch(
        parent=parent,
        child=child,
        scope=scope,
        prompt=rendered,
        sprint_name=sprint_name,
        ticket_id=ticket_id,
        template_used="dispatch-template.md.j2",
    )

    # 3. LOAD contract
    contract = load_contract(child)

    # Resolve working directory from contract or override
    work_dir = cwd_override or scope
    contract_cwd = contract.get("cwd", "")
    if contract_cwd and not cwd_override:
        # Substitute template variables in cwd
        resolved_cwd = contract_cwd
        for key, value in template_params.items():
            resolved_cwd = resolved_cwd.replace(f"{{{key}}}", str(value))
        # Only use if we resolved all variables
        if "{" not in resolved_cwd:
            work_dir = resolved_cwd

    # Try to import the SDK -- handle gracefully if not available
    try:
        from claude_agent_sdk import (  # type: ignore[import-not-found]
            query,
            ClaudeAgentOptions,
            ResultMessage,
        )
    except ImportError:
        # SDK not installed -- log the error and return
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
        return json.dumps({
            "status": "error",
            "message": error_msg,
            "log_path": str(log_path),
        }, indent=2)

    # Build options from contract
    options = ClaudeAgentOptions(
        system_prompt=_load_agent_system_prompt(child),
        cwd=work_dir,
        allowed_tools=contract.get("allowed_tools", []),
        mcp_servers=contract.get("mcp_servers", []),
        model=contract.get("model", "sonnet"),
    )

    # 4. EXECUTE
    result_text = ""
    try:
        async for message in query(prompt=rendered, options=options):
            if isinstance(message, ResultMessage):
                result_text = message.result
    except Exception as e:
        update_dispatch_result(
            log_path,
            result="error",
            files_modified=[],
            response=str(e),
        )
        return json.dumps({
            "status": "error",
            "message": str(e),
            "log_path": str(log_path),
        }, indent=2)

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
    return json.dumps({
        "status": validation["status"],
        "result": result_text,
        "log_path": str(log_path),
        "validations": validation,
    }, indent=2)


# ---------------------------------------------------------------------------
# Dispatch tools
# ---------------------------------------------------------------------------

@server.tool()
async def dispatch_to_requirements_narrator(
    project_path: str,
) -> str:
    """Dispatch to the requirements-narrator agent via Agent SDK.

    Renders the dispatch template, logs the dispatch, executes the
    subagent via query(), validates the result against the agent
    contract, logs the result, and returns structured JSON.

    Args:
        project_path: Path to the project root
    """
    return await _dispatch(
        parent="team-lead",
        child="requirements-narrator",
        template_params={"project_path": project_path},
        scope=project_path,
    )


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
    return await _dispatch(
        parent="team-lead",
        child="todo-worker",
        template_params={"todo_ids": todo_ids, "action": action},
        scope=str(Path.cwd()),
    )


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
    sprint_name = Path(sprint_directory).name
    return await _dispatch(
        parent="team-lead",
        child="sprint-planner",
        template_params={
            "sprint_id": sprint_id,
            "sprint_directory": sprint_directory,
            "todo_ids": todo_ids,
            "goals": goals,
        },
        scope=sprint_directory,
        sprint_name=sprint_name,
        mode=mode,
    )


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
    sprint_name = Path(sprint_directory).name
    return await _dispatch(
        parent="team-lead",
        child="sprint-executor",
        template_params={
            "sprint_id": sprint_id,
            "sprint_directory": sprint_directory,
            "branch_name": branch_name,
            "tickets": tickets,
        },
        scope=sprint_directory,
        sprint_name=sprint_name,
    )


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
    return await _dispatch(
        parent="team-lead",
        child="ad-hoc-executor",
        template_params={
            "task_description": task_description,
            "scope_directory": scope_directory,
        },
        scope=scope_directory,
    )


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
    sprint_name = Path(sprint_directory).name
    return await _dispatch(
        parent="team-lead",
        child="sprint-reviewer",
        template_params={
            "sprint_id": sprint_id,
            "sprint_directory": sprint_directory,
        },
        scope=sprint_directory,
        sprint_name=sprint_name,
    )


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
    sprint_name = Path(sprint_directory).name
    return await _dispatch(
        parent="sprint-planner",
        child="architect",
        template_params={
            "sprint_id": sprint_id,
            "sprint_directory": sprint_directory,
        },
        scope=sprint_directory,
        sprint_name=sprint_name,
    )


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
    sprint_name = Path(sprint_directory).name
    return await _dispatch(
        parent="sprint-planner",
        child="architecture-reviewer",
        template_params={
            "sprint_id": sprint_id,
            "sprint_directory": sprint_directory,
        },
        scope=sprint_directory,
        sprint_name=sprint_name,
    )


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
    sprint_name = Path(sprint_directory).name
    return await _dispatch(
        parent="sprint-planner",
        child="technical-lead",
        template_params={
            "sprint_id": sprint_id,
            "sprint_directory": sprint_directory,
        },
        scope=sprint_directory,
        sprint_name=sprint_name,
    )


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
    return await _dispatch(
        parent="sprint-executor",
        child="code-monkey",
        template_params={
            "ticket_path": ticket_path,
            "ticket_plan_path": ticket_plan_path,
            "scope_directory": scope_directory,
            "sprint_name": sprint_name,
            "ticket_id": ticket_id,
        },
        scope=scope_directory,
        sprint_name=sprint_name,
        ticket_id=ticket_id,
    )


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
    return await _dispatch(
        parent="ad-hoc-executor",
        child="code-reviewer",
        template_params={
            "file_paths": file_paths,
            "review_scope": review_scope,
        },
        scope=str(Path.cwd()),
    )
