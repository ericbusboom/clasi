---
id: "013"
title: "Dispatch logs should reference sprint documents"
status: open
use-cases: [SUC-003]
depends-on: ["009"]
github-issue: ""
todo: "dispatch-logs-should-reference-sprint-documents.md"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Dispatch logs should reference sprint documents

## Description

Dispatch logs record the prompt sent to a subagent and the result, but
they do not reference the sprint planning documents the subagent was
expected to read and work from. A reader of an execution dispatch log
cannot trace what planning context the agent had -- which sprint.md it
was working from, which architecture it was following, or which tickets
it was executing.

This makes the dispatch log incomplete as an audit trail. You can see
what the agent was told and what it changed, but not what planning
artifacts informed its decisions.

This ticket adds a `context_documents` field to dispatch logs so every
dispatch records the planning documents the subagent was working from.

### Changes

#### 1. Add context_documents to dispatch log frontmatter

Update the dispatch log format to include a `context_documents` field
listing the planning documents relevant to the dispatch:

```yaml
context_documents:
  - docs/clasi/sprints/024-e2e-guessing-game-test/sprint.md
  - docs/clasi/sprints/024-e2e-guessing-game-test/architecture-update.md
  - docs/clasi/sprints/024-e2e-guessing-game-test/usecases.md
```

#### 2. Automatic population by log_subagent_dispatch

`log_subagent_dispatch` already receives `sprint_name` and optionally
`ticket_id`. Update it to automatically resolve the sprint directory
and list the standard planning documents (sprint.md, architecture-update.md,
usecases.md) plus any referenced ticket files. This removes the burden
from the dispatching agent to remember which documents to list.

#### 3. Accept optional context_documents override

Allow the dispatching agent to pass an explicit `context_documents` list
to `log_subagent_dispatch` for cases where the automatic resolution is
not sufficient (e.g., when extra documents outside the sprint directory
are relevant).

#### 4. Update dispatch log rendering

Ensure the dispatch log markdown includes a `## Context Documents`
section listing all referenced documents with their paths, so the log
is human-readable as well as machine-parseable via frontmatter.

## Acceptance Criteria

- [ ] `log_subagent_dispatch` auto-populates `context_documents` from the sprint directory when `sprint_name` is provided
- [ ] Dispatch log frontmatter includes `context_documents` list
- [ ] Dispatch log body includes a `## Context Documents` section
- [ ] `log_subagent_dispatch` accepts optional `context_documents` parameter for manual override
- [ ] Sprint-executor dispatch logs reference sprint.md, architecture-update.md, usecases.md, and ticket files
- [ ] Sprint-planner dispatch logs reference upstream artifacts (project overview, spec)
- [ ] `uv run pytest` passes with no regressions

## Testing

- **Existing tests to run**: `uv run pytest` -- no regressions to existing test suite
- **New tests to write**:
  - Unit test: `log_subagent_dispatch` with `sprint_name` auto-populates context_documents
  - Unit test: `log_subagent_dispatch` with explicit `context_documents` uses the provided list
  - Unit test: dispatch log markdown includes `## Context Documents` section
  - Unit test: frontmatter `context_documents` field matches the documents listed in body
- **Verification command**: `uv run pytest`
