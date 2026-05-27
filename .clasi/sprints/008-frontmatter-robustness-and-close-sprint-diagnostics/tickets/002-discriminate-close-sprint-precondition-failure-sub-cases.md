---
id: '002'
title: Discriminate close_sprint precondition failure sub-cases
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
issue: close-sprint-not-found-error-misleading.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Discriminate close_sprint precondition failure sub-cases

## Description

`_close_sprint_full`'s precondition block catches any `ValueError` from
`project.get_sprint` and returns a generic "Sprint not found in active or done
— create or restore the sprint directory" error. This misdirects the operator
when the sprint directory and `sprint.md` are present but the frontmatter is
corrupt: the directory does not need to be recreated; the frontmatter needs to
be fixed.

This ticket updates `_close_sprint_full` (in `clasi/tools/artifact_tools.py`)
to catch the three typed sprint exception classes introduced by ticket 001 and
return a specific, actionable error message for each sub-case.

## Acceptance Criteria

- [x] When `sprint.md` is present but has a malformed frontmatter fence,
      `close_sprint` returns an error with:
      - `message` naming the specific `sprint.md` file path and describing the
        parse failure.
      - `recovery.instruction` saying to fix the frontmatter in the named file
        (not to create or restore the directory).
- [x] When frontmatter parses but the `id:` field is absent or mismatched,
      `close_sprint` returns an error with:
      - `message` naming the file, the found id, and the requested id.
      - `recovery.instruction` saying to correct the `id:` field in the named
        file.
- [x] When no matching directory exists, the existing "not found — create or
      restore the directory" message is preserved unchanged.
- [x] The fallback `except ValueError` catch-all is retained for unanticipated
      sub-classes but is reached only after the three typed cases.
- [x] All existing tests pass without modification.
- [x] New unit/integration tests cover: malformed frontmatter sub-case, id
      mismatch sub-case, and genuine not-found sub-case.

## Implementation Plan

### Approach

Depends on ticket 001. The typed exception classes `SprintNotFoundError`,
`SprintFrontmatterError`, and `SprintIdMismatchError` must exist in `project.py`
before this ticket can be implemented.

Replace the single `except ValueError` block in `_close_sprint_full` with three
ordered `except` clauses, each returning a specific error JSON.

### Files to modify

**`clasi/tools/artifact_tools.py`**

Locate the precondition block at approximately lines 1141-1155:

```python
try:
    sprint = project.get_sprint(sprint_id)
    sprint_dir = sprint.path
except ValueError:
    return json.dumps({
        "status": "error",
        "error": {
            "step": "precondition",
            "message": f"Sprint '{sprint_id}' not found in active or done",
            "recovery": {"recorded": False, "allowed_paths": [], "instruction": "Create or restore the sprint directory."},
        },
        ...
    }, indent=2)
```

Replace with:

```python
from clasi.project import (
    SprintNotFoundError,
    SprintFrontmatterError,
    SprintIdMismatchError,
)

try:
    sprint = project.get_sprint(sprint_id)
    sprint_dir = sprint.path
except SprintFrontmatterError as e:
    return json.dumps({
        "status": "error",
        "error": {
            "step": "precondition",
            "message": str(e),
            "recovery": {
                "recorded": False,
                "allowed_paths": [],
                "instruction": (
                    "The sprint.md file has malformed frontmatter. "
                    "Fix the opening '---' fence in the file named in "
                    "the message, then call close_sprint again."
                ),
            },
        },
        "completed_steps": [],
        "remaining_steps": [...],
    }, indent=2)
except SprintIdMismatchError as e:
    return json.dumps({
        "status": "error",
        "error": {
            "step": "precondition",
            "message": str(e),
            "recovery": {
                "recorded": False,
                "allowed_paths": [],
                "instruction": (
                    "The sprint.md file has a missing or incorrect 'id:' field. "
                    "Correct the id field in the file named in the message, "
                    "then call close_sprint again."
                ),
            },
        },
        "completed_steps": [],
        "remaining_steps": [...],
    }, indent=2)
except (SprintNotFoundError, ValueError):
    # Sprint dir might already be archived (idempotent retry) or
    # an unanticipated ValueError sub-class.
    return json.dumps({
        "status": "error",
        "error": {
            "step": "precondition",
            "message": f"Sprint '{sprint_id}' not found in active or done",
            "recovery": {
                "recorded": False,
                "allowed_paths": [],
                "instruction": "Create or restore the sprint directory.",
            },
        },
        "completed_steps": [],
        "remaining_steps": [...],
    }, indent=2)
```

The import of the three exception classes should be added at the top of the
file or inside the function body (lazy import) — use whichever pattern the file
already uses for `project.py` imports.

### Testing plan

File: `tests/test_artifact_tools.py` (create or extend)

- `test_close_sprint_malformed_frontmatter_error`: set up a sprint directory
  with a `sprint.md` with a corrupted fence; call `close_sprint`; parse the
  JSON result; assert `status == "error"`, `error.step == "precondition"`,
  `error.message` contains the file path, and `error.recovery.instruction`
  mentions fixing the frontmatter (not "create or restore").
- `test_close_sprint_id_mismatch_error`: set up a sprint directory with valid
  frontmatter but `id: "999"`; call `close_sprint("001")`; assert the message
  names the id mismatch and the instruction mentions correcting the `id:` field.
- `test_close_sprint_not_found_error`: no sprint directory; call
  `close_sprint("001")`; assert the existing "not found" message and "create or
  restore" instruction are returned unchanged.

### Documentation updates

None required. The changed behavior is observable only through the MCP/CLI
response JSON, which is not separately documented.
