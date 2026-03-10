---
id: "006"
title: "Sync project AGENTS.md with updated agents-section.md"
status: todo
use-cases: [SUC-015-001]
depends-on: ["001"]
---

# Sync project AGENTS.md with updated agents-section.md

## Description

After ticket 001 completes the agents-section.md rewrite, copy the updated
CLASI block into this project's own `AGENTS.md`. The content between
`<!-- CLASI:START -->` and `<!-- CLASI:END -->` should match the template.

**File**: `AGENTS.md`

## Acceptance Criteria

- [ ] AGENTS.md CLASI block matches agents-section.md template exactly
- [ ] No content outside the CLASI block is modified

## Testing

- **Existing tests to run**: `uv run pytest tests/`
- **New tests to write**: None (documentation sync)
- **Verification command**: `uv run pytest`
