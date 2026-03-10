---
id: '005'
title: Update tests
status: done
use-cases:
- SUC-016-001
- SUC-016-002
depends-on:
- '001'
- '002'
- '003'
---

# Update tests

## Description

Update all test files to reflect the technical-plan to architecture change:

1. **`tests/system/test_sprint_review.py`** — Replace `technical-plan.md`
   refs with `architecture.md`. Update template references.
2. **`tests/system/test_artifact_tools.py`** — Update `create_sprint` tests
   to expect `architecture.md` instead of `technical-plan.md`.
3. **`tests/unit/test_mcp_server.py`** — Update tool counts and expected
   lists if tools changed.
4. **`tests/unit/test_init_command.py`** — Update expected wording.
5. Add new tests for architecture copy-on-create behavior.

## Acceptance Criteria

- [ ] All existing tests pass with the new artifact name
- [ ] New test: `create_sprint` copies architecture from previous sprint
- [ ] New test: `create_sprint` falls back to template
- [ ] No test references to `technical-plan.md` remain
- [ ] `uv run pytest` passes clean

## Testing

- **Verification command**: `uv run pytest`
