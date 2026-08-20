---
status: done
sprint: 029
tickets:
- 029-003
---

# get_project() has no upward root discovery

## Description

`get_project()` (`src/clasi/hook_handlers.py:25-27`) constructs
`Project(Path.cwd())` directly — there is no search for `.clasi/` in
any ancestor directory. Every `Project` property (`issues_dir`,
`sprints_dir`, `clasi_dir`, `db_path`, `log_dir`, `reflections_dir`,
`design_dir`, `protected_paths`, `excluded_paths`, `sources`, etc.)
therefore silently resolves against the wrong root whenever a hook
fires with cwd set to a subdirectory of the actual project root rather
than the root itself.

This is the root cause of a narrower bug already fixed (out of
process, 2026-07-17): `_oop_active()` did a bare
`Path(".clasi/oop").exists()` check, which silently returned `False`
when cwd was e.g. `tests/e2e/` even though `.clasi/oop` existed at the
real project root — the OOP bypass looked like it wasn't set when it
was. That narrow case is now fixed with a local `_find_project_root()`
helper used only inside `_oop_active()`.

`db-backed-oop-flag-file-as-unconditional-override.md` already flags
this exact gap in passing (its "Caveat to record in the docstring" and
"Out of scope, deliberately" sections: *"Fixing `get_project()`'s
no-upward-search assumption (separate issue)"*) but no separate issue
was ever filed for it. This is that issue.

## Cause

- `get_project()` has no upward search — it trusts cwd unconditionally.
- Every other hook handler (role-guard, mcp-guard, sprint/ticket state
  checks, artifact tools) calls `get_project()` and inherits whatever
  root it resolves, with no independent verification.

## Impact

Any PreToolUse/hook invocation whose cwd is a subdirectory of the
project root — not just the `.clasi/oop` case already fixed — gets
silently wrong `Project` paths. This could affect:

- Role-guard allow/block prefix checks (`issues_dir`, `sprints_dir`,
  etc.) built from `get_project()` in `handle_role_guard`.
- `protected_paths`/`excluded_paths` resolution (added this session)
  once a project opts into that config.
- Sprint/ticket state lookups (`_get_sprint_context`,
  `_get_active_tickets`) that resolve paths via `get_project()`.
- Any other hook handler in this module that calls `get_project()`.

Not yet confirmed how often real Claude Code hook invocations actually
fire with cwd != project root outside the one observed case (editing a
file under `tests/e2e/` with the shell cwd already there) — this issue
is about the structural gap, not a claim that every handler is
observed broken today.

## Proposed fix

Add the same walk-up-to-find-`.clasi/` discovery logic used in the
narrower `_oop_active()` fix to `get_project()` itself (or to `Project`
construction generally), falling back to cwd unchanged when no
`.clasi/` is found in any ancestor — this preserves current behavior
for legitimate non-project cwds (e.g. tests that construct `Project`
against an isolated `tmp_path` with no ancestor `.clasi/`).

Given the blast radius (the most central function in
`hook_handlers.py`, called by nearly every handler), this needs its own
ticket/sprint rather than an ad hoc fix — deliberately scoped out of
the 2026-07-17 OOP session for that reason.

## Verification

- Test coverage simulating hook invocations from subdirectories across
  the various hook handlers that call `get_project()` — not just
  `_oop_active()` (which already has this coverage from the narrower
  fix).
- Confirm no regression for legitimate non-project cwds (tests using
  isolated `tmp_path` fixtures with no ancestor `.clasi/`).

## Related

- `db-backed-oop-flag-file-as-unconditional-override.md` — the
  narrower `_oop_active()` cwd bug this issue generalizes from; already
  anticipated this issue in its own scope notes.
- Discovered live 2026-07-17 during e2e-harness OOP work
  (`tests/e2e/start.sh`/`Dockerfile` changes, `protected_paths`/
  `excluded_paths` config addition): editing `.gitignore` and
  `start.sh` from a shell whose cwd was `tests/e2e/` was blocked by
  role-guard despite `.clasi/oop` existing at the repo root, reproducing
  the same cwd-resolution defect this issue is about.
