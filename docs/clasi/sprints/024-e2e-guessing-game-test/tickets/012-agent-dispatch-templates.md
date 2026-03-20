---
id: "012"
title: "Agent dispatch templates with role and field conventions"
status: open
use-cases: [SUC-003]
depends-on: ["009"]
github-issue: ""
todo: "agent-dispatch-templates-with-role-and-field-conventions.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Agent dispatch templates with role and field conventions

## Description

When a higher-level agent dispatches work to a lower-level agent, the
dispatching agent composes the prompt ad hoc. There is no standard form
governing what information gets passed down, leading to inconsistency:
critical context is sometimes included and sometimes forgotten. The
receiving agent may not get explicit instructions about its role, scope,
or expected artifacts.

This ticket introduces dispatch templates -- markdown files with
UPPERCASE placeholders that the dispatching agent fills in before sending.
Each template includes a role declaration, behavioral instructions,
fillable fields, and context document references.

### Changes

#### 1. Create dispatch templates

Create dispatch template files for each standard dispatch relationship:

- **team-lead -> sprint-planner** (`docs/clasi/templates/dispatch-sprint-planner.md`)
- **team-lead -> sprint-executor** (`docs/clasi/templates/dispatch-sprint-executor.md`)
- **sprint-executor -> code-monkey** (`docs/clasi/templates/dispatch-code-monkey.md`)

Each template includes:
- Role declaration telling the receiving agent what it is and its scope
- Behavioral instructions (commit cadence, test requirements, scope limits)
- UPPERCASE fillable fields (SPRINT_ID, SPRINT_DIRECTORY, BRANCH_NAME,
  GOALS, TICKETS, etc.)
- Context document references pointing to planning artifacts

#### 2. Templating convention

Fields are written in `UPPERCASE_WITH_UNDERSCORES`. The dispatching
agent's instructions say: "Get template X, fill in all UPPERCASE fields,
then dispatch." No control flow, no conditionals, no loops.

#### 3. Update dispatching agent definitions

Update agent definitions for team-lead and sprint-executor to reference
their dispatch templates. Instructions should state: "Before dispatching
to agent X, load template Y, fill in the UPPERCASE fields, and use the
result as your dispatch prompt."

#### 4. Sprint-executor -> code-monkey template logging

The code-monkey dispatch template must include an explicit instruction to
call `log_subagent_dispatch` before dispatching and `update_dispatch_log`
after. This reinforces the dispatch logging requirement from ticket 009.

#### 5. Add template_used field to dispatch logging

Update `log_subagent_dispatch` to accept an optional `template_used`
field so the audit trail records which template was filled in for each
dispatch.

## Acceptance Criteria

- [ ] Dispatch template exists for team-lead -> sprint-planner
- [ ] Dispatch template exists for team-lead -> sprint-executor
- [ ] Dispatch template exists for sprint-executor -> code-monkey
- [ ] Each template includes role declaration, behavioral instructions, UPPERCASE fields, and context document references
- [ ] Team-lead agent definition references dispatch templates for sprint-planner and sprint-executor dispatches
- [ ] Sprint-executor agent definition references dispatch template for code-monkey dispatches
- [ ] Code-monkey dispatch template includes mandatory `log_subagent_dispatch` / `update_dispatch_log` instructions
- [ ] `log_subagent_dispatch` accepts optional `template_used` field
- [ ] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**:
  - Unit test: `log_subagent_dispatch` with `template_used` parameter records the template name
  - Manual verification: Dispatch templates render correctly with filled-in fields
  - Manual verification: Agent definitions reference templates in dispatch workflows
- **Verification command**: `uv run pytest`
