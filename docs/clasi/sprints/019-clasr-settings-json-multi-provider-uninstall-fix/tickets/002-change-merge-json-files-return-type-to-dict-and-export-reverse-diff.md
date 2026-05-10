---
id: "002"
title: "Change merge_json_files return type to dict and export reverse_diff"
status: todo
use-cases: [SUC-001, SUC-002, SUC-004]
depends-on: ["001"]
github-issue: ""
todo: ""
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Change merge_json_files return type to dict and export reverse_diff

## Description

Change the second return value of `merge_json_files` from `list[str]` (top-level key
names) to `dict` (the deep-diff snapshot produced by `_deep_diff`). Add `reverse_diff` as
a public export (thin wrapper around `_reverse_diff`) for callers in platform uninstallers.

Current signature:
```python
merge_json_files(existing, incoming, provider, other_provider) -> tuple[dict, list[str]]
```

New signature:
```python
merge_json_files(existing, incoming, provider, other_provider) -> tuple[dict, dict]
# Second element: deep-diff snapshot of what incoming contributes beyond existing
```

The `reverse_diff` public export is needed by the platform uninstall handlers (ticket 004)
so they can strip a provider's contribution without duplicating the dict-walking logic.

Update the module docstring and function docstring to reflect the new API.

## Acceptance Criteria

- [ ] `merge_json_files` calls `_deep_diff(base, incoming)` to compute the contribution.
- [ ] `merge_json_files` returns `(merged_dict, diff)` where `diff` is the deep-diff dict.
- [ ] `reverse_diff(current, diff) -> dict` is exported as a public function (wraps `_reverse_diff`).
- [ ] The conflict warning behavior (one WARNING per conflicting top-level key) is unchanged.
- [ ] The merged result dict is unchanged in behavior — `_deep_merge` still produces it.
- [ ] `merge_json_files` docstring updated to document new return type.
- [ ] `reverse_diff` has a module-level docstring describing its contract.
- [ ] `uv run pytest tests/clasr/test_merge.py` passes with existing tests updated for dict return type.
- [ ] Existing callers in `claude.py`, `codex.py`, `copilot.py` are NOT yet updated (that is ticket 003).

## Implementation Plan

### Approach

In `merge_json_files`, after computing `merged = _deep_merge(base, incoming)`, compute
`diff = _deep_diff(base, incoming)` and return `(merged, diff)` instead of
`(merged, list(incoming.keys()))`.

Add `reverse_diff` as a one-line public wrapper:
```python
def reverse_diff(current: dict, diff: dict) -> dict:
    """Remove the contribution recorded in *diff* from *current*. See _reverse_diff."""
    return _reverse_diff(current, diff)
```

### Files to modify

- `clasr/merge.py`: update `merge_json_files` body and return statement; add `reverse_diff`
  public function after `_reverse_diff`; update module and function docstrings.

### Testing plan

- Update `tests/clasr/test_merge.py`: change assertions that currently check
  `contributed == ["beta", "gamma"]` (list) to check that `contributed` is a `dict` and
  contains the expected keys. Full new tests are added in ticket 005.
- Run `uv run pytest tests/clasr/test_merge.py` to confirm existing tests pass.
- Note: `claude.py`, `codex.py`, `copilot.py` callers will break until ticket 003 updates
  them. If running the full test suite, run only `tests/clasr/test_merge.py` at this
  ticket stage, or do tickets 002 and 003 in the same session.

### Documentation updates

Update docstrings in `clasr/merge.py` only.
