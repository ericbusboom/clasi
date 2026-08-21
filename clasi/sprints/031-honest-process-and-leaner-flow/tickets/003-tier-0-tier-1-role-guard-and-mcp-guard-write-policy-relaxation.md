---
id: '003'
title: Tier-0/tier-1 role-guard and mcp-guard write-policy relaxation
status: open
use-cases:
- SUC-003
depends-on: []
github-issue: ''
issue: report-guard-friction-slowness-relax-tier-0-restrictions.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Tier-0/tier-1 role-guard and mcp-guard write-policy relaxation

## Description

Stakeholder decision (Eric, 2026-08-19): block protected source paths and
`create_ticket`; allow everything else for tier 0. Verified against the
current code during planning:

- `handle_role_guard` (`hook_handlers.py:1172-1185`) blocks tier 0 from
  `sprints_dir` outright (`blk-sprint`); tier 1 is already allowed
  (`hook_handlers.py:1196-1201`).
- The mcp-guard hook matcher (`.claude/settings.json` and `plugin/hooks/
  hooks.json`, both, line 51) is
  `mcp__clasi__create_ticket|mcp__clasi__create_sprint` — blocking
  `create_sprint` too, which the decided policy says should be allowed.
- `insert_sprint` was never covered by the matcher — an existing
  inconsistency the fix resolves as a side effect of shrinking the
  matcher (both tools become equally tier-0-legal).
- Item 6 of the issue's proposed fix (name the actual registered role in
  the block message) is **already shipped** — verified: `hook_handlers.py`'s
  block-message code (around line 1235-1244) already resolves the agent
  name from the same DB record the tier came from when
  `_tier_source_db` is true, landed by ticket 026-001. No further change
  needed for that item; do not re-implement it.

## Acceptance Criteria

- [ ] The tier-0 `blk-sprint` block (`for blk in _block_prefixes` loop
      scoped to `agent_tier in ("", "0")`) is deleted.
- [ ] The existing tier-1 `sprints_dir` allow (`agent_tier == "1"`) is
      extended to also match `agent_tier in ("", "0")` — tier 0 gets the
      same `ALLOW` for `.clasi/sprints/**` tier 1 already has.
- [ ] `handle_role_guard`'s docstring allow/block matrix is updated:
      `.clasi/sprints/**` reads `ALLOW` for tier 0.
- [ ] The mcp-guard matcher shrinks from
      `mcp__clasi__create_ticket|mcp__clasi__create_sprint` to
      `mcp__clasi__create_ticket` alone, in **both**
      `.claude/settings.json` (this repo's own installed copy) and
      `plugin/hooks/hooks.json` (the source new installs copy from).
- [ ] `create_ticket` still exits 2 for tier 0 (unchanged — ticket
      creation remains planner-owned).
- [ ] The protected-source-path block is unchanged — still `BLOCK` for
      tier 0/1.
- [ ] No change to item 6 (block-message identity) — confirm via a
      passing existing test or a quick manual check that it already
      works; do not add a second implementation.

## Implementation Plan

**Approach**: two small, mechanical edits (delete a block, widen a
condition) plus two config-file matcher edits. No new module, no new
dependency.

**Files to modify**:
- `src/clasi/hook_handlers.py` — delete the `blk-sprint` block; widen
  the tier-1 `sprints_dir` allow condition; update the docstring matrix
- `.claude/settings.json` — shrink the mcp-guard matcher
- `src/clasi/plugin/hooks/hooks.json` — shrink the mcp-guard matcher
  (same change, source of truth for new installs)

**Do not modify**: the protected-source-path block; the tier-2
ticket-state gate; any OOP/recovery/staleness gate; `handle_mcp_guard`'s
own body (the matcher change alone is sufficient — confirmed during
planning that `handle_mcp_guard` has no tool-name-specific branching of
its own, it relies entirely on which tool names the matcher routes to
it).

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is a hard block, not a silent allow. Testing
  this ticket's own change means poking at the guard that gates your own
  writes — if you hit an unexpected block while testing, that is the
  guard doing its job.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or any mechanism that
  avoids the tool the guard is watching. Reporting a block is a
  successful outcome of this ticket, not a failure.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/unit/test_hook_handlers.py -v`
- **New tests to write**: real-payload tests asserting tier 0 +
  `sprints_dir` → allow; tier 0 + `create_sprint` → allow; tier 0 +
  `create_ticket` → still block; tier 0 + protected source path → still
  block (per the project's gate-testing discipline: assert both the
  allow and the deny paths with real captured payload shapes, not just
  the allow).
- **Verification command**: the existing-tests command above, scoped to
  this ticket's module.
