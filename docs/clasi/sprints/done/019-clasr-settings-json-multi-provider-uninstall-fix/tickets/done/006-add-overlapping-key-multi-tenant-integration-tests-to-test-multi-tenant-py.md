---
id: "006"
title: "Add overlapping-key multi-tenant integration tests to test_multi_tenant.py"
status: done
use-cases: [SUC-001, SUC-002, SUC-003, SUC-005]
depends-on: ["004"]
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add overlapping-key multi-tenant integration tests to test_multi_tenant.py

## Description

Add `TestJsonMergeUninstallOverlapping` (Section C2) to
`tests/clasr/test_multi_tenant.py` to exercise the overlapping-key uninstall scenario
that was the original bug. These tests use `make_asr_dir` from `tests/clasr/conftest.py`
with `settings_keys` that overlap between provider1 and provider2, then verify that
selective uninstall preserves the surviving provider's data.

Also add a test covering the old-format manifest fallback (SUC-005): manually inject an
old-format manifest entry (`"keys"` only, no `"contributed"`) and confirm that uninstall
completes + WARNING is emitted.

The existing Section C tests (`TestJsonMergeUninstall.test_c1_uninstall_b_leaves_a_key`
and `test_c2_file_deleted_when_both_uninstalled`) are non-overlapping key tests and must
continue to pass without modification.

## Acceptance Criteria

- [x] `TestJsonMergeUninstallOverlapping` class is added with these test methods:
- [x] `test_c2_1_uninstall_b_leaves_a_model_intact`: both providers set `model`; uninstall B
      leaves A's `model` value in `settings.json`.
- [x] `test_c2_2_uninstall_b_leaves_a_permissions_intact`: both providers set `permissions.allow`
      (different lists); uninstall B leaves A's `permissions` key intact.
- [x] `test_c2_3_uninstall_both_deletes_file`: after uninstalling B then A, `settings.json` is deleted.
- [x] `test_c2_4_old_format_manifest_fallback_emits_warning`: manually craft old-format manifest
      entry (no `"contributed"` field); call `claude_platform.uninstall()`; confirm WARNING
      on stderr and uninstall completes without error.
- [x] `test_provider_b_manifest_records_json_merged` in `TestJsonMergeInstall` is updated to also
      assert `"contributed"` is present and is a `dict` in provider_b's manifest entry.
- [x] All existing `TestJsonMergeUninstall` tests still pass.
- [x] `uv run pytest tests/clasr/test_multi_tenant.py` passes.

## Implementation Plan

### Approach

Add the new test class at the end of `tests/clasr/test_multi_tenant.py`. Use
`make_asr_dir` with `settings_keys={"model": "val", "permissions": {"allow": [...]}}` for
both providers with different values.

For the old-format test: install provider_a normally; then write a modified version of
provider_b's manifest directly (using `manifest.write_manifest`) with the `json-merged`
entry missing `"contributed"`. Call `claude_platform.uninstall(target, "provider_b")` and
capture stderr.

### Files to modify

- `tests/clasr/test_multi_tenant.py`: add `TestJsonMergeUninstallOverlapping` class; update
  one existing assertion in `TestJsonMergeInstall.test_provider_b_manifest_records_json_merged`.

### Testing plan

- Run `uv run pytest tests/clasr/test_multi_tenant.py -v` to see all tests.
- Run `uv run pytest tests/clasr/` to confirm no regressions in other test files.

### Documentation updates

None.
