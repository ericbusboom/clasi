---
id: '001'
title: Ensure log-dir gitignore on runtime hook_handlers mkdir
status: done
use-cases:
- SUC-016-002
- SUC-016-003
depends-on: []
github-issue: ''
issue: gh-15-clasi-must-gitignore-docs-clasi-log-transcripts-contain-live-secrets.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Ensure log-dir gitignore on runtime hook_handlers mkdir

## Description

`clasi/hook_handlers.py` creates the log directory at runtime (`log_dir.mkdir(...)`) in
two places but does not write a `.gitignore` afterward. If the log directory is first
created by a hook invocation (rather than by `clasi init`), it exists without gitignore
protection until `init` is manually run. This matches the confirmed incident pattern from
`gh-15`.

`clasi/init_command.py` already handles the init-time case correctly (lines 212–215). This
ticket closes the runtime gap in `hook_handlers.py`.

## Acceptance Criteria

- [x] `clasi/hook_handlers.py` contains a module-level helper `_ensure_log_gitignore(log_dir: Path) -> None` that writes `<log_dir>/.gitignore` with content `*\n!.gitignore\n` if the file does not already exist.
- [x] `_ensure_log_gitignore` is called immediately after every `log_dir.mkdir(...)` call in `hook_handlers.py` (currently two call sites: lines ~61 and ~315).
- [x] If `.gitignore` already exists in the log directory, `_ensure_log_gitignore` does not overwrite it (idempotent).
- [x] New unit tests in `tests/unit/test_hook_handlers.py` (or a new `test_hook_handlers_gitignore.py`) verify that after a hook invocation that creates the log directory, the `.gitignore` is present with correct content.
- [x] `uv run pytest` is green.

## Implementation Plan

### Approach

Add a single helper to `hook_handlers.py` and call it at both `mkdir` sites. This is a
pure additive change — no existing behavior changes.

### Files to Modify

- `clasi/hook_handlers.py`
  - Add `_ensure_log_gitignore(log_dir: Path) -> None` near the top of the module (after
    imports, before `_log_hook_event`).
  - At line ~61 (inside `_log_hook_event`): add `_ensure_log_gitignore(log_dir)` after
    `log_dir.mkdir(parents=True, exist_ok=True)`.
  - At line ~315 (inside `_get_sprint_context`): add `_ensure_log_gitignore(log_base)`
    after `log_base.mkdir(parents=True, exist_ok=True)`.

### Helper implementation sketch

```python
def _ensure_log_gitignore(log_dir: Path) -> None:
    """Write a .gitignore in log_dir if one does not already exist."""
    gitignore = log_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*\n!.gitignore\n", encoding="utf-8")
```

### Testing Plan

Locate or extend the hook handler test fixture in `tests/unit/test_hook_handlers.py`. Add
test cases:

1. `test_ensure_log_gitignore_creates_file` — call `_ensure_log_gitignore` on a fresh
   temp directory; assert `.gitignore` exists with `*` and `!.gitignore` in content.
2. `test_ensure_log_gitignore_idempotent` — write a custom `.gitignore` first, call the
   helper, assert original content is preserved.
3. Integration: mock `get_project()` to return a project pointing at a temp dir; trigger
   the hook event that creates the log dir; assert `.gitignore` is present.

### Documentation Updates

None required. The architecture update already documents this change.
