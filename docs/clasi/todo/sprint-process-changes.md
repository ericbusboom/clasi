# Sprint Process Changes

Two changes to how sprints are planned and executed.

## Architecture update moves to sprint planning

The architecture update was previously written at sprint end as a record of what changed. That position made it a recording artifact with no forcing function — it described drift after the fact rather than committing to structural intent before work started.

Moving it to the front of sprint planning makes it a planning artifact. The diff between successive architecture updates becomes the sprint's structural contract.

The post-change "what is the architecture now?" question is answered by reading the code. We don't maintain a separate snapshot document — a snapshot drifts, and once drifted, neither it nor the code can be trusted as the source of truth. The architecture update documents accumulate as a sequence of past intents (effectively ADRs at sprint granularity).

One consequence: there are now two useful diffs per sprint. The architecture diff at sprint start is the plan. The code diff at sprint end is the verification. Drift between them is informative — either implementation surfaced something the plan missed, or someone went off-script.

### New sprint planning order

1. **Sprint overview** — why and scope
2. **Use cases** — behavior, what user-visible operations
3. **Architecture update** — structural changes
4. **To-dos** — desired feature outcomes
5. **Tickets** — work units derived from the above

Architecture comes before to-dos so the to-dos don't bake in pre-architecture assumptions about how work breaks down.

## Exception cord for lower-level agents

Ticket planners and coding agents can throw an exception when they hit a wall — something they can't proceed on without overriding an upstream decision.

When they throw:

- Write the exception to the ticket: what was attempted, what failed, what the conflict is
- Exit cleanly; do not partially complete the work
- The ticket-with-exception is the carrier; no out-of-band signaling

The team lead picks up the exception and routes:

- If it affects user-visible behavior (per the use case doc), escalate to stakeholders or the developer
- If it's purely internal, loop with the architect agent and revise the structural plan

There is no formal escalation policy beyond this. The team lead reasons over the exception and decides. The use case doc anchors the user-visible-vs-internal distinction, which means it has to be precise enough to support that judgment in non-obvious cases.

### Threshold

Exceptions are for "I can't proceed without overriding an upstream decision," not "this is going to be hard." Hard work is work. The wall has to be structural.

### Calibration signal

How often exceptions get thrown is information about whether the upstream architecture step is calibrated. Frequent revisions mean the team lead is shooting from too far away — the architecture step needs more input or a different prompt. Keep the original architecture plan plus revisions when the loop runs, rather than only the final version, so this signal stays visible.
