---
id: "010"
title: "Deprecate clasr/platforms/detect.py as a wrapper around registry.detect()"
status: todo
use-cases: [SUC-006]
depends-on: ["006"]
github-issue: ""
todo: ""
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Deprecate clasr/platforms/detect.py as a wrapper around registry.detect()

## Description

Replace the body of `clasr/platforms/detect.py` with a thin compatibility wrapper that delegates to `registry.detect()` and converts back to the old `dict[str, list[str]]` return format for any callers still using the old API.

The old `detect(target) -> dict[str, list[str]]` signature is preserved in the wrapper but decorated with a `DeprecationWarning`. Update `tests/clasr/test_platform_detect.py` to test the new `registry.detect()` interface directly; the compatibility path is covered by a separate test asserting the wrapper still returns the old format.

Old format: `{"claude": ["provider1"], "codex": [], "copilot": ["provider2"]}`.
New format from `registry.detect()`: `[ClaudeIntegration(), CopilotIntegration()]`.

The compatibility wrapper converts: for each integration instance returned by `registry.detect()`, look up its `id` and find providers from manifests in `target_root / ".clasr-manifest"`.

## Acceptance Criteria

- [ ] `clasr/platforms/detect.py` body replaced with compatibility wrapper.
- [ ] `detect(target)` still returns `dict[str, list[str]]` (old format) but issues `DeprecationWarning`.
- [ ] `registry.detect(target)` returns `list[IntegrationBase]` instances.
- [ ] `tests/clasr/test_platform_detect.py` updated to test `registry.detect()` primarily; old-format test retained as compatibility check.
- [ ] `uv run pytest tests/clasr/test_platform_detect.py` passes.
- [ ] `uv run pytest` green.

## Implementation Plan

### Files to Modify

- `clasr/platforms/detect.py` — replace body with wrapper.
- `tests/clasr/test_platform_detect.py` — update tests for new interface.

### Testing Plan

- `uv run pytest tests/clasr/test_platform_detect.py` — passes.
- `uv run pytest` — full suite green.

### Documentation Updates

None (deprecation noted in docstring).
