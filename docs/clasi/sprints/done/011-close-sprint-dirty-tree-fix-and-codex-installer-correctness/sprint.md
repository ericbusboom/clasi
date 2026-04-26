---
id: '011'
title: close_sprint dirty-tree fix and Codex installer correctness
status: done
branch: sprint/011-close-sprint-dirty-tree-fix-and-codex-installer-correctness
todos:
- close-sprint-rebase-fails-on-dirty-clasi-db.md
- codex-install-parity-and-misleading-se-pointer.md
use-cases:
- SUC-001
- SUC-002
- SUC-003
- SUC-004
- SUC-005
- SUC-006
- SUC-007
- SUC-008
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 011: close_sprint dirty-tree fix and Codex installer correctness

## Goals

1. Fix `close_sprint` so it never fails on a dirty working tree caused by its own `.clasi.db`
   writes, and ensure the execution lock is always released even when merge fails.

2. Correct the Codex installer output to match the actual Codex spec: fix the
   `.codex/hooks.json` schema, add `.codex/agents/<name>.toml` sub-agent install, drop the
   misleading `/se` pointer from the CLASI section template, and implement rule content
   placement via nested `AGENTS.md` files.

## Problem

**Track A — `close_sprint` dirty-tree bug**: The `close_sprint` lifecycle writes to
`docs/clasi/.clasi.db` in step 4 (`db_update`) and optionally in step 5 (`version_bump`,
via `git add -A` commit). However the rebase in step 6 (`merge`) operates on the sprint
branch, and by the time rebase runs the working tree already contains the uncommitted
`.clasi.db` change. `git rebase` refuses to proceed with unstaged changes, so every
`close_sprint` invocation fails at the merge step. Additionally, when merge fails the
execution lock is left held, requiring a manual `release_execution_lock` call.

**Track B — Codex installer correctness**: Sprint 010 shipped a Codex installer
(`clasi/platforms/codex.py`) with a `.codex/hooks.json` schema that Codex does not honor.
The hook wrapper structure is wrong (missing `type: "command"` and the joined command
string), so the `codex-plan-to-todo` hook never fires. Sub-agents (team-lead,
sprint-planner, programmer) are not installed to `.codex/agents/` — the correct native
location. The CLASI section template contains a misleading `/se` line. Rules have no
Codex-native equivalent and need to be placed correctly.

## Solution

**Track A**: Move the `.clasi.db` commit to BEFORE the merge step. The `version_bump`
step already does a `git add -A` and commit; extend it to also stage and commit
`.clasi.db` changes on the sprint branch before the rebase. Wrap the merge step in a
try/finally so that `release_execution_lock` is called even on failure.

**Track B**:
- Rewrite `_CLASI_STOP_HOOK` in `codex.py` to the correct Codex hooks.json wrapper
  structure. Update the uninstall backward-compat logic to replace old-shape entries.
- Add a `_install_agents` function that writes `.codex/agents/<name>.toml` for each
  bundled agent (team-lead, sprint-planner, programmer), converting the Markdown agent
  definition body to the `developer_instructions` TOML field.
- Drop the "Available skills: run `/se` for a list." line from
  `clasi/templates/clasi-section.md`.
- Implement rule placement via nested `AGENTS.md` at `.claude/` and key subdirectory
  roots. The Codex installer writes these files; the uninstaller removes them. (Chosen
  over SE-skill embedding — see architecture rationale.)
- Update all affected tests and add end-to-end install correctness tests.
- Update README to describe the corrected Codex footprint.

## Success Criteria

- `close_sprint` completes without dirty-tree errors when `.clasi.db` is git-tracked.
- Execution lock is released even when the merge step fails.
- `clasi install --codex` produces a `.codex/hooks.json` that round-trip parses to the
  exact Codex spec shape.
- `.codex/agents/team-lead.toml`, `sprint-planner.toml`, `programmer.toml` are written
  on codex install and removed on uninstall.
- The CLASI section in `AGENTS.md` no longer contains the `/se` line.
- Rule content is present in nested `AGENTS.md` files at the appropriate paths.
- All existing tests pass; new tests cover the corrected shapes and new artifacts.

## Scope

### In Scope

- Fix `close_sprint` dirty-tree rebase failure (Track A ticket 001)
- Fix execution lock leak on merge failure (bundled with Track A)
- Fix `.codex/hooks.json` schema (Track B ticket 002)
- Investigate and document repo-local vs. `~/.codex/hooks.json` firing behavior (Track B ticket 002)
- Drop `/se` line from `clasi-section.md` template (Track B ticket 003)
- Add `.codex/agents/<name>.toml` install and uninstall (Track B ticket 004)
- Implement nested `AGENTS.md` rule files for Codex (Track B ticket 005)
- End-to-end Codex install correctness tests (Track B ticket 006)
- README update for corrected Codex footprint (Track B ticket 007)

### Out of Scope

- Global `~/.codex/hooks.json` install (document the limitation; do not change install scope)
- `--platform=other` / generic AGENTS.md-only install mode (follow-on sprint)
- Translating Claude-Code-specific agent.md phrasing to Codex-specific equivalents (use verbatim
  agent.md body for `developer_instructions`; noted as a known limitation)
- Changes to the Claude platform installer

## Test Strategy

- Unit tests for `_close_sprint_full` covering the dirty-tree scenario (mock `git rebase`
  failure; verify lock is released via the finally block).
- Unit tests for `_write_codex_hooks`: assert the exact JSON structure matches the Codex spec
  via round-trip `json.loads`.
- Unit tests for `_install_agents` / `_uninstall_agents`: check TOML round-trip and field presence.
- Unit test for `clasi-section.md` content: assert the `/se` line is absent.
- Integration test (install into `tmp_path`): invoke `codex.install()`, then parse every emitted
  file and assert spec-conformance (hooks.json, config.toml, agent TOMLs, nested AGENTS.md files).

## Architecture Notes

See `architecture-update.md` for the full design. Key decisions:

- Rule placement: nested `AGENTS.md` files at subdirectory roots. Rationale: this is the
  closest Codex-native equivalent to path-scoped rules; it avoids bloating the SE skill body
  with content that is specific to individual rule files.
- Hooks.json fix: replace the flat `{command, args}` format with the wrapper structure
  `{hooks: [{type: "command", command: "...", timeout: N}]}` at the `Stop` array level.
- Agent TOML: convert agent.md body verbatim to `developer_instructions`. Claude-specific
  phrasing is a known limitation; a translation layer is deferred.
- Lock release: use try/finally in `_close_sprint_full` wrapping the merge step.

## GitHub Issues

(None assigned yet.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [x] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [x] Architecture review passed
- [x] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On | Group |
|---|-------|------------|-------|
| 001 | Fix close_sprint dirty-tree failure and lock leak | — | 1 |
| 002 | Fix .codex/hooks.json schema and verify firing behavior | — | 1 |
| 003 | Drop misleading /se line from CLASI section template | — | 1 |
| 004 | Add .codex/agents/<name>.toml sub-agent install | — | 1 |
| 005 | Implement nested AGENTS.md rule files for Codex | — | 1 |
| 006 | End-to-end Codex install correctness tests | 002, 003, 004, 005 | 2 |
| 007 | Update README for corrected Codex install footprint | 006 | 3 |

**Groups**: Tickets in the same group can execute in parallel.
Groups execute sequentially (1 before 2, etc.).
