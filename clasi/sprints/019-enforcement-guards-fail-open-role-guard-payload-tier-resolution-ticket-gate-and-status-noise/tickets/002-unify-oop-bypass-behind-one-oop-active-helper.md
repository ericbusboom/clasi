---
id: '002'
title: Unify OOP bypass behind one _oop_active() helper
status: open
use-cases: [SUC-005]
depends-on: ['001']
github-issue: ''
issue: enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Unify OOP bypass behind one _oop_active() helper

## Description

The OOP (out-of-process) bypass flag is split-brain in
`src/clasi/hook_handlers.py`: `handle_role_guard` (line 171) and
`handle_mcp_guard` (line 285) check `.clasi-oop` (repo root, hyphen);
`handle_status_inject` (line 463) checks `.clasi/oop` (inside `.clasi/`,
slash). All five `.claude/rules/*.md` bodies and the `oop` skill document
promise `.clasi/oop`. The documented escape hatch does not open the
enforced door for two of the four call sites.

Add one shared helper, `_oop_active() -> bool`, in `hook_handlers.py`:
checks `Path(".clasi/oop").exists()` first (canonical, matches
documentation), then falls back to `Path(".clasi-oop").exists()` (legacy,
keeps working for any session already relying on it). Replace all inline
flag-file checks in `handle_role_guard`, `handle_mcp_guard`,
`handle_status_inject`, and `handle_subagent_start` with calls to this
helper. No handler may check either flag file directly outside the
helper after this ticket.

Depends on ticket 001 because it edits the same functions (`handle_role_guard`,
`handle_mcp_guard`) that 001 touches for payload parsing — sequencing
avoids a merge/rebase conflict within the sprint's serial execution, and
001's real-payload test fixture is reused here rather than re-invented.

Root cause reference: `clasi/issues/enforcement-guards-fail-open-role-guard-payload-and-tier-resolution.md`
defect 5 (OOP split-brain).

## Acceptance Criteria

- [ ] New `_oop_active()` helper added to `hook_handlers.py`: returns
      `True` if `Path(".clasi/oop").exists()`, else `True` if
      `Path(".clasi-oop").exists()`, else `False`.
- [ ] `handle_role_guard`'s inline `.clasi-oop` check (line 171) replaced
      with a call to `_oop_active()`.
- [ ] `handle_mcp_guard`'s inline `.clasi-oop` check (line 285) replaced
      with a call to `_oop_active()`.
- [ ] `handle_status_inject`'s inline `.clasi/oop` check (line 463)
      replaced with a call to `_oop_active()`.
- [ ] `handle_subagent_start`'s inline `.clasi/oop` check (line 543)
      replaced with a call to `_oop_active()`.
- [ ] `grep -n '"\.clasi-oop"\|"\.clasi/oop"' src/clasi/hook_handlers.py`
      shows matches only inside `_oop_active()` itself — no other
      handler references either flag file string directly.
- [ ] Test: create only `.clasi/oop` in a temp project; assert
      `_oop_active()` returns `True`, and assert bypass actually occurs
      in `handle_role_guard`, `handle_mcp_guard` (both via a live guard
      call, not just calling the helper directly).
- [ ] Test: create only `.clasi-oop` (legacy) in a temp project; assert
      the same bypass occurs in the same set of handlers. Both flag
      files must be tested independently — a test that only ever creates
      both together would not have caught the original split-brain bug.
- [ ] Test: neither flag file exists; assert `_oop_active()` returns
      `False` and guards proceed to their normal (non-bypassed) logic.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_hook_handlers.py -v`
- **New tests to write**: `_oop_active()` unit tests (both flags, neither
  flag) plus integration-style tests asserting bypass actually occurs in
  `handle_role_guard` and `handle_mcp_guard` for both flag files
  independently (not just helper-level unit tests — the original bug was
  in a handler failing to *call* the check for one of the files, so
  handler-level tests are the ones that actually catch a regression of
  this kind).
- **Verification command**: `uv run pytest tests/unit/test_hook_handlers.py -v`;
  manually: `touch .clasi/oop && echo '{"tool_name":"Write","tool_input":{"file_path":"source/main.cpp"}}' | clasi hook role-guard; echo "exit=$?"`
  (expect 0), then `rm .clasi/oop && touch .clasi-oop` and repeat (expect
  0), then `rm .clasi-oop` and repeat (expect 2, per ticket 001's fix).
