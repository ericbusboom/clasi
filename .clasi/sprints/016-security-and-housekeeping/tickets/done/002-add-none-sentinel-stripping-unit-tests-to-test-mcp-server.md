---
id: '002'
title: Add NONE-sentinel stripping unit tests to test_mcp_server
status: done
use-cases:
- SUC-016-004
depends-on: []
github-issue: ''
issue: plan-document-the-empty-argument-tool-call-bug.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add NONE-sentinel stripping unit tests to test_mcp_server

## Description

`clasi/mcp_server.py` already strips `"NONE"` → `None` in `_logged_call_tool` (lines
197–200), but there are no tests for this behavior. The stripping is critical safety
infrastructure (sprint-closure failures 007, 010, 011 were caused by this bug). Without
tests, a future refactor could silently remove the protection.

This ticket adds a focused test class to `tests/unit/test_mcp_server.py` that directly
exercises the stripping logic by inspecting what arguments reach the underlying
`call_tool` implementation.

Note: `issue: completes_issue: false` because ticket 003 also addresses the same issue
file (`plan-document-the-empty-argument-tool-call-bug.md`). The issue will be completed
when ticket 003 is done.

## Acceptance Criteria

- [x] `tests/unit/test_mcp_server.py` contains a `TestNoneSentinelStripping` class.
- [x] Test: passing `{"notes": "NONE"}` to `_logged_call_tool` results in the underlying `call_tool` receiving `{"notes": None}`.
- [x] Test: passing `{"notes": "real value"}` passes through unchanged as `{"notes": "real value"}`.
- [x] Test: mixed dict `{"sprint_id": "016", "gate": "NONE", "notes": "NONE"}` strips only the `"NONE"` values.
- [x] Test: an empty `arguments` dict `{}` is passed through unchanged (no KeyError or mutation).
- [x] `uv run pytest` is green.

## Implementation Plan

### Approach

The `_logged_call_tool` closure is created inside `run_server()`, which requires a live
MCP server context to instantiate. To test the stripping logic in isolation, extract it
into a module-level pure function `_strip_none_sentinel(arguments: dict) -> dict` in
`clasi/mcp_server.py`, then call that function from `_logged_call_tool`. Tests import and
call `_strip_none_sentinel` directly.

Alternatively, if extracting the function is too invasive, test through the closure by
patching `_tm.call_tool` and calling `run_server()` in a partial setup. Choose whichever
approach is simpler given the existing test infrastructure in `test_mcp_server.py`.

### Files to Modify

- `clasi/mcp_server.py`
  - Extract the dict comprehension on line 200 into a module-level function
    `_strip_none_sentinel(arguments: dict) -> dict`.
  - Call `_strip_none_sentinel(arguments)` from `_logged_call_tool` where the comprehension
    currently sits.

- `tests/unit/test_mcp_server.py`
  - Import `_strip_none_sentinel` from `clasi.mcp_server`.
  - Add class `TestNoneSentinelStripping` with the test cases listed in Acceptance
    Criteria.

### Testing Plan

The `_strip_none_sentinel` function is a pure function (dict in, dict out). No mocking
needed. Test cases:

```python
from clasi.mcp_server import _strip_none_sentinel

class TestNoneSentinelStripping:
    def test_strips_none_sentinel_value(self):
        result = _strip_none_sentinel({"notes": "NONE"})
        assert result == {"notes": None}

    def test_passes_through_real_value(self):
        result = _strip_none_sentinel({"notes": "real value"})
        assert result == {"notes": "real value"}

    def test_strips_only_none_sentinel_in_mixed_dict(self):
        result = _strip_none_sentinel({"sprint_id": "016", "gate": "NONE", "notes": "NONE"})
        assert result == {"sprint_id": "016", "gate": None, "notes": None}

    def test_empty_dict_unchanged(self):
        result = _strip_none_sentinel({})
        assert result == {}

    def test_does_not_mutate_input(self):
        original = {"notes": "NONE"}
        _strip_none_sentinel(original)
        assert original == {"notes": "NONE"}
```

### Documentation Updates

None. The behavior and the convention are documented in ticket 003's rule file.
