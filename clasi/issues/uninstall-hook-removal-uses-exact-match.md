---
status: pending
type: bug
tags:
- install
- follow-up
---

# uninstall's hook removal uses exact-match, so it can leave CLASI entries behind

## Description

Surfaced by the programmer implementing ticket 032-004, reported rather
than silently fixed out of scope.

That ticket fixed `clasi init` clobbering user-defined hooks: install now
merges per event type, replacing only entries whose commands start with
`clasi hook` (`_is_clasi_hook_entry` / `_merge_hooks` in
`src/clasi/platforms/claude.py`).

`uninstall()` was not updated to match. Its hook-removal path still does
an exact-match comparison per event type against the plugin's
`hooks.json`.

Before the init fix this was harmless: install always replaced the whole
hooks object, so a CLASI event's entries could never have user hooks
mixed in, and exact-match always matched. After the fix, a user hook can
legitimately coexist with CLASI's under the same event key — and when it
does, uninstall's exact-match check no longer matches, so CLASI's own
entries are not stripped.

**No data loss** — nothing of the user's is deleted. The failure is an
incomplete uninstall: CLASI hook entries survive an uninstall and keep
firing against a project that no longer has CLASI installed, which will
fail noisily on every matched tool call.

## Acceptance criteria

- [ ] `uninstall()` removes CLASI hook entries using the same per-entry
      predicate install uses (`_is_clasi_hook_entry`), not exact-match
      against `hooks.json`.
- [ ] A test installs, adds a user-defined hook under an event key CLASI
      also uses, uninstalls, and asserts: the user hook survives AND no
      `clasi hook` entry remains.
- [ ] The symmetry is stated once where both functions can see it —
      install and uninstall must agree on what "a CLASI hook entry" is,
      or they will drift again.
