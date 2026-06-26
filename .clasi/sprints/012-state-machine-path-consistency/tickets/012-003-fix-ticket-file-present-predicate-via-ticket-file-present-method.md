---
id: "012-003"
title: Fix is_ticket_file_present predicate via ticket_file_present protocol method
status: open
use-cases: [SUC-003]
depends-on: ["012-001"]
issue:
- gh-16-state-machine-predicates-read-artifact-paths-that-don-t-match-where.md
- gh-18-predicates-read-legacy-docs-clasi-bare-id-paths-while-writers-use.md
---

# 012-003: Fix is_ticket_file_present predicate via ticket_file_present protocol method

## Description

`is_ticket_file_present` in `predicates/ticket.py` currently hardcodes
`docs/clasi/sprints/{sprint_id}/tickets/{ticket_id}.md` — bare ID, wrong root,
no slug. The write side creates `<sprint-id>-<ticket-id>-<slug>.md` under
`.clasi/sprints/<sprint-id>-<slug>/tickets/`.

`ClasiStateReader` already has a private `_find_ticket_path(sprint_id, ticket_id)`
method that correctly performs slug-aware ticket discovery. This ticket exposes
that logic as a protocol-visible `ticket_file_present(sprint_id, ticket_id) -> bool`
method, then updates the predicate to call it.

(Depends on 001 for the `StateReader` protocol foundation pattern; can run
concurrently with 002 but both depend on 001.)

## Acceptance Criteria

- [ ] `StateReader` protocol has `ticket_file_present(sprint_id: str, ticket_id: str) -> bool`.
- [ ] `ClasiStateReader.ticket_file_present()` returns `self._find_ticket_path(sprint_id, ticket_id) is not None`.
- [ ] `NullStateReader.ticket_file_present()` returns False.
- [ ] `is_ticket_file_present` calls `ctx.reader.ticket_file_present(ctx.sprint_id, ctx.ticket_id)` (no hardcoded paths).
- [ ] The predicate handles both active (`tickets/`) and done (`tickets/done/`) locations — already covered by `_find_ticket_path`.
- [ ] Module docstring in `predicates/ticket.py` updated to reference `ticket_file_present` instead of `file_exists`.
- [ ] `pytest tests/unit/test_state_machine/test_predicates.py tests/unit/test_status/test_reader.py` passes.

## Implementation Plan

### Approach

Thin wrapper method that exposes `_find_ticket_path` through the protocol. The
predicate body becomes a single-line delegation.

### Files to Modify

**`clasi/state_machine/context.py`** — two additions:
1. Add to `StateReader` Protocol (after `sprint_artifact_exists`):
```python
def ticket_file_present(self, sprint_id: str, ticket_id: str) -> bool:
    """Return True iff the ticket file exists anywhere in the sprint's tickets tree.

    Searches both tickets/ and tickets/done/ using slug-aware glob,
    matching the filename pattern the write tools create.
    """
    ...
```
2. Add to `NullStateReader`:
```python
def ticket_file_present(self, sprint_id: str, ticket_id: str) -> bool:
    return False
```

**`clasi/status/reader.py`** — add method to `ClasiStateReader` (after `ticket_count`):
```python
def ticket_file_present(self, sprint_id: str, ticket_id: str) -> bool:
    """Return True iff a ticket file for ticket_id exists in the sprint's tickets tree.

    Source: filesystem. Delegates to _find_ticket_path which searches
    both tickets/ and tickets/done/ with slug-aware glob + frontmatter confirm.
    """
    return self._find_ticket_path(sprint_id, ticket_id) is not None
```
Also add `ticket_file_present | Filesystem` to the data-sources table.

**`clasi/state_machine/predicates/ticket.py`** — update `is_ticket_file_present` and docstring:
```python
"""...
StateReader methods used:
- ``ticket_file_present(sprint_id, ticket_id)`` — slug-aware ticket presence check
- ...
"""

@predicate("is_ticket_file_present")
def is_ticket_file_present(ctx: TicketContext) -> bool:
    """Return True iff the ticket file exists somewhere under the sprint's tickets/ tree."""
    return ctx.reader.ticket_file_present(ctx.sprint_id, ctx.ticket_id)
```
Remove the old two-path `active`/`done` variable construction.

### Testing Plan

**`tests/unit/test_state_machine/test_predicates.py`**:
1. Add `reader.ticket_file_present.return_value = False` to `_mock_reader` defaults.
2. Update `TestIsTicketFilePresent` to use `ticket_file_present=True/False` kwargs
   instead of `file_exists=True/False`:
```python
class TestIsTicketFilePresent:
    def test_true_when_ticket_exists(self):
        reader = _mock_reader(ticket_file_present=True)
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_ticket_file_present
        assert is_ticket_file_present(ctx) is True

    def test_false_when_ticket_missing(self):
        reader = _mock_reader(ticket_file_present=False)
        ctx = _ticket_ctx(reader=reader)
        from clasi.state_machine.predicates.ticket import is_ticket_file_present
        assert is_ticket_file_present(ctx) is False
```

**`tests/unit/test_status/test_reader.py`** — add tests:
```python
def test_ticket_file_present_true(self, reader, project):
    # Create a slugged sprint + slugged ticket file with correct frontmatter
    sprint_dir = project.sprints_dir / "001-my-sprint"
    tickets_dir = sprint_dir / "tickets"
    tickets_dir.mkdir(parents=True)
    fm_sprint = "---\nid: '001'\ntitle: My Sprint\nstatus: open\nbranch: sprint/001-my-sprint\n---\n"
    (sprint_dir / "sprint.md").write_text(fm_sprint)
    fm_ticket = "---\nid: '001-001'\ntitle: My Ticket\nstatus: open\n---\n"
    (tickets_dir / "001-001-my-ticket.md").write_text(fm_ticket)
    assert reader.ticket_file_present("001", "001-001") is True

def test_ticket_file_present_false(self, reader):
    assert reader.ticket_file_present("001", "001-001") is False
```

### Documentation Updates

Module docstring update in `predicates/ticket.py` as shown above.
