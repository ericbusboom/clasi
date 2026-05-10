---
id: '001'
title: Add _deep_diff and _reverse_diff helpers to clasr/merge.py
status: todo
use-cases: [SUC-001, SUC-002, SUC-004]
depends-on: []
github-issue: ''
todo: clasr-settings-json-multi-provider-uninstall-overlapping-top-level-keys.md
completes_todo: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add _deep_diff and _reverse_diff helpers to clasr/merge.py

## Description

Add two private helper functions to `clasr/merge.py` that implement the deep-diff
algorithm for precise per-provider contribution tracking. These are pure dict operations
with no file I/O and no imports outside the stdlib.

The root problem: `merge_json_files` currently returns `list(incoming.keys())` — a flat
list of top-level key names. On uninstall, the platform module pops those entire top-level
keys, wiping both providers' data for any key they share. The fix records the exact nested
contribution so only the contributing provider's leaves are removed.

`_deep_diff(base, overlay) -> dict`: returns the sub-tree of `overlay` that contributes
new or changed values relative to `base`.
- Key absent from base: include full value.
- Both dicts: recurse; include only non-empty sub-diffs.
- Scalar/list/type-mismatch: include overlay value only if it differs from base; omit if equal.

`_reverse_diff(current, diff) -> dict`: returns a copy of `current` with the leaves
recorded in `diff` removed.
- Both dicts: recurse; if recursion yields empty dict, remove the key from current.
- Otherwise: delete `current[k]` entirely (no element-level list subtraction).
- Keys absent from `current`: silently skip.
- Neither input is mutated.

## Acceptance Criteria

- [ ] `_deep_diff` is implemented in `clasr/merge.py` as a private module-level function.
- [ ] `_reverse_diff` is implemented in `clasr/merge.py` as a private module-level function.
- [ ] Neither function mutates its inputs.
- [ ] `_deep_diff({}, {"a": 1})` returns `{"a": 1}`.
- [ ] `_deep_diff({"a": 1}, {"a": 1})` returns `{}` (equal values: no contribution).
- [ ] `_deep_diff({"a": 1}, {"a": 2})` returns `{"a": 2}` (scalar conflict).
- [ ] `_deep_diff({"x": {"p": 1}}, {"x": {"p": 1, "q": 2}})` returns `{"x": {"q": 2}}`.
- [ ] `_reverse_diff({"a": 1, "b": 2}, {"a": 1})` returns `{"b": 2}`.
- [ ] `_reverse_diff({"x": {"p": 1, "q": 2}}, {"x": {"q": 2}})` returns `{"x": {"p": 1}}`.
- [ ] `_reverse_diff({"a": 1}, {"b": 2})` returns `{"a": 1}` (missing key: skipped).
- [ ] `_reverse_diff({"x": {"p": 1}}, {"x": {"p": 1}})` returns `{}` (entire sub-dict removed).
- [ ] No new imports from `clasi` or other `clasr` modules.
- [ ] `uv run pytest tests/clasr/test_merge.py` passes (no regressions).

## Implementation Plan

### Approach

Add `_deep_diff` and `_reverse_diff` after the existing `_deep_merge` helper in
`clasr/merge.py`, before `merge_json_files`. Both functions are called by the updated
`merge_json_files` (ticket 002).

### Files to modify

- `clasr/merge.py`: insert `_deep_diff` and `_reverse_diff` after `_deep_merge`; update
  the module docstring to document them.

### Testing plan

- Run `uv run pytest tests/clasr/test_merge.py` to confirm no regressions.
- Unit tests for these helpers are added in ticket 005.

### Documentation updates

Update the module-level docstring in `clasr/merge.py` to list the two new private helpers
and describe their contracts briefly.
