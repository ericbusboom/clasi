---
id: "005"
title: "Update sprint-planner agent prompt with exception protocol section"
status: todo
use-cases:
  - SUC-002
depends-on:
  - "018-003"
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update sprint-planner agent prompt with exception protocol section

## Description

Add an "Exception Protocol" section to
`clasi/plugin/agents/sprint-planner/agent.md`. The sprint-planner agent can
encounter structural walls during architecture authoring or ticket decomposition.
Without explicit guidance, it either papers over the conflict or emits
unstructured text that the team-lead cannot route systematically.

The section mirrors the programmer version (ticket 004) with two adaptations:
- `thrown_by` is `"sprint-planner"`.
- During planning phases (before any ticket exists), the sprint-planner cannot
  write to a ticket's frontmatter. In that case, it surfaces the exception in
  its return text using the same schema fields in a clearly marked block.

## Acceptance Criteria

- [ ] `clasi/plugin/agents/sprint-planner/agent.md` contains a clearly
  delimited "Exception Protocol" section.
- [ ] Section states the threshold (same as programmer: structural wall, not
  hard work).
- [ ] Section instructs the sprint-planner to call `throw_ticket_exception`
  with `thrown_by="sprint-planner"` when a ticket exists to carry the payload.
- [ ] Section explains the pre-ticket case: surface exception payload in
  return text using the same five-field schema, clearly marked.
- [ ] Section defines `surface` classification (same rules as programmer).
- [ ] Section instructs clean exit — do not leave partial artifacts.
- [ ] No existing content in `agent.md` is removed or materially altered.
- [ ] No tests to write (documentation change only).

## Implementation Plan

**File to modify**: `clasi/plugin/agents/sprint-planner/agent.md`

**Approach**: Append a new top-level section. Read current file first.
The section content:

```markdown
## Exception Protocol

**Threshold**: Throw when you cannot resolve a conflict without overriding
an upstream architecture decision or a use-case boundary set by a prior
sprint. Hard design decisions are within your authority; upstream overrides
are not.

**When a ticket exists** (during ticketing phase or after): Call
`throw_ticket_exception(path, thrown_by="sprint-planner", attempted=...,
conflict=..., surface=...)`. Then stop. Leave no partial artifacts.

**When no ticket exists yet** (during planning-docs or architecture-review
phase): Surface the exception in your return text in this format:

```
EXCEPTION:
  thrown_by: sprint-planner
  attempted: |
    <what was tried>
  conflict: <specific decision or section being blocked>
  surface: <"user-visible" | "internal">
```

Do not continue planning past an exception. The team-lead will route.

**Surface classification**:
- `"user-visible"`: conflict touches behavior described in usecases.md.
- `"internal"`: purely structural (module boundary, data model, etc.).
  When in doubt, prefer `"internal"`.
```

**Verification**: Read the updated file; confirm section is present and
existing content is intact. Check ticket 004 was completed first (same
`throw_ticket_exception` reference).
