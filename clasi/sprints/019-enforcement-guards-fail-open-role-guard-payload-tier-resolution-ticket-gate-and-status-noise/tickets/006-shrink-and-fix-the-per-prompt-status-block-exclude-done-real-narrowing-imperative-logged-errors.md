---
id: '006'
title: Shrink and fix the per-prompt status block (exclude done/, real narrowing,
  imperative, logged errors)
status: open
use-cases: [SUC-007]
depends-on: ['002', '004']
github-issue: ''
issue: enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Shrink and fix the per-prompt status block (exclude done/, real narrowing, imperative, logged errors)

## Description

`clasi hook status-inject` emits 34,467 bytes on every prompt (verified:
`clasi hook status-inject | wc -c`) — all 18 sprints and 84 tickets
including `done/` archives, 144 lines about reopening already-closed
tickets, and no imperative of any kind. At 33.5KB it overflows the
inline threshold and spills to a file, so it never actually reaches
context. This ticket fixes the status-block pipeline
(`hook_handlers._build_status_block`/`handle_status_inject`,
`status/reporter.py`, `status/narrowing.py`) to produce a small, accurate,
actionable block. It does NOT include bulk-correcting the 18 existing
`status: done` archived sprint files — that is ticket 007, split out
because it is mechanically independent (a one-time frontmatter script vs.
this ticket's code changes) and can be verified separately.

Four independent fixes, all required for this ticket:

1. **Exclude `done/` from the assembled status dict.**
   `StatusReporter._build_sprints_block`/`_build_tickets_block` currently
   iterate `sprint.list_tickets()` and `project.list_sprints()`, both of
   which explicitly include `sprints/done/` and `tickets/done/` (verified
   in `sprint.py`/`project.py` — this is intentional for on-demand MCP
   queries like `list_sprints`/`get_sprint_status`, which must keep
   returning full history). Add an option/parameter so the status-block
   path excludes `done/` entries while the on-demand MCP query path
   continues to include them — do not change `list_sprints`/
   `list_tickets` behavior globally, only the status-block assembly.
2. **Thread real `sprint_id`/`ticket_id` into `narrow_status`.**
   `_build_status_block` in `hook_handlers.py` currently calls
   `narrow_status(full, agent=agent)` with no `sprint_id`/`ticket_id` —
   dead code for narrowing purposes, since `narrow_status` needs those to
   scope anything below the team-lead's full-firehose default. Resolve
   the active `sprint_id` (via `_get_sprint_context()`, already used
   elsewhere in this file) and, for `handle_subagent_start`'s
   programmer-role case, the active `ticket_id` (via
   `_get_active_tickets()`), and pass them through.
3. **Add the missing imperative.** When a sprint is executing
   (`_get_sprint_context()` returns a sprint_id, meaning a lock is held)
   and zero tickets are in-progress, the status block's `notes` section
   must state plainly that source edits are gated (per ticket 004's new
   gate) and name the two exits: start/resume a ticket via the
   execute-ticket flow, or set `.clasi/oop` (via the shared
   `_oop_active()` helper from ticket 002 — reference it, don't
   reimplement the check).
4. **Replace the silent exception swallow.** `_build_status_block`
   currently has `except Exception: return ""` — a broken status hook is
   indistinguishable from a healthy one. Replace with a logged warning
   (use the project's existing logging pattern — check
   `_log_hook_event` or Python's `logging` module, whichever this
   codebase already uses elsewhere in `hook_handlers.py`) that still
   returns `""` so the hook itself never fails, but the failure is now
   observable.

Depends on ticket 002 (the imperative text must reference the real
`_oop_active()` helper, not a separate ad hoc check) and ticket 004 (the
imperative describes ticket 004's gate behavior — this ticket cannot
correctly describe a gate that doesn't exist yet).

Root cause reference: `clasi/issues/enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md`
defect 7 (status block noise), scoped to exclude the historical
bulk-correction (ticket 007).

## Acceptance Criteria

- [ ] `clasi hook status-inject | wc -c` is well under 5KB on this
      project's real, current (multi-sprint) state — target explicitly
      verified, not just "smaller than before."
- [ ] `done/` sprints and their tickets are excluded from the
      status-block assembly path specifically; `list_sprints()` and
      `Sprint.list_tickets()` continue to return full history including
      `done/` when called directly (e.g. via MCP tools) — verify this
      with a test that calls both paths against the same fixture data
      and asserts they differ only in the done/ exclusion.
- [ ] `_build_status_block` threads a real `sprint_id` (from
      `_get_sprint_context()`) into `narrow_status` for all callers; for
      `handle_subagent_start`'s programmer-role invocation, also threads
      a real `ticket_id` when one can be resolved.
- [ ] Test: with a real (unmocked) multi-sprint fixture project including
      at least one `done/` sprint, `narrow_status` output for a
      `sprint-planner`/`programmer` agent role is demonstrably narrower
      than the team-lead's full view (not just "narrow_status was
      called" — assert the actual returned dict is smaller/scoped).
- [ ] When a sprint is executing with zero in-progress tickets, the
      status block's notes contain an explicit sentence naming both
      exits (start/resume a ticket; `.clasi/oop`).
- [ ] `except Exception: return ""` in `_build_status_block` is replaced
      with a logged warning (verify the log actually fires under a
      simulated failure — e.g. inject a broken reader/mock that raises)
      followed by the same `return ""` fallback behavior (the hook still
      never fails outright).
- [ ] **Size assertion test against the REAL, unmocked status block** —
      not `_build_status_block` mocked away, which is how every existing
      test in `tests/unit/test_status/test_hook_injection.py` missed the
      original 34KB. Build (or reuse) a realistic multi-sprint fixture
      project and assert the actual byte count of
      `handle_status_inject`'s output.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_status/ -v tests/unit/test_hook_handlers.py -v`
- **New tests to write**: done/-exclusion test (status-block path vs.
  on-demand MCP path, same fixture); real `sprint_id`/`ticket_id`
  narrowing test; imperative-sentence-present test; logged-warning test
  for the exception path; real unmocked size assertion.
- **Verification command**: `uv run pytest tests/unit/test_status/ -v`;
  manually: `clasi hook status-inject | wc -c` (expect well under 5000).
