---
sprint: "018"
---

# Use Cases — Sprint 018: Lower-agent exception protocol

## SUC-001: Programmer agent encounters a structural wall and throws an exception

**Actor**: Programmer agent  
**Trigger**: While executing a ticket, the programmer agent reaches a point
where proceeding requires overriding an architecture decision it cannot change.

**Preconditions**:
- The ticket is `in-progress`.
- The programmer agent has determined the blocker is structural (an upstream
  architecture or use-case decision), not merely difficult implementation work.

**Main flow**:
1. The programmer agent recognizes the structural conflict (threshold: "I cannot
   proceed without overriding an upstream decision").
2. The agent writes a structured `exception:` block to the ticket's YAML
   frontmatter: `thrown_by`, `thrown_at`, `attempted`, `conflict`, `surface`.
3. The agent updates the ticket status to `exception`.
4. The agent exits cleanly without partially completing the work.

**Postconditions**:
- The ticket file contains the exception block in frontmatter.
- The ticket status is `exception`.
- No out-of-band signaling has occurred; the ticket is the sole carrier.

**Out of scope**: Automated detection of structural walls; agent judgment about
what constitutes "hard work" vs. a structural blocker.

---

## SUC-002: Sprint-planner agent throws an exception during detail planning

**Actor**: Sprint-planner agent  
**Trigger**: While authoring `architecture-update.md` or creating tickets, the
sprint-planner encounters a conflict with an upstream decision that it cannot
resolve.

**Preconditions**:
- The sprint is in `planning-docs` or `ticketing` phase.
- The conflict is structural — not ambiguity resolvable via design judgment.

**Main flow**:
1. The sprint-planner writes the exception payload to the relevant planning
   artifact (or to a designated exception record in the sprint directory).
2. The sprint-planner sets ticket status to `exception` if a ticket is the
   appropriate carrier; otherwise surfaces the exception inline in its return
   text to the team-lead.
3. The sprint-planner exits without leaving partial artifacts in an
   inconsistent state.

**Postconditions**:
- The exception payload is in a defined location (ticket or sprint-level note).
- The team-lead can read the exception without requiring out-of-band context.

---

## SUC-003: Team-lead receives an exception and routes it

**Actor**: Team-lead  
**Trigger**: A lower-level agent (programmer or sprint-planner) has set a
ticket to `exception` status.

**Preconditions**:
- At least one ticket has status `exception`.
- The ticket contains a well-formed `exception:` frontmatter block.

**Main flow**:
1. The team-lead reads the exception payload from the ticket frontmatter.
2. The team-lead consults `usecases.md` to determine whether the conflict
   affects user-visible behavior.
3. **User-visible path**: The team-lead escalates to the stakeholder/developer
   with a clear description of the conflict and what decision is needed.
4. **Internal path**: The team-lead loops with the sprint-planner to revise the
   `architecture-update.md`, resolving the conflict without stakeholder input.
5. After resolution, the team-lead either re-opens the ticket (clears exception
   status) or creates a revised ticket.

**Postconditions**:
- The exception is resolved or explicitly escalated.
- No exception ticket is silently abandoned.

**Out of scope**: Formal escalation policies beyond team-lead reasoning;
automated routing; user-facing notification systems.

---

## SUC-004: User-visible vs. internal routing decision uses use-case doc as anchor

**Actor**: Team-lead  
**Trigger**: During exception routing (SUC-003), the team-lead must determine
whether the conflict is user-visible.

**Preconditions**:
- `usecases.md` for the sprint exists and is sufficiently precise.
- The exception payload's `surface` field identifies the affected concern.

**Main flow**:
1. The team-lead reads the `surface` field of the exception payload.
2. The team-lead cross-references `surface` against `usecases.md` use-case
   descriptions.
3. If the surface maps to a user-visible behavior (an actor, trigger, or
   postcondition in the use cases), the exception is classified as
   user-visible.
4. If the surface is purely structural (module boundary, dependency direction,
   internal data model), it is classified as internal.
5. The classification drives the routing choice per SUC-003.

**Postconditions**:
- The routing decision is traceable to a use-case entry.

---

## SUC-005: Architecture revision loop preserves original plus all revision artifacts

**Actor**: Sprint-planner (during architecture revision triggered by an exception)  
**Trigger**: An exception resolves via an internal loop that requires revising
`architecture-update.md`.

**Preconditions**:
- The sprint is in `architecture-review` or later phase.
- An exception has been classified as internal (SUC-003 step 4).
- The team-lead has dispatched the sprint-planner to revise the architecture.

**Main flow**:
1. The sprint-planner reads the current `architecture-update.md`.
2. The sprint-planner writes the revision as `architecture-update-r1.md`
   (subsequent revisions: `-r2.md`, `-r3.md`, etc.).
3. The original `architecture-update.md` is NOT overwritten or deleted.
4. The revised document becomes the active planning artifact for subsequent
   tickets; the original and intermediate revisions remain as historical record.

**Postconditions**:
- The sprint directory contains `architecture-update.md` (original) and one or
  more `architecture-update-rN.md` files (revisions).
- The calibration signal is preserved: reviewers can see how many revision
  cycles the sprint required.

---

## SUC-006: Calibration signal informs upstream planning quality

**Actor**: Team-lead / stakeholder (post-sprint review)  
**Trigger**: Sprint retrospective or ongoing sprint monitoring.

**Preconditions**:
- One or more sprints have completed with exception artifacts present.

**Main flow**:
1. A reviewer counts revision artifacts (`architecture-update-rN.md` files)
   across recent sprints.
2. High revision counts signal that architecture planning is too coarse or
   insufficiently grounded.
3. The signal informs decisions about the sprint-planner agent prompt,
   architecture-authoring skill guidance, or input quality for future sprints.

**Postconditions**:
- No automated action is required; the artifacts themselves are the signal.

---

## SUC-007: Exception payload written atomically via MCP tool

**Actor**: Programmer agent or sprint-planner agent  
**Trigger**: An exception is being thrown per SUC-001 or SUC-002.

**Preconditions**:
- A CLASI MCP tool (`throw_ticket_exception`) is available.

**Main flow**:
1. The agent calls `throw_ticket_exception(path, thrown_by, attempted,
   conflict, surface)`.
2. The tool writes the `exception:` YAML block to the ticket's frontmatter.
3. The tool transitions the ticket status to `exception`.
4. The tool returns confirmation with the ticket path and new status.

**Postconditions**:
- The exception payload and status transition happen in one atomic operation.
- The agent does not need to call `update_ticket_status` separately.
