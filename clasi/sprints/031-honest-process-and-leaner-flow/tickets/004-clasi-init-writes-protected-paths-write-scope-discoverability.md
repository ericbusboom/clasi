---
id: '004'
title: clasi init writes protected_paths; write-scope discoverability
status: open
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

- [ ] `clasi init` on a fresh fixture project detects (or is
      interactively told) the project's source/test directories and
      writes `protected_paths:` to `.clasi/config.yaml`.
- [ ] A project that declines, or that upgrades without re-running
      `init`, keeps today's block-by-default fallback unchanged (no
      regression for existing configured or unconfigured projects).
- [ ] A dispatched tier-1/tier-2 subagent's `SubagentStart` output
      includes a 3-4 line write-scope summary: allowed prefixes, blocked
      prefixes, the OOP recovery route (`clasi oop on --reason '...'`).
- [ ] The same summary (or its tier-0-scoped equivalent) is folded into
      the existing tier-0 status block.
- [ ] The summary text reflects ticket 003's post-relaxation policy —
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
