---
status: pending
---

# Typed Dispatch MCP Tools with Jinja2 Templates

**Do not implement yet.**

## Problem

The current dispatch mechanism has two separate steps that agents
routinely fail to combine correctly:

1. Call `get_dispatch_template(target_agent)` to get a markdown template
   with UPPERCASE placeholders (e.g., `SPRINT_ID`, `TICKET_PATH`).
2. Manually fill in placeholders, then pass the rendered prompt plus a
   `template_used` string to `log_subagent_dispatch`.

This is error-prone. Agents forget to fill placeholders, pass wrong
values, or skip the template entirely -- triggering the `template_used`
enforcement error in `dispatch_log.py`. The enforcement mechanism
(TEMPLATED_AGENTS set + ValueError when template_used is None) is a
guardrail for a bad interface rather than a fix for the root cause.

## Proposed Solution

Replace `get_dispatch_template` and the template_used enforcement with
three purpose-built MCP tools that accept typed parameters, render the
template internally, log the dispatch automatically, and return the
rendered prompt ready to pass to the Agent tool.

### New MCP Tools

**`dispatch_to_sprint_planner`**

Parameters (matching the sprint-planner dispatch-template.md fields):
- `sprint_id: str` -- the sprint ID
- `sprint_directory: str` -- path to the sprint directory
- `todo_ids: list[str]` -- TODO IDs to address
- `goals: str` -- sprint goals description

**`dispatch_to_sprint_executor`**

Parameters (matching the sprint-executor dispatch-template.md fields):
- `sprint_id: str` -- the sprint ID
- `sprint_directory: str` -- path to the sprint directory
- `branch_name: str` -- the git branch name
- `tickets: list[str]` -- list of ticket identifiers to execute

**`dispatch_to_code_monkey`**

Parameters (matching the code-monkey dispatch-template.md fields):
- `ticket_path: str` -- path to the ticket file
- `ticket_plan_path: str` -- path to the ticket plan file (or empty)
- `scope_directory: str` -- directory the code-monkey works within
- `sprint_name: str` -- sprint name for dispatch logging
- `ticket_id: str` -- ticket ID for dispatch logging

### Behavior (all three tools)

1. Load the corresponding Jinja2 template from the agent's directory.
2. Render the template with the typed parameters.
3. Call `log_dispatch` internally (parent/child/scope/prompt/sprint info
   are all known from the parameters and calling context).
4. Return a JSON result with:
   - `rendered_prompt: str` -- the filled-in dispatch prompt
   - `log_path: str` -- the dispatch log file path

The calling agent then passes `rendered_prompt` directly to the Agent
tool. No manual placeholder filling. No separate logging call.

### Template Migration

Convert the three existing `dispatch-template.md` files to Jinja2
templates (`dispatch-template.md.j2` or similar):

- `agents/domain-controllers/sprint-planner/dispatch-template.md`
  -- replace `SPRINT_ID`, `SPRINT_DIRECTORY`, `TODO_IDS`, `GOALS`
  with `{{ sprint_id }}`, `{{ sprint_directory }}`, etc.
- `agents/domain-controllers/sprint-executor/dispatch-template.md`
  -- replace `SPRINT_ID`, `SPRINT_DIRECTORY`, `BRANCH_NAME`, `TICKETS`
  with Jinja2 variables.
- `agents/task-workers/code-monkey/dispatch-template.md`
  -- replace `TICKET_PATH`, `TICKET_PLAN_PATH`, `SCOPE_DIRECTORY`,
  `SPRINT_NAME`, `TICKET_ID` with Jinja2 variables.

### Removals

- Remove `get_dispatch_template` MCP tool from `artifact_tools.py`.
- Remove `template_used` parameter from `log_subagent_dispatch` and
  `log_dispatch`.
- Remove `TEMPLATED_AGENTS` enforcement set from `dispatch_log.py`.
- Update agent definitions that reference `get_dispatch_template`
  (team-lead, sprint-executor) to use the new tools instead.

### Dependency

Add `jinja2` to project dependencies (`pyproject.toml`).

## Files to Create or Modify

```
pyproject.toml                                         (add jinja2 dependency)
claude_agent_skills/artifact_tools.py                  (remove get_dispatch_template, add 3 new tools)
claude_agent_skills/dispatch_log.py                    (remove TEMPLATED_AGENTS, template_used enforcement)
claude_agent_skills/agents/domain-controllers/sprint-planner/dispatch-template.md   (convert to Jinja2)
claude_agent_skills/agents/domain-controllers/sprint-executor/dispatch-template.md  (convert to Jinja2)
claude_agent_skills/agents/task-workers/code-monkey/dispatch-template.md            (convert to Jinja2)
claude_agent_skills/agents/domain-controllers/sprint-executor/agent.md              (update dispatch instructions)
claude_agent_skills/agents/main-controller/team-lead/agent.md                       (update dispatch instructions)
tests/unit/test_dispatch_log.py                        (update tests for removed enforcement)
tests/unit/test_mcp_server.py                          (add tests for new tools, remove old tool tests)
```

## Open Questions

- Should the old `dispatch-template.md` files be kept alongside the
  `.j2` files during a transition period, or replaced in one shot?
- Should `log_subagent_dispatch` remain as a general-purpose tool for
  non-templated dispatches (e.g., architect, architecture-reviewer), or
  should those also get typed dispatch tools eventually?
- The `template_used` field in dispatch log frontmatter -- should it be
  auto-set to the tool name (e.g., `dispatch_to_code_monkey`), or
  dropped entirely since the tool name is implicit?
