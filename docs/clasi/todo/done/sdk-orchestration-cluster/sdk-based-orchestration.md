---
status: in-progress
source: https://github.com/ericbusboom/clasi/issues/9
sprint: '001'
tickets:
- 001-002
---

# SDK based orchestration

## Problem

The `dispatch_to_*` and `log_subagent_dispatch` MCP tools log the *intended*
prompt but do not control the *actual* dispatch. The team-lead calls a dispatch
tool to render and log the prompt, then separately invokes Claude's built-in
`Agent` tool to execute the subagent. These are two independent steps with no
enforcement coupling between them.

This means the team-lead can (and does) skip logging, log a different prompt
than it actually sends, or call `Agent` directly without going through the
dispatch tools at all. Logging compliance is a social contract enforced by
instructions, not a structural property of the system.

## Desired Behavior

The `dispatch_to_*` tools should own the full dispatch lifecycle: render the
prompt, log it, execute the subagent via the Agent SDK `query()` call, log the
result, and return the subagent's output to the team-lead. The team-lead never
calls `Agent` directly — it calls a typed dispatch tool and gets back a result.

This makes logging structurally enforced: the log call is in the same function
body as the `query()` call. There is no code path through which a dispatch
can occur without a log entry.

## Proposed Changes

### 1. Add Agent SDK dependency

Add `claude-agent-sdk` to `pyproject.toml`. The MCP server tools become
`async def` functions, which FastMCP supports.

### 2. Refactor `dispatch_to_sprint_planner` and `dispatch_to_sprint_executor`

Change these tools from "render and return prompt" to "render, log, execute,
log result, return output":

```python
@server.tool()
async def dispatch_to_sprint_planner(
    sprint_id: str,
    sprint_directory: str,
    todo_ids: list[str],
    goals: str,
) -> str:
    from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage
    from claude_agent_skills.dispatch_log import log_dispatch, update_dispatch_result

    rendered = template.render(...)

    # Log BEFORE — always happens, no Claude cooperation required
    log_path = log_dispatch(
        parent="team-lead",
        child="sprint-planner",
        prompt=rendered,
        sprint_name=Path(sprint_directory).name,
        template_used="dispatch-template.md.j2",
    )

    # Execute — sub-agent gets full Claude Code agent loop
    result_text = ""
    async for message in query(
        prompt=rendered,
        options=ClaudeAgentOptions(
            system_prompt=_load_agent_system_prompt("sprint-planner"),
            cwd=sprint_directory,
            allowed_tools=["Read", "Write", "Edit", "Bash", "mcp__clasi__*"],
        ),
    ):
        if isinstance(message, ResultMessage):
            result_text = message.result

    # Log AFTER — always happens
    update_dispatch_result(log_path, result="success", response=result_text)

    return json.dumps({"result": result_text, "log_path": str(log_path)})
```

Apply the same pattern to `dispatch_to_sprint_executor` and
`dispatch_to_code_monkey`.

### 3. Add a helper to load agent system prompts

The `query()` call needs the agent's role definition as its system prompt.
Add a small helper that reads and returns the agent.md content for a named
agent, to be used inside dispatch tools.

### 4. Handle `cwd` explicitly

Each dispatch tool should resolve the correct working directory for the
sub-agent. Sprint-scoped agents (sprint-planner, sprint-executor, code-monkey)
use the sprint directory. Ad-hoc agents use the project root (`Path.cwd()`
at the time the MCP server received the tool call, which is the project root).

The MCP server process must be started from the project root for this to
resolve correctly — which is already the case when invoked via `.mcp.json`.

### 5. Remove team-lead instruction to call `Agent` directly

Update `team-lead/agent.md` to remove the delegation map entries that
reference the built-in `Agent` tool. The team-lead's instruction becomes:
call the typed dispatch tool and pass its return value to the stakeholder.
The `log_subagent_dispatch` / `update_dispatch_log` tools remain available
for agents that do not yet have typed dispatch tools (todo-worker,
requirements-narrator), but should eventually be replaced the same way.

### 6. Authentication

The Agent SDK sub-agents need Anthropic credentials. For local development,
they can inherit the Claude Code session via the bundled CLI
(`apiKeyRequired: false` mode). For CI or server deployment, an
`ANTHROPIC_API_KEY` environment variable is required. Document both paths.

## What Does Not Change

- `dispatch_log.py` — reused as-is
- Agent definition `.md` files — reused as system prompts
- Jinja2 dispatch templates — reused as-is
- The team-lead's role as interactive VS Code / Claude Code session
- The CLASI MCP server structure and FastMCP setup

## Open Questions

- FastMCP async tool support: verify that `async def` tools work correctly
  with the current FastMCP version in use.
- Sub-agent MCP access: sub-agents spawned via `query()` need access to the
  CLASI MCP server themselves (to call `create_ticket`, `list_todos`, etc.).
  Pass the MCP server configuration in `ClaudeAgentOptions(mcp_servers=...)`
  pointing at the same running CLASI server instance, or start a second
  instance scoped to the sub-agent's working directory.
- Result truncation: `query()` returns the final `ResultMessage.result` text.
  For long sub-agent runs this may be a summary rather than the full output.
  Evaluate whether the team-lead needs the full transcript or just the result.
