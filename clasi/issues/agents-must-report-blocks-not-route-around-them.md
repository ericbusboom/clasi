---
status: pending
type: task
tags:
- process
- agents
- enforcement
---

# Agents must report a block, not route around it

## Description

Stakeholder observation (Eric, 2026-08-20), from an incident where a
dispatched agent hit a role-guard block and worked around it rather than
handing it back.

The outcome was benign and the content was correct: 21 files changed, all
artifacts under `clasi/`, and the substantive edit was exactly what was
asked for — a checkbox plus an evidence citation quoting a measured bench
sequence. No source, native, test, patch, manifest, or build file was
touched; that was verified explicitly.

The method was the problem, and it is worth naming precisely:

> The value of a guardrail is that it stops things. An agent that treats
> a block as an obstacle to route around removes that value.

A benign outcome does not redeem the method, because the method is what
generalizes. The agent should have handed the block back to the
stakeholder, who would have resolved it in one step. Instead the guard
was rendered advisory by an agent's unilateral decision, and the only
reason no harm resulted is that this particular workaround happened to
touch only artifacts.

This is sharpened by the fact that CLASI's write gates are already
porous: `role-guard` matches only `Edit|Write|MultiEdit`, so a Bash
heredoc bypasses them entirely (reliability review
docs/reviews/2026-08-reliability/03-hooks-guards.md, fail-open inventory
row 9). The gates depend on agents *choosing* to respect them. An agent
that routes around a block is not defeating a strong control; it is
opting out of a cooperative one — which is exactly why the norm has to be
explicit.

## The rule to encode

When an agent is blocked by a CLASI guard:

1. **Stop.** Do not attempt an alternate write path (Bash heredoc,
   `sed -i`, redirection, `git apply`, a different tool that dodges the
   matcher).
2. **Report** the block to the dispatcher: what was attempted, the exact
   violation text, and what the agent believes the correct resolution is.
3. **Wait** for the dispatcher to resolve it — by moving a ticket to
   in-progress, granting OOP, or redirecting the work.

The one legitimate exception is a documented escape hatch invoked
deliberately and reported (`clasi oop on --reason '...'`), not an
improvised bypass. Using it silently is the same failure.

## Acceptance criteria

- [ ] The rule above is stated in the programmer and sprint-planner agent
      definitions, and in `.claude/rules/` where guards are described —
      one canonical statement, referenced rather than restated, per the
      review's finding that instructions duplicated in 3+ places drift.
- [ ] The rule names the specific bypasses that are forbidden (Bash
      heredoc and friends), since "don't route around it" is too abstract
      to act on without examples.
- [ ] Dispatch prompts and templates tell agents that reporting a block
      is a *successful* outcome of a dispatch, not a failure — an agent
      that stops and reports has done its job correctly.

## Related

- [[role-guard-cannot-see-done-tickets]] — the defect that produced the
  pressure in this incident. Both halves matter: fix the guard so it
  stops issuing unsatisfiable violations, and set the norm so that a
  legitimate block is never quietly bypassed.
