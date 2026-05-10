---
id: 018
title: Lower-agent exception protocol
status: done
branch: sprint/018-lower-agent-exception-protocol
use-cases: []
source-todos:
- sprint-process-changes.md
---

# Sprint 018: Lower-agent exception protocol

## Goals

Give sprint-planner and programmer agents a structured, tool-supported way to
signal "I cannot proceed without overriding an upstream decision." Define the
exception payload format, write it to the ticket, and specify how the team-lead
receives and routes the exception — to stakeholders if user-visible behavior is
implicated, or to an architecture revision loop if purely internal.

Also add a calibration signal: preserve the original architecture delta plus
all revisions when the exception loop runs, so the team-lead can observe how
often lower agents are throwing and whether upstream planning quality is the
root cause.

## Problem

When a programmer or sprint-planner agent hits a structural wall — a conflict
that cannot be resolved without overriding an architecture decision — there is
no defined way to surface that. Agents either improvise workarounds, silently
partially complete work, or emit unstructured error messages that the team-lead
has no protocol to handle. The result is inconsistency: some walls get thrown,
some get papered over, and the team-lead has no systematic routing logic.

The calibration signal problem is related: if the architecture step is too
vague or too far from reality, lower agents will throw frequently. Without
preserving the original plan plus its revisions, this frequency is invisible.

Note: the "architecture update moves to sprint planning" half of the source
TODO (`sprint-process-changes.md`) is already being implemented by sprint 016
(in flight) and is NOT in scope here. This sprint addresses only the exception
cord half.

## Solution outline

- Define a structured exception payload: what was attempted, what failed,
  what the conflict is (referenced by architecture module or use case).
- Define the protocol for writing this to the ticket (not out-of-band). The
  ticket-with-exception is the carrier.
- Update the programmer agent and sprint-planner agent prompts with throw
  threshold guidance: "I can't proceed without overriding an upstream decision"
  is the bar, not "this is hard."
- Define the team-lead routing rules: use-case doc anchors the
  user-visible-vs-internal distinction; team-lead reasons over the exception
  and routes accordingly.
- Preserve original architecture-update plus all revision artifacts when the
  exception loop triggers a revision. Do not collapse to final-version-only.

## Success criteria

- Agent prompts (programmer, sprint-planner) include explicit exception-throw
  guidance with threshold definition and structured payload schema.
- Team-lead agent prompt includes routing rules for received exceptions:
  escalate to stakeholder if user-visible; loop with architect if internal.
- The exception payload is written to the ticket file in a defined YAML or
  structured-markdown block; no out-of-band signaling.
- When an architecture revision loop runs, the sprint directory retains the
  original architecture-update.md plus revision artifacts (e.g.
  `architecture-update-r1.md`, `architecture-update-r2.md`).
- The use-case document is specified as the anchor for the
  user-visible-vs-internal routing decision; team-lead guidance references it.
- At least one system test or acceptance scenario exercises the throw-and-route
  path end-to-end.

## In Scope

- `clasi/plugin/agents/programmer/agent.md`: exception throw guidance,
  payload schema, threshold definition.
- `clasi/plugin/agents/sprint-planner/agent.md`: same for sprint-planner role.
- `clasi/plugin/agents/team-lead/agent.md`: routing rules for exceptions
  received from lower agents.
- Sprint directory convention for preserving architecture revision artifacts.
- Possibly: a new MCP tool or ticket status value to flag
  "exception thrown, needs routing" (architect to decide).

## Out of Scope

- "Architecture update moves to sprint planning" — already implemented in
  sprint 016. Do not re-scope here.
- Automated exception detection (parsing agent output). The protocol is
  agent-driven, not automated.
- Formal escalation policies beyond team-lead reasoning over the exception.
- Any user-facing UI or notification system for exceptions.

## Dependencies and sequencing

- Sprint 016 (in-flight) should close before 018 begins. Sprint 016 covers
  architecture-positioning; 018 picks up the other half of the same source
  TODO without overlap.
- Sprint 017 (two-phase tooling) is not a blocker but landing it first means
  018 can be detail-planned using the new `detail_sprint` tool.
- Independent of sprints 019, 020, 021, 022.

## Source TODOs

- `docs/clasi/todo/sprint-process-changes.md` (exception-cord section only;
  architecture-positioning section is in-scope for sprint 016)

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Add `exception` to ticket status enum and ticket_counts() | — |
| 002 | Add `exception:` frontmatter block schema to Ticket class | — |
| 003 | Implement `throw_ticket_exception` MCP tool | 001, 002 |
| 004 | Update programmer agent prompt with exception protocol section | 003 |
| 005 | Update sprint-planner agent prompt with exception protocol section | 003 |
| 006 | Update team-lead agent prompt with exception routing rules | 003, 004, 005 |
| 007 | Update architecture-authoring skill with revision naming and preservation rule | 006 |
| 008 | Write tests, SE overview "Exception protocol" section | 001, 002, 003, 007 |
