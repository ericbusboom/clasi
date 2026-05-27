---
status: done
sprint: '011'
tickets:
- 011-001
---

# close_sprint fails on pytest exit code 5 (no tests collected)

`_close_sprint_full` treats any non-zero pytest exit code as a test failure. Pytest exit code 5 means "no tests were collected" — this is normal for repos without a test suite and should be treated as pass. Instead, close_sprint returns a test-failure error, the agent loses context, and subsequent retries arrive with empty arguments (`{}`), making the parameter drop look like the root cause.

## Evidence

From `/Volumes/Proj/proj/league-projects/infrastructure/inventory/.clasi/log/mcp-server.log`:

```
10:48:20  CALL close_sprint({"sprint_id": "002", "branch_name": "sprint/002-readme-tagline", ...})
10:48:20  OK close_sprint -> {"status": "error", "error": {"step": "tests",
          "message": "Tests failed (exit code 5)",
          "output": "collected 0 items\n\n============================ no tests ran ..."}}
10:48:25  CALL close_sprint({})   ← agent lost context, retries with empty args
10:48:28  CALL close_sprint({})
10:48:31  CALL close_sprint({})
```

The first call had perfectly correct parameters and was received correctly by the server. The failure was in test execution, not parameter passing.

## Root Cause

`clasi/tools/artifact_tools.py` line 1357:
```python
if test_result.returncode != 0:
```

Pytest exit codes:
- 0: all tests passed
- 1: some tests failed
- 5: no tests were collected (not a failure for repos without tests)

## Fix

```python
if test_result.returncode not in (0, 5):
```

Also update the `test_command` documentation in `close_sprint`'s docstring and the `close-sprint` skill to note that exit code 5 is treated as pass, so users of repos without tests don't need to pass `test_command=""`.
