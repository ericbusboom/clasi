---
id: '002'
title: Gate-order fix and event-derived phase transitions
status: open
use-cases:
- SUC-002
depends-on: []
github-issue: ''
issue: sprint-phase-gate-order-contradicts-plan-sprint-skill-docs.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Gate-order fix and event-derived phase transitions

## Description

The phase machine requires a recorded `stakeholder_approval` gate to
advance `stakeholder-review` → `ticketing` (`_GATE_REQUIREMENTS` in
`state_db_class.py:124-132`), and `create_ticket` hard-rejects before
that phase (`_check_sprint_phase_for_ticketing`,
`tools/artifact_tools.py:515-537`) — while every doc (the plan-sprint
skill, sprint-planner agent.md, team-lead agent.md) describes the
opposite order: tickets created during planning, reviewed by the
stakeholder afterward. This forces a second sprint-planner dispatch
every sprint that exists only to materialize tickets after approval
(the sprint-026 incident that produced this issue; the fresh 2026-08-20
E2E run reproduced it live — the single failed call out of 40 in that
run's `mcp-calls.jsonl`).

Fix (verified against the live code, not assumed): delete the
`stakeholder-review` artifact entry from `schemas/se-process/
schema.yaml`; `ticketing`'s `requires:` becomes `[architecture-review]`.
`_compute_phases()` derives the new 7-value phase list with no other
code change (it reads the schema-derived artifact list positionally).
`stakeholder_approval` moves to gate `acquire_execution_lock` instead —
verified during planning that `StateDB.acquire_lock()`
(`state_db_class.py:445`) performs **no gate check at all** today, so
this is a net-new check, not a relocation of an existing DB-layer check.

Additionally (per this sprint's already-approved Solution and the
architecture's Design Rationale): both remaining structural transitions
become event-derived, generalizing `StateDB.force_close()`'s existing
"jump directly to a target phase, check one precondition, transactional,
idempotent" shape (verified by reading `force_close`,
`state_db_class.py:519`) via a new `StateDB.advance_to()`. `create_ticket`'s
first call jumps the phase to `ticketing` after checking the
`architecture_review` gate directly (not a phase index);
`acquire_execution_lock` jumps it to `executing` after checking
`stakeholder_approval`. Neither requires a separate agent-driven
`advance_sprint_phase` call.

## ⚠ This ticket lands as ONE atomic commit — schema, `advance_to()`, and both tool-level checks together

This is the single highest-risk ticket in the sprint (it changes the
enforcement every later sprint plans and executes under), and the reason
is structural, not caution for its own sake: `_compute_phases()` derives
the phase list from `schema.yaml`, and `_GATE_REQUIREMENTS`/
`create_ticket`/`acquire_execution_lock` all key off the phase strings
and gate names that list produces. If the schema half lands (the
`stakeholder-review` entry deleted) without the `state_db_class.py`/
`tools/artifact_tools.py` half landing in the same commit — or vice
versa — the two halves disagree about what phase list and gate
requirements are in force. Concretely: `create_ticket`'s *old*
phase-index check running against the *new*, shorter phase list changes
what index `"ticketing"` resolves to, silently changing which phase is
required for a live sprint's DB row to already be sitting at, evaluated
against logic that no longer agrees with the schema that produced the
list it's indexing into. A half-applied state is not merely
"incomplete" — it is a phase machine making decisions against an
internally inconsistent picture of its own phase list. Land schema +
`advance_to()` + the `create_ticket`/`acquire_execution_lock` checks in
one commit; do not push an intermediate state.

## Acceptance Criteria

- [ ] `schemas/se-process/schema.yaml`: `stakeholder-review` artifact
      entry deleted; `ticketing`'s `requires:` is `[architecture-review]`.
- [ ] `state_db_class.py`: `_GATE_REQUIREMENTS` no longer has a
      `"stakeholder-review"` key.
- [ ] `state_db_class.py`: new `StateDB.advance_to(sprint_id,
      target_phase, required_gate=None)` — idempotent no-op if already
      at/past `target_phase`; checks `required_gate`'s recorded result
      is `passed`/`skipped` when given (raises if not); jumps the phase
      directly to `target_phase` in one transaction; records one
      `phase_transitions` row; raises a named, actionable error (not a
      raw `ValueError` from `list.index()`) if the sprint's *current*
      phase is absent from the computed phases list.
- [ ] `tools/artifact_tools.py`: `create_ticket`'s
      `_check_sprint_phase_for_ticketing` is replaced by a direct check
      of the `architecture_review` gate's recorded result, followed by
      `advance_to(sprint_id, "ticketing", "architecture_review")` on the
      sprint's first `create_ticket` call.
- [ ] `tools/artifact_tools.py`: `acquire_execution_lock` checks the
      `stakeholder_approval` gate's recorded result **before** calling
      `db.acquire_lock()` — no lock is granted without a recorded
      `passed`/`skipped` result — then calls `advance_to(sprint_id,
      "executing", "stakeholder_approval")` after the lock is granted.
- [ ] **Failure-mode contract**: if `advance_to` fails after
      `db.acquire_lock()` has already succeeded, the lock is **not**
      rolled back (the lock, not the phase string, is what the tier-2
      ticket-state gate and `close_sprint`'s precondition check treat as
      authoritative); the failure is surfaced to the caller, never
      swallowed; a retried `acquire_execution_lock` call is safe
      (`db.acquire_lock()`'s existing re-entrant path plus `advance_to`'s
      own idempotency). Add a test that forces `advance_to` to raise
      after a successful `acquire_lock()` and asserts the lock is still
      held and a retry completes cleanly.
- [ ] `advance_sprint_phase` (the MCP tool) and `sprint.advance_phase()`
      are unchanged in behavior — still usable for manual recovery; no
      doc this ticket touches instructs an agent to call it in the
      standard flow (tickets 006/007 own the doc updates; this ticket
      only must not regress the tool itself).
- [ ] A single sprint-planner dispatch following the documented flow
      (record `architecture_review` → create tickets → record
      `stakeholder_approval` → `acquire_execution_lock`) reaches ticket
      creation with zero rejected MCP calls — verified against a real
      dispatch or an equivalent E2E-fixture-driven test.
- [ ] `record_gate_result` is unaffected — still callable at any phase
      (confirmed during planning: it validates gate name/result/sprint
      registration only, no phase check).

## Implementation Plan

**Approach**: land the schema change and `advance_to()` together with
both tool-level call sites in one commit (see the warning above). Build
`advance_to()` by direct analogy to the already-shipped `force_close`
(same file) rather than inventing a new shape.

**Files to modify**:
- `src/clasi/schemas/se-process/schema.yaml`
- `src/clasi/state_db_class.py` — `_GATE_REQUIREMENTS`, new `advance_to`
- `src/clasi/tools/artifact_tools.py` — `create_ticket`,
  `acquire_execution_lock`
- New/updated tests (see Testing)

**Do not modify**: `force_close` itself (this ticket generalizes its
*pattern*, not its code — `advance_to` is a new, separate method);
`.claude/settings.json`/`plugin/hooks/hooks.json` (ticket 003's scope);
`software-engineering.md`/`sprint-plan.md`/agent definitions (tickets
006/007's scope — do not describe the new flow in prose here, only
implement it).

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is a hard block, not a silent allow.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or any mechanism that
  avoids the tool the guard is watching. Reporting a block is a
  successful outcome of this ticket, not a failure.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/unit/test_state_db_class.py tests/unit/test_artifact_tools.py tests/system/test_artifact_tools.py tests/clasi/schemas/test_se_schema.py tests/unit/test_schema_loader.py -v`
- **New tests to write**: `advance_to()` unit tests (idempotency, gate
  check, stranded-phase-value error); `create_ticket`'s new gate-based
  check (both the pass and reject case); `acquire_execution_lock`'s new
  gate check and the failure-mode-contract test above; an end-to-end
  "single dispatch reaches ticket creation" test.
- **Verification command**: the existing-tests command above, scoped to
  this ticket's modules.
