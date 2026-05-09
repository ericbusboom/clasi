---
id: "C"
title: "Lower-agent exception protocol"
status: planning
branch: sprint/C-lower-agent-exception-protocol
use-cases: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint C: Lower-agent exception protocol

## Goals

Give lower-tier agents (sprint-planner, programmer, ticket-author) a structured way to throw a "I can't proceed without overriding an upstream decision" exception, and define team-lead routing rules so those exceptions become information instead of dropped balls.

## Problem

When a programmer hits a wall — an architectural decision the ticket implicitly assumes that turns out to be wrong, a use-case ambiguity that blocks ticket completion, a missing prerequisite — the current options are:

1. Power through with a workaround. Quietly desyncs implementation from architecture.
2. Hallucinate "done." Worse than (1).
3. Stop and ask out-of-band. No recorded artifact; team-lead has no audit trail.

There's no in-process channel for "I'm stopping cleanly because a structural assumption is wrong, and here's what I tried." Same problem for ticket-authors who discover that a sprint plan can't be ticketed without an architectural revision.

## Solution

Define an **exception cord**: a structured payload a lower-tier agent writes onto its ticket (or sprint plan) when blocked, plus team-lead routing rules.

1. **Payload** — written into the ticket frontmatter (or a sibling `exception.md` in the ticket dir):
   ```yaml
   exception:
     thrown_by: programmer
     thrown_at: 2026-05-07T14:23:00Z
     attempted: <what was attempted>
     conflict: <what upstream decision is being overridden>
     surface: user-visible | internal
   ```
   The ticket transitions to `status: exception`; programmer exits cleanly without partial completion.

2. **Routing rules for team-lead**:
   - `surface: user-visible` (per the use-cases doc) → escalate to stakeholder. Team-lead pauses sprint; surfaces the exception for stakeholder decision.
   - `surface: internal` → loop with architecture-authoring agent; revise the architecture-delta; re-derive tickets. Original architecture plan is preserved alongside the revision (calibration signal).

3. **Calibration signal** — exception frequency is information about whether the architecture step is well-calibrated. Frequent revisions mean the architect is shooting from too far away. Keep both the original plan and revisions when this loop runs, so the signal stays visible.

4. **Threshold rule documented**: exceptions are for "structural wall," not "this is hard." Hard work is work. The wall has to be a real upstream-decision conflict.

## Success Criteria

- `exception` is a recognized ticket status.
- A new MCP tool or internal helper records the exception payload (attempt, conflict, surface) and transitions the ticket to `status: exception`.
- Programmer agent prompt updated with the threshold rule and the throw protocol.
- Team-lead agent prompt updated with routing rules (user-visible vs internal) and the loop-with-architect path.
- A new test verifies that thrown exceptions block ticket-completion and surface to team-lead routing.
- Calibration signal: when an architecture-delta is revised in response to an exception, the original is retained (e.g. `architecture-delta.md` + `architecture-delta.v1.md`).
- Documentation in SE-overview explaining the protocol with one user-visible example and one internal example.

## Scope

### In Scope

- Ticket-frontmatter schema extension for `exception` field.
- New ticket status value `exception` (alongside `open`/`in-progress`/`done`).
- Programmer / sprint-planner agent prompt updates.
- Team-lead routing rules (in `team-lead/agent.md`).
- Architecture-delta retention rule (preserve originals on revision).
- Tests covering throw → block-completion → team-lead-surface flow.

### Out of Scope

- A formal escalation policy with timers or auto-routing — this is meant to be team-lead judgment, not a state machine.
- Per-tier exception types beyond user-visible/internal.
- Auto-resolution of internal exceptions — team-lead always loops with the architect rather than rewriting plans unilaterally.
- A UI / dashboard for active exceptions.

## Test Strategy

- Unit test: `Ticket` accepts `status: exception` and the `exception:` frontmatter block.
- Unit test: programmer-tier write-permission hook permits the exception write but blocks `status: done`.
- Integration test: synthetic ticket → throw exception → team-lead reads → routes appropriately. Two paths (user-visible, internal).
- Snapshot test: agent prompts include the threshold rule and the throw protocol.

## Architecture impact

Adds one terminal status to the ticket lifecycle (`exception` joins `done`). Adds a routing surface to team-lead. Architecture-authoring gains a "revise in response to exception" mode that preserves history.

Best landed *after* Sprint B (delta spec) so the architect-loop path has a structured artifact to revise. Workable before Sprint B with `architecture-update.md`.

## Dependencies / sequencing notes

- Best after Sprint B (delta spec) so the architect-loop revises a parseable artifact, but workable before.
- Independent of Sprints A, D, E, F. Sprint A's vocabulary rename should land first only because `status: open` collides with `status: exception` discussions in the prompts.

## Source TODO to be archived as superseded by this sprint

- `sprint-process-changes.md` (exception-cord half only; architecture-positioning half goes to Sprint B)
