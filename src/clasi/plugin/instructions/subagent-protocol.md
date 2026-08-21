---
name: subagent-protocol
description: Rules for curating context when dispatching subagents — what to include, what to exclude, directory scope, and logging
---

# Subagent Protocol

Rules for dispatching subagents via the `dispatch-subagent` skill.

## Context Curation

### Include

- **Ticket**: description, acceptance criteria, testing section
- **Ticket plan**: approach, files to modify, testing plan
- **Source files**: content of files the subagent will read or modify
- **Architecture**: relevant decisions from the sprint's `sprint.md`
  Architecture section (or its `architecture-update.md` file, for sprints
  planned before the single-doc rewrite)
- **Standards**: coding-standards, testing, git-workflow instructions
- **Language instructions**: per-project language-specific standards

### Exclude

- **Conversation history**: the controller's prior messages
- **Other tickets**: only the current ticket's context
- **Debug logs**: from prior failed attempts (unless re-dispatching
  with feedback)
- **Full directory listings**: only include specific file paths
- **Sprint planning docs**: sprint.md (including its Architecture and
  Use Cases sections), unless the task is planning

## Directory Scope

When dispatching, always specify the `scope_directory`:

- The subagent prompt must state: "You may only create or modify files
  under `<scope_directory>`. You may read files from any location."
- Subagents may **read** from anywhere — they need source files,
  instructions, and architecture for context.
- Subagents may only **write** within their declared scope.
- If the task requires writing outside the scope, the subagent should
  **return a request** to the controller asking for expanded scope,
  rather than writing directly.

## Logging

**No dispatch logging is currently mandated or MCP-tool-backed.** Earlier
versions of this instruction required calling `dispatch_log.log_dispatch()`
before every dispatch and updating the log afterward — but that function
is a plain Python helper in `src/clasi/dispatch_log.py`, not a registered
MCP tool, so no agent following this protocol can actually invoke it (see
the `dispatch-subagent` skill's own Notes section for the same finding,
confirmed by `tests/unit/test_dispatch_log.py`, which asserts the absence
of any MCP-tool wrapper). Do not follow stale instructions elsewhere that
imply this call is available or required.

## Examples

### Dispatching code-monkey for a ticket

```
scope_directory: claude_agent_skills/, tests/
context:
  - ticket-001-add-feature.md
  - ticket-001-add-feature-plan.md
  - claude_agent_skills/artifact_tools.py (content)
  - instructions/coding-standards.md
  - instructions/testing.md
  - instructions/git-workflow.md
prompt: |
  You are the code-monkey. Implement ticket 001.
  You may only modify files under claude_agent_skills/ and tests/.
  [ticket content]
  [plan content]
  [source file content]
```

### Dispatching architect for sprint planning

```
scope_directory: clasi/sprints/001-my-sprint/
context:
  - docs/architecture/architecture-021.md (previous)
  - clasi/sprints/001-my-sprint/sprint.md
  - instructions/architectural-quality.md
prompt: |
  You are the architect. Update the architecture for sprint 001.
  You may only modify files under clasi/sprints/001-my-sprint/.
  [previous architecture content]
  [sprint goals]
```
