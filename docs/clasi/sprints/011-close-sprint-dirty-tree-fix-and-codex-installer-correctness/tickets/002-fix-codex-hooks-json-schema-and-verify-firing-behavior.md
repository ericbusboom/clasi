---
id: '002'
title: Fix .codex/hooks.json schema and verify firing behavior
status: done
use-cases:
  - SUC-003
depends-on: []
github-issue: ''
todo: codex-install-parity-and-misleading-se-pointer.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix .codex/hooks.json schema and verify firing behavior

## Description

The `.codex/hooks.json` written by `clasi install --codex` uses the wrong schema:
the current `_CLASI_STOP_HOOK` is a flat `{"command": "clasi", "args": [...]}` object.
Codex's actual schema wraps handlers in an outer object with a `"hooks"` list containing
entries with `type`, `command` (joined string), and `timeout`. The result is that the
`codex-plan-to-todo` Stop hook has never fired since sprint 010.

This ticket rewrites the hook constant and the `_write_codex_hooks` / uninstall logic
in `clasi/platforms/codex.py` to emit the correct schema. It also includes a
verification note about whether repo-local `.codex/hooks.json` fires in interactive
sessions (GitHub issue openai/codex#17532).

## Acceptance Criteria

- [x] `_CLASI_STOP_HOOK` (or the replacement constant/structure) produces the following
      exact JSON shape when serialized:
      ```json
      { "hooks": { "Stop": [ { "hooks": [ { "type": "command",
        "command": "clasi hook codex-plan-to-todo", "timeout": 30 } ] } ] } }
      ```
- [x] `"args"` key is absent from every hook handler entry in the written file.
- [x] Re-running `clasi install --codex` on a project that already has the old flat-format
      entry replaces it (not duplicates it).
- [x] `clasi uninstall --codex` removes the new-format wrapper entry; it does not error on
      a file that contains the old format.
- [x] Unit test in `tests/unit/test_platform_codex.py` round-trips the emitted JSON through
      `json.loads` and asserts the exact structure.
- [x] A code comment or docstring in `codex.py` documents the repo-local firing limitation
      (openai/codex#17532) and the manual workaround (copy to `~/.codex/hooks.json`).

## Implementation Plan

### Approach

In `clasi/platforms/codex.py`:

1. Replace `_CLASI_STOP_HOOK` (the flat dict) with a new constant representing the
   correct wrapper structure:
   ```python
   _CLASI_STOP_HOOK_WRAPPER = {
       "hooks": [
           {"type": "command", "command": "clasi hook codex-plan-to-todo", "timeout": 30}
       ]
   }
   ```

2. Rewrite `_write_codex_hooks`:
   - Read existing JSON (or start with `{}`).
   - Get the `Stop` list from `hooks`.
   - Remove any entry matching the old flat format `{"command": "clasi", "args": [...]}`.
   - Check whether the new wrapper entry is already present (compare by `hooks[0]["command"]`
     value to be resilient to minor field differences).
   - If not present, append `_CLASI_STOP_HOOK_WRAPPER`.
   - Write back.

3. Update `uninstall` / `_remove_codex_hooks` to remove the wrapper entry:
   - Identify the CLASI entry by checking `entry.get("hooks", [{}])[0].get("command") ==
     "clasi hook codex-plan-to-todo"`.
   - Remove it. Remove `Stop` key if list is empty. Remove `hooks` key if dict is empty.
   - Delete the file if the resulting dict is empty.

4. Add a docstring comment above `_write_codex_hooks` documenting:
   - The Codex hooks spec source URL.
   - The repo-local firing limitation (openai/codex#17532) and workaround.

### Files to Modify

- `clasi/platforms/codex.py` — `_CLASI_STOP_HOOK`, `_write_codex_hooks`, `uninstall`
  hooks removal section.
- `tests/unit/test_platform_codex.py` — update any assertion that matches the old flat
  hook shape; add test for exact wrapper structure round-trip; add test for backward-compat
  replacement of old-format entry.

### Testing Plan

1. `uv run pytest tests/unit/test_platform_codex.py -v` — confirm updated assertions pass.
2. `uv run pytest` — full suite regression check.

### Documentation Updates

- Code comment in `codex.py` documenting firing limitation (no separate doc file needed).
- README update is deferred to ticket 007.
