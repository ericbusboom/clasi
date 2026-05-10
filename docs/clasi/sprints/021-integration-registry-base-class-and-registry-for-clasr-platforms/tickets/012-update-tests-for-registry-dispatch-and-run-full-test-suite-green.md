---
id: "012"
title: "Update tests for registry dispatch and run full test suite green"
status: todo
use-cases: [SUC-002, SUC-006, SUC-007, SUC-008, SUC-009]
depends-on: ["011"]
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update tests for registry dispatch and run full test suite green

## Description

Final validation ticket. Audit all test files in `tests/clasr/` to ensure they use the class-based API exclusively (no remnant shim imports, no references to the old `detect()` dict format). Add any missing coverage identified during the audit. Run the full test suite and confirm it is green.

Specific checks:
- `test_platform_claude.py`, `test_platform_codex.py`, `test_platform_copilot.py` — use class API, no shim imports.
- `test_platform_detect.py` — tests `registry.detect()` new interface; compatibility wrapper path covered.
- `test_integration_contract.py` — 4 parametrized runs (claude, codex, copilot, cursor), all pass.
- `test_cli.py` — covers `clasr platforms list` output and registry-dispatch install/uninstall.
- `test_three_platform_roundtrip.py` — still passes (uses install+uninstall for all three original platforms).

Also confirm mypy passes on the full `clasr/` package with no `IntegrationBase` violations.

## Acceptance Criteria

- [ ] All test files use class-based API exclusively.
- [ ] `test_integration_contract.py` shows 4 runs, all green.
- [ ] `test_cli.py` covers `clasr platforms list`.
- [ ] `test_three_platform_roundtrip.py` passes.
- [ ] `mypy clasr/` passes clean.
- [ ] `uv run pytest` — full suite green, zero failures, zero errors.

## Implementation Plan

### Files to Review/Modify

- `tests/clasr/test_platform_claude.py` — audit for shim usage.
- `tests/clasr/test_platform_codex.py` — audit.
- `tests/clasr/test_platform_copilot.py` — audit.
- `tests/clasr/test_platform_detect.py` — confirm new-interface coverage.
- `tests/clasr/test_integration_contract.py` — confirm 4 parametrized runs.
- `tests/clasr/test_cli.py` — confirm `platforms list` coverage.
- `tests/clasr/test_three_platform_roundtrip.py` — confirm passes.

### Testing Plan

- `uv run pytest` — zero failures required.
- `mypy clasr/` — zero errors required.

### Documentation Updates

Update `clasr/README.md` to document the `IntegrationBase` hierarchy and `INTEGRATION_REGISTRY` for contributors who want to add a new platform.
