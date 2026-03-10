---
id: '002'
title: Update create_sprint to copy architecture doc
status: done
use-cases:
- SUC-016-001
depends-on:
- '001'
---

# Update create_sprint to copy architecture doc

## Description

Modify `create_sprint()` and `insert_sprint()` in `artifact_tools.py` to:

1. Look for the most recent `architecture-NNN.md` in `docs/plans/architecture/`
2. Copy it into the new sprint directory as `architecture.md`
3. If none exists, create `architecture.md` from the new template
4. Stop creating `technical-plan.md`

Also update references to `technical-plan.md` in the sprint ID update logic.

## Acceptance Criteria

- [ ] `create_sprint` copies previous architecture doc when one exists
- [ ] `create_sprint` uses template when no previous architecture exists
- [ ] `create_sprint` no longer creates `technical-plan.md`
- [ ] `insert_sprint` has same behavior
- [ ] Sprint ID references updated in `architecture.md`

## Testing

- **Existing tests to run**: `uv run pytest tests/system/`
- **New tests to write**: Test copy behavior, test template fallback
- **Verification command**: `uv run pytest`
