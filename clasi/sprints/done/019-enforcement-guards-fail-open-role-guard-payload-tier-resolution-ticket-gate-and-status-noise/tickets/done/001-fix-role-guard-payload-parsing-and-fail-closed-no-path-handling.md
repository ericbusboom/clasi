---
id: '001'
title: Fix role-guard payload parsing and fail-closed no-path handling
status: done
use-cases:
- SUC-001
- SUC-002
depends-on: []
github-issue: ''
issue: enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix role-guard payload parsing and fail-closed no-path handling

## Description

`handle_role_guard` in `src/clasi/hook_handlers.py:140` reads `file_path`
from the payload root (`tool_input = payload if payload else {}`). Claude
Code actually nests it under `payload["tool_input"]["file_path"]`. Every
real invocation therefore hits `file_path == ""`, short-circuits to
`_exit_hook("role-guard", payload, 0, "no-path")`, and allows — silently,
on every single call. This is the root defect: nothing downstream in
role-guard (tier checks, ticket gate in ticket 004, prefix classification)
can matter until this is fixed, because the function never reaches that
logic today.

The same file already parses the nested shape correctly at line 1014
(`payload.get("tool_input", {}).get("planFilePath")`) — this ticket makes
`handle_role_guard` match that existing, correct pattern, not invent a new
one.

Root cause reference: `clasi/issues/enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md`
defect 1 (verified, file:line, with reproduction commands).

**Bootstrap note**: this ticket, executed by a programmer under ticket
`019-001`, runs *before* the ticket-state gate (ticket 004) exists. Normal
execution is unaffected either way — but be aware this is the ticket that
makes role-guard's payload parsing correct for the first time; if
`no-path` starts blocking legitimate writes during your own work on this
ticket for any payload shape you didn't anticipate, `.clasi/oop` is the
documented escape hatch (do not hand-roll a workaround — see ticket 004
for the fuller warning once the ticket-gate is also live).

## Acceptance Criteria

- [x] `handle_role_guard` reads `file_path` via
      `payload.get("tool_input", payload).get("file_path")` (or
      `.get("path")` / `.get("new_path")` fallback), matching the pattern
      already correct at line 1014 — not a new ad hoc parse.
- [x] `echo '{"tool_name":"Write","tool_input":{"file_path":"source/main.cpp"}}' | clasi hook role-guard` exits 2 for tier 0 (was 0/`no-path`).
- [x] The no-path branch (neither nested nor flat shape yields a
      `file_path`) fails CLOSED for tier 0 and tier 1: logs a WARN-level
      reason (including the actual payload keys present, for
      diagnosability) and exits 2.
- [x] The no-path branch continues to ALLOW (exit 0) for tier 2 — tier 2
      already has unrestricted write scope by design; no-path fail-closed
      only applies where directory-scope enforcement is meaningful.
- [x] `_role_guard_payload()` in `tests/unit/test_hook_handlers.py`
      (currently hand-builds the flat, never-occurring
      `{"file_path": ...}` shape) is replaced with a fixture built from a
      REAL captured payload — pull an actual `role-guard` line's
      structure from `.clasi/log/hooks.log` if one exists with useful
      shape, or construct the fixture to exactly match Claude Code's
      documented nested `PreToolUse` payload
      (`{"tool_name": "Write", "tool_input": {"file_path": "..."}}`).
      No hand-built flat fixtures anywhere in this file going forward.
- [x] A new test asserts the DENY path explicitly end-to-end: nested real
      payload shape + tier 0 (or unset) + a source-code path (not under
      any safe/allow prefix) → `handle_role_guard` exits 2. This is
      non-negotiable — a guard whose block branch is never exercised is
      untested, which is exactly how this bug shipped.
- [x] **Non-negotiable, explicit acceptance criterion**: the new deny-path
      test(s) added by this ticket MUST FAIL if the line-140 payload-read
      fix is reverted (i.e. if `tool_input = payload if payload else {}`
      is restored). Verify this directly before marking the ticket done:
      temporarily revert the fix, run the new test(s), confirm they fail;
      then restore the fix and confirm they pass. Do not skip this
      manual check — it is the only verification that catches "a test
      that merely restates the bug," which is how the original defect
      survived undetected for months.
- [x] Regression test added (or an existing test extended) asserting that
      `handle_role_guard`'s `_allow_prefixes` (built from
      `Project.issues_dir`, `reflections_dir`, `design_dir`, `clasi_dir`,
      `log_dir`) still correctly ALLOWS tier-0 writes to
      `clasi/issues/**`, `clasi/reflections/**`, and `docs/design/**`
      once the payload fix makes role-guard live for the first time.
      This was verified correct by inspection during planning
      (`ARTIFACT_PATH_DEFAULTS` already resolves to visible `clasi/...`
      paths, not `.clasi/...`) but "verified during planning" is not the
      same as "covered by a test" — this ticket must close that gap.
- [x] Existing role-guard tests (tier-1/tier-2 allow paths, safe-prefix
      allow paths, block paths) still pass after the payload-read change
      — run the full `tests/unit/test_hook_handlers.py` suite, not just
      the new tests.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_hook_handlers.py -v`
  (full file — this ticket changes the shared payload-read path used by
  every role-guard test).
- **New tests to write**:
  - Real nested-payload fixture replacing `_role_guard_payload()`.
  - Deny-path test: nested payload, tier 0, source path → exit 2.
  - No-path fail-closed test: tier 0/1 → exit 2 with WARN reason logged;
    tier 2 → exit 0 (unchanged).
  - Non-regression test: tier-0 write to an artifact dir (`clasi/issues/`,
    `clasi/reflections/`, `docs/design/`) still exits 0 after this fix.
  - Manual revert-and-confirm-failure check for the deny-path test(s), as
    described in Acceptance Criteria (documented in the ticket's
    completion notes, not necessarily a permanent CI step).
- **Verification command**: `uv run pytest tests/unit/test_hook_handlers.py -v`
  and the live CLI check:
  `echo '{"tool_name":"Write","tool_input":{"file_path":"source/main.cpp"}}' | clasi hook role-guard; echo "exit=$?"`
  (expect `exit=2`).

## Completion notes

- Fixed `handle_role_guard` to read `payload.get("tool_input", payload)`,
  matching the existing correct pattern at line 1014
  (`handle_plan_to_issue`). Moved tier resolution above the no-path check
  so the no-path branch can discriminate tier 2 (still allow) from
  tier 0/1 (now fail closed, exit 2, with a `logger.warning` including the
  sorted payload top-level keys).
- Replaced `_role_guard_payload()` in `tests/unit/test_hook_handlers.py`
  with a fixture matching Claude Code's real nested `PreToolUse` shape
  (`{"tool_name", "tool_input": {"file_path"}, "session_id"}`), confirmed
  against real captured `role-guard` lines in `.clasi/log/hooks.log`
  (which show `tool_name`, `agent_type`, `agent_id`, `session_id` — the
  log doesn't retain the raw payload body, so the nested shape used here
  is built from Claude Code's documented `PreToolUse` contract plus the
  already-correct sibling parse at line 1014, per the ticket's fallback
  instruction). No hand-built flat fixtures remain in the file.
- **Revert-and-confirm-failure check (performed manually, not a
  permanent CI step)**:
  1. Temporarily reverted line 143 to `tool_input = payload if payload
     else {}`.
  2. Ran the new deny-path tests
     (`TestRoleGuardNestedPayloadShape::test_deny_path_nested_payload_*`).
     **First attempt exposed a real gap**: asserting only on exit code 2
     was insufficient — the reverted code still returns exit 2, but via
     the *new* fail-closed no-path branch (since the flat-shape read
     finds no `file_path` at the payload root either), not via the
     source-code block branch. This is precisely the "test that merely
     restates the bug" failure mode the ticket warned about, caught by
     the check itself.
  3. Fixed the tests to assert on stderr content
     (`"attempted direct file write to"` + the literal path
     `source/main.cpp`), which only appears when `file_path` was actually
     parsed and reached the source-code block branch. Re-ran with the fix
     still reverted: **both tests failed** as required
     (`AssertionError: assert 'source/main.cpp' in ''`).
  4. Restored the line-143 fix. Re-ran the same tests: **both passed**.
  5. Ran the full file: **122 passed**.
- Live CLI check via the working tree's editable install
  (`uv run clasi hook role-guard`): confirmed `exit=2` for
  `{"tool_name":"Write","tool_input":{"file_path":"source/main.cpp"}}`.
  Note: the separately pipx-installed `clasi` on `$PATH` (version
  `0.20260627.14`) is a stale build predating this fix and still returns
  `exit=0`; this is the known installed-build-vs-working-tree gap noted
  in the ticket, not a defect in this change. `uv run clasi` (or
  `.venv/bin/clasi`) reflects the fix; the global pipx install does not
  until reinstalled.
