---
id: '006'
title: 'Programmer agent definition: no-background test discipline, scoped tests,
  single full-suite gate ownership'
status: done
use-cases:
- SUC-009
- SUC-010
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

- [x] `plugin/agents/programmer/*` states explicitly, as a hard rule:
      never run the test suite (or any command whose completion the
      agent needs to see) with `run_in_background: true`; run
      synchronously so the agent stays alive to see the result.
- [x] The same agent definition states a ticket is not done until its
      code is committed and its status is updated — a backgrounded test
      run with no foreground follow-up is never an acceptable terminal
      state for a turn.
- [x] The agent definition scopes test runs to tests relevant to the
      ticket being implemented, not the full suite.
- [x] `execute-sprint` (or the close-sprint gate) skill/process
      documentation states that it owns running the full test suite
      exactly once, before sprint close, replacing the prior
      once-per-ticket full-suite convention.
- [x] No source or test code changes are required for this ticket —
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

## Implementation Notes

**Files changed (canonical, `src/clasi/`)**:
- `plugin/agents/programmer/agent.md` — new "Test Execution" section
  (hard no-`run_in_background` rule, scoped-test rule, same-turn
  completion rule); Workflow step 6 and the Error Recovery Phase 4
  regression-check line both reworded off "run the full test suite."
- `plugin/agents/programmer/dispatch-template.md.j2` — dispatch
  Behavioral Instructions and Required Return Format reworded to
  scoped/foreground tests.
- `plugin/agents/programmer/contract.yaml` — `tests_passed` description
  reworded off "full test suite."
- `plugin/agents/programmer/systematic-debugging.md`,
  `plugin/agents/programmer/tdd-cycle.md` — the sibling copies embedded
  in the programmer agent directory; their regression-check lines
  reworded the same way. The *generic* `plugin/skills/systematic-debugging/`
  and `plugin/skills/tdd-cycle/` copies were left untouched — out of
  this sprint's `plugin/agents/programmer/*` scope, and those skills
  apply to debugging/TDD work generally, not only ticket execution.
- `schemas/se-process/instructions/execution.md` (§5 Close Sprint) and
  `schemas/se-process/instructions/close.md` (`test_command` step) —
  both now state explicitly that the full-suite run there is the
  sprint's single full-suite gate, replacing the prior once-per-ticket
  convention.
- `plugin/agents/team-lead/agent.md` — Ticket Completion Rules item 3
  reworded off "All tests pass (`uv run pytest`)" to name the
  ticket-scoped, foreground run and point to the once-per-sprint gate.
- `platforms/_rules.py` (`SOURCE_CODE_BODY`, item 4) — the canonical
  source for the installed `.claude/rules/source-code.md` rule;
  reworded to require foreground execution and ticket-scoped runs
  under a ticket, while keeping full-suite runs for out-of-process
  (no-sprint) commits, since OOP has no later `close_sprint` gate to
  catch what a scoped run would miss.

**Tracked mirrors updated (`.agents/skills/`, git-tracked, symlinked
from `.claude/skills/`)**: `execute-sprint/SKILL.md` and
`close-sprint/SKILL.md` — same full-suite-gate-ownership sentence added
as in their canonical `execution.md`/`close.md` sources. Per the
`.agents/skills/<name>/SKILL.md` convention (confirmed against
`platforms/claude.py` and documented in ticket 005's implementation
notes), these mirrors are the git-tracked canonical copies for skills;
`.claude/skills/<name>/SKILL.md` is a symlink to them, so no separate
local-copy step was needed for the skill content.

**Local-only refresh (gitignored, not part of this commit)**: re-copied
the fixed `plugin/agents/programmer/{agent.md,systematic-debugging.md,
tdd-cycle.md}` over their `.claude/agents/programmer/` counterparts
(confirmed byte-identical to the pre-edit canonical before copying, so
this was a pure sync, not a merge); applied the same targeted edit to
`.claude/agents/team-lead/agent.md`'s Ticket Completion Rules item 3
(confirmed that section was otherwise identical to canonical -- the
rest of that file has independently drifted from canonical with
richer roadmap/arc process content not touched by this ticket);
regenerated `.claude/rules/source-code.md` directly from the updated
`SOURCE_CODE_BODY` constant. These three locations are gitignored
direct/generated copies with no tracked mirror (per ticket 005's
documented convention), so they only affect this session's live
behavior and are not part of the commit.

**Not changed, considered and rejected**: `.claude/rules/git-commits.md`
(canonical `GIT_COMMITS_BODY` in `_rules.py`) has a similarly-phrased
"All tests pass (run the project's test suite)" pre-commit check. Left
untouched — out of this ticket's explicit scope (only
`.claude/rules/source-code.md` and team-lead's Ticket Completion Rules
were named for the consistency check) and its cadence/version-bump
content is unrelated to per-ticket vs. per-sprint test scope. `src/clasi/AGENTS.md`
(a package-root file, not an installed-copy target) has matching
"Run the project's test suite after changes" text but is independently
stale (references the pre-migration `docs/clasi/oop` path, not
`.clasi/oop`) — left alone as a pre-existing, unrelated drift rather
than folded into this ticket.

**Testing**: no source or test code changed (matching the ticket's own
acceptance criterion). Verified by running the test modules covering
the touched content in the foreground, `--no-cov`:
`test_platform_claude.py`, `test_contracts.py`, `test_agent.py`,
`test_skill_stub_loader.py`, `test_mcp_server.py`, `test_cli_schema.py`,
`schemas/test_round_trip.py`, `test_three_platform_install.py`,
`clasr/test_three_platform_roundtrip.py`, `clasr/test_platform_claude.py`,
`test_hooks_json.py`, `test_uninstall_command.py`,
`test_platform_copilot.py`, `test_init_command.py` — 421 tests total,
all passing. No test asserted the literal strings changed here.
