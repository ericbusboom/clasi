---
id: '002'
title: Test dispatch retry with mock subagent that returns prose then JSON
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Test dispatch retry with mock subagent that returns prose then JSON

## Description

Add integration-style tests for the `Agent.dispatch()` retry path using a
reusable `make_prose_then_json_subagent` factory that simulates a subagent
returning prose on the first call and valid JSON on the second call.

The unit tests from ticket 001 (`TestAgentDispatchRetry`) use inline closures.
This ticket adds a dedicated factory helper and a `TestDispatchRetryMockSubagent`
class that exercises the caller-visible contract of the retry path more directly
and provides a reusable pattern for future tests.

## Acceptance Criteria

- [x] `make_prose_then_json_subagent(prose_response, json_payload)` factory added to `tests/unit/test_agent.py` — returns a `(query_func, calls)` tuple
- [x] `TestDispatchRetryMockSubagent` test class added with five tests:
  - [x] `test_mock_subagent_returns_valid_after_retry` — verifies status=valid after prose-then-JSON
  - [x] `test_mock_subagent_retry_result_contains_json_summary` — verifies result text includes summary from retry JSON
  - [x] `test_mock_subagent_retry_result_contains_log_path` — verifies log_path is always present
  - [x] `test_mock_subagent_always_prose_is_fatal` — verifies fatal error when both calls return prose
  - [x] `test_mock_subagent_exactly_one_retry_attempted` — verifies retry is capped at exactly one attempt
- [x] All new tests pass with `uv run pytest tests/unit/test_agent.py`

## Testing

- **Existing tests to run**: `tests/unit/test_agent.py`
- **New tests to write**: `make_prose_then_json_subagent` factory + `TestDispatchRetryMockSubagent` in `tests/unit/test_agent.py`
- **Verification command**: `uv run pytest tests/unit/test_agent.py`
