---
status: pending
---

# Agent Dispatch Templates with Role and Field Conventions


## Problem

When a higher-level agent (e.g., team-lead) dispatches work to a
lower-level agent (e.g., sprint-planner, sprint-executor), the
dispatching agent composes the prompt ad hoc every time. There is no
standard form or template governing what information gets passed down.
This leads to inconsistency: sometimes critical context is included,
sometimes it's forgotten. The receiving agent may not get explicit
instructions about what role it should adopt, what its scope is, or
what artifacts it should produce.

The stakeholder wants each level of agent to have a **dispatch
template** — a document that the dispatching agent retrieves, fills in,
and hands to the next agent. These are not Jinja or programmatic
templates. They use a simple CLASI-native templating convention:
fields in UPPERCASE are placeholders that the dispatching agent fills
in before sending.

## Desired Behavior

### Template structure

Each dispatch template is a markdown file that contains:

1. **Role declaration** — explicit instructions telling the receiving
   agent what type of subagent it is (e.g., "You are the
   sprint-executor. Your scope is..."). This removes ambiguity about
   the agent's identity and boundaries.

2. **Behavioral instructions** — additional directives about how the
   receiving agent should work (e.g., "Commit after each ticket",
   "Do not modify files outside the sprint directory", "Run the test
   suite before marking a ticket done").

3. **Fillable fields** — placeholders in UPPERCASE that the
   dispatching agent replaces with concrete values before dispatch.
   For example:
   - `SPRINT_ID` — the sprint being worked on
   - `SPRINT_DIRECTORY` — path to the sprint directory
   - `TICKETS` — list of tickets to execute
   - `BRANCH_NAME` — the git branch to work on
   - `GOALS` — summary of what the sprint or task should accomplish

4. **Context document references** — paths to planning artifacts the
   receiving agent should read (sprint.md, architecture.md, etc.).
   These may themselves be templated fields (e.g.,
   `ARCHITECTURE_DOC_PATH`).

### Templating convention

The templating language is deliberately minimal:

- Fields are written in `UPPERCASE_WITH_UNDERSCORES`.
- The dispatch instructions say: "Get template X, fill in all
  UPPERCASE fields, then dispatch."
- No control flow, no conditionals, no loops. If a template needs
  to vary structurally, create a separate template variant.

### Templates needed

At minimum, one template per standard dispatch relationship:

- **team-lead -> sprint-planner** — dispatch to plan a sprint
- **team-lead -> sprint-executor** — dispatch to execute a sprint
- **sprint-executor -> code-monkey** — dispatch to execute a
  single ticket (if ticket-level dispatch is used)

Additional templates may be needed for review dispatches
(architecture-reviewer, use-case-reviewer) as those roles are
formalized.

### Integration with dispatch logging

Dispatch logs (`log_subagent_dispatch`) should record which template
was used, so the audit trail shows not just what was sent but what
form it followed.

## Proposed Solution

### File location

Templates live alongside agent definitions if that's more natural:

```
agents/
  sprint-planner/
    dispatch-template.md
  sprint-executor/
    dispatch-template.md
```

The stakeholder should decide which layout is preferred.

### Example template sketch

```markdown
# Dispatch: Sprint Execution

You are the **sprint-executor**. Your job is to execute all tickets
in a sprint, in order, committing after each one.

## Sprint

- Sprint ID: SPRINT_ID
- Sprint directory: SPRINT_DIRECTORY
- Branch: BRANCH_NAME

## Goals

GOALS

## Tickets

TICKETS

## Context Documents

Read these before starting:

- SPRINT_DIRECTORY/sprint.md
- SPRINT_DIRECTORY/architecture.md
- SPRINT_DIRECTORY/usecases.md

## Instructions

- Execute tickets in order.
- Run the full test suite after each ticket.
- Move each ticket to done/ when complete.
- Do not modify files outside the sprint scope unless a ticket
  explicitly requires it.
```

### Changes to dispatching agents

Agent definitions (team-lead, sprint-executor) would be updated to
reference their dispatch templates. The process instructions would
say: "Before dispatching to agent X, load template Y, fill in the
UPPERCASE fields, and use the result as your dispatch prompt."

### Changes to dispatch logging

`log_subagent_dispatch` could accept an optional `template_used`
field to record which template was filled in for the dispatch.

## Files to Create or Modify

```
docs/clasi/templates/*.md                 (new dispatch templates)
agents/team-lead.md                       (reference templates in dispatch instructions)
agents/sprint-executor.md                 (reference templates if it dispatches to sub-agents)
claude_agent_skills/dispatch_log.py       (optional: add template_used field)
```

## Related

- `docs/clasi/todo/dispatch-logs-should-reference-sprint-documents.md` —
  addresses context document references in dispatch logs, which
  overlaps with the template's context documents section.
- Agent definitions in `agents/` — these define agent roles but
  currently don't include dispatch templates.

## Decisions

- Templates are part of the CLASI package, not project-level artifacts.
  Versioned with the package, served via MCP.
- `log_subagent_dispatch` should enforce template usage for dispatches
  to the agents we have identified templates for.

## Decisions (continued)

- Templates provide context for what the subagent is doing and reinforce
  process compliance. The agent definition says what the role IS; the
  template reminds it what to do THIS TIME. Templates are the place to
  add behavioral reinforcement for things agents keep forgetting (like
  logging dispatches to code-monkey).
- The sprint-executor → code-monkey dispatch template must include an
  explicit instruction to call `log_subagent_dispatch` before dispatching
  and `update_dispatch_log` after. This is the dispatch that keeps not
  getting logged despite being in the agent definition.
