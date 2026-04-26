---
id: '003'
title: Drop misleading /se line from CLASI section template
status: done
use-cases:
  - SUC-006
depends-on: []
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Drop misleading /se line from CLASI section template

## Description

`clasi/templates/clasi-section.md` ends with:

```
Available skills: run `/se` for a list.
```

This line misdirects agents on both Claude Code and Codex. `/se` is a user-facing
dispatcher that shows an 8-row high-traffic command table — it is not a skill enumerator.
Both platforms auto-discover skill files at session start (`.claude/skills/` and
`.agents/skills/` respectively), so the line is redundant and misleading.

Remove the line. The CLASI section's entry-point sentence is sufficient.

## Acceptance Criteria

- [x] `clasi/templates/clasi-section.md` does not contain the text
      `"Available skills: run"` or `"/se"`.
- [x] Unit test in `tests/unit/test_init_command.py` (or a test of the rendered template
      output) asserts that the CLASI section does not contain the `/se` substring.
- [x] Unit test in `tests/unit/test_platform_codex.py` asserts the same for the Codex
      AGENTS.md CLASI section output.
- [x] All existing tests pass after the change.

## Implementation Plan

### Approach

This is a one-line template edit:

1. Remove the line `"Available skills: run `/se` for a list."` from
   `clasi/templates/clasi-section.md`. The file should end after the entry-point sentence.

2. Update `tests/unit/test_init_command.py`: find any assertion that checks the CLASI
   section content and add `assert "/se" not in clasi_section_content` (or equivalent).

3. Update `tests/unit/test_platform_codex.py`: find any AGENTS.md content assertion and
   add `assert "/se" not in agents_md_content`.

### Files to Modify

- `clasi/templates/clasi-section.md` — remove the `/se` line.
- `tests/unit/test_init_command.py` — add content assertion.
- `tests/unit/test_platform_codex.py` — add content assertion.

### Testing Plan

1. `uv run pytest tests/unit/test_init_command.py tests/unit/test_platform_codex.py -v`
2. `uv run pytest` — full suite regression.

### Documentation Updates

None. The template change is self-explanatory.
