---
id: 008
title: Rework architecture-authoring, architecture-review, plan-sprint, close-sprint,
  execute-sprint skills and team-lead role
status: done
use-cases:
- SUC-004
- SUC-005
- SUC-006
- SUC-007
depends-on:
- '004'
- '005'
- '006'
- '007'
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Rework architecture-authoring, architecture-review, plan-sprint, close-sprint, execute-sprint skills and team-lead role

## Description

Rework the five skills and the team-lead role definition named as ripple
effects in the issue, so the whole opted-in sprint lifecycle is coherent
prose end to end. This ticket depends on 004-007 because it documents
behavior that must already exist in code/other skills to describe
accurately — it is the "wire the prose together" ticket, done last among
the design-focused work so it can reference real tool names and real
hook points rather than speculating.

Scope, one change per skill:

- **`architecture-authoring`**: add a third mode (or fold into existing
  modes) for authoring a sprint's `design/` overlay files instead of a
  `sprint.md` Architecture section, when the doc set is opted in. Keep
  the existing "N/A — trivial" / compact / substantial tiering — it
  still governs whether an overlay is written at all (Open Question 4's
  resolution: no overlay for trivial).
- **`architecture-review`**: when opted in, read `<name>.diff.md` files
  in the sprint's `design/` directory instead of the `sprint.md`
  Architecture section; same five review categories and verdict levels
  unchanged (SUC-007).
- **`plan-sprint`**: document the seed-copies-at-creation step and where
  in Phase 2 the sprint-planner identifies which canonical docs are
  affected (resolving ticket 006's open sequencing question precisely);
  document the opt-in skip path (no `design/` dir when not opted in,
  behavior identical to today).
- **`close-sprint`**: document the apply-at-close step and its
  before-tag/merge sequencing; document the opt-in skip path.
- **`execute-sprint`**: change programmer dispatch context from "relevant
  architecture sections" (of `sprint.md`) to "relevant subsystem doc(s)
  plus this sprint's overlay," when opted in.
- **team-lead `agent.md`**: add detection (no `docs/design/design.md` and
  no recorded opt-in/opt-out decision) -> prompt stakeholder -> record
  decision -> dispatch bootstrap agent on approval (SUC-006). Must not
  re-prompt once a decision is recorded.

## Acceptance Criteria

- [x] Each of the five skill files and the team-lead `agent.md` is
      updated in place (following this project's own convention of
      revising skills in place rather than versioning them, consistent
      with the "Revising in place" convention already documented in
      `architecture-authoring`).
- [x] `architecture-authoring`'s tiering rules (trivial/compact/
      substantial) are preserved unchanged — this ticket changes *where*
      the output goes (overlay vs. inline section), not the sizing logic.
- [x] `architecture-review`'s verdict levels (APPROVE / APPROVE WITH
      CHANGES / REVISE) and REVISE-triggering conditions are unchanged —
      only the input source changes.
- [x] `plan-sprint` explicitly states the sequencing resolution from
      ticket 006 (when seed-and-commit fires relative to
      `create_sprint`/Phase 2) so there's one authoritative source for
      that timing, not two skills disagreeing.
- [x] `close-sprint` explicitly states that a failed apply blocks
      tag/merge, matching ticket 006's implementation.
- [x] `execute-sprint`'s dispatch-context change is described concretely
      enough that a programmer agent reading it knows exactly which
      files it receives (subsystem doc path(s) + sprint overlay path, not
      a vague "relevant docs").
- [x] Team-lead `agent.md` update covers all four SUC-006 acceptance
      criteria: no `design/` overlays on decline; decision persists
      across sessions (read from config, not session state); no
      re-prompting once recorded; opt-in dispatches the bootstrap agent.
- [x] None of the six documents' *unrelated* existing content is altered
      beyond what this ticket's scope requires — this is a targeted
      rework, not a rewrite.

## Implementation Plan

**Approach**: Prose-only ticket, same as 007. Read each of the six
target files in full before editing (already done once during sprint
planning for four of the five skills — re-read at implementation time
since this ticket lands after 004-007's code exists, and cross-check
against the actual implemented function names/hook points rather than
this sprint plan's descriptions, in case implementation details shifted
during 004-006).

**Files to create/modify**:
- `.agents/skills/architecture-authoring/SKILL.md`
- `.agents/skills/architecture-review/SKILL.md`
- `.agents/skills/plan-sprint/SKILL.md`
- `.agents/skills/close-sprint/SKILL.md`
- `.agents/skills/execute-sprint/SKILL.md`
- `.claude/agents/team-lead/agent.md`

**Testing plan**:
- No automated tests for skill/role prose. Verification is downstream:
  the next sprint that opts in and uses these skills is the real test,
  outside this sprint's scope. Within this sprint, self-check each
  document against the acceptance criteria above by re-reading it after
  editing.

**Documentation updates**:
- This ticket *is* the documentation update.
