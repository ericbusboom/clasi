---
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 018 Use Cases

## Issue A — Worktree parallel execution

### SUC-001: Controller executes independent tickets in parallel worktrees
Parent: UC — Sprint execution

- **Actor**: Team-lead (execute-sprint controller)
- **Preconditions**: Sprint has `worktree: true` in `sprint.md` frontmatter;
  sprint is in `executing` phase; execution lock held by this sprint; no
  tickets currently `in-progress`.
- **Main Flow**:
  1. Controller runs the preflight `reconcile_worktrees` sweep.
  2. Controller reads open tickets and their plan files, calls
     `check_independence` to partition them into serial groups of
     parallel-safe tickets.
  3. For each group (in order): controller re-runs the per-creation
     `reconcile_worktrees` gate, creates a worktree + ticket branch per
     ticket in the group, dispatches one programmer agent per ticket
     concurrently into its worktree.
  4. Controller waits for all dispatches in the group to return, then
     sequentially validates and merges each ticket branch back into the
     sprint branch.
  5. On successful merge, controller immediately tears down the worktree
     and deletes the ticket branch (no lingering directories).
- **Postconditions**: All tickets in the group are `done` and merged into
  the sprint branch; zero worktree directories remain for merged tickets.
- **Acceptance Criteria**:
  - [ ] Two file-disjoint tickets in one sprint create two `../worktree-*`
        directories and run concurrently.
  - [ ] Each worktree is removed immediately after its ticket merges, not
        deferred to sprint close.
  - [ ] A sprint without `worktree: true` runs the existing serial path
        unchanged.

### SUC-002: Controller determines which tickets are safe to parallelize
Parent: UC — Sprint execution

- **Actor**: Team-lead (execute-sprint controller), via `check_independence`
- **Preconditions**: Open tickets exist with plan files containing a
  `## Files to create or modify` (or `###`) heading, or `files_to_create`
  / `files_to_modify` frontmatter.
- **Main Flow**:
  1. For each ticket, extract its planned file set (frontmatter keys, else
     the plan-file heading, else "unknown").
  2. Normalize paths (repo-relative POSIX, strip leading `src/`).
  3. Two tickets are dependent if their file sets overlap, their derived
     test-module basenames overlap, or either set is "unknown".
  4. Partition into connected components; order groups by topological sort
     of aggregated `depends-on`, tie-break by ticket id.
- **Postconditions**: Ordered list of groups; each group is safe to run in
  parallel.
- **Acceptance Criteria**:
  - [ ] Overlapping file sets are placed in the same (serial) group.
  - [ ] `src/clasi/foo.py` and `clasi/foo.py` are recognized as the same
        file (regression case).
  - [ ] Tickets with no discoverable file list are always dependent on all
        others (safe default).

### SUC-003: Cleanup prevents worktree accumulation (the reaper)
Parent: UC — Sprint execution

- **Actor**: Team-lead (execute-sprint controller), via `reconcile_worktrees`
- **Preconditions**: A sprint directory with a `.worktree-audit.json` and
  zero or more live `ticket/<sprint>-*` worktrees exist.
- **Main Flow**:
  1. `reconcile_worktrees` reads the audit record and `git worktree list
     --porcelain`.
  2. Every `ticket/<sprint>-*` worktree is classified: merged-not-cleaned,
     clean-but-abandoned, or ambiguous (dirty tree / failed / conflict /
     in-progress audit state).
  3. Safe classes are auto-cleaned (`cleanup_worktree` + audit update to
     `cleaned_up`); ambiguous cases are returned untouched for the
     controller/stakeholder to resolve.
  4. Runs at three trigger points: execution-session start, immediately
     before creating any new worktree (hard gate — blocks new work until
     unresolved worktrees are resolved), and at sprint close (safety net).
- **Postconditions**: No worktree directory survives a `reconcile_worktrees`
  call unless it was returned in `escalated`. Second consecutive call is a
  no-op.
- **Acceptance Criteria**:
  - [ ] A stale, clean, abandoned worktree is removed automatically; its
        branch is kept.
  - [ ] A worktree with uncommitted changes or `failed`/`conflict` audit
        state is never auto-removed — it is escalated.
  - [ ] Starting a new sprint while an unresolved stale worktree exists is
        blocked until it is resolved (accumulation is a blocking
        condition).
  - [ ] Close-sprint's existing `_prune_sprint_worktrees` safety net also
        catches orphaned `ticket/<sprint>-*` worktrees (not just the sprint
        branch worktree), retaining `failed`/`conflict` branches and
        reporting them in the close result.

## Issue B — Right-sized sprint planning

### SUC-004: Planner sizes planning effort to the change
Parent: UC — Sprint planning

- **Actor**: Sprint-planner agent
- **Preconditions**: A sprint has been promoted to detail planning
  (`detail_sprint` called).
- **Main Flow**:
  1. Sprint-planner writes ONE `sprint.md` containing `## Architecture` and
     `## Use Cases` sections sized to the change (may be one line or
     "N/A — trivial" for small sprints).
  2. For trivial/small sprints (doc-only, roughly under 5 files, no new
     modules/interfaces): minimal sections, architecture-review gate
     recorded as `skipped`.
  3. For substantial/structural sprints: full sections with diagrams as
     needed, and a full architecture review is performed and recorded as
     `passed`/`failed`.
- **Postconditions**: No separate `usecases.md` or `architecture-update.md`
  is created for sprints planned after this sprint closes.
- **Acceptance Criteria**:
  - [ ] `detail_sprint` scaffolds only `tickets/` + `tickets/done/` (plus
        the pre-existing `sprint.md`) — no `usecases.md` or
        `architecture-update.md` files are written.
  - [ ] A small sprint reaches `ticketed`/`executing` with a recorded
        `architecture_review: skipped` gate.
  - [ ] A substantial sprint can still record a full `passed`/`failed`
        architecture review.

### SUC-005: Historical sprints remain valid and renderable
Parent: UC — Sprint planning / backward compatibility

- **Actor**: Team-lead, stakeholder
- **Preconditions**: Sprints 001-017 are closed with their original
  `usecases.md` + `architecture-update.md` files intact.
- **Main Flow**:
  1. State-machine invariants `is_architecture_present` /
     `is_usecases_present` are removed, so their presence or absence no
     longer gates any transition.
  2. `Sprint.usecases` / `Sprint.architecture` accessors remain (read-only)
     so historical sprints still render via status tools.
  3. `review_sprint_pre_close` no longer requires `usecases.md` /
     `architecture-update.md` to exist or be non-draft.
- **Postconditions**: Old sprint directories are untouched; new validation
  logic does not regress them.
- **Acceptance Criteria**:
  - [ ] `get_status` / `list_sprints` on sprints 001-017 succeeds unchanged.
  - [ ] No code path rewrites or deletes historical `usecases.md` /
        `architecture-update.md` files.

### SUC-006: Stakeholder gets a coordinated architecture view on demand
Parent: UC — Architecture consolidation

- **Actor**: Stakeholder / team-lead
- **Preconditions**: One or more sprints have been closed with Architecture
  sections in their `sprint.md` (new model) and/or legacy
  `architecture-update.md` files (old model, sprints 001-017).
- **Main Flow**:
  1. Stakeholder invokes the `consolidate-architecture` skill on demand
     (not automatically at sprint close).
  2. The skill reads sprint docs (`clasi/sprints/**` including `done/`,
     covering both the new sprint.md Architecture sections and legacy
     architecture-update.md files) plus current source code.
  3. The skill writes one coordinated `docs/design/architecture.md`.
- **Postconditions**: `docs/architecture/` no longer exists in this repo;
  closing a sprint no longer writes into it.
- **Acceptance Criteria**:
  - [ ] `Sprint.archive()` no longer copies anything into
        `docs/architecture/`.
  - [ ] Running consolidate-architecture produces
        `docs/design/architecture.md` reflecting sprint docs + code.
  - [ ] `docs/architecture/` is deleted from this repo as part of this
        sprint.
