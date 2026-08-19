---
id: '006'
title: 'Programmer agent definition: no-background test discipline, scoped tests,
  single full-suite gate ownership'
status: open
use-cases: [SUC-009, SUC-010]
depends-on: []
github-issue: ''
issue: programmer-agents-stall-on-background-pytest.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Programmer agent definition: no-background test discipline, scoped tests, single full-suite gate ownership

## Description

Roughly six times in one session, a dispatched programmer sub-agent
finished its code edits, launched the full test suite as a
background/detached Bash task, and then ended its turn — the harness
does not reliably resume a sub-agent when its background task completes,
so the commit, ticket-status update, and final report were silently
orphaned each time, and the team-lead had to take over. Every programmer
also redundantly runs the full suite once per ticket (N tickets × full
suite), which is both slow and part of what makes backgrounding tempting
in the first place. This ticket fixes both at the agent-definition/
process level (prompt content, not a code change).

**Note**: the source issue's ranked proposal #3 (a CLASI-level
enforcement hook denying `run_in_background` from tier-2 dispatches) was
originally planned as a separate stretch ticket (007) but was **deferred
by stakeholder decision** during sprint review — it is out of this
sprint's scope. This ticket covers only the agent-definition/process fix
(proposals #1 and #2 from the source issue).

## Acceptance Criteria

- [ ] `plugin/agents/programmer/*` states explicitly, as a hard rule:
      never run the test suite (or any command whose completion the
      agent needs to see) with `run_in_background: true`; run
      synchronously so the agent stays alive to see the result.
- [ ] The same agent definition states a ticket is not done until its
      code is committed and its status is updated — a backgrounded test
      run with no foreground follow-up is never an acceptable terminal
      state for a turn.
- [ ] The agent definition scopes test runs to tests relevant to the
      ticket being implemented, not the full suite.
- [ ] `execute-sprint` (or the close-sprint gate) skill/process
      documentation states that it owns running the full test suite
      exactly once, before sprint close, replacing the prior
      once-per-ticket full-suite convention.
- [ ] No source or test code changes are required for this ticket —
      agent-definition and skill-content changes only.

## Implementation Plan

**Approach**: Edit `plugin/agents/programmer/*` (this repo's canonical
source for the programmer agent definition) to add the no-background
rule and the ticket-scoped-tests rule as explicit, hard requirements
(not soft guidance — prompt-level guidance alone previously failed to
stop the behavior, per the source issue's contributing-factors list;
this ticket implements the prompt-level fix, with the enforcement-hook
backstop explicitly deferred). Edit `execute-sprint`'s skill content (or
wherever the close-sprint gate's test-run responsibility is documented)
to state it owns the single full-suite run before close.

**Files to modify**:
- `src/clasi/plugin/agents/programmer/*` (agent.md and any sibling
  files in that directory).
- `src/clasi/plugin/skills/execute-sprint/SKILL.md` (or the close-sprint
  skill, whichever currently owns/should own the full-suite-before-close
  responsibility).
- Confirm whether this repo's own installed `.claude/agents/programmer/*`
  needs a companion re-install/migrate step to pick up the change, per
  sprint.md's Open Questions — if the existing installer convention
  requires a manual re-sync, document that step in this ticket's
  completion notes rather than silently leaving the installed copy
  drifted.

**Testing plan**: No code-level tests apply (this is prompt/doc
content). Verify by reading the updated agent definition against the
acceptance criteria above, and, if feasible, a manual dispatch check
observing a programmer sub-agent run its scoped tests in the foreground
and complete its full terminal sequence (commit, status update, report)
without backgrounding.

**Documentation updates**: This sprint's `design/` overlay
(`plugin-DESIGN.md`) already documents this change at the module level.
