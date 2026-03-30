---
id: '002'
title: Extract dispatch_tools.py with SDK-based query() orchestration
status: todo
use-cases:
  - SUC-001
  - SUC-002
depends-on:
  - '001'
github-issue: ''
todo: sdk-orchestration-cluster/sdk-based-orchestration.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Extract dispatch_tools.py with SDK-based query() orchestration

## Description

Create a new `dispatch_tools.py` module that owns the full subagent
lifecycle via the Claude Agent SDK `query()` function. This replaces the
current approach where the team-lead calls Claude's `Agent` tool
directly.

The module contains all 11 `async def dispatch_to_*` functions, each
following a consistent 7-step pattern:

1. Render the Jinja2 dispatch template with provided parameters.
2. Log the pre-execution dispatch entry (prompt, target agent, template).
3. Load the target agent's `contract.yaml` via `load_contract()`.
4. Configure `ClaudeAgentOptions` from the contract (`allowed_tools`,
   `mcp_servers`, `model`, `cwd`) and call `query()`.
5. Validate the return JSON against the contract's `returns` schema.
6. Log the post-execution result.
7. Return structured JSON to the caller.

Implementation tasks:

- Create `dispatch_tools.py` with all 11 dispatch functions.
- Remove the 3 existing dispatch functions from `artifact_tools.py`.
- Remove the `log_subagent_dispatch` and `update_dispatch_log` MCP tools
  (dispatch logging is now internal to each dispatch function).
- Add `claude-agent-sdk` to pyproject.toml.
- Update `mcp_server.py` to import and register dispatch_tools.
- Create dispatch templates for agents that do not yet have them.
- Update agent.md files to remove references to calling the Agent tool
  directly -- agents now use `dispatch_to_*` MCP tools.
- Pass the `model` field from the contract to `ClaudeAgentOptions`.

## Acceptance Criteria

- [ ] `dispatch_tools.py` exists with all 11 `dispatch_to_*` async functions
- [ ] Each function follows the 7-step pattern (render, log, load, execute, validate, log, return)
- [ ] Old dispatch functions removed from `artifact_tools.py`
- [ ] `log_subagent_dispatch` and `update_dispatch_log` MCP tools removed
- [ ] `mcp_server.py` imports and registers dispatch_tools
- [ ] `claude-agent-sdk` added to pyproject.toml
- [ ] Dispatch templates exist for all 11 agent dispatch edges
- [ ] Agent.md files updated to remove Agent tool references
- [ ] `model` field from contract passed to `ClaudeAgentOptions`
- [ ] Unit tests with mocked `query()` verifying logging, contract loading, and validation

## Testing

- **Existing tests to run**: `tests/test_artifact_tools.py` (verify removed functions are gone), `tests/test_process_tools.py`
- **New tests to write**: `tests/test_dispatch_tools.py` -- tests with mocked `query()` for each dispatch function, verifying the 7-step pattern (pre-log written, contract loaded, query called with correct options, return validated, post-log written, structured JSON returned)
- **Verification command**: `uv run pytest`
