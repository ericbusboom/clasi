---
id: '011'
title: Remove module-level shims and confirm full registry dispatch end-to-end
status: done
use-cases:
- SUC-003
- SUC-004
- SUC-005
- SUC-007
depends-on:
- '007'
- 009
- '010'
github-issue: ''
todo: ''
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove module-level shims and confirm full registry dispatch end-to-end

## Description

Remove the module-level `install()` and `uninstall()` shim functions from `claude.py`, `codex.py`, and `copilot.py`. The shims were kept for backward compatibility during the conversion phase; at this point `cli.py` uses the registry and the existing test files have been updated. Removing the shims completes the migration and confirms the class-based API is the sole entry point.

After shim removal, update any remaining test helpers that call the module-level functions directly (e.g., `from clasr.platforms.claude import install`) to use the class API instead (`ClaudeIntegration().install(...)`).

Verify that an end-to-end install + uninstall cycle through the CLI (using `clasr install --claude --codex --copilot --cursor ...`) completes cleanly with no legacy import paths.

## Acceptance Criteria

- [x] `claude.py`, `codex.py`, `copilot.py` have no module-level `install()` or `uninstall()` free functions.
- [x] All three modules export only `ClaudeIntegration`, `CodexIntegration`, `CopilotIntegration` classes (plus private helpers).
- [x] All test files that previously imported the free functions are updated to use class API.
- [x] `uv run pytest` green — no import errors, no broken references.
- [x] `clasr install --claude --codex --copilot --source ... --provider ...` completes end-to-end without errors.

## Implementation Plan

### Files to Modify

- `clasr/platforms/claude.py` — remove shim functions.
- `clasr/platforms/codex.py` — remove shim functions.
- `clasr/platforms/copilot.py` — remove shim functions.
- Any test file importing shim-based free functions — update to class API.

### Testing Plan

- `uv run pytest` — full suite green.
- Manual CLI smoke test with a real source directory.

### Documentation Updates

None.
