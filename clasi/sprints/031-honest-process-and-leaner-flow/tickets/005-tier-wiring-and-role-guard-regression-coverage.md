---
id: '005'
title: Tier wiring and role-guard regression coverage
status: open
use-cases:
- SUC-005
depends-on:
- '003'
- '004'
github-issue: ''
issue:
- sprint-planner-tier-1-may-never-be-set-verify-clasi-agent-tier-wiring.md
- role-guard-blocks-plan-mode-plans-dir.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Tier wiring and role-guard regression coverage

## ⚠ This ticket writes regression tests for behavior that ALREADY WORKS — it is not a bugfix

Both issues this ticket closes turned out, on investigation during
sprint 031 planning, to describe already-fixed or already-working
production behavior with no regression test pinning it. **Verify this
for yourself before writing anything** — do not take this ticket's word
for it either; the point is that the *test* is what's missing, not that
the behavior needs fixing. Do not go looking for a defect that isn't
there and "fix" something that doesn't need it.

**Live evidence gathered during sprint 031's own planning** (this
repo's own `.clasi/log/hooks.log` and `active_agents` table, queried
directly, not from memory):

- `grep -c "tier=1" .clasi/log/hooks.log` → 79 occurrences. Two are from
  the same day this sprint was planned: the sprint-planner dispatches
  that created sprints 031 and 032 themselves both resolved `tier=1(db)`
  and successfully wrote `clasi/sprints/031.../sprint.md` and
  `clasi/sprints/032.../sprint.md` respectively — `role-guard 0 tier-1
  ... match=clasi/sprints/`.
- The `active_agents` table during planning showed a live row for the
  currently-dispatched sprint-planner (`tier=1`), registered by
  `handle_subagent_start`, not purged by `clear_stale_agents`'s sweep
  (confirmed by reading the call order in `hook_handlers.py`:
  `clear_stale_agents` runs, THEN `register_active_agent` — the sweep
  cannot purge a row it hasn't written yet).
- The DB-backed `get_active_tier` fallback (`019-003`) is therefore
  load-bearing and correct for the sprint-planner path, contrary to the
  issue's original "planner has never resolved tier-1" framing — that
  framing was accurate against an *older* log window, not the current
  code.
- Separately, `handle_role_guard`'s outside-root allow
  (`hook_handlers.py`, the `if file_path and Path(file_path).is_absolute():
  ... _exit(0, "outside-root")` branch, plus the narrower
  `claude-plans-dir` check just above it) already covers
  `~/.claude/plans/**` and every other outside-root path, for every
  tier — landed by sprint 024 ticket 003 and generalized by sprint
  026/001 (confirmed via `git log -S`).

**What this ticket actually does**: write the tests that were missing,
using real dispatches and real payloads, not fixture inserts or
hand-set env vars — per each issue's own stated verification criteria.
If, while writing these tests, you find a genuine failure, stop and
report it rather than silently patching around it — that would mean
this ticket's premise (based on live evidence gathered during planning)
was wrong for your environment, which is itself worth surfacing, not
quietly absorbing.

## Acceptance Criteria

- [ ] A test dispatches a **real** sprint-planner (via the `Agent` tool
      or the project's existing real-dispatch test harness — not a
      fixture insert, not a hand-set `CLASI_AGENT_TIER` env var) and
      asserts it writes `clasi/sprints/**` successfully with no OOP flag
      active, and that `hooks.log`/the decision trail shows reason
      `tier-1`.
- [ ] A test dispatches a real programmer and asserts it still resolves
      `tier-2` (regression guard — this must not break).
- [ ] A test confirms team-lead (unresolved/tier-0) is still blocked
      from `clasi/sprints/**` and source paths — the fix must not make
      the unresolved case permissive.
- [ ] Parametrized real-payload tests assert a tier-0 write to
      `~/.claude/plans/<name>.md` and to an arbitrary outside-root path
      (e.g. `~/Desktop/x.md`) both exit 0.
- [ ] No production code changes as part of this ticket. If your
      investigation finds one is actually needed, stop and report rather
      than making it — that is new information this planning pass did
      not have.

## Implementation Plan

**Approach**: real-dispatch and real-payload tests only.

**Depends on tickets 003 and 004 (hard)**: this ticket's real-dispatch
test asserts a tier-0 write to `sprints_dir` is still blocked in one
case and a tier-0 write elsewhere is allowed in another — those
assertions are against ticket 003's post-relaxation policy. Sequencing
this ticket after 003/004 avoids writing a test against a policy that's
about to change out from under it; it also lets this ticket's
write-scope assertions reuse ticket 004's discoverability output as a
secondary check that the summary text matches actual enforcement.

**Files to modify**:
- `tests/unit/test_hook_handlers.py` or a new
  `tests/system/test_real_dispatch_tier_resolution.py` — the real
  sprint-planner/programmer dispatch tests
- `tests/unit/test_hook_handlers.py` — the parametrized outside-root/
  plans-dir tests

**Do not modify**: `hook_handlers.py`, `state_db.py`, or any production
module — see the acceptance criteria's explicit "no production code
changes" bullet.

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
  `uv run pytest tests/unit/test_hook_handlers.py tests/unit/test_hook_payload_replay.py -v`
- **New tests to write**: see Acceptance Criteria above — real-dispatch
  tier-1/tier-2/unresolved-tier tests, real-payload outside-root/
  plans-dir tests.
- **Verification command**: the existing-tests command above plus the
  new test file(s), scoped to this ticket's modules.
