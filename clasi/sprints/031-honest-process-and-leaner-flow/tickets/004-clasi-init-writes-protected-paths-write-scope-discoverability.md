---
id: '004'
title: clasi init writes protected_paths; write-scope discoverability
status: done
use-cases:
- SUC-004
depends-on:
- '003'
github-issue: ''
issue: report-guard-friction-slowness-relax-tier-0-restrictions.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# clasi init writes protected_paths; write-scope discoverability

## Description

Two gaps verified during planning: `init_command.py` never writes
`protected_paths:` to `config.yaml` (grepped: zero hits) — so every
fresh `clasi init` runs in the harsher block-by-default mode where
anything not allow-listed is blocked for tiers 0/1, contradicting
`handle_role_guard`'s own docstring claim that `clasi init` writes it.
Second, an agent currently has no way to learn its write scope except by
being blocked first — nothing at `SubagentStart` or in the status block
states allowed/blocked prefixes.

**Depends on ticket 003 (soft — sequencing, not a build block):** this
ticket's write-scope summary describes ticket 003's *post*-relaxation
policy (tier 0 allowed under `sprints_dir`, blocked only from protected
paths and `create_ticket`). Landing this ticket before 003 would mean
writing a summary that describes the old policy, needing a second edit
the moment 003 lands. There is no code-level import or call dependency
between the two — a project without 003's changes would still function
with this ticket's `init`/discoverability work; the summary text would
simply be temporarily inaccurate, which is why the ordering matters even
without a hard dependency.

## Acceptance Criteria

- [x] `clasi init` on a fresh fixture project detects (or is
      interactively told) the project's source/test directories and
      writes `protected_paths:` to `.clasi/config.yaml`.
- [x] A project that declines, or that upgrades without re-running
      `init`, keeps today's block-by-default fallback unchanged (no
      regression for existing configured or unconfigured projects).
- [x] A dispatched tier-1/tier-2 subagent's `SubagentStart` output
      includes a 3-4 line write-scope summary: allowed prefixes, blocked
      prefixes, the OOP recovery route (`clasi oop on --reason '...'`).
- [x] The same summary (or its tier-0-scoped equivalent) is folded into
      the existing tier-0 status block.
- [x] The summary text reflects ticket 003's post-relaxation policy —
      confirm 003 has landed before writing this ticket's summary
      strings; if it hasn't yet, coordinate rather than guessing at the
      wording.

## Implementation Plan

**Approach**: `init_command.py` gains source/test-dir detection (reuse
whatever convention-based detection is cheapest — e.g. `src/`, `tests/`
at the project root — plus an interactive prompt if ambiguous);
`handle_subagent_start`'s existing status-block build gains a short,
templated write-scope block keyed on the resolved tier.

**Files to modify**:
- `src/clasi/init_command.py` — detect/write `protected_paths`
- `src/clasi/hook_handlers.py` — `handle_subagent_start`, the tier-0
  status-block builder

**Do not modify**: the role-guard/mcp-guard decision logic itself
(ticket 003's scope, must already be landed) — this ticket only makes
the *existing* (post-003) policy visible and correctly configured on
fresh installs.

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
  `uv run pytest tests/unit/test_init_command.py tests/unit/test_init_interactive.py tests/unit/test_hook_handlers.py -v`
- **New tests to write**: `clasi init` on a fresh fixture project writes
  `protected_paths`; a project that declines keeps the fallback;
  `SubagentStart` output for tier 1/2 includes the write-scope summary;
  tier-0 status block includes it too.
- **Verification command**: the existing-tests command above, scoped to
  this ticket's modules.

## Post-Close Gate Fix (2026-08-20)

`close_sprint`'s single full-suite gate (ticket 008) failed with 6
collateral failures after this ticket landed. Reopened to fix; both
causes verified as stale test premises, not source regressions -- no
production code changed, only test fixtures:

- **`tests/unit/test_relocate.py` (5 failures)**: this ticket's new
  `_prompt_protected_paths()` interactive prompt (added to `run_init`)
  legitimately fires in 5 `test_relocate.py` tests that fully mock
  `clasi.init_command.sys` with both `isatty()` calls returning `True`
  to simulate an interactive TTY for the *legacy-file-relocation*
  prompt further down `run_init` -- an incidental side effect none of
  those fixtures anticipated. This ticket's own commit (a4d2cbf) hit
  the identical issue in `test_init_interactive.py` and fixed it there
  by patching `clasi.init_command._prompt_protected_paths` to return
  `[]`; it just didn't know about `test_relocate.py`. Applied the same
  established fix to the 5 affected tests.
- **`tests/unit/test_issue_lifecycle.py::TestIssueLinkageInstructionsPresent::test_team_lead_main_workflow_calls_link_sprint_issues_inline`
  (1 failure)**: NOT caused by this ticket -- caused by ticket 031-007's
  process-doc rewrite (887e63f), unrelated to this ticket's scope.
  Verified the `link_sprint_issues` inline call is fully intact and
  even reinforced ("required", "the most common way issue linkage
  silently fails") in team-lead agent.md's "Execute Issues Through a
  Sprint" workflow -- this is not a regression. The test's ordering
  assertion just checked for literal strings (`create_sprint(title=`,
  `Invoke the sprint-planner agent`) describing an old workflow shape
  (team-lead calling `create_sprint` directly) that predates even
  sprint 029; the doc has since legitimately moved to sprint-planner
  calling `create_sprint` inline during its Roadmap Mode dispatch.
  Updated the test's anchor strings to match the current, correct doc
  text while preserving the same ordering guarantee (create -> link ->
  next sprint-planner dispatch).

Verified via
`uv run pytest tests/unit/test_relocate.py tests/unit/test_issue_lifecycle.py tests/unit/test_init_command.py tests/unit/test_init_interactive.py tests/unit/test_hook_handlers.py tests/unit/test_status/test_hook_injection.py tests/system/test_process_tools.py tests/system/test_tool_signature_docs.py -v --no-cov`
-- all pass (211 tests across the two failing modules plus their
directly related neighbors).
