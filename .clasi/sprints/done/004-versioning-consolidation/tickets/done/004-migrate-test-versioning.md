---
id: 004-004
title: "Migrate tests/unit/test_versioning.py \u2014 rewrite against shim"
status: done
use-cases:
- SUC-004
depends-on:
- 004-002
issue:
- migrate-clasi-versioning-to-depend-on-dotconfig.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# 004-004: Migrate tests/unit/test_versioning.py — rewrite against shim

## Description

`tests/unit/test_versioning.py` currently has ~31 patches against `clasi.versioning.*`
internals for logic that will have moved to `dotconfig.versioning` after ticket 002.
Those tests must be deleted (the logic now lives in dotconfig's own suite). Tests
for clasi-specific functions are retained and updated for any signature changes.

This ticket runs after ticket 002 (the shim must exist before tests are rewritten).

## Acceptance Criteria

- [x] `test_versioning.py` no longer patches or directly tests:
      `parse_format`, `format_has_auto`, `build_version`, `build_tag_regex`,
      `update_pyproject_version`, `update_package_json_version`, `update_version_file`,
      `create_version_tag` — these belong to dotconfig's suite.
- [x] `test_versioning.py` retains (and passes) tests for:
      `load_version_trigger`, `should_version`, `detect_version_file`,
      `read_current_version`, `VERSION_PATTERN` compat alias.
- [x] `compute_next_version` tests are retained only insofar as they test the
      clasi shim's wrapper behavior (format from `.clasi/settings.yaml`). Tests
      that simply validate the core compute logic are deleted.
- [x] Full test suite passes (`pytest`).
- [x] Coverage threshold (`fail_under = 84` in `pyproject.toml`) is either met,
      or the threshold is lowered with a comment explaining that the deleted lines
      now live in dotconfig's own test suite.

## Implementation Plan

### Approach

**Classes/tests to delete entirely** (logic in dotconfig):
- `TestParseFormat`
- `TestFormatHasAuto`
- `TestBuildVersion`
- `TestBuildTagRegex`
- `TestUpdatePyprojectVersion`
- `TestUpdatePackageJsonVersion`
- `TestUpdateVersionFile`
- `TestCreateVersionTag`

**Classes to delete or significantly trim** (logic in dotconfig):
- `TestComputeNextVersion` — delete all tests that patch `clasi.versioning._get_existing_tags`
  and `clasi.versioning.load_version_format`. Optionally retain one smoke test that
  calls `compute_next_version()` end-to-end with a real git repo (but this is a slow
  integration test; it can be skipped or deferred).

**Classes to retain** (clasi-specific):
- `TestVersionPattern` — keep, tests the compat alias
- `TestLoadVersionFormat` — keep; tests `.clasi/settings.yaml` loading
- `TestLoadVersionTrigger` — keep
- `TestShouldVersion` — keep
- `TestDetectVersionFile` — keep
- Any test class for `read_current_version` if it exists (currently tested implicitly)

**Import cleanup**: Remove imports from `clasi.versioning` that no longer exist
(e.g., `build_tag_regex`, `build_version`, `parse_format`, `format_has_auto`,
`update_package_json_version`, `update_pyproject_version`).

### Coverage Threshold

After deletion, measure the new coverage. If it drops below 84%, lower
`fail_under` in `pyproject.toml` to the new floor and add a comment:
```toml
# Lowered from 84 after sprint 004: deleted test_versioning logic
# now lives in dotconfig's own test suite.
fail_under = <new_value>
```

### Files to Modify

- `tests/unit/test_versioning.py` — large deletion, minor retention
- `pyproject.toml` — only if coverage threshold needs adjustment

### Testing Plan

1. `pytest tests/unit/test_versioning.py` — all retained tests must pass.
2. `pytest` (full suite) — no regressions, coverage threshold met or adjusted.

### Documentation Updates

None.
