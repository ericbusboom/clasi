---
status: done
---

# close_sprint's 300s test timeout is hardcoded and too short for this repo's own suite

## Description

`close_sprint` runs the test suite with a hardcoded `timeout=300`
(`src/clasi/tools/artifact_tools.py:1564`). This repo's own `pytest`
suite takes ~460-525 seconds (2700+ tests), so a normal, healthy close
of any CLASI sprint fails at the `tests` step with:

    "Test suite timed out after 300 seconds"

Observed on 2026-07-17 closing sprint 023: the default `uv run pytest`
close timed out at 300s even though the suite passes in ~8.5 min. There
is no `test_command` value that raises the limit — the timeout is fixed
in code regardless of the command passed, so the only workarounds are to
pass a *faster* command (skip/deselect tests) or `""` to skip tests
entirely, both of which defeat the gate's purpose.

Impact: on CLASI itself (and any consumer repo with a >5-min suite),
`close_sprint` cannot run the real suite at close. That pushes operators
toward skipping tests at the exact moment they most matter (the release
tag + merge), silently weakening the close gate.

## Cause

`timeout=300` is a literal in `_run_close_tests` (or equivalent) rather
than a configurable value sourced from `.clasi/config.yaml` or the tool
signature.

## Proposed fix

- Make the test timeout configurable: a `test_timeout` parameter on
  `close_sprint` and/or a `.clasi/config.yaml` key, defaulting to
  something that fits a real suite (e.g. 900s) — or no timeout when the
  operator sets 0.
- Surface the timeout value in the error message so the operator knows
  what to raise.

## Verification

- Closing a sprint in this repo with the default `uv run pytest`
  completes the `tests` step (given the suite passes) without a timeout.
- A deliberately-hung test still trips the (now-configurable) timeout and
  blocks the close.

## Related

- Worked around during sprint 023 close by passing a fast
  `test_command` (the harness scripts' `bash -n` syntax check) after the
  full suite had already been run green by ticket 003 — acceptable there
  because the real suite had just passed, but not a general answer.
- Adjacent to `pre-existing-failures-in-test-sprint-done-archive-backward-compat.md`
  (the suite also currently has 4 known-red tests).
