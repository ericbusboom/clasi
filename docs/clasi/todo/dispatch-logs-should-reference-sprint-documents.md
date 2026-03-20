---
status: pending
---

# Dispatch Logs Should Reference Sprint Planning Documents

**Do not implement yet.**

## Problem

Dispatch logs record the prompt sent to a subagent and, after the
subagent returns, the result and files modified. But they do not
reference the sprint planning documents that the subagent is expected
to read and work from.

In `tests/e2e/project/docs/clasi/log/sprints/001-project-structure-and-menu/sprint-planner-001.md`,
the dispatch from team-lead to sprint-planner includes the sprint goals
and key details inline in the prompt body. This is useful — but the log
does not reference the planning documents that were produced or that a
subsequent executor would consume:

- `sprint.md` — sprint scope, goals, and deliverables
- `architecture-update.md` — architectural changes for the sprint
- `usecases.md` — use cases the sprint covers
- Ticket files in `tickets/` — the individual work items

The `files_modified` frontmatter field lists files the subagent changed,
which partially addresses this for planning dispatches (the planner
creates sprint.md, usecases.md, architecture-update.md). But for
execution dispatches, `files_modified` lists code files, not the
planning documents the executor was reading. A reader of the execution
dispatch log cannot trace what planning context the agent had — which
sprint.md it was working from, which architecture it was following,
which tickets it was executing.

This makes the dispatch log incomplete as an audit trail. You can see
what the agent was told and what it changed, but not what planning
artifacts informed its decisions.

## Desired Behavior

Each dispatch log should include a section or frontmatter field that
lists the planning documents the subagent was expected to reference.
For a sprint-executor dispatch, this would include:

```yaml
context_documents:
- docs/clasi/sprints/001-project-structure-and-menu/sprint.md
- docs/clasi/sprints/001-project-structure-and-menu/architecture-update.md
- docs/clasi/sprints/001-project-structure-and-menu/usecases.md
- docs/clasi/sprints/001-project-structure-and-menu/tickets/001-create-package-structure.md
- docs/clasi/sprints/001-project-structure-and-menu/tickets/002-implement-main-menu.md
```

For a sprint-planner dispatch, the context documents would be upstream
artifacts like the project overview and spec.

The key principle: a reader should be able to open a dispatch log and
follow every document reference to reconstruct the full context the
agent had when it performed the work.

## Proposed Solution

### Option A: Frontmatter field

Add a `context_documents` field to dispatch log frontmatter. The
dispatching agent (or the `log_subagent_dispatch` tool) populates it
with paths to the planning documents relevant to the dispatch.

Pros: machine-readable, easy to validate.
Cons: requires the dispatching agent to know which documents matter,
or requires the tool to infer them from the sprint structure.

### Option B: Body section

Add a `## Context Documents` section to the dispatch log body, listing
the documents with brief descriptions of their role.

Pros: more human-readable, can include notes on why each document
matters.
Cons: harder to parse programmatically.

### Option C: Automatic population by the tool

`log_subagent_dispatch` already receives `sprint_name` and optionally
`ticket_id`. It could automatically resolve the sprint directory and
list the standard planning documents (sprint.md, architecture-update.md,
usecases.md) plus any ticket files. This removes the burden from the
dispatching agent.

This is the preferred option — it keeps logging accurate without
relying on the agent to remember which documents to list.

## Files to Modify

```
claude_agent_skills/dispatch_log.py          (add context_documents to log entries)
claude_agent_skills/artifact_tools.py        (pass context info through)
```

## Related

- `docs/clasi/todo/done/append-subagent-response-to-dispatch-log.md` —
  adds the subagent response to logs (what the agent said back).
- `docs/clasi/todo/done/subagent-dispatch-logging-at-all-levels.md` —
  ensures all dispatching agents log dispatches (coverage).
- `docs/clasi/todo/done/missing-sub-dispatch-logs-in-e2e-output.md` —
  addresses missing sub-dispatch logs in the e2e test output.

This TODO addresses a different gap: not whether logs exist or what the
agent responded, but whether the log records what documents the agent
was working from.
