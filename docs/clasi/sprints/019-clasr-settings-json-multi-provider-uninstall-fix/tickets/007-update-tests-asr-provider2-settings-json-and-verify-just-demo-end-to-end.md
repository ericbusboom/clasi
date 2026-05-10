---
id: "007"
title: "Update tests/asr provider2 settings.json and verify just demo end-to-end"
status: todo
use-cases: [SUC-006]
depends-on: ["004", "006"]
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update tests/asr provider2 settings.json and verify just demo end-to-end

## Description

Update `tests/asr/provider2/claude/settings.json` to include `model` (overlapping with
provider1's `model`) and an additional `permissions.allow` entry, so the `just demo`
scenario actually exercises the overlapping-key bug that this sprint fixes. Without this
change, provider2 only contributes `mcpServers` (non-overlapping), and the demo does not
demonstrate the problem or prove the fix.

Then run `just demo` manually in `tests/asr/` to confirm the full multi-provider round-trip:
install both, inspect, uninstall provider2 selectively, confirm provider1's `model` and
`permissions` survive, then run `just uninstall-all` to confirm clean teardown.

Also delete the stale pre-committed `tests/asr/project/` directory artifacts (the project
directory should be created fresh by `just demo` and not committed to the repo).

## Acceptance Criteria

- [ ] `tests/asr/provider2/claude/settings.json` is updated to include both `model`
      (different value from provider1) and `mcpServers`.
- [ ] After `just install-first && just install-second`, `settings.json` contains both
      providers' `model` (provider2 wins), both providers' `mcpServers`, and provider1's
      `permissions`.
- [ ] After `just uninstall-second`, `settings.json` still exists and contains provider1's
      `model` value and `permissions` (provider2's `model` contribution is removed by deep-diff reversal).
- [ ] `just uninstall-all` leaves no `settings.json` in the project directory.
- [ ] `tests/asr/project/` is removed from git tracking (add to `.gitignore` or confirm
      already gitignored; delete committed artifacts if present).
- [ ] `uv run pytest tests/clasr/` passes after these data file changes.

## Implementation Plan

### Approach

Edit `tests/asr/provider2/claude/settings.json` to add:
```json
{
  "model": "claude-opus",
  "mcpServers": {
    "release-bot": {
      "command": "echo",
      "args": ["release-bot mcp stub"]
    }
  }
}
```
(provider1 has `"model": "sonnet"`; provider2 now has `"model": "claude-opus"` — overlapping).

Run `cd tests/asr && just demo` manually to verify the output. No automated test for
the justfile demo itself — the existing pytest integration tests cover the same scenario
programmatically.

Check whether `tests/asr/project/` is in `.gitignore`; if not, add it. Remove any
committed files from `tests/asr/project/` from git tracking (`git rm -r --cached`).

### Files to modify

- `tests/asr/provider2/claude/settings.json`: add `"model"` key.
- `.gitignore` (root): add `tests/asr/project/` if not already present.
- `tests/asr/project/` committed files: remove from git tracking.

### Testing plan

- Run `uv run pytest tests/clasr/` to confirm no regressions.
- Manually run `cd tests/asr && just demo` and verify the output shows:
  - After install: merged settings with both providers' keys.
  - After uninstall-second: provider1's `model` ("sonnet") present, provider2's gone.
- Run `just uninstall-all` to confirm clean teardown.

### Documentation updates

None.
