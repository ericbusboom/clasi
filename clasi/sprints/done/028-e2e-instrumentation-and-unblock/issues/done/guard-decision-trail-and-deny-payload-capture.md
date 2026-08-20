---
status: done
type: feature
tags:
- reliability-campaign
- phase-0
- hooks
- observability
sprint: 028
tickets:
- 028-005
---

# Hooks: decision-trail tokens in hooks.log and full-payload capture on every denial

## Description

hooks.log answers what was decided but not why, and the failure paths log
nothing at all (guard crashes bypass `_exit_hook`; the plan handlers have
written zero log lines in 3,021 events). From the reliability review
(03-hooks-guards.md recommendation 3, fail-open inventory #15;
05-e2e-test-infra.md instrumentation plan item 5).

1. Extend `_exit_hook` with a per-invocation `decisions: list[str]` that
   handlers append to (examples: `tier=2(db)`, `match=clasi/issues/`,
   `gate=ticket-state:skipped(db-error)`, `missing=[file_path]`), emitted
   as trailing tokens on the existing hooks.log line.
2. When `exit_code == 2` (and on guard-internal exceptions), dump the full
   hook payload to `.clasi/log/denied/<ts>-<hook>.json` — the directory
   already auto-gitignores via `_ensure_log_gitignore`. This builds the
   real-payload corpus the Phase 1 replay tests consume.
3. Route both plan handlers (`handle_plan_to_issue`, `handle_plan_guard`)
   through `_exit_hook` so they log at all.

## Acceptance criteria

- Every guard decision line carries the decision tokens that produced it.
- Every denial leaves a replayable payload file.
- Plan-to-issue events appear in hooks.log.
- Tests assert token emission for at least one allow and one deny path.
