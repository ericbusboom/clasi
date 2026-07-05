---
id: '001'
title: Add Sprint.worktree opt-in flag
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: plan-re-enable-git-worktree-based-parallel-ticket-execution-in-clasi.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add Sprint.worktree opt-in flag

## Description

Issue A (worktree parallel execution) opt-in mechanism (Chunk 2, opt-in
half only — the execution.md consumption of this flag is ticket 009).
Add a `Sprint.worktree` boolean property to `src/clasi/sprint.py`,
matching the existing accessor pattern used by `.status` (line ~74-77):

```python
@property
def worktree(self) -> bool:
    """From sprint.md frontmatter 'worktree' field. Opt-in for parallel
    execution; default False (serial) for backward compatibility."""
    return bool(self.sprint_doc.frontmatter.get("worktree", False))
```

Place it directly after the existing `.status` property. Add
`worktree: false` to the `sprint.md` template frontmatter
(`src/clasi/templates/sprint.md`) so newly created sprints default to
serial execution and existing sprints (missing the key entirely) also
default to `False` via the `.get(..., False)` fallback — no migration
needed for sprints already in flight.

Do **not** add this flag to the state machine or predicates
(`sprint.yaml` / `predicates/sprint.py`) — it is an execution-strategy
toggle, not a lifecycle gate, per the issue's explicit confirmed
decision. Do not add a new MCP setter tool; the flag is set by editing
`sprint.md` at plan time (sprint-planner writes it, or a stakeholder/
team-lead uses `write_artifact_frontmatter`).

This ticket lands FIRST among the tickets touching `src/clasi/sprint.py`
(see architecture-update.md "Shared-File Sequencing") because it is
purely additive and unblocks ticket 009 (execution.md mode selection)
earliest, before ticket 003's larger `detail_promote`/`archive`/`to_dict`
rewrite lands.

## Acceptance Criteria

- [x] `Sprint.worktree` property exists, returns `False` when the
      frontmatter key is absent, `True`/`False` when explicitly set.
- [x] `templates/sprint.md` frontmatter includes `worktree: false`.
- [x] `get_sprint_status` (or equivalent status-building code path) that
      already reads sprint frontmatter surfaces the `worktree` flag in
      its output so the controller can decide execution mode with one
      MCP call it already makes (verify: check `src/clasi/status/` or
      wherever `get_sprint_status`/`get_status` is implemented — extend
      if the flag is not already passed through generically).
- [x] No state-machine or predicate file is modified by this ticket.
- [x] No new MCP tool is added by this ticket.

## Files to create or modify

- `src/clasi/sprint.py` — add `Sprint.worktree` property after `.status`.
- `src/clasi/templates/sprint.md` — add `worktree: false` to frontmatter.
- `src/clasi/status/` (or the module backing `get_sprint_status`) — surface
  the `worktree` flag if not already generically passed through from
  sprint frontmatter (inspect before assuming a change is needed).

## Testing

- **Existing tests to run**: `tests/unit/test_sprint.py`,
  `tests/system/test_artifact_tools.py` (sprint creation / status tests),
  full `uv run pytest`.
- **New tests to write**: `tests/unit/test_sprint.py` — `Sprint.worktree`
  default `False` on a fixture sprint without the key; `True` when
  frontmatter sets `worktree: true`; `False` when explicitly `false`.
  A status-tool test confirming `worktree` appears in `get_sprint_status`
  output for a sprint with the flag set.
- **Verification command**: `uv run pytest`
