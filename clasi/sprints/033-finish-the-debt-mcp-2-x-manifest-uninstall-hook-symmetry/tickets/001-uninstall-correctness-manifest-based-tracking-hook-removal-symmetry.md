---
id: '001'
title: 'Uninstall correctness: manifest-based tracking + hook-removal symmetry'
status: open
use-cases: [SUC-002, SUC-003]
depends-on: []
github-issue: ''
issue:
- port-clasr-manifest-uninstall-to-clasi-platforms.md
- uninstall-hook-removal-uses-exact-match.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Uninstall correctness: manifest-based tracking + hook-removal symmetry

## Description

Two independent `uninstall()`-correctness fixes to
`src/clasi/platforms/claude.py`, combined into one ticket because both
touch the same function in the same file (see sprint 033's `sprint.md`
Architecture Design Rationale for why splitting them has no independent
value).

**Fix A — manifest-based uninstall tracking** (closes review finding F14,
`clasi/issues/port-clasr-manifest-uninstall-to-clasi-platforms.md`).
Today, `uninstall()` enumerates the skill/agent/rule *names the currently
installed package uses* and deletes files matching those names. A file
written by an older `clasi` under a name since renamed or split is never
found and is orphaned forever — silently, with no error.

Port a **simplified, single-tenant** version of `clasr`'s manifest model
(reference implementation on the local `archive/clasr` branch:
`git show archive/clasr:src/clasr/manifest.py` and
`git show archive/clasr:src/clasr/platforms/claude.py`, specifically its
`install`/`uninstall` methods around lines 222-426). Do **not** port the
`provider`-keyed schema verbatim — `clasr` supported multiple provider
packages layering into one host directory; `clasi` has exactly one
installer identity, so the manifest is a single file, not one per
provider (see sprint.md Design Rationale: "drop the provider dimension").

Critically, also add **install-time reconciliation**, which `clasr`'s own
port does **not** have: before writing the new manifest, `install()` must
read the *previous* manifest (if any) and delete any path present there
but absent from the new install's own entries list. Without this,
`clasr`'s model only fixes the "upgrade `clasi` without re-running
`init`" case — the common case (re-running `clasi init` after an
upgrade) would still silently drop old, renamed files from tracking the
moment the new manifest overwrites the old one, one install cycle later
than the original bug, not actually fixed. See sprint.md Architecture §5
("What Changed — ticket 001") and the `platforms-DESIGN.md` overlay
entry (`clasi/sprints/033-.../design/platforms-DESIGN.md`) for the full
write-up and a component diagram.

**Fix B — hook-removal symmetry**
(`clasi/issues/uninstall-hook-removal-uses-exact-match.md`). Sprint
032/004 made `install()`'s hook merge per-entry (`_merge_hooks` at
`claude.py:252`, using the `_is_clasi_hook_entry` predicate at
`claude.py:233`), so a user-defined hook can now legitimately coexist
with CLASI's own entries under one event key. `uninstall()`'s hooks
step (`claude.py:651-678`) was not updated to match — it still compares
an entire event type's entry *list* for exact equality against the
plugin's `hooks.json`, which no longer matches once a user entry is
mixed in, so CLASI's entries silently survive the uninstall.

## Acceptance Criteria

- [ ] `src/clasi/platforms/_manifest.py` (new) provides
      `manifest_path(platform_dir)`, `write_manifest(platform_dir,
      manifest)`, `read_manifest(platform_dir)`, `delete_manifest(platform_dir)`
      — no `provider` parameter (single-tenant simplification). Writes
      are atomic (write to a `.tmp` sibling, then `os.replace` over the
      final path — matching this project's existing frontmatter-write
      convention, sprint 029). The module has zero `clasi` imports,
      matching `clasr.manifest`'s own boundary rule.
- [ ] `install()` builds an `entries: list[{"path": str, "kind": str}]`
      as it writes each skill alias, agent file, rule file, CLAUDE.md/
      AGENTS.md marker block, and settings.local.json permission entry.
- [ ] `install()` reads the previous manifest (if present) **before**
      writing the new one, computes `old_paths - new_paths`, and deletes
      every path in that difference — **only after the full new entries
      list is built**, never diffing against a partially-built list (an
      early-written file must not be wrongly flagged as stale before its
      own entry is appended — see sprint.md's architecture-review gate
      notes for why this ordering is called out explicitly).
- [ ] `install()` writes the new manifest to
      `.claude/.clasi-manifest.json` as its last step, after every other
      artifact.
- [ ] `uninstall()` reads the manifest first (before touching any file).
      When present, it removes exactly the manifest's listed paths
      (reversing each `kind` the way `install()` wrote it: alias/copy →
      unlink, marker-block → strip just that block, permission entry →
      remove from the allow list) and then deletes the manifest file.
      When absent, or on a manifest read failure (corrupt JSON), it falls
      back to the pre-033 name-based enumeration unchanged — never raises
      and never leaves the target project's CLASI integration stuck.
- [ ] `uninstall()`'s `.claude/settings.json` hooks step calls
      `_is_clasi_hook_entry` per-entry (the same predicate `_merge_hooks`
      already uses) instead of comparing an event type's whole entry list
      for exact equality.
- [ ] A regression test installs, then re-installs with a simulated
      renamed skill (a different skill set than the first install), and
      asserts the first install's now-orphaned file is gone after the
      second install (reconciliation).
- [ ] A regression test installs then uninstalls, and asserts every
      manifest-listed path is removed and the manifest file itself is
      deleted.
- [ ] A regression test uninstalls a project with **no** manifest (a
      simulated pre-033 install) and asserts it still succeeds via the
      pre-033 fallback path, unchanged.
- [ ] A regression test installs, adds a user-defined hook under an event
      key CLASI also uses, uninstalls, and asserts: the user hook
      survives AND no `clasi hook`-prefixed entry remains under that key.
- [ ] `install()`/`uninstall()`'s public signatures
      (`install(target, mcp_config, copy=False, migrate=False)` /
      `uninstall(target, copy=False)`) are unchanged — `init_command.py`/
      `uninstall_command.py` require no changes.

## Implementation Plan

**Approach:**

1. Write `src/clasi/platforms/_manifest.py`, adapting
   `archive/clasr:src/clasr/manifest.py` (88 lines) — drop the `provider`
   path segment/parameter throughout; keep `manifest_path`, atomic
   `write_manifest`, `read_manifest` (returns `None` on
   `FileNotFoundError`), `delete_manifest` (returns `bool`).
2. In `claude.py`'s `install()` / `_install_plugin_content()`: thread an
   `entries: list[dict]` through each write site (skills, agents, hooks
   merge, rules — CLAUDE.md/AGENTS.md marker write and the
   settings.local.json permission update happen in `install()` itself,
   not `_install_plugin_content()`; entries from both need to flow into
   one final list). Append one entry per file/block/permission actually
   written, recording enough to reverse it (`{"path": ..., "kind":
   "alias"|"copy"|"rendered"|"marker-block"|"permission"}` — choose the
   `kind` vocabulary that maps cleanly onto this file's *existing*
   write operations, not `clasr`'s, since the write mechanisms differ
   file-by-file).
3. At the end of `install()`: read the previous manifest via
   `_manifest.read_manifest`, compute the stale-path set, delete those
   paths (best-effort — a `FileNotFoundError` on an already-gone path is
   not an error), then `_manifest.write_manifest` the new entries.
4. In `uninstall()`: read the manifest first. If present, iterate its
   entries and reverse each by `kind`; delete the manifest file at the
   end via `_manifest.delete_manifest`. If absent or unreadable, fall
   through to the existing name-based code unchanged (do not delete or
   restructure that path — it is the pre-033 fallback, not dead code).
5. In `uninstall()`'s hooks section (`claude.py:651-678`): replace the
   `current_hooks[event_type] == clasi_entries` exact-match check with a
   per-entry filter using `_is_clasi_hook_entry`, mirroring
   `_merge_hooks`'s own `kept = [e for e in existing_entries if not
   _is_clasi_hook_entry(e)]` shape.

**Files to modify:**
- `src/clasi/platforms/_manifest.py` (new)
- `src/clasi/platforms/claude.py` (`_install_plugin_content`, `install`,
  `uninstall`)
- `tests/unit/test_platform_claude.py`
- `tests/unit/test_uninstall_command.py` (if it exercises hook removal or
  manifest-absent behavior — check before assuming no change needed)

**Testing plan:**
- New unit tests for `_manifest.py` itself (write/read/delete round-trip,
  atomicity, missing-file `None` return).
- New/extended tests in `test_platform_claude.py` per the Acceptance
  Criteria above (reconciliation, manifest replay, no-manifest fallback,
  hook symmetry).
- Scoped foreground run (see Testing section below) — do not run the
  full suite; that happens once at `close_sprint`.

**Documentation updates:**
- None beyond this ticket and the sprint's `design/` overlay
  (`platforms-DESIGN.md`), already written during planning — no separate
  doc update is expected from this ticket's implementer.

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_platform_claude.py tests/unit/test_uninstall_command.py -v`
- **New tests to write**: manifest round-trip tests in a new
  `tests/unit/test_platform_manifest.py` (or alongside
  `test_platform_claude.py`, implementer's call); reconciliation,
  manifest-replay-uninstall, no-manifest-fallback, and hook-symmetry
  tests in `test_platform_claude.py` per the Acceptance Criteria.
- **Verification command**: `uv run pytest tests/unit/test_platform_claude.py tests/unit/test_uninstall_command.py tests/unit/test_platform_manifest.py -v`
  (scoped to the modules this ticket touches, per `.claude/rules/source-code.md`
  rule 4 — the full suite runs once, at `close_sprint`, not per ticket).

## Process Notes

- Guards fail closed in this project — if a role-guard or mcp-guard
  blocks a write you believe is in scope, **STOP and report it** rather
  than routing around it (no `sed -i`, no shell redirection, no `git
  apply` as a workaround). Reporting a block is a successful outcome of
  this ticket, not a failure.
- Tier-2 (a ticket in `in-progress` status under a locked sprint) may
  edit files under this sprint's own `tickets/` tree directly — you do
  not need a separate MCP call to update this ticket's own checkboxes as
  you complete them, but `status:` transitions and the done-move still go
  through the MCP tools below.
- `update_ticket_status(path, "done")` now **also moves the file** into
  `tickets/done/` in the same call (sprint 030). Do not call
  `move_ticket_to_done` separately, and do not move the file yourself —
  edit this ticket's frontmatter/checkboxes directly as you work, and
  leave the status transition + move to the team-lead's
  `update_ticket_status(path, "done")` call at the end.
- Sequencing note (not a code dependency, a risk-isolation choice made
  during planning): this ticket is intentionally ordered *before* ticket
  002 (the mcp 2.x migration) in this sprint, so that if ticket 002 needs
  its own rollback near the end of the sprint, this ticket's work is
  already committed and unaffected. Nothing in this ticket's own
  implementation depends on ticket 002.
