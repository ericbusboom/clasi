---
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 019 Use Cases

## SUC-001: Role guard blocks an unauthorized direct source write
Parent: UC-002, UC-006

- **Actor**: Team-lead (tier 0) or sprint-planner (tier 1) issuing an
  `Edit`/`Write`/`MultiEdit` tool call against source code, tests, or
  config, with no OOP flag present.
- **Preconditions**: Claude Code's real nested payload shape
  (`{"tool_name": ..., "tool_input": {"file_path": ...}}`) is sent to the
  `role-guard` hook. No `.clasi/oop` or `.clasi-oop` file exists.
- **Main Flow**:
  1. Claude Code fires the PreToolUse hook with the nested payload.
  2. `handle_role_guard` reads `file_path` from `payload["tool_input"]`.
  3. The path resolves to a source/test/config file outside any safe or
     allow-listed prefix.
  4. The calling agent's tier is tier 0 or tier 1.
  5. The guard prints a role-violation message and exits 2.
- **Postconditions**: The write is blocked; stderr names the correct
  agent to dispatch to; `.clasi/log/hooks.log` records a reason other
  than `no-path`.
- **Acceptance Criteria**:
  - [ ] `echo '{"tool_name":"Write","tool_input":{"file_path":"source/main.cpp"}}' | clasi hook role-guard` exits 2.
  - [ ] A guard-deny test exists that fails when the payload-read fix (line 140) is reverted.
  - [ ] The historical flat-payload shape (`{"file_path": ...}`) is no longer used by any test as the sole guard-input fixture.

## SUC-002: Role guard fails closed when the file path cannot be resolved
Parent: UC-002, UC-006

- **Actor**: Any agent issuing an `Edit`/`Write` call whose payload the
  guard cannot parse into a file path.
- **Preconditions**: No OOP flag present.
- **Main Flow**:
  1. The guard attempts to extract `file_path` from the nested and flat
     payload shapes and finds neither.
  2. For tier 0/1, the guard logs a WARN reason including the payload
     keys actually present, and exits 2 (block).
  3. For tier 2 (programmer), the guard still allows (unchanged tier-2
     behavior), since tier-2 write scope is unrestricted by design.
- **Postconditions**: An unparseable payload is loud, not silent, for the
  tiers where directory-scope enforcement matters.
- **Acceptance Criteria**:
  - [ ] `no-path` at tier 0/1 exits 2 with a logged WARN reason (not `0 no-path` allow).
  - [ ] `no-path` at tier 2 continues to allow (tier-2 already has full write scope).

## SUC-003: Tier resolution reflects the calling agent, not an arbitrary one
Parent: UC-002, UC-006

- **Actor**: Any two or more agents with `active_agents` rows registered
  concurrently (e.g. a stale sprint-planner row alongside a live
  programmer row).
- **Preconditions**: `CLASI_AGENT_TIER` env var is unset for the caller
  (forcing DB lookup), and at least one other agent's row exists in
  `active_agents`.
- **Main Flow**:
  1. The calling agent's identity (`agent_id`/`session_id`) is threaded
     from the hook payload into the tier lookup.
  2. `get_active_tier` queries `active_agents` keyed on that identity,
     not `LIMIT 1`.
  3. If no matching row exists, the tier is unresolvable and the caller
     is treated as fail-closed (least privilege), not granted a
     stranger's tier.
- **Postconditions**: A caller's enforcement tier is always its own tier
  or the fail-closed default — never another agent's.
- **Acceptance Criteria**:
  - [ ] A test registers two agents concurrently with different tiers and asserts each caller's guard decision matches its own tier, not the other's.
  - [ ] An unresolvable tier (no matching row, no env var) fails closed rather than defaulting to an arbitrary allowed tier.
  - [ ] `handle_subagent_stop` reliably unregisters the agent's `active_agents` row (primary purge path — precise, immediate).
  - [ ] `clear_stale_agents` is actually invoked from a frequently-hit path (e.g. `subagent-start`) as a backstop for agents that die without firing `SubagentStop` (crash/kill/timeout) — both mechanisms present, not either/or.
  - [ ] The TTL default is reduced well below 24h (a 24-hour-old "active" agent is not a real thing).

## SUC-004: Source writes are blocked when no ticket is in-progress
Parent: UC-002, UC-006

- **Actor**: Programmer (tier 2) or any tier, attempting a source/test
  write while a sprint is executing but zero tickets are `in-progress`,
  with no OOP flag present.
- **Preconditions**: An execution lock is held by a sprint; that sprint
  has zero tickets with `status: in-progress`.
- **Main Flow**:
  1. The guard resolves sprint context via `_get_sprint_context()`.
  2. The guard checks active tickets via `_get_active_tickets()`.
  3. If the active-ticket list is empty and no OOP flag is present, the
     guard blocks the write — regardless of tier, including tier 2.
  4. If at least one ticket is `in-progress`, the write proceeds to the
     existing tier-based scope checks.
- **Postconditions**: A programmer cannot write source code outside the
  scope of an in-progress ticket, closing the exact gap that let
  sprint-101's eight commits land untracked.
- **Acceptance Criteria**:
  - [ ] Sprint executing + zero in-progress tickets + tier 2 + source write → exit 2.
  - [ ] Sprint executing + one in-progress ticket + tier 2 + source write → exit 0 (subject to existing scope rules).
  - [ ] No sprint executing (no lock held) does not trigger this gate (existing tier-based rules apply unchanged).

## SUC-005: OOP bypass works from either flag file, consistently across all guards
Parent: UC-006

- **Actor**: Stakeholder who has created an OOP flag file to opt out of
  process enforcement for a session.
- **Preconditions**: Either `.clasi/oop` (canonical, documented) or
  `.clasi-oop` (legacy) exists in the project root.
- **Main Flow**:
  1. Every guard and status handler (`role-guard`, `mcp-guard`,
     `status-inject`, `subagent-start`, and the ticket-state gate from
     SUC-004) calls one shared `_oop_active()` helper.
  2. The helper checks `.clasi/oop` first, then `.clasi-oop`.
  3. If either exists, all gates in that handler are bypassed.
- **Postconditions**: The documented escape hatch (`.clasi/oop`, per all
  five rule templates and the `oop` skill) actually opens every enforced
  door, not just some of them.
- **Acceptance Criteria**:
  - [ ] A test creates only `.clasi/oop` and asserts bypass in role-guard, mcp-guard, and the ticket-state gate.
  - [ ] A separate test creates only `.clasi-oop` and asserts the same bypass in the same set of handlers.
  - [ ] No handler in `hook_handlers.py` checks either flag file directly outside `_oop_active()`.

## SUC-006: The ticket-write rule is reachable in the project's actual source layout
Parent: UC-001, UC-002

- **Actor**: `clasi init` running against a project whose source code is
  not under `src/clasi/**` or `src/clasr/**` (CLASI's own layout).
- **Preconditions**: A scratch project with code under, e.g., `source/`.
  Claude Code's `.claude/rules/*.md` frontmatter supports only a
  `paths:` key (positive globs; brace expansion works). There is no
  `exclude:` key and no negated-glob support (verified against official
  docs). A rule fires only when Claude *reads a file matching one of its
  `paths:` patterns* — not on every tool use. A rule with no `paths:` key
  loads unconditionally at launch, same priority as CLAUDE.md.
- **Main Flow**:
  1. Before this fix, `clasi init` wrote `.claude/rules/source-code.md`
     (and the Copilot equivalent) scoped to `paths: [src/clasi/**,
     src/clasr/**, tests/**]`. In a project without either `src/`
     subdirectory, this rule could never fire for any file — it was not
     merely narrow, it was **unreachable**. This is a third independent
     instance of the sprint's core failure shape (a guard/rule that
     cannot resolve/match its input silently does nothing), on the
     rules-engine layer rather than the hook layer.
  2. Fix: drop the `paths:` key from `source-code.md` entirely so it
     loads unconditionally at launch. State the path exclusions
     (`.clasi/`, `.claude/`, `docs/`, `*.md`) in the rule's prose body
     instead of attempting to encode them as a glob (the rules engine
     cannot express "match everything except"). This rule is advisory
     backup to the hard block in SUC-004's ticket gate, so its
     always-loaded cost is acceptable — it is short prose, not a large
     injection.
- **Postconditions**: The "you must have a ticket in-progress" rule is
  visible to the agent on every prompt, in every project layout — not
  just CLASI's own, and never silently absent.
- **Acceptance Criteria**:
  - [ ] `clasi init` into a scratch repo with code under `source/` produces a `source-code.md` rule with no `paths:` key (loads unconditionally) and prose that names `source/` as in scope for the ticket-in-progress requirement.
  - [ ] The rule's prose states the `.clasi/`, `.claude/`, `docs/`, `*.md` exclusions explicitly.
  - [ ] `SOURCE_CODE_BODY` states that a commit message is not a process action — only an MCP call moves a ticket.
  - [ ] The rule demonstrably fires (is present in context) in a repo whose code is NOT under `src/clasi/**` — the acceptance bar the coordinator specified as non-negotiable for this fix.

## SUC-010: Generated `clasi-artifacts.md` and `todo-dir.md` rules match real paths
Parent: UC-001, UC-002

- **Actor**: `clasi init` (or a project that already ran it, including
  this repo).
- **Preconditions**: Artifacts moved from hidden `.clasi/` to visible
  `clasi/` (sprint 013). `platforms/claude.py`'s `RULES` dict and
  `platforms/copilot.py`'s `_PATH_RULES` list are the single generators
  for these rule files, but were not updated when the artifact layout
  moved.
- **Main Flow**:
  1. `clasi-artifacts.md` is generated with `paths: [.clasi/**]`, but
     `.clasi/` now holds only state files (`config.yaml`, `log/`,
     `.clasi.db`) — sprint artifacts live at `clasi/sprints/**`. The rule
     that says "use MCP tools, don't hand-edit sprint files directly"
     never fires on an edit to `clasi/sprints/**`. Same failure shape as
     SUC-006: an unreachable rule that looks present but silently does
     nothing.
  2. `todo-dir.md` is generated with `paths: [.clasi/issues/**]`, but
     issues live at `clasi/issues/**` (`Project.issues_dir`'s live
     default, verified correct). This repo's on-disk `todo-dir.md` was
     hand-corrected to `clasi/issues/**` at some point — the generator
     and disk have silently diverged, meaning any future `clasi init`
     re-run (or a fresh project) regenerates the broken value.
  3. Fix both generators (`platforms/claude.py`, `platforms/copilot.py`,
     sourcing the same corrected paths from `platforms/_rules.py` where
     applicable) to emit `clasi/**`-based paths.
  4. Add a test: after a fresh `clasi init`, for every generated rule
     file carrying a `paths:` key, assert the pattern matches at least
     one path that actually exists in the initialized project. This is
     the general check that would have caught SUC-006's and this
     use case's defects before either shipped, and prevents recurrence
     for any future rule.
- **Postconditions**: `clasi-artifacts.md` fires on edits to
  `clasi/sprints/**`; `todo-dir.md` fires on edits to `clasi/issues/**`;
  the generator and any on-disk installation agree, in this repo and in
  every future `clasi init`.
- **Acceptance Criteria**:
  - [ ] `platforms/claude.py`'s `RULES["clasi-artifacts.md"]` emits `paths: [clasi/**]` (or equivalent covering `clasi/sprints/**`, `clasi/issues/**`, `clasi/reflections/**`), not `.clasi/**`.
  - [ ] `platforms/claude.py`'s `RULES["todo-dir.md"]` emits `paths: [clasi/issues/**]`, not `.clasi/issues/**`.
  - [ ] `platforms/copilot.py`'s equivalent `_PATH_RULES` entries are fixed the same way.
  - [ ] A fresh `clasi init` into a scratch project produces `clasi-artifacts.md` and `todo-dir.md` whose `paths:` match real paths in that project.
  - [ ] The generic rule-path-reachability test (checked in SUC-006 too) covers both of these rules.

## SUC-007: Status block is small, accurate, and carries an imperative
Parent: UC-013

- **Actor**: Any agent whose `UserPromptSubmit` or `SubagentStart` hook
  triggers status injection.
- **Preconditions**: The project has multiple sprints, including
  archived (`done/`) sprints and tickets.
- **Main Flow**:
  1. `_build_status_block` builds the real (unmocked) status block.
  2. `done/` sprints and tickets are excluded from the block's contents.
  3. The `done`-vs-`closed` terminology mismatch no longer produces
     `state_drift` warnings for every archived sprint.
  4. `narrow_status` is called with the real `sprint_id`/`ticket_id` for
     the calling context, actually narrowing scope instead of returning
     the full firehose.
  5. When a sprint is executing with no ticket in-progress, the block
     states plainly that source edits are gated and names the two exits
     (start a ticket, or set the OOP flag).
  6. Any exception while building the block is logged as a warning
     instead of silently swallowed into an empty string.
  7. The 18 existing `clasi/sprints/done/*/sprint.md` files are
     bulk-corrected from `status: done` to `status: closed` — `done` is
     not a state the sprint machine defines (its terminal state is
     `closed`), so this is real systemic drift, not cosmetic. Fixing only
     `Sprint.archive()`'s future writes (without correcting history)
     would leave `detect_inconsistencies` permanently correct-but-ignored
     for all 18 archives and would leave a landmine for any future code
     that reads archived sprint status directly (not just the per-prompt
     block). Mechanical, low-risk: a scripted frontmatter rewrite,
     verified by grep.
- **Postconditions**: `clasi hook status-inject | wc -c` is well under
  5KB; the block contains zero bogus `state_drift` entries for archived
  sprints; the block contains at least one actionable imperative when
  relevant; no archived sprint frontmatter declares a status the state
  machine does not define.
- **Acceptance Criteria**:
  - [ ] `clasi hook status-inject | wc -c` is under 5KB on this project's real (multi-sprint) state.
  - [ ] A size assertion test exists against the real, unmocked status block (not `_build_status_block` mocked away).
  - [ ] Zero `state_drift` entries are produced solely by the done/closed mismatch for sprints under `sprints/done/`.
  - [ ] `except Exception: return ""` is replaced with a logged warning path.
  - [ ] `grep -c "^status: done" clasi/sprints/done/*/sprint.md` returns 0 across all 18 archived sprints.

## SUC-008: Stray architecture transition artifact is removed
Parent: UC-005

- **Actor**: N/A (housekeeping, no runtime actor).
- **Preconditions**: `docs/architecture/architecture-update-018.md`
  exists as a one-time leftover from sprint 018's transition to the
  single-doc architecture model.
- **Main Flow**:
  1. Delete `docs/architecture/architecture-update-018.md`.
  2. Delete the now-empty `docs/architecture/` directory.
- **Postconditions**: No stray pre-single-doc-model artifact remains on
  disk; `docs/architecture/` no longer exists.
- **Acceptance Criteria**:
  - [ ] `docs/architecture/architecture-update-018.md` no longer exists.
  - [ ] `docs/architecture/` directory no longer exists.

## SUC-009: e2e-001 review is archived and pruned to its live items
Parent: UC-005

- **Actor**: N/A (housekeeping, no runtime actor).
- **Preconditions**: `clasi/issues/e2e-001-review.md` exists with 8
  numbered improvement items; items 2 and 8 already shipped in sprint
  018; item 7 ships in this sprint; items 5 and 6 are stale (both
  directories they complain about are now populated).
- **Main Flow**:
  1. Copy `clasi/issues/e2e-001-review.md` to `clasi/review/` (a new
     directory, explicitly not a CLASI-tracked artifact type — plain
     archival copy).
  2. Prune the original issue file down to its two remaining live items:
     item 3 (version-bump noise, stays pending) and item 7 (done/closed
     terminology, done in this sprint).
  3. Note in the pruned issue that items 2 and 8 shipped in sprint 018,
     and items 5 and 6 are no longer true.
- **Postconditions**: `clasi/issues/e2e-001-review.md` reflects only
  live, actionable content; the full historical review is preserved
  under `clasi/review/`.
- **Acceptance Criteria**:
  - [ ] `clasi/review/e2e-001-review.md` exists as a full copy of the original.
  - [ ] `clasi/issues/e2e-001-review.md` contains only items 3 and 7, plus a note on items 2, 5, 6, 8.
