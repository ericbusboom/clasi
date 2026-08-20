---
status: pending
---

# status-inject residual latency: git subprocess spawns and process startup keep it above 200 ms

## Description

Follow-up from sprint 026 (stakeholder-accepted close, 2026-08-20).
Sprint 026 cut status-inject from ~1,050-1,150 ms to a median 238.4 ms
per prompt (best single run 207.8 ms, n=20) — but the sprint's <200 ms
success criterion was not fully met. Ticket 007's Measurement Notes
(clasi/sprints/done/026-hook-performance-and-guard-reliability/tickets/done/007-*.md
after archival) attribute the residual ~40 ms to costs outside the
sweep/filter scope that sprint addressed:

- Real git subprocess spawn overhead: ticket 003's memoization removed
  redundant calls (28 → ~3 per invocation), but each surviving spawn
  still costs ~20-30 ms of OS process creation on this machine.
- The `.clasi/oop`/StateDB bypass check that runs before build_status.
- One-time Python process/import startup for the hook process itself.

## Proposed fix (candidate directions, pick at planning time)

- Collapse the surviving git calls further: one `git for-each-ref`/
  plumbing batch call instead of separate branch/default/merged queries,
  or read `.git/HEAD` and refs directly for the branch-name checks.
- Trim hook-process startup: audit remaining eager imports on the
  `clasi hook` path (click CLI import chain); consider a minimal
  entrypoint that dispatches hook events without importing the full CLI.
- Measure before choosing; per sprint 026's discipline, acceptance
  criteria must carry before/after numbers and call-count assertions.

## Verification

- `time clasi hook status-inject < captured-payload.json` median under
  200 ms on this repo (n≥12). Ticket 003/007's captured-payload method
  is the measurement convention.
- No behavior change to status content, `clasi status` CLI, or the
  hook's exit semantics.

## Related

- Sprint 026 tickets 003 and 007 (the two prior latency passes; their
  Measurement Notes carry the profiling data this issue starts from).
