---
status: done
type: bug
tags:
- reliability-campaign
- phase-1
- hooks
- enforcement
sprint: 029
tickets:
- 029-010
---

# role-guard globs tickets/*.md non-recursively, so editing a done ticket is permanently blocked

## Description

The role-guard hook's ticket-state gate enumerates in-progress tickets by
globbing `tickets/*.md` **non-recursively**. Tickets that have been
relocated to `tickets/done/` are therefore invisible to it. Any edit to a
completed ticket raises a false `no ticket is in-progress` violation —
permanently, with no legitimate path.

Editing a done ticket is a normal thing to need to do. The reported case
was recording after-the-fact benchmark evidence on a completed ticket:
checking a box and citing a measured bench sequence. That is exactly the
kind of honest, post-hoc artifact correction the process should welcome,
and the guard forbids it outright.

Note the shape of the failure: it is not "the guard is too strict." It is
"the guard is wrong." There is no correct way to satisfy it, because the
condition it checks for cannot be made true — the ticket it is looking
for has, by definition, already been moved out of the directory it
searches.

## Why this is urgent now

Sprint 029's ticket 009 arms the fail-closed exception boundary, which
converts guard failures from silent allows into hard blocks. A gate that
produces unsatisfiable false violations becomes materially worse under
fail-closed semantics. This should land **before** the boundary is armed,
or at minimum in the same sprint.

It also interacts with the known guard-ordering trap already observed
three times in this campaign: programmers must check acceptance-criteria
boxes *before* flipping `status: done`, because artifact edits are
blocked afterward. That trap and this defect are the same underlying
problem seen from two angles — the gate's notion of "a ticket is in
progress" does not survive the ticket's own completion.

## Cause

The glob pattern in the ticket-state gate helper (`_get_active_tickets`
and/or its caller in `handle_role_guard`, `src/clasi/hook_handlers.py`)
is non-recursive and does not consider the `done/` subdirectory. Confirm
the exact call site before fixing; the reliability review's fail-open
inventory (docs/reviews/2026-08-reliability/03-hooks-guards.md, row 14)
touches the same helper for a different reason.

## Acceptance criteria

- [ ] Editing a ticket that lives in `tickets/done/` does not raise a
      `no ticket is in-progress` violation.
- [ ] The gate still blocks source edits when genuinely no ticket is in
      progress — the fix must not become a blanket allow. Verify with a
      real captured deny payload, per the replay corpus added in ticket
      029-008.
- [ ] A test covers the done-ticket edit case specifically, using a real
      payload shape rather than a hand-built dict.
- [ ] The related guard-ordering trap is either fixed alongside (an agent
      may edit its own ticket's body after setting `status: done`) or
      explicitly documented as still-required behavior with the reason.

## Related

- [[agents-must-report-blocks-not-route-around-them]] — the behavioral
  half of the same incident; this defect is the pressure that produced
  the workaround.
