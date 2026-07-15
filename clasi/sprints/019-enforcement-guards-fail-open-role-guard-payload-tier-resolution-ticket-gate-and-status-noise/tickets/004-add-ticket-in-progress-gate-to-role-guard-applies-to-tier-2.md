---
id: '004'
title: Add ticket-in-progress gate to role-guard (applies to tier 2)
status: open
use-cases: [SUC-004]
depends-on: ['001', '002', '003']
github-issue: ''
issue: enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add ticket-in-progress gate to role-guard (applies to tier 2)

## Description

No gate anywhere in CLASI checks ticket state. `role-guard` checks
role/tier only, and tier 2 (programmer) is allowed to write anywhere —
so a programmer writing with no in-progress ticket (the exact failure
that let `radio-robot-elite` sprint 101 land eight untracked commits) is
permitted even after tickets 001-003 fix the payload and tier-resolution
bugs.

Add a ticket-state gate to `handle_role_guard`: block Edit/Write/MultiEdit
calls to source/test/config paths when a sprint execution lock is held,
zero tickets in that sprint are `status: in-progress`, and no OOP flag is
set (via `_oop_active()` from ticket 002) — applying to **tier 2 as
well**. Reuse the existing `_get_sprint_context()` (~line 318) and
`_get_active_tickets()` (~line 363) helpers already present in
`hook_handlers.py` — do not reimplement sprint/ticket lookup.

The existing early return `if agent_tier == "2": _exit_hook(..., 0,
"tier-2")` (line 166-167) must move to AFTER this new check, not before
it — currently it exits before any ticket-state logic could run, which
is exactly why tier 2 has no gate today.

**⚠️ BOOTSTRAP RISK — read before starting this ticket.** This ticket,
combined with ticket 001 (payload fix), makes `role-guard` fully live and
enforcing for the very first time in this repository's history. Tickets
001-003 landed real logic changes but role-guard's actual blocking
behavior for tier 0/1 was already restored by ticket 001 alone; THIS
ticket is what makes the block apply to tier 2 (programmers) as well —
meaning **every ticket that executes after this one in this same sprint,
including the remaining tickets in this sprint's own execution, is
subject to the gate for the first time.** A programmer implementing
ticket 005 (or any ticket after this one) will be blocked from writing
source unless its ticket is `status: in-progress` — which it will be
under normal `execute-ticket` skill flow, so no special action should be
needed. But if a programmer working on a later ticket in this sprint
unexpectedly hits a block it doesn't understand:
1. Confirm the ticket it is executing is actually marked
   `status: in-progress` (via `update_ticket_status`, not just assigned).
2. If something is genuinely broken in the gate logic itself (not a
   process gap), the sanctioned escape is `.clasi/oop` — do NOT invent a
   workaround, do NOT hand-edit source outside the ticket flow to "fix"
   the block. Set the flag, proceed, and flag the gate bug for
   follow-up; remove the flag when done.
This note exists so a programmer hitting this for the first time
recognizes it immediately instead of treating it as a mysterious new
failure — this is a documented, expected consequence of this ticket
landing, not a regression.

Depends on ticket 001 (payload parsing must work for any of this logic to
be reachable), ticket 002 (the gate's own OOP bypass must use the shared
`_oop_active()` helper, not a fifth ad hoc check), and ticket 003 (the
gate's tier-2 determination must use the fixed, caller-keyed tier
resolution — applying a ticket gate on top of an arbitrary tier lookup
would misapply the gate to the wrong agent).

Root cause reference: `clasi/issues/enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md`
defect 6 ("no gate on ticket state at all").

## Acceptance Criteria

- [ ] New check in `handle_role_guard`: if an execution lock is held
      (via `_get_sprint_context()`) and `_get_active_tickets()` returns
      an empty list for that sprint, and `_oop_active()` is `False`,
      block the write (exit 2) with a clear stderr message naming the
      two exits (start/resume a ticket via the execute-ticket flow, or
      set `.clasi/oop`).
- [ ] This check applies REGARDLESS of tier, including tier 2. The
      `if agent_tier == "2": allow` early return is moved to after this
      new check, not before it.
- [ ] If no execution lock is held (no sprint executing), this gate does
      not trigger — existing tier-based rules apply unchanged. (A sprint
      in `planning-docs`/`ticketing`/etc. with no lock is not this
      failure mode.)
- [ ] If at least one ticket is `in-progress`, the write proceeds to
      existing tier-based scope checks (this gate does not further
      restrict which files a tier-2 agent may write — only whether ANY
      ticket is in-progress at all).
- [ ] Test: sprint executing (lock held) + zero in-progress tickets +
      tier 2 + source-path write → exit 2.
- [ ] Test: sprint executing + one in-progress ticket + tier 2 +
      source-path write → exit 0.
- [ ] Test: sprint executing + zero in-progress tickets + tier 2 +
      `.clasi/oop` present → exit 0 (OOP bypass still works for this
      gate).
- [ ] Test: no execution lock held + tier 2 + source-path write → exit 0
      (gate does not apply when no sprint is executing).
- [ ] Test: sprint executing + zero in-progress tickets + tier 0/1 +
      source-path write → exit 2 (gate applies to all tiers, verify it's
      not accidentally tier-2-only).

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_hook_handlers.py -v`
  (full file — this changes early-return ordering that other tests may
  depend on).
- **New tests to write**: the five scenarios listed in Acceptance
  Criteria above, using `_get_sprint_context()`/`_get_active_tickets()`
  fixtures (real sprint/ticket directory structures in a temp project,
  not mocks of the helpers themselves — this exercises the actual
  frontmatter-reading logic those helpers already have, consistent with
  the sprint's "no hand-built fixtures that bypass real logic" standard).
- **Verification command**: `uv run pytest tests/unit/test_hook_handlers.py -v`
