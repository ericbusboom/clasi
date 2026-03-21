---
id: "015"
title: "Typed dispatch MCP tools with Jinja2 templates"
status: done
use-cases: [SUC-003]
depends-on: ["014"]
github-issue: ""
todo: "typed-dispatch-mcp-tools-with-jinja2-templates.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Typed dispatch MCP tools with Jinja2 templates

## Description

The current dispatch mechanism requires agents to perform two separate
steps: call `get_dispatch_template(target_agent)` to get a markdown
template with UPPERCASE placeholders, then manually fill in the
placeholders and pass the rendered prompt plus a `template_used` string
to `log_subagent_dispatch`. This is error-prone -- agents forget to fill
placeholders, pass wrong values, or skip the template entirely.

This ticket replaces `get_dispatch_template` and the `template_used`
enforcement with three purpose-built MCP tools that accept typed
parameters, render the template internally via Jinja2, log the dispatch
automatically, and return the rendered prompt ready to pass to the Agent
tool.

### Changes

#### 1. Add Jinja2 dependency

Add `jinja2` to `pyproject.toml` project dependencies.

#### 2. Convert dispatch templates to Jinja2

Convert the three existing `dispatch-template.md` files to Jinja2
templates (`.md.j2` or similar):

- `agents/domain-controllers/sprint-planner/dispatch-template.md`
  -- replace `SPRINT_ID`, `SPRINT_DIRECTORY`, `TODO_IDS`, `GOALS`
  with `{{ sprint_id }}`, `{{ sprint_directory }}`, etc.
- `agents/domain-controllers/sprint-executor/dispatch-template.md`
  -- replace `SPRINT_ID`, `SPRINT_DIRECTORY`, `BRANCH_NAME`, `TICKETS`
  with Jinja2 variables.
- `agents/task-workers/code-monkey/dispatch-template.md`
  -- replace `TICKET_PATH`, `TICKET_PLAN_PATH`, `SCOPE_DIRECTORY`,
  `SPRINT_NAME`, `TICKET_ID` with Jinja2 variables.

#### 3. Create three typed dispatch MCP tools

**`dispatch_to_sprint_planner`** -- Parameters: `sprint_id`, `sprint_directory`,
`todo_ids`, `goals`. Loads the sprint-planner Jinja2 template, renders it,
logs the dispatch, returns `rendered_prompt` and `log_path`.

**`dispatch_to_sprint_executor`** -- Parameters: `sprint_id`,
`sprint_directory`, `branch_name`, `tickets`. Loads the sprint-executor
Jinja2 template, renders it, logs the dispatch, returns `rendered_prompt`
and `log_path`.

**`dispatch_to_code_monkey`** -- Parameters: `ticket_path`,
`ticket_plan_path`, `scope_directory`, `sprint_name`, `ticket_id`. Loads
the code-monkey Jinja2 template, renders it, logs the dispatch, returns
`rendered_prompt` and `log_path`.

All three tools follow the same behavior:
1. Load the corresponding Jinja2 template from the agent's directory.
2. Render the template with the typed parameters.
3. Call `log_dispatch` internally (parent/child/scope/prompt/sprint info
   are all known from the parameters and calling context).
4. Return JSON with `rendered_prompt` and `log_path`.

#### 4. Remove old dispatch infrastructure

- Remove `get_dispatch_template` MCP tool from `artifact_tools.py`.
- Remove `template_used` parameter from `log_subagent_dispatch` and
  `log_dispatch`.
- Remove `TEMPLATED_AGENTS` enforcement set from `dispatch_log.py`.

#### 5. Update agent definitions

Update agent definitions that reference `get_dispatch_template`
(team-lead, sprint-executor) to use the new typed dispatch tools instead.

## Acceptance Criteria

- [x] `jinja2` added to `pyproject.toml` dependencies
- [x] Three dispatch templates converted to Jinja2 format (`.md.j2`)
- [x] `dispatch_to_sprint_planner` MCP tool exists, accepts typed params, renders template, logs dispatch, returns rendered prompt
- [x] `dispatch_to_sprint_executor` MCP tool exists, accepts typed params, renders template, logs dispatch, returns rendered prompt
- [x] `dispatch_to_code_monkey` MCP tool exists, accepts typed params, renders template, logs dispatch, returns rendered prompt
- [x] `get_dispatch_template` MCP tool removed
- [x] `template_used` parameter removed from `log_subagent_dispatch`
- [x] `TEMPLATED_AGENTS` enforcement removed from `dispatch_log.py`
- [x] Agent definitions updated to use new typed dispatch tools
- [x] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**:
  - Unit test: `dispatch_to_sprint_planner` renders template with correct variable substitution
  - Unit test: `dispatch_to_sprint_executor` renders template with correct variable substitution
  - Unit test: `dispatch_to_code_monkey` renders template with correct variable substitution
  - Unit test: Each typed dispatch tool logs the dispatch automatically
  - Unit test: Each typed dispatch tool returns `rendered_prompt` and `log_path`
  - Unit test: Old `get_dispatch_template` tool no longer exists
  - Unit test: `log_subagent_dispatch` no longer requires `template_used`
- **Verification command**: `uv run pytest`
