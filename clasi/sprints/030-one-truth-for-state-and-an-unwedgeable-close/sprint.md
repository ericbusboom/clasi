---
id: '030'
title: One truth for state and an unwedgeable close
status: roadmap
branch: sprint/030-one-truth-for-state-and-an-unwedgeable-close
worktree: false
use-cases: []
issues:
- single-sprint-stage-vocabulary.md
- resumable-transactional-close-sprint.md
- fix-unsatisfiable-state-machine-predicates.md
- ticket-status-single-writer.md
- uniform-mcp-tool-envelope.md
- sprint-lifecycle-three-way-integration-test.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 030: One truth for state and an unwedgeable close

## Goals

Sprint stage has exactly one vocabulary and one writer; a failed
`close_sprint` is resumable and can never leave the execution lock
wedged or mint duplicate version tags; the state-machine predicates
describe the process that actually runs. This is Phase 2 — the final
phase — of the three-sprint reliability arc from the comprehensive
review (`docs/reviews/2026-08-reliability/00-review.md`, Part 5).
Sprint 028 built the instrumented E2E baseline and started capturing a
real deny-payload and call-trace corpus; sprint 029 spent that
instrument on the fail-closed and root-discovery root causes (RC-2,
RC-3). This sprint spends it on RC-1 — "four disagreeing vocabularies
for one sprint stage" — before any later phase touches process docs or
deletes code.

## Problem

Per the review's RC-1 and C3-C8 findings (`01-state-layer.md` findings
1-4, 6-10, 14, 20; `02-mcp-tools.md` F1, F2, F5, F6, F9, F15): a
sprint's stage lives in four disagreeing vocabularies — DB phase,
frontmatter `status:`, computed machine state, and directory location —
plus a fifth, `list_sprints`-advertised vocabulary that nothing writes.
The drift detector compares two of these vocabularies that are disjoint
by construction, so it flags every healthy sprint. `close_sprint`
wraps its DB update in `except: pass`, so a failed close can archive
the sprint directory while the DB keeps the old phase and the
execution lock held — the next sprint cannot start. Retry re-runs the
version bump (double tags) because `close_sprint` writes recovery
state on failure but never reads it back; `git push --tags` pushes
every local tag instead of the sprint's own. The state-machine
predicates reference phase strings the toolchain cannot produce
(`"ticketed"` when the DB only ever holds `"ticketing"`) and a
`sprint_review` gate that `record_gate` rejects, so the `closed`
invariant can never hold and `enter-sprint` is permanently blocked.
Ticket `done`-move and `status: done` are two uncoordinated operations,
so frontmatter-based and directory-based ticket counts can diverge.
The 34 artifact MCP tools have a three-way inconsistent error contract
(raise / `{"error": ...}` / a third close_sprint-specific shape), and
the `"NONE"` sentinel mitigation is installed by monkey-patching
private MCP-library internals — a library upgrade silently disables
it. None of today's state-machine tests exercise real writers, so this
whole drift class has shipped repeatedly as a "weird runtime bug"
instead of a red test.

## Solution

Six phase-2 issues, ordered so the vocabulary fix lands first (nothing
else can be verified against a stable ground truth until stage has one
writer), the close and predicate fixes follow, and the integration
test lands last as the phase's acceptance test:

1. `single-sprint-stage-vocabulary.md` — the DB phase list becomes the
   single stage vocabulary; frontmatter `status:` is derived from it
   at write time by one `set_sprint_stage()`; the other vocabulary
   strings are deleted from writers, templates, tool docstrings, and
   `.claude/rules/clasi-artifacts.md`; `detect_inconsistencies` and
   `list_sprints(status=...)` compare and filter on values that
   actually exist.
2. `resumable-transactional-close-sprint.md` — `StateDB.force_close`
   sets phase to done and releases the execution lock in one
   transactional step, surfaced — never swallowed — on failure; retry
   reads recovery state and skips completed steps (no re-run tests, no
   repeat version bump); self-repair becomes read-only before the test
   gate, mutations only after; git failures in the bump/tag/merge
   sequence fail loudly, and only the sprint's own tag is pushed.
3. `fix-unsatisfiable-state-machine-predicates.md` — every phase
   string a predicate references exists in the enforced phase list;
   `sprint_review` is either made recordable or removed along with the
   writer-less skip flags; gate predicates check
   `result in {"passed", "skipped"}`; `evaluate_state` defines
   most-advanced-match-wins and the exception-message parser is
   deleted.
4. `ticket-status-single-writer.md` — `update_ticket_status(path,
   "done")` performs the frontmatter write and the done-directory move
   in one call; a shared ticket-listing helper excludes `*-plan.md`
   companion files everywhere ticket counts are computed.
5. `uniform-mcp-tool-envelope.md` — a `@clasi_tool` decorator wrapping
   `server.tool()` strips the `"NONE"` sentinel in owned code, anchors
   relative paths to `project.root`, and converts domain exceptions
   into one `{"ok": false, "error": {...}}` shape across all 34
   artifact tools; the decorator also absorbs the `mcp-calls.jsonl`
   call-trace instrumentation sprint 028 added ad hoc, so tracing and
   envelope normalization live in the same wrapper instead of two.
6. `sprint-lifecycle-three-way-integration-test.md` — one integration
   test drives a sprint through the real writers (create → detail →
   gates → tickets → in-progress → done → close) against a real
   temporary project, asserting DB phase, frontmatter status, and
   computed machine state agree at every step, gate predicates and
   `advance_phase` agree on gate semantics, and `detect_inconsistencies`
   reports zero drift on the healthy path. This is deliberately last:
   it only passes once issues 1-5 have landed, and it is the acceptance
   test for the whole phase, not just its own ticket.

## Success Criteria

- The E2E close-failure scenario passes: kill tests mid-close,
  re-run, and assert a single version tag, the execution lock released
  or held correctly per the failure point, and resumption skips
  completed steps.
- The instrumented run report (from sprint 028) shows zero self-repairs
  on the happy-path close.
- The new writer-to-reader integration test
  (`sprint-lifecycle-three-way-integration-test.md`) passes, and a
  deliberately reintroduced vocabulary regression fails it.
- `detect_inconsistencies` reports zero drift entries for a healthy
  active sprint; `list_sprints(status=...)` filters on values that
  actually exist.
- The status block's `enter-sprint` transition is no longer blocked by
  a predicate that cannot be true.

## Scope

### In Scope

The six phase-2 issues listed under Solution above — single stage
vocabulary and its one writer, transactional/resumable `close_sprint`,
the state-machine predicate fixes, single-writer ticket status, the
uniform MCP tool envelope (absorbing sprint 028's call-trace
decorator), and the writer-to-reader integration test that closes out
the phase.

### Out of Scope

- Phase 3 of the arc (gate-order fix, tier-0 relaxation, one-canonical-
  text-per-topic documentation consolidation, sprint-review/close
  ownership) — planned separately, next in the review's Part 5
  sequencing.
- Phase 4 (deleting the worktree parallel-path lifecycle, dead
  versioning surface, `dispatch_log`; installer fixes;
  `artifact_tools.py` decomposition; the mtime frontmatter cache) —
  later phases.
- Any change to guard fail-closed behavior or root discovery — that
  was sprint 029's scope and is not reopened here.
- The OpenRouter E2E auth path — stays parked in
  `clasi/issues/later/claude-cli-rejects-models-through-openrouter-redirect-in-e2e.md`
  per the review's Part 6 decision.

## Test Strategy

(To be detailed when this sprint is promoted to Detail Mode. At a
minimum: unit tests for `set_sprint_stage()`, `StateDB.force_close`
transactionality and recovery-state resumption, the fixed state-machine
predicates, and single-writer ticket status; the writer-to-reader
integration test itself is the phase's acceptance test and runs in the
default suite tier. Primary end-to-end validation is the instrumented
E2E close-failure scenario from sprint 028's harness: kill tests
mid-close, re-run, assert single tag / released lock / resumed steps.)

## Architecture

(Architecture for this sprint's change, sized to the change — a
one-paragraph note for a trivial sprint, a fuller write-up with
component/data-model detail for a substantial one. May read "N/A —
trivial" when the change has no architectural impact.)

### Architecture Overview

(High-level structure and component relationships, if applicable.)

### Design Rationale

(Significant decisions with alternatives considered and reasoning, if
applicable.)

### Migration Concerns

(Data migration, backward compatibility, deployment sequencing — or
"None" if not applicable.)

## Use Cases

(Use cases sized to the change — may read "N/A — trivial" for small
sprints that don't warrant new or updated use cases.)

### SUC-001: (Title)
Parent: UC-XXX

- **Actor**: (Who)
- **Preconditions**: (What must be true before)
- **Main Flow**:
  1. (Step)
- **Postconditions**: (What is true after)
- **Acceptance Criteria**:
  - [ ] (Criterion)

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|

Tickets execute serially in the order listed.
