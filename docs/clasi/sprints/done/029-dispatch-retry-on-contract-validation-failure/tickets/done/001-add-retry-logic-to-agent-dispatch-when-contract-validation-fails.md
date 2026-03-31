---
id: '001'
title: Add retry logic to Agent.dispatch() when contract validation fails
status: done
use-cases: []
depends-on: []
github-issue: ''
todo: dispatch-retry-on-contract-validation-failure.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add retry logic to Agent.dispatch() when contract validation fails

## Description

When a subagent returns prose instead of structured JSON, the dispatch
tool logged a validation error but passed the response through to the
caller anyway. This ticket adds retry logic so the dispatch automatically
re-asks the subagent for valid JSON when validation fails, and returns a
fatal error if both attempts fail.

## Acceptance Criteria

- [x] `Agent.dispatch()` retries with a feedback prompt when the first response fails contract validation (no JSON found or schema mismatch)
- [x] Retry is limited to one attempt (max — no infinite loops)
- [x] `_build_retry_prompt()` includes the original prompt, the validation errors, and the required JSON schema from the contract
- [x] If the retry returns valid JSON, dispatch returns that result with status "valid"
- [x] If the retry also fails validation, dispatch returns `{"status": "error", "fatal": True, ...}` with an instruction to stop and report
- [x] If the retry query raises an exception, dispatch falls through with the original validation result (no crash)
- [x] Module docstring updated to document the new step 5b (RETRY)
- [x] Unit tests cover all retry scenarios: prose-then-JSON, always-prose (fatal), exception-on-retry, no-retry-on-success, retry prompt content

## Testing

- **Existing tests to run**: `tests/unit/test_agent.py`
- **New tests to write**: `TestBuildRetryPrompt` and `TestAgentDispatchRetry` classes in `tests/unit/test_agent.py`
- **Verification command**: `uv run pytest tests/unit/test_agent.py`
