---
id: "014"
title: "Enforce dispatch template usage"
status: done
use-cases: [SUC-003]
depends-on: ["012"]
github-issue: ""
todo: "enforce-dispatch-template-usage.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Enforce dispatch template usage

## Description

Dispatch templates were created in ticket 012 and placed in agent
directories. Agent definitions tell agents to use them. However, the e2e
test shows that dispatches are still ad-hoc prompts -- agents compose
whatever they want and send it, ignoring the templates entirely.

This is an instructional control failure: telling agents to use templates
does not work because nothing mechanically forces them to load or follow
the templates. The templates exist, agents are told to use them, and they
don't.

This ticket adds mechanical enforcement so that template usage is
required, not optional.

### Changes

#### 1. MCP tool: `get_dispatch_template(target_agent)`

Add an MCP tool that returns the dispatch template text for a given
agent. The dispatching agent calls this tool, receives the template with
UPPERCASE placeholders, fills them in, and uses the result as the
dispatch prompt.

This creates a mechanical step in the workflow -- the agent calls a tool
and gets back text it must use, rather than being told to go read a file
it can ignore.

#### 2. `log_subagent_dispatch` requires `template_used`

For dispatches to agents that have defined templates, the
`log_subagent_dispatch` tool should require a `template_used` field and
reject the call if it is missing. This makes the dispatch log the
enforcement point: the agent cannot log the dispatch (which it is
already required to do) without also declaring it used the template.

The tool should:
- Accept `template_used: <template-name>` as a parameter
- Reject with an error if the target agent has a template but
  `template_used` is not provided
- Allow `template_used` to be omitted for agents without templates

#### 3. E2E verification

The e2e verify script should check dispatch log frontmatter for the
`template_used` field. For dispatches to templated agents, the field
must be present. Its absence is a verification failure.

## Acceptance Criteria

- [x] `get_dispatch_template` MCP tool exists and returns template text for a given agent
- [x] `get_dispatch_template` returns an error for agents without templates
- [x] `log_subagent_dispatch` accepts `template_used` parameter
- [x] `log_subagent_dispatch` rejects dispatches to templated agents when `template_used` is missing
- [x] `log_subagent_dispatch` allows omitting `template_used` for agents without templates
- [x] E2E verify script checks `template_used` in dispatch log frontmatter for templated agents
- [x] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**:
  - Unit test: `get_dispatch_template` returns correct template for known agents
  - Unit test: `get_dispatch_template` returns error for agents without templates
  - Unit test: `log_subagent_dispatch` with `template_used` records field in frontmatter
  - Unit test: `log_subagent_dispatch` rejects call when target agent has template but `template_used` is missing
  - Unit test: `log_subagent_dispatch` accepts call without `template_used` when agent has no template
  - Unit test: verify script flags missing `template_used` as a failure
- **Verification command**: `uv run pytest`
