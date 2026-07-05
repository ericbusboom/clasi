---
id: 018
title: Worktree parallel execution and right-sized sprint planning
status: done
branch: sprint/018-worktree-parallel-execution-and-right-sized-sprint-planning
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
- SUC-005
- SUC-006
issues:
- plan-re-enable-git-worktree-based-parallel-ticket-execution-in-clasi.md
- right-size-sprint-planning-one-sprint-md-no-per-sprint-architecture-docs-on-demand-architecture-consolidation.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 018: Worktree parallel execution and right-sized sprint planning

## Goals

Two independent-but-file-adjacent capabilities:

1. **Re-enable git-worktree-based parallel ticket execution** (Issue A):
   implement the 8 stubbed functions in `src/clasi/worktree.py` plus a new
   `reconcile_worktrees` reaper, gate parallel execution behind a per-sprint
   `worktree: true` flag, rewrite `execution.md` to select parallel-with-
   serial-fallback, and make aggressive continuous cleanup (the reaper) the
   core discipline that prevents the worktree-directory accumulation that
   killed this feature the first time.
2. **Right-size sprint planning** (Issue B): collapse `usecases.md` +
   `architecture-update.md` into right-sized sections of a single
   `sprint.md`; stop accumulating per-sprint architecture documents in
   `docs/architecture/`; make the architecture-review gate optional/
   skippable for small sprints; produce a consolidated architecture on
   demand at `docs/design/architecture.md`.

## Problem

**Issue A**: Worktrees were built (sprint 023), disabled as "unreliable"
because unused worktree directories accumulated until the pile itself
became the problem, then re-designed but never implemented (sprint 022 —
spec at `docs/design/worktree-process.md`, stub API at
`src/clasi/worktree.py`). The stakeholder wants the capability back, this
time with cleanup treated as a first-class, continuous concern rather than
a close-time afterthought.

**Issue B**: Every sprint — regardless of size — is currently forced
through a heavy three-document planning model (`sprint.md` + `usecases.md`
+ `architecture-update.md`) plus a mandatory architecture-review gate, and
each sprint's architecture-update is copied into a growing
`docs/architecture/` pile with no single coordinated picture. The e2e
review (`clasi/issues/e2e-001-review.md`) documented multi-thousand-word
plans with Mermaid diagrams for 40-line modules — massive overkill for
small changes, and no consolidated architecture view for large ones.

## Solution

**Issue A**: Implement the worktree lifecycle module to its existing
docstring contract (audit read/write, `check_independence`,
`create_worktree`/`create_ticket_branch`/`validate_worktree`/
`merge_ticket_branch`/`cleanup_worktree`), add a new `reconcile_worktrees`
reaper that classifies every ticket worktree as merged-not-cleaned /
clean-but-abandoned / ambiguous and auto-cleans the first two classes,
wire the reaper into `execution.md` at three trigger points (session
start, per-creation gate, close-time safety net via
`_prune_sprint_worktrees`), and add the opt-in `Sprint.worktree` flag.
Concurrency remains plan-ahead-only: the global execution lock stays a
singleton; only intra-sprint, intra-group ticket implementation runs
concurrently. All controller git operations (create/validate/merge/
cleanup) remain sequential on the controller.

**Issue B**: Fold the `usecases.md` and `architecture-update.md` template
bodies into `sprint.md` as `## Architecture` and `## Use Cases` sections;
`detail_sprint`/`detail_promote()` scaffolds only `tickets/` +
`tickets/done/`; drop the `is_architecture_present`/`is_usecases_present`
state-machine invariants (keep `is_sprint_doc_present`); keep the
architecture-review gate mechanism but let the planner record it
`skipped` for small sprints; repoint `consolidate-architecture` to read
sprint docs (new sections + legacy files) + code and write one
`docs/design/architecture.md` on demand; stop copying into
`docs/architecture/` at sprint close and delete the existing
`docs/architecture/` directory. Historical sprints 001-017 keep their
existing files unchanged; read-only `Sprint.usecases`/`Sprint.architecture`
accessors are preserved so they still render.

## Success Criteria

- `uv run pytest` passes in full at the end of the sprint.
- A `worktree: true` sprint with two file-disjoint tickets creates two
  worktree directories that run concurrently and are torn down
  immediately on merge (not deferred to close); zero worktree dirs remain
  mid-sprint after the last merge.
- Starting new worktree work while an unresolved stale worktree exists is
  blocked until it is resolved or escalated.
- A `worktree: false` (or flag-absent) sprint runs the existing serial
  path unchanged.
- `create_sprint` + `detail_sprint` on a new sprint produce only
  `sprint.md` (with Architecture/Use Cases sections) + `tickets/` — no
  `usecases.md`/`architecture-update.md`.
- A small sprint reaches `ticketed`/`executing` with a recorded
  `architecture_review: skipped` gate; a substantial sprint can still
  record a full `passed`/`failed` review.
- `docs/architecture/` is deleted from this repo; closing a sprint no
  longer writes into it; `consolidate-architecture` produces
  `docs/design/architecture.md` on demand from sprint docs + code.
- Sprints 001-017 still validate/render (`get_status`/`list_sprints`
  unaffected) with their original files untouched.

## Scope

### In Scope

- `src/clasi/worktree.py`: implement all 8 stub functions + new
  `reconcile_worktrees`.
- `tests/clasi/test_worktree_stubs.py` → replaced by
  `tests/clasi/test_worktree.py` (behavioral tests).
- `src/clasi/sprint.py`: `Sprint.worktree` property; `detail_promote()`
  stops writing `usecases.md`/`architecture-update.md`; `archive()` stops
  copying to `docs/architecture/`; `to_dict()` drops the two files.
- `src/clasi/templates/sprint.md` (+ `worktree: false` default) and
  `templates.py` (remove `SPRINT_USECASES_TEMPLATE`,
  `SPRINT_ARCHITECTURE_UPDATE_TEMPLATE`, `SPRINT_ARCHITECTURE_TEMPLATE`
  loaders + their template files).
- `src/clasi/schemas/se-process/instructions/execution.md`: flag-gated
  parallel path with serial fallback; `execute-sprint/SKILL.md`
  description update.
- `src/clasi/tools/artifact_tools.py`: `_prune_sprint_worktrees` extended
  for `ticket/<sprint>-*` branches; `insert_sprint` stops writing the two
  files; `review_sprint_pre_close` drops the two files from
  `planning_docs_pre_close`.
- `src/clasi/schemas/state-machines/sprint.yaml` +
  `src/clasi/state_machine/predicates/sprint.py`: drop
  `is_architecture_present`/`is_usecases_present`.
- `src/clasi/schemas/se-process/schema.yaml`: `planning-docs` /
  `architecture-review` artifacts point at `sprint.md`.
- `src/clasi/dispatch_log.py`: `_auto_context_documents` drops the two
  files.
- `src/clasi/project.py`: remove `architecture` from
  `ARTIFACT_PATH_DEFAULTS`; `src/clasi/hook_handlers.py`: drop
  `architecture_dir` from role-guard allow-prefixes.
- Sprint-planner agent/skills: `agent.md`, `plan-sprint.md`,
  `dispatch-template.md.j2`, `contract.yaml`, `architecture-authoring`,
  `architecture-review`, `create-tickets` skills; repoint
  `consolidate-architecture` to sprint docs + code, output
  `docs/design/architecture.md`.
- Delete `docs/architecture/` (17 `architecture-update-*.md` files) from
  this repo.
- Optional MCP surface for `reconcile_worktrees` (Issue A Chunk 6).

### Out of Scope

- Relaxing the execution lock to allow concurrent sprint execution
  (explicitly preserved as a singleton).
- Computed (git-diff-based) independence checking — static extraction
  from plan files only, per the issue's confirmed decision (documented
  follow-on).
- Rewriting historical sprints 001-017 to the new single-doc model.
- Generating the first `docs/design/architecture.md` for this repo (can be
  run on demand after this sprint closes; not a blocking deliverable).
- A daemon/background process for the reaper — it runs only at the three
  defined trigger points, or on demand via the optional MCP tool.

## Test Strategy

Two independent test surfaces, sequenced per the shared-file dependency
order below.

- **Issue A**: real-temp-git-repo fixtures driving
  `create_worktree`/`create_ticket_branch`/`validate_worktree`
  (ff / --no-ff / conflict-abort-leaves-clean-tree) /`merge_ticket_branch`/
  `cleanup_worktree` (keep True/False); pure/fast unit tests for the audit
  pair and `check_independence` (overlap, disjoint, shared-test-module,
  missing-info→dependent, heading-spelling variants, `src/` normalization
  regression, `depends-on` group ordering); a dedicated high-value
  `reconcile_worktrees` test covering all three classifications plus
  idempotency; `tests/unit/test_sprint.py` additions for `Sprint.worktree`;
  `tests/system/test_artifact_tools.py` mock-sequence updates for the
  extended `_prune_sprint_worktrees`.
- **Issue B**: unit tests for `Sprint.detail_promote()`/`archive()`/
  `to_dict()` no longer touching the two files; state-machine tests for
  the dropped invariants; `review_sprint_pre_close` tests for the reduced
  `planning_docs_pre_close` list; a backward-compat test that a sprint
  fixture with the historical three-file layout still validates.
- **End-to-end** (both issues): full `uv run pytest` green at the end.
  Manually (or via a scripted fixture) drive one opt-in sprint with two
  disjoint tickets through execution to confirm concurrent dispatch +
  immediate teardown; drive one small sprint through
  create→detail→ticket→execute→close with a skipped architecture-review
  gate.

## Architecture Notes

See `architecture-update.md` for the full treatment. Key constraint:
Issue A and Issue B both edit `src/clasi/sprint.py` and
`src/clasi/tools/artifact_tools.py` — ticket sequencing enforces a defined
edit order on both files via `depends-on` so neither issue's changes are
clobbered by the other (see architecture-update.md "Shared-File
Sequencing").

## GitHub Issues

None linked. Source issues (now sprint-scoped, in-progress):
`issues/plan-re-enable-git-worktree-based-parallel-ticket-execution-in-clasi.md`
(Issue A — tickets 001, 006-011),
`issues/right-size-sprint-planning-one-sprint-md-no-per-sprint-architecture-docs-on-demand-architecture-consolidation.md`
(Issue B — tickets 002-005, 012-015).

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [x] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Issue | Depends On |
|---|-------|-------|------------|
| 001 | Add Sprint.worktree opt-in flag | A | — |
| 002 | Fold usecases and architecture templates into sprint.md | B | — |
| 003 | Rewrite Sprint.detail_promote, archive, and to_dict for single-doc model | B | 001, 002 |
| 004 | Drop separate-file state machine invariants and add skipped gate result | B | 003 |
| 005 | Update schema.yaml, review_sprint_pre_close, insert_sprint, and _renumber_sprint_dir for single-doc model | B | 003, 004 |
| 006 | Implement worktree.py lifecycle functions and behavioral tests | A | — |
| 007 | Implement reconcile_worktrees reaper and tests | A | 006 |
| 008 | Extend _prune_sprint_worktrees for orphaned ticket worktrees | A | 005, 007 |
| 009 | Rewrite execution.md for flag-gated parallel execution with serial fallback | A | 001, 006 |
| 010 | Wire reconcile_worktrees into controller trigger points | A | 007, 009 |
| 011 | Add optional MCP tool wrapping reconcile_worktrees | A | 007 |
| 012 | Update sprint-planner agent and planning skills for right-sized single-doc planning | B | 002, 004, 005 |
| 013 | Repoint consolidate-architecture skill to sprint docs and on-demand output | B | 003 |
| 014 | Remove architecture path defaults and role-guard prefix | B | 013 |
| 015 | Delete docs/architecture, update dispatch_log context, and verify backward compatibility | B | 013, 014 |
| 016 | Full-suite verification and sprint integration check | A+B | 008, 009, 010, 011, 012, 015 |

Tickets execute serially in the order listed (topological order — a
ticket's dependencies always appear earlier in this table). Tickets with
no listed dependencies and no dependency on each other (e.g. 002 and 006)
are independent of one another and are candidates for parallel worktree
execution in a future sprint that opts in via `worktree: true` — this
sprint itself plans serially since a per-sprint opt-in flag does not yet
exist in the codebase until ticket 001 lands (a bootstrapping note, not a
blocker: this sprint's own execution is unaffected either way since the
`worktree` flag on this sprint's own `sprint.md` is absent/false,
meaning it runs the current serial execute-sprint process).
