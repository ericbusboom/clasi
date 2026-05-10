---
id: '002'
title: Add `exception:` frontmatter block schema to ticket template and Ticket class
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-004
- SUC-007
depends-on: []
github-issue: ''
todo: ''
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add `exception:` frontmatter block schema to ticket template and Ticket class

## Description

Define the `exception:` YAML block that exception-throwing agents write into
ticket frontmatter. This ticket adds the schema definition to the `Ticket`
class (an `exception_payload` property) so tools can read structured exception
data, and documents the schema in a comment in the ticket template.

Schema (from architecture-update.md §2):
```yaml
exception:
  thrown_by: "programmer"          # "programmer" | "sprint-planner"
  thrown_at: "2026-05-07T14:23:00Z"
  attempted: |
    ...
  conflict: "architecture-update.md §3 — ..."
  surface: "internal"              # "user-visible" | "internal"
```

No validation is enforced at read time — the `Ticket.exception_payload`
property returns the raw dict or `None` if the field is absent. Validation
happens at write time in the `throw_ticket_exception` tool (ticket 003).

## Acceptance Criteria

- [x] `Ticket.exception_payload` property exists; returns `dict | None` from
  frontmatter `exception` key.
- [x] When frontmatter has no `exception` key, `exception_payload` returns
  `None`.
- [x] The ticket template includes a commented-out example of the `exception:`
  block so authors know the schema.
- [x] `uv run pytest` passes with no regressions.

## Implementation Plan

**Files to modify**:
- `clasi/ticket.py` — add `exception_payload` property (read-only, ~5 lines)
- The ticket template file — add commented-out `exception:` block to the
  frontmatter section

**Approach**: In `ticket.py`, follow the same pattern as `use_cases`, `id`,
`title`:
```python
@property
def exception_payload(self) -> dict | None:
    val = self.frontmatter.get("exception")
    return dict(val) if isinstance(val, dict) else None
```

No existing behavior changes. The property is purely additive.

**Tests**: Unit test in `tests/unit/test_ticket.py` verifying the property
returns `None` when absent and the dict when present.

**Verification**: `uv run pytest tests/unit/test_ticket.py`
