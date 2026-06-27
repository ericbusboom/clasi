---
id: '005'
title: Update create-tickets, team-lead, and close-sprint docs with lifecycle instructions
status: in-progress
use-cases:
- SUC-003
depends-on:
- '004'
github-issue: ''
issue: ''
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update create-tickets, team-lead, and close-sprint docs with lifecycle instructions

## Description

Three more plugin documents need lifecycle instructions to complete the issue →
sprint → ticket → done chain: `create-tickets`, `team-lead`, and `close-sprint`.

- `create-tickets` already has the correct `issue:` back-ref documentation;
  this ticket verifies it and adds a reinforcement that every ticket must carry
  `issue:` when implementing an issue.
- `team-lead/agent.md` needs a new "Issue Lifecycle Responsibility" section with
  four checkpoints covering the full lifecycle.
- `close-sprint/SKILL.md` needs documentation of the auto-sweep and the
  non-blocking `unresolved_issues` report.

Note: all edits target `clasi/plugin/` only. Do not edit `.claude/` copies.

## Acceptance Criteria

- [ ] `clasi/plugin/skills/create-tickets/SKILL.md` reinforces that every ticket implementing an issue must carry `issue:` in its frontmatter; programmer verifies back-refs before closing a ticket.
- [ ] `clasi/plugin/agents/team-lead/agent.md` contains a new "Issue Lifecycle Responsibility" section with these four checkpoints: (1) link at roadmap via `link_sprint_issues`; (2) confirm tickets carry `issue:` back-refs after sprint planning; (3) after close, confirm resolved issues landed in `<sprint>/issues/done/`; (4) address any `unresolved_issues` from the close result.
- [ ] `clasi/plugin/skills/close-sprint/SKILL.md` documents: (a) that `_sweep_done_issues` is called automatically at close and moves resolved sprint issues to `<sprint>/issues/done/`; (b) that `unresolved_issues` in the result is non-blocking; (c) instruction to read `unresolved_issues` from the close result and surface them to the team-lead for mop-up.
- [ ] No references to manual frontmatter writes for issue lifecycle remain in any of these three files.

## Implementation Plan

### Approach

**B3 — `clasi/plugin/skills/create-tickets/SKILL.md`**

Read the file. The "Issue lifecycle" and "Multi-ticket issue propagation"
paragraphs already describe `create_ticket(issue=)` and `add_issue_ref`. Add a
reinforcement sentence to the "Multi-ticket issue propagation" block:

```
Before returning from ticket creation, verify that every ticket working
toward an issue has a non-empty `issue:` field.
```

**B4 — `clasi/plugin/agents/team-lead/agent.md`**

Read the file. After the "Pre-Flight Check" section (or after "Behavioral
Rules"), add a new section:

```markdown
## Issue Lifecycle Responsibility

The team-lead owns the full issue → done lifecycle. At each stage:

1. **Roadmap**: After `create_sprint`, call `link_sprint_issues(sprint_id,
   [filenames])` for every issue claimed by the sprint. Do not write `issues:`
   frontmatter manually.
2. **After planning**: Confirm that each ticket in the sprint carries an `issue:`
   back-reference for any issue it implements. If back-refs are missing, call
   `add_issue_ref(ticket_path, issue_filename)` to repair them.
3. **After close**: Confirm resolved issues landed in `<sprint>/issues/done/`.
   Read the close result — if `unresolved_issues` is present, surface the
   filenames to the stakeholder and create follow-up issues or defer them to
   the next sprint.
4. **Mop-up**: Do not leave any issue in an ambiguous state. Every issue must
   be either in `done/`, deferred to a future sprint, or explicitly abandoned
   with a note.
```

**B5 — `clasi/plugin/skills/close-sprint/SKILL.md`**

Read the file. The current SKILL.md delegates to a schema instructions file.
Determine where to add the auto-sweep documentation (the stub or the delegated
source). Add:

```markdown
## Issue Sweep at Close

When `close_sprint` runs, it automatically calls `_sweep_done_issues`, which
moves any resolved sprint issues from `<sprint>/issues/` to
`<sprint>/issues/done/`. No manual `move_issue_to_done` call is needed for
issues whose tickets are all done.

If any sprint issues remain unresolved at close, the close still succeeds.
The result JSON will contain an `unresolved_issues` list with the filenames.
Read this list and surface it to the team-lead for mop-up — these issues were
not resolved in the sprint and need follow-up.
```

### Files to Modify

- `clasi/plugin/skills/create-tickets/SKILL.md` — reinforce `issue:` back-ref
  verification.
- `clasi/plugin/agents/team-lead/agent.md` — add "Issue Lifecycle
  Responsibility" section.
- `clasi/plugin/skills/close-sprint/SKILL.md` — add "Issue Sweep at Close"
  section (or update the delegated instruction source).

### Testing Plan

- No automated tests for doc changes. Verify by reading the updated files.
- Run `pytest -q` to confirm no regressions.

### Documentation Updates

This ticket IS the documentation update. No code changes.
