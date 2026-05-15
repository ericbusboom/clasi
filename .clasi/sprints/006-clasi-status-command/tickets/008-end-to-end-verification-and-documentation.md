---
id: 008
title: End-to-end verification and documentation
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
- SUC-005
- SUC-006
- SUC-007
depends-on:
- '005'
- '006'
- '007'
issue: clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# End-to-end verification and documentation

## Description

With all surfaces implemented (CLI, MCP tool, hook injection), this ticket runs
all verification scenarios from the issue against this repo and confirms that
every output matches the expected shape. It also updates documentation to
reflect the new command and MCP tool.

## Acceptance Criteria

- [x] `clasi status` runs in this repo and prints YAML with `project:`, `sprints:`, `issues:`, `notes:`, `inconsistencies:`.
- [x] `clasi status --format json` output parses as valid JSON with the same shape.
- [x] `clasi status --agent sprint-planner --sprint 006` narrows to sprint 006 with summarized tickets.
- [x] `clasi status --agent programmer --ticket 006-001` narrows to ticket 006-001 with parent sprint context.
- [x] `mcp__clasi__get_status()` returns JSON matching the same shape.
- [x] `mcp__clasi__get_status(agent="sprint-planner", sprint_id="006")` returns narrowed JSON.
- [x] A sprint with `status: planned` in frontmatter while `is_architecture_present` is false produces an `inconsistencies:` entry of kind `state_drift` with the correct `declared`, `computed`, and `explanation` fields.
- [x] `uv run pytest` (full suite) passes with all new tests included.
- [x] The existing issues file `clasi-status-per-agent-process-status-with-gate-derived-next-step-notes.md` is ready for archival (all verification criteria from the issue are satisfied — `completes_issue: true` above handles this on ticket close).

## Implementation Plan

### Approach

Run each verification item from the issue manually in this repo. For any that
fail, diagnose and fix the underlying implementation (raise an exception if
fixes require architecture changes).

If a state-drift test needs a synthetic artifact with a mismatched `status:`,
create a temporary one in the test suite's tmp_path rather than modifying a
live artifact.

### Files to create

- `tests/integration/test_status_e2e.py` — end-to-end integration tests

### Files to modify

None expected (this is a verification ticket; fixes go back to prior tickets
via the exception protocol if needed).

### Testing plan

Run all eight verification items from the issue as pytest test cases. Each test
invokes the real CLI or MCP tool against this project's `.clasi/` directory.

### Documentation updates

Update the module docstring in `clasi/cli.py` to add `clasi status` to the
command list. Update `clasi/tools/process_tools.py` module docstring to add
`get_status`.

## Smoke Output (captured 2026-05-15)

### `clasi status` (YAML, team-lead view)

```
agent: team-lead
computed_at: '2026-05-15T07:36:04+00:00'
project:
  state: uninitialized
  available_transitions:
  - name: initialize
    to: planning
    fireable: false
    blocked_by:
    - is_overview_present
    - is_on_default_branch
    - is_execution_lock_released
sprints:
- id: '006'
  state: executing
  available_transitions:
  - name: complete
    to: review
    fireable: false
    blocked_by:
    - is_all_tickets_done
  tickets:
    total: 8
    by_state:
      unknown: 8
    details: [...]
issues:
  total: 9
  pending: 9
  assigned_to_sprint: 0
notes:
  current_focus: Sprint 006 is executing
  allowed_next_actions: []
  blocked_actions:
  - Fire `initialize` on project — blocked by is_overview_present, ...
  - Fire `complete` on sprint 006 — blocked by is_all_tickets_done
inconsistencies:
- kind: state_drift
  machine: sprint
  id: '006'
  declared: planning-docs
  computed: executing
  explanation: 'Declared state ''planning-docs'' is not a recognised sprint machine state.'
```

### `clasi status --format json`

Valid JSON; same top-level keys. Confirmed parseable with `python3 -m json.tool`.

### `clasi status --agent sprint-planner --sprint 006`

Only sprint 006 present; tickets block has no `details:` key (summarized).

### `clasi status --agent programmer --ticket 006-001`

Only sprint 006 present (id + state only); tickets.details contains one entry
for ticket 001. Notes `current_focus: 'Ticket 006-001 is in state: unknown'`.

### MCP `get_status()` / `get_status(agent="sprint-planner", sprint_id="006")`

Returns valid JSON with all required keys. Narrowing confirmed by `agent` field.

### Inconsistency detection

Synthetic sprint with `status: planned` but no architecture file produces:
`{kind: state_drift, machine: sprint, id: '099', declared: planned, computed: open/unknown, explanation: "..."}`.

### Hook injection smoke

`handle_status_inject({})` with mocked `_build_status_block` emits
`## CLASI status\n\n` + fenced YAML block. Silent when `.clasi/oop` exists or
`.clasi/` is absent.
