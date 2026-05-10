---
id: '005'
title: Add deep-diff unit tests to tests/clasr/test_merge.py
status: done
use-cases:
- SUC-001
- SUC-002
- SUC-004
depends-on:
- '002'
github-issue: ''
todo: ''
completes_todo: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add deep-diff unit tests to tests/clasr/test_merge.py

## Description

Add unit tests to `tests/clasr/test_merge.py` covering `_deep_diff`, `_reverse_diff`,
`reverse_diff` (public export), and the updated `merge_json_files` return type. Also
update the two existing tests that assert the second return value is a list (they now
expect a dict).

The private helpers `_deep_diff` and `_reverse_diff` are importable for testing via:
```python
from clasr.merge import _deep_diff, _reverse_diff, reverse_diff
```

Add a round-trip property test: merge then reverse should reproduce the original base
(for non-overlapping keys, where diff == full incoming).

## Acceptance Criteria

- [x] Existing test `test_merge_json_files_basic` updated: assert `contributed` is a `dict`
      containing `{"beta": 2, "gamma": 3}`.
- [x] Existing test `test_merge_json_files_returns_contributed_keys` updated: assert
      `contributed` is `{"mcpServers": {"my-server": {}}}` (full value, not `["mcpServers"]`).
- [x] New test: `test_deep_diff_absent_key` — key absent from base: full value returned.
- [x] New test: `test_deep_diff_equal_values_excluded` — equal values not included in diff.
- [x] New test: `test_deep_diff_scalar_conflict` — overlay scalar wins; included in diff.
- [x] New test: `test_deep_diff_nested_partial` — only new nested leaf in diff, not full sub-dict.
- [x] New test: `test_reverse_diff_removes_key` — removes a contributed key from current.
- [x] New test: `test_reverse_diff_nested` — removes a nested contributed leaf.
- [x] New test: `test_reverse_diff_missing_key_skipped` — missing key in current is silently skipped.
- [x] New test: `test_reverse_diff_entire_sub_dict_removed` — empty after reverse yields key removed.
- [x] New test: `test_merge_json_files_round_trip` — merge then reverse reproduces base
      (for non-overlapping incoming).
- [x] New test: `test_reverse_diff_public_export` — `reverse_diff(current, diff)` is callable
      and produces correct result.
- [x] `uv run pytest tests/clasr/test_merge.py` passes — all new and updated tests green.

## Implementation Plan

### Approach

Add new test functions to `tests/clasr/test_merge.py` in a new section titled
`# _deep_diff and _reverse_diff` following the existing sections. Update the two existing
tests that check `contributed == [...]`.

### Files to modify

- `tests/clasr/test_merge.py`: update 2 existing tests; add ~12 new test functions.

### Testing plan

- Run `uv run pytest tests/clasr/test_merge.py -v` to see all test names and results.
- All tests must be green.

### Documentation updates

None — tests are self-documenting.
