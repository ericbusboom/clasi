---
id: '003'
title: Update sprint review tools for architecture.md
status: done
use-cases:
- SUC-016-002
depends-on:
- '001'
---

# Update sprint review tools for architecture.md

## Description

Update `review_sprint_pre_execution`, `review_sprint_pre_close`, and
`review_sprint_post_close` in `artifact_tools.py` to validate
`architecture.md` instead of `technical-plan.md`.

## Acceptance Criteria

- [ ] Pre-execution review checks `architecture.md` exists, non-draft, non-template
- [ ] Pre-close review checks `architecture.md` status
- [ ] No references to `technical-plan.md` remain in review functions

## Testing

- **Existing tests to run**: `uv run pytest tests/system/test_sprint_review.py`
- **New tests to write**: None (existing tests updated in ticket 005)
- **Verification command**: `uv run pytest`
