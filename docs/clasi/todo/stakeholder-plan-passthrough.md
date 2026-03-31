---
status: pending
---

# Preserve Stakeholder's Detailed Plan Through Requirements

## Problem

When the stakeholder provides a detailed plan (e.g., a spec with sprint
breakdowns, exact messages, game rules), the requirements-narrator
currently produces only a brief and use cases. The detailed plan
document — which contains specific implementation details the agent
needs — is not preserved as a formal artifact. The agent reads it once
from the spec file but the information can get lost as context compresses.

## Proposed Changes

1. **If the stakeholder provides a detailed plan**, the requirements-narrator
   should produce a `plan.md` artifact alongside `brief.md` and `usecases.md`.
   The plan preserves the stakeholder's implementation-level detail: sprint
   breakdowns, exact user-facing messages, specific behavior rules, test
   expectations.

2. **The overview should reference the plan.** `overview.md` should note
   that a stakeholder-provided plan exists and link to it.

3. **Sprint planners should read the plan.** The dispatch template for
   sprint-planner should include `plan.md` in its context documents so
   the planner has access to the stakeholder's detailed specifications
   throughout planning, not just the abstracted brief and use cases.

## Alternative

Instead of a separate `plan.md`, the brief could include a "Detailed
Specification" section that preserves the stakeholder's plan verbatim.
This keeps the artifact count down but makes the brief longer.
