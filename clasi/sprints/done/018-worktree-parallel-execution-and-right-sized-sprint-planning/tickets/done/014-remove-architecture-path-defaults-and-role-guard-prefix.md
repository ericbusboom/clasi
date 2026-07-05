---
id: '014'
title: Remove architecture path defaults and role-guard prefix
status: done
use-cases:
- SUC-006
depends-on:
- '013'
github-issue: ''
issue: right-size-sprint-planning-one-sprint-md-no-per-sprint-architecture-docs-on-demand-architecture-consolidation.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Remove architecture path defaults and role-guard prefix

## Description

Issue B Part 5. Depends on ticket 013 (consolidate-architecture must
already be repointed at `design_dir` before the old `architecture_dir`
config/property is removed, so there is no window where a component
still refers to `architecture_dir` for its primary output path).

1. **`src/clasi/project.py`**: remove the `"architecture": "docs/
   architecture"` entry from `ARTIFACT_PATH_DEFAULTS` (currently line
   ~26). Remove (or repurpose per the issue's "remove/repurpose"
   wording — prefer removal since nothing after ticket 003/013 writes to
   it) the `Project.architecture_dir` property (currently ~lines
   116-118). Grep for `architecture_dir` and `ARTIFACT_PATH_DEFAULTS[
   "architecture"]`-style access across `src/clasi/` before removing —
   ticket 003 already removed `Sprint.archive()`'s use of it; confirm no
   other call site remains (e.g. `insert_sprint`/status code) — if one is
   found that this ticket didn't anticipate, fix it here (it's in scope:
   "config/paths" cleanup) rather than deferring.

2. **`src/clasi/hook_handlers.py`**: remove `_prefix(_proj.
   architecture_dir)` from the role-guard `_allow_prefixes` list
   (currently ~line 216, inside `handle_role_guard`). `design_dir`
   (`docs/design/`) is already in the same list (~line 217) and already
   covers the consolidated architecture doc's new location
   (`docs/design/architecture.md`), so no replacement entry is needed —
   this is a pure removal, not a swap.

Since `Project.architecture_dir` is removed by this ticket, step 1 must
land before or atomically with step 2 (both are in this one ticket, so
order within the ticket is: remove the property usage in
`hook_handlers.py` first or simultaneously with removing the property
itself in `project.py`, so there's no intermediate commit where
`hook_handlers.py` calls a property that no longer exists — since this
is one ticket/one PR-equivalent, just make both edits together before
running tests).

## Acceptance Criteria

- [x] `ARTIFACT_PATH_DEFAULTS` in `project.py` no longer has an
      `"architecture"` key.
- [x] `Project.architecture_dir` property is removed.
- [x] `hook_handlers.py`'s `handle_role_guard` no longer includes
      `architecture_dir` in `_allow_prefixes`.
- [x] `design_dir` remains in `_allow_prefixes` (unchanged) and already
      covers `docs/design/architecture.md`.
- [x] A repo-wide grep for `architecture_dir` after this ticket's edits
      shows zero remaining references in `src/clasi/` (test fixtures
      referencing the old path for historical/backward-compat purposes,
      if any, are out of scope for this specific grep — flag separately
      if found).
- [x] `uv run pytest` collection succeeds (no import errors from a
      removed property/key).

## Files to create or modify

- `src/clasi/project.py` — `ARTIFACT_PATH_DEFAULTS`, `architecture_dir`
  property.
- `src/clasi/hook_handlers.py` — `handle_role_guard`'s `_allow_prefixes`.

## Testing

- **Existing tests to run**: any test referencing `architecture_dir` or
  `ARTIFACT_PATH_DEFAULTS["architecture"]` (grep `tests/` first), the
  role-guard hook test suite if one exists, full `uv run pytest`.
- **New tests to write**: a role-guard test confirming a write to
  `docs/design/architecture.md` is still allowed (via `design_dir`) for
  tier 0, and that no test relies on `docs/architecture/` being
  allow-listed anymore.
- **Verification command**: `uv run pytest`

## Completion Notes

The pre-removal grep surfaced three unanticipated call sites beyond the
two named in this ticket's description (`project.py`,
`hook_handlers.py`), all fixed here per "config/paths cleanup is in
scope, don't defer":

1. **`src/clasi/migrate_command.py`** (`detect_moves`'s `category_dst`
   map) — used `project.architecture_dir` as the migration destination
   for the `"architecture"` legacy-source category (probing
   `.clasi/architecture` / `docs/clasi/architecture`). Repointed the
   destination to `project.design_dir`, mirroring ticket 013's
   repointing of consolidate-architecture's output — legacy architecture
   content now merges into `docs/design/` on `clasi migrate`. The
   `"architecture"` key stays in `CANDIDATE_LOCATIONS` (it is still a
   valid probed source) but is intentionally absent from
   `ARTIFACT_PATH_DEFAULTS`, since it has no destination of its own
   anymore — `test_all_default_keys_present` in
   `tests/unit/test_migrate_command.py` was updated to assert this
   subset relationship explicitly instead of equality.
2. **`src/clasi/tools/artifact_tools.py`** (`_find_latest_architecture`)
   — a private helper reading `architecture_dir`, confirmed dead code via
   repo-wide grep (zero callers anywhere, including tests). Removed
   outright rather than repointed, since its `architecture-*.md` glob
   matched the old versioned-file convention ticket 013 already
   deprecated.
3. **`src/clasi/sprint.py`** (`Sprint.archive()` docstring) — a prose
   reference to `project.architecture_dir` left over from ticket 003's
   edit. Reworded to describe the current design (design_dir via the
   consolidate-architecture skill) instead of naming a property that no
   longer exists.

Also updated for consistency, since they broke as a direct consequence
of removing `"architecture"` from `ARTIFACT_PATH_DEFAULTS` (not
call-site bugs, but tests asserting the old default-scaffolding
behavior): `tests/unit/test_init_command.py`'s
`test_creates_architecture_at_new_default_path` (renamed/inverted to
`test_does_not_create_architecture_dir` — `clasi init` no longer
scaffolds `docs/architecture/` since it iterates
`ARTIFACT_PATH_DEFAULTS` generically) and
`test_init_command_no_longer_hardcodes_old_dirs` (assertion flipped to
`not exists`).

Role-guard behavior change worth flagging explicitly: under the fresh
default layout, `docs/architecture/x.md` writes by tier 0 are now
**blocked** (previously allowed via the dedicated `architecture_dir`
prefix) — covered by
`test_tier0_docs_architecture_no_longer_allow_listed` in
`tests/unit/test_hook_handlers.py`. Under the legacy config-pinned
layout, `.clasi/architecture/x.md` remains allowed, but only
incidentally because it falls under the `clasi_dir` (`.clasi/`)
catch-all prefix, not because of a dedicated architecture prefix — see
`test_tier0_legacy_architecture_path_allowed_via_clasi_dir`.

Full `uv run pytest`: 2424 passed, coverage 87.96% (threshold 84%).
Repo-wide grep for `architecture_dir` in `src/clasi/` after all edits:
zero matches. Remaining prose-only mentions of `architecture_dir` (test
docstrings explaining the removal, and historical sprint docs /
`docs/architecture/*.md` under this repo, which ticket 015 owns
deleting) are out of scope per this ticket's grep criterion.
