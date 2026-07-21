---
id: '006'
title: clasi oop CLI group + docs rewording
status: open
use-cases: [SUC-004]
depends-on: ['004']
github-issue: ''
issue: db-backed-oop-flag-file-as-unconditional-override.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# clasi oop CLI group + docs rewording

## Description

With the DB-backed OOP state layer in place (ticket 004: `oop_state`
table and `StateDB` methods) and `_oop_active()`/`_oop_source()` rewritten
to consult it (ticket 005), this ticket adds the operator-facing CLI
surface and rewords documentation to make `clasi oop on/off/status` the
primary, documented way to engage the bypass — with the flag file
retained and documented as the emergency path (for when CLASI's own
tooling itself is broken).

Add a new `@cli.group()` named `oop` in `src/clasi/cli.py`, mirroring the
existing `sprint` group's structure (same command-registration pattern,
same help-text conventions):
- `clasi oop on [--reason TEXT] [--ttl-hours FLOAT]` — reason is required;
  if omitted, prompt for it interactively rather than defaulting to a
  blank reason.
- `clasi oop off` — clears the DB row (via `clear_oop()`) **and** removes
  flag files (`.clasi/oop`, and tolerates/removes the legacy `.clasi-oop`
  if present), printing a notice of what was cleared.
- `clasi oop status` — prints source, reason, age, and expiry (using
  `_oop_source()`/`get_oop()` from tickets 004/005).

Then reword the following to document `clasi oop on --reason '...'` as the
primary instruction, with the flag file kept as the documented emergency
path (not removed, not deprecated — just no longer primary):
- `src/clasi/platforms/_rules.py` — `MCP_REQUIRED_BODY`,
  `CLASI_ARTIFACTS_BODY`, `SOURCE_CODE_BODY`, `TODO_DIR_BODY`.
- Guard error strings in `src/clasi/hook_handlers.py` (wherever a denial
  message currently mentions the flag file as the bypass).
- `src/clasi/plugin/skills/oop/SKILL.md` — add an "Enabling the bypass"
  section documenting the CLI command.
- This repo's own on-disk generated rules — regenerate `.claude/rules/
  mcp-required.md`, `.claude/rules/clasi-artifacts.md`, `.claude/rules/
  source-code.md`, and the TODO-dir equivalent from the updated generator
  sources, and verify by reading the regenerated files back.

## Acceptance Criteria

- [ ] `clasi oop on --reason '<why>'` sets the DB-backed bypass (default
      TTL 8 hours per ticket 004's `set_oop` default) and prints
      confirmation.
- [ ] `clasi oop on` with no `--reason` prompts interactively for one
      rather than silently defaulting to empty.
- [ ] `clasi oop off` clears the DB row and removes `.clasi/oop` (and
      `.clasi-oop` if present), printing a notice naming what was cleared.
- [ ] `clasi oop status` prints source (`file`/`db`/both/none), reason,
      age, and expiry, matching `_oop_source()`/`get_oop()`'s data.
- [ ] `src/clasi/platforms/_rules.py`'s `MCP_REQUIRED_BODY`,
      `CLASI_ARTIFACTS_BODY`, `SOURCE_CODE_BODY`, and `TODO_DIR_BODY` are
      reworded so their primary bypass instruction is `clasi oop on
      --reason '...'`, with the flag file documented as the emergency
      path (used when `clasi` itself is broken), not removed from the
      text.
- [ ] Guard error strings in `hook_handlers.py` that reference the bypass
      are reworded to mention the CLI command as primary.
- [ ] `src/clasi/plugin/skills/oop/SKILL.md` gains an "Enabling the
      bypass" section documenting `clasi oop on/off/status`.
- [ ] This repo's on-disk `.claude/rules/*.md` files are regenerated from
      the updated generator sources, and the regenerated content is read
      back and confirmed to match the new wording (not just assumed from
      the generator diff).
- [ ] `uv run pytest --no-cov -q` passes, including any new CLI-command
      tests for `oop on`/`off`/`status`.

## Implementation Plan

**Approach**: Add the CLI group following the existing `sprint` group's
registration pattern in `cli.py` exactly (same decorators, same option-
parsing style, same success/error message conventions), wired to the
`state_db` module-level wrappers from ticket 004 and the
`_oop_source()`/`_oop_active()` helpers from ticket 005. Then do a
rewording pass across the listed doc sources, and regenerate this repo's
own `.claude/rules/*.md`.

**Files to modify**:
- `src/clasi/cli.py` — new `oop` `@cli.group()` with `on`, `off`, `status`
  subcommands.
- `src/clasi/platforms/_rules.py` — reword `MCP_REQUIRED_BODY`,
  `CLASI_ARTIFACTS_BODY`, `SOURCE_CODE_BODY`, `TODO_DIR_BODY`.
- `src/clasi/hook_handlers.py` — reword guard error/denial strings that
  mention the OOP bypass.
- `src/clasi/plugin/skills/oop/SKILL.md` — add "Enabling the bypass"
  section.
- This repo's own `.claude/rules/mcp-required.md`,
  `.claude/rules/clasi-artifacts.md`, `.claude/rules/source-code.md`, and
  the TODO-dir rule file — regenerated from the updated generator sources
  (not hand-edited to match, to keep the generator as the single source
  of truth).

**Testing plan**:
- Existing tests to run: full suite, especially any existing `cli.py`
  command tests (regression) and any tests asserting the current wording
  of `_rules.py` bodies or guard error strings (expected to need updates,
  not silently fail).
- New tests: `clasi oop on`/`off`/`status` CLI invocation tests (success
  paths and the reason-prompt-when-omitted path); a regeneration-and-read-
  back check that the on-disk `.claude/rules/*.md` files match the
  updated generator output.
- Verification command: `uv run pytest --no-cov -q`.

**Documentation updates**:
- This ticket *is* the documentation-update ticket for the OOP redesign —
  see the files listed above. After regenerating, manually read back each
  regenerated `.claude/rules/*.md` file to confirm the wording landed as
  intended, per this project's own `tool-call-empty-args.md`-style
  discipline of verifying generated artifacts rather than trusting the
  generator ran correctly.
