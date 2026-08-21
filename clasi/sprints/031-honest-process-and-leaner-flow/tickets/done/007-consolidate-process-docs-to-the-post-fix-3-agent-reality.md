---
id: '007'
title: Consolidate process docs to the post-fix 3-agent reality
status: done
use-cases:
- SUC-007
depends-on:
- '002'
- '003'
- '006'
github-issue: ''
issue: one-canonical-text-per-process-topic.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Consolidate process docs to the post-fix 3-agent reality

## Description

`software-engineering.md` (636 lines, confirmed by `wc -l` during
planning) describes a retired seven-agent roster with a per-ticket
code-reviewer and mandatory separate `-plan.md` files — the actual
process is three agents (team-lead, sprint-planner, programmer). The
installed `.claude/agents/team-lead/agent.md` (333 lines) and the
plugin-source `src/clasi/plugin/agents/team-lead/agent.md` (312 lines)
differ (confirmed via `diff`/`wc -l` during planning) — the next plugin
sync would regress whichever process the installed copy currently
describes correctly. `sprint-plan.md`/the `plan-sprint` skill still
describe the pre-002 gate order (tickets after stakeholder review) and
the pre-003 tier-0 policy (team-lead cannot call `create_sprint`
directly).

**Hard dependency on tickets 002, 003, and 006**: this ticket's entire
job is describing the process those three tickets actually implement.
Landing it first would mean describing a process that doesn't exist yet
and rewriting it again once 002/003 land — wasted work, not caution for
its own sake. 006 is listed as a hard dependency too (even though it
doesn't change the gate order or tier policy this ticket describes)
because it fixes the exact two pointers (`source-code.md`,
`dispatch-subagent`) this ticket's own doc audit would otherwise
re-discover and re-fix, duplicating 006's work if run out of order.

## Acceptance Criteria

- [x] `software-engineering.md` is rewritten to the real 3-agent process
      (team-lead, sprint-planner, programmer) or reduced to a pointer
      page — the retired seven-agent roster and per-ticket
      code-reviewer sections are removed.
- [x] `.claude/agents/team-lead/agent.md` and `src/clasi/plugin/agents/
      team-lead/agent.md` are reconciled to agree (whichever is newer
      wins, per the issue's own stated rule — confirm which one that is
      before choosing, do not assume).
- [x] `schemas/se-process/instructions/sprint-plan.md` / the
      `plan-sprint` skill describes: tickets created once the
      `architecture_review` gate passes (not after a separate
      stakeholder-review phase — ticket 002); team-lead calling
      `create_sprint`/writing sprint files directly (ticket 003).
- [x] The tool-signature introspection test from ticket 006 passes
      against this ticket's rewritten docs (extend its doc list if this
      ticket's rewrite introduces a new signature reference).
- [x] `create-tickets`/`tdd-cycle`/`systematic-debugging`'s agent-local
      copies are explicitly **not** touched by this ticket (out of
      scope — flagged in the architecture's Open Questions as a
      follow-up, not silently pulled in here).

## Implementation Plan

**Approach**: audit each doc against the now-current (post-002/003/006)
code and enforcement, rewrite the specific contradicting passages —
this is prose consolidation, not new design; every fact it should state
was already verified during sprint 031's planning pass (see `sprint.md`'s
architecture, Step 1 and the M2/M3 boundaries) and re-confirmed by
tickets 002/003's own acceptance criteria having landed.

**Files to modify**:
- `src/clasi/plugin/instructions/software-engineering.md`
- `.claude/agents/team-lead/agent.md`
- `src/clasi/plugin/agents/team-lead/agent.md`
- `src/clasi/schemas/se-process/instructions/sprint-plan.md`
- `src/clasi/plugin/skills/plan-sprint/SKILL.md` (if it carries a
  separate copy of the same content — confirm during implementation)

**Do not modify**: `dispatch-subagent`, `source-code.md`/`_rules.py`
(ticket 006, already landed — do not re-touch); `create-tickets`/
`tdd-cycle`/`systematic-debugging` agent-local copies (explicitly out of
scope, see Acceptance Criteria).

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
  `uv run pytest tests/system/test_process_tools.py -v`
- **New tests to write**: none beyond extending ticket 006's
  signature-introspection test's doc list if needed.
- **Verification command**: the existing-tests command above, scoped to
  this ticket's modules.
