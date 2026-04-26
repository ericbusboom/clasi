---
sprint: "009"
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Use Cases — Sprint 009: Multi-Sprint TODO Bug Fix

## SUC-001: Single-sprint TODO is auto-archived on ticket completion (existing behavior preserved)

**Actor**: Engineer closing a sprint  
**Trigger**: All tickets referencing a single-sprint TODO are moved to done  
**Preconditions**:
- A TODO file exists in `docs/clasi/todo/` with `status: in-progress`
- One or more tickets reference that TODO
- All referencing tickets have `completes_todo` absent or set to `true`

**Main Flow**:
1. Engineer calls `move_ticket_to_done` for the last remaining ticket referencing the TODO.
2. The tool detects that all referencing tickets are done and that none have `completes_todo: false` for that TODO filename.
3. The TODO is moved to `docs/clasi/todo/done/`.

**Postconditions**: TODO is archived. `close_sprint` completes without finding any unresolved TODOs.

**Acceptance Criteria**:
- [ ] `move_ticket_to_done` archives the TODO when all tickets are done and `completes_todo` defaults to `true`
- [ ] `close_sprint` finds no unresolved TODOs in the standard single-sprint case
- [ ] Existing test coverage for this path continues to pass

---

## SUC-002: Multi-sprint TODO survives sprint close when at least one linked ticket has `completes_todo: false`

**Actor**: Engineer closing the first sprint of a multi-sprint plan  
**Trigger**: All tickets in the sprint are moved to done, but the umbrella TODO has `completes_todo: false` on the current sprint's tickets  
**Preconditions**:
- A TODO file exists in `docs/clasi/todo/` with `status: in-progress`
- Multiple tickets across multiple sprints reference that TODO
- The tickets in the current sprint each set `completes_todo: false` for that TODO link

**Main Flow**:
1. Engineer calls `move_ticket_to_done` for each ticket in the sprint.
2. For each ticket, the tool checks `completes_todo` for the linked TODO filename.
3. Because `completes_todo: false` is set for the umbrella TODO, the tool does NOT move the TODO to `done/`.
4. Engineer calls `close_sprint`.
5. `close_sprint` detects the TODO is still in-progress but recognizes it is intentionally deferred (at least one linked ticket has `completes_todo: false`), and allows the sprint to close successfully.

**Postconditions**: Sprint closes successfully. The umbrella TODO remains in the active TODO directory for the next sprint.

**Acceptance Criteria**:
- [ ] `move_ticket_to_done` does NOT archive the TODO when any linked ticket has `completes_todo: false`
- [ ] `close_sprint` does not treat a deferred TODO as an error condition
- [ ] The umbrella TODO file is present in the active TODO directory after sprint close

---

## SUC-003: `move_ticket_to_done` respects `completes_todo` per linked TODO filename

**Actor**: Engineer completing a ticket that references multiple TODOs  
**Trigger**: A ticket with mixed `completes_todo` settings is moved to done  
**Preconditions**:
- A ticket references two TODO files: one single-sprint (`feature-a.md`) and one multi-sprint (`program-b.md`)
- The ticket's `completes_todo` map sets `feature-a.md` to `true` (or absent) and `program-b.md` to `false`

**Main Flow**:
1. Engineer calls `move_ticket_to_done`.
2. The tool inspects `completes_todo` for each linked TODO filename independently.
3. For `feature-a.md`: no `completes_todo: false` override — if all referencing tickets are done, the TODO is archived.
4. For `program-b.md`: `completes_todo: false` suppresses archival for that file regardless of ticket completion state.

**Postconditions**: `feature-a.md` is archived; `program-b.md` remains active.

**Acceptance Criteria**:
- [ ] Archival decision is made per-TODO-filename, not per-ticket
- [ ] A ticket with `completes_todo: false` for one filename does not suppress archival of other linked TODOs

---

## SUC-004: Backward compatibility — existing tickets without `completes_todo` behave as before

**Actor**: Any engineer using existing ticket files written before this sprint  
**Trigger**: `move_ticket_to_done` is called on a ticket with no `completes_todo` field  
**Preconditions**:
- Ticket frontmatter contains `todo: "some-file.md"` but no `completes_todo` field

**Main Flow**:
1. The tool reads the ticket frontmatter.
2. `completes_todo` is absent — the default (`true`) is applied for all linked filenames.
3. If all referencing tickets are done, the TODO is archived as before.

**Postconditions**: No change in behavior for existing tickets.

**Acceptance Criteria**:
- [ ] Tickets without `completes_todo` field behave identically to `completes_todo: true`
- [ ] No migration of existing ticket files is required

---

## SUC-005: Ticket template and documentation surface the new field

**Actor**: Engineer planning a new multi-sprint project  
**Trigger**: Engineer creates a new ticket or consults the SE documentation  
**Preconditions**: `completes_todo` is added to the ticket template and documented in the SE instruction

**Main Flow**:
1. Engineer reads the ticket template or software-engineering instruction.
2. Engineer sees `completes_todo` documented with its default value and its purpose.
3. Engineer sets `completes_todo: false` for tickets referencing an umbrella TODO.

**Postconditions**: Engineer can discover and correctly use the field without reading source code.

**Acceptance Criteria**:
- [ ] `completes_todo` appears in `clasi/templates/ticket.md` with a comment explaining its purpose
- [ ] `clasi/plugin/instructions/software-engineering.md` documents the field and its default
