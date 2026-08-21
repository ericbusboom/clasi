---
source_file: DESIGN.md
source_hash: 1f680f9ed70cfce30c7d80ce1dde21c8f5847a71c2a52a51ba837f09fca76a82
---
# Diff: DESIGN.md

Comparison of the sprint overlay copy of `DESIGN.md` against its pristine (seed-commit) canonical version.

```diff
--- DESIGN.md (pristine)
+++ DESIGN.md (current)
@@ -140,6 +140,28 @@
   safely without re-deriving "did the last attempt already get this
   far." No schema change: `force_close` writes the same `sprints` and
   `execution_locks` tables every other phase/lock write already used.
+  **As of sprint 031**: a new `StateDB.advance_to(sprint_id,
+  target_phase, required_gate=None)` generalizes `force_close`'s own
+  shape (jump directly to a target phase, checking one named
+  precondition, transactional, idempotent if already there) to two
+  non-terminal transitions: `create_ticket`'s first call jumps a
+  sprint's phase to `"ticketing"` after checking the `architecture_review`
+  gate directly (not a phase-index comparison), and
+  `acquire_execution_lock` jumps it to `"executing"` after checking
+  `stakeholder_approval`, granting the lock only if that gate has
+  recorded `passed`/`skipped`. `_GATE_REQUIREMENTS` loses its
+  `"stakeholder-review"` entry — that phase value is deleted from
+  `se-process/schema.yaml` (see `schemas-DESIGN.md`'s sprint-031 entry)
+  since `stakeholder_approval` now gates the lock instead of the
+  ticketing transition. `advance_to` raises a named, actionable error
+  (not a raw `ValueError` from `list.index()`) if a sprint's current
+  phase is absent from the computed phases list — the stranded-legacy-
+  value case for a downstream project that might have a sprint parked
+  at the now-deleted phase. `force_close` itself is unchanged;
+  `advance_to` generalizes its pattern rather than refactoring
+  `force_close` to call it — the two methods keep deliberately
+  different contracts (unconditional terminal jump vs. gate-checked
+  non-terminal jump).
 - `gitutil.py` (sprint 029) — one `run_git(args, cwd)` helper
   wrapping `subprocess.run(["git", *args], cwd=..., capture_output=True,
   text=True)`, promoted from `design/overlay.py`'s previously-local
@@ -279,10 +301,36 @@
   `Path(clasi.__file__).parent` has a newer mtime — closing the
   same-version-drift gap the first two signals (version string, install
   path) cannot see for a long-lived editable-install MCP server.
+  **As of sprint 031**: the tier-0/tier-1 write policy in
+  `handle_role_guard` is relaxed to the stakeholder's 2026-08-19
+  decision — the tier-0 `blk-sprint` block is deleted (`.clasi/sprints/**`
+  becomes `ALLOW` for tier 0, matching the pre-existing tier-1 allow) and
+  the docstring allow/block matrix is updated to match; `create_ticket`
+  remains the only tier-0-blocked MCP artifact-creation tool (see
+  `plugin-DESIGN.md`'s sprint-031 entry for the matching `hooks.json`
+  matcher change). `handle_subagent_start` additionally injects a 3-4
+  line write-scope summary (allowed prefixes, blocked prefixes, the OOP
+  recovery route) for tier 1/2 dispatches, folded into the existing
+  tier-0 status block too — an agent can now learn its write scope
+  without triggering a block first. Verified, not re-fixed: the
+  outside-root allow (any absolute path role-guard cannot make
+  root-relative, including `~/.claude/plans/**`) already covers every
+  tier, landed by sprints 024 and 026 — this sprint adds the real-
+  dispatch/real-payload regression tests that behavior never had. The
+  DB-backed `get_active_tier` fallback (`019-003`) is confirmed
+  load-bearing by live evidence gathered during this sprint's own
+  planning (`tier=1(db)` resolved correctly for the sprint-planner
+  dispatches that created sprints 031 and 032 themselves) — not a
+  defect, a missing regression test.
 - `init_command.py`, `migrate_command.py`, `uninstall_command.py`,
   `versioning.py`, `worktree.py`, `contracts.py`, `agent.py`,
   `dispatch_log.py` — installation, migration, versioning, worktree, and
-  agent-dispatch machinery.
+  agent-dispatch machinery. **As of sprint 031**: `init_command.py`
+  detects (or is told) the project's source/test directories and writes
+  `protected_paths:` to `config.yaml` on a fresh `clasi init` — a
+  project that declines or upgrades without re-running init keeps the
+  pre-existing block-by-default fallback role-guard already applies when
+  `protected_paths` is unconfigured.
 
 ## 3. Constraints and Invariants
 
@@ -362,6 +410,25 @@
   must report against the process that runs, not an aspirational one. See
   `state_machine-DESIGN.md`'s sprint-030 entry for the specific
   predicates removed under this rule.
+- **A structural phase transition arrives as a side effect of the tool
+  call that earns it, never a separate agent-driven
+  `advance_sprint_phase` call (sprint 031):** `roadmap` (`create_sprint`),
+  `planning-docs` (`detail_sprint`), `ticketing` (`create_ticket`'s first
+  call), `executing` (`acquire_execution_lock`), and `done`
+  (`close_sprint`, unchanged since sprint 030) each arrive via the tool
+  call whose success implies the transition, checked against the one
+  gate (if any) that transition requires — `StateDB.advance_to()`
+  generalizes `force_close`'s pre-existing "jump + own precondition"
+  shape to the two transitions (`ticketing`, `executing`) that gained
+  this behavior in sprint 031. `advance_sprint_phase` (the MCP tool)
+  remains available for manual recovery; no shipped instruction routes
+  the standard flow through it. `record_gate_result` for
+  `stakeholder_approval` stays an explicit, agent-driven call
+  (deliberately — it is how a human's actual approval gets recorded as a
+  fact independent of whoever consumes it, one of the two safety
+  properties this campaign does not relax) — see the sprint 031
+  `sprint.md` Design Rationale for the full argument against folding it
+  into `acquire_execution_lock` as an implicit default.
 
 ## 4. See Also
 
```
