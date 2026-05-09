---
id: "A"
title: "CLASI artifact layout migration to .clasi/"
status: planning
branch: sprint/A-clasi-artifact-layout-migration
use-cases: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint A: CLASI artifact layout migration to `.clasi/`

## Goals

Land all four overlapping layout TODOs as a single coordinated change, so the test suite churns once and rule files / agent prompts / installers re-render in one pass:

- Move CLASI's artifact root from `docs/clasi/` to `.clasi/` in target projects and in this source repo.
- Rename the `TODO` artifact concept to `issue` (vocabulary, files, MCP tools, CLI, skill, frontmatter fields).
- Move issue lifecycle from `<root>/issues/in-progress|done/` into `<sprint>/issues/`. Issues claimed by a sprint travel with that sprint into `done/` at close.
- Consolidate the per-platform `.clasi-version` markers into one file at `.clasi/clasi-version`.
- Fix the latent bug where `Project.design_dir` points at an empty `docs/clasi/design/` instead of the populated `docs/design/`.

## Problem

Four TODOs propose changes to overlapping surface area (`Project` properties, `Todo`/`Issue` class, hook handlers, MCP tools, every rule file's path glob, and ~75 test references). Landing them separately would cause three to four rounds of cascading fixture/rule-file edits and breaks the historical "single grep target" property the layout move is supposed to deliver. The four TODOs being combined:

- `move-clasi-artifact-root-from-docs-clasi-to-dot-clasi`
- `rename-clasi-todos-to-issues`
- `sprint-scoped-issues-directory`
- `consolidate-the-clasi-version-marker-into-clasi-clasi-version`

`docs/clasi/` also mixes process artifacts with user-authored documentation in the same tree, which pollutes `docs/` for projects that publish a docs site. `.clasi/` parallels `.git/`, `.github/`, `.vscode/`.

## Solution

A single sprint with ticketed phases. Hard cut, no backward-compat shims:

1. **Vocabulary rename** (cheapest, no path moves yet): symbols `Todo` → `Issue`, `clasi/todo.py` → `clasi/issue.py`, MCP tools `list_todos`/`move_todo_to_done` → `list_issues`/`move_issue_to_done`, CLI `plan-to-todo` → `plan-to-issue`, skill `/todo` → `/issue`, ticket frontmatter `todo:` → `issue:` and `completes_todo:` → `completes_issue:`, status enum `status: todo` → `status: open` (collision fix).
2. **Path constants**: `Project.clasi_dir` returns `.clasi/`, all derived properties inherit. Hook handlers, installers, init, docstrings updated. `Project.design_dir` corrected to `docs/design/`.
3. **Issue lifecycle**: pending issues live at `.clasi/issues/`. `Issue.move_to_in_progress(sprint_id, ticket_id)` moves the file into `<sprint>/issues/`. `Issue.move_to_done` becomes frontmatter-only (no directory move). Add `Sprint.issues_dir` and `Sprint.list_issues()`. Drop `<root>/issues/in-progress` and `<root>/issues/done` entirely.
4. **Version marker single-write**: `write_version_stamp(target)` writes one file at `<target>/.clasi/clasi-version`. Each platform installer calls it once. Opportunistically delete stale `.clasi-version` files in old platform dirs. Uninstall removes `.clasi/clasi-version` and the `.clasi/` dir if empty.
5. **`clasi migrate` subcommand**: one-shot migration for downstream projects on the old layout. Verifies no execution lock, `git mv docs/clasi .clasi`, updates `.gitignore`, re-runs `clasi install --force`.
6. **Re-render** rule files, agent prompts, installer templates, README. This source repo's own artifacts get migrated in this sprint's close commit.

## Success Criteria

- `grep -rn "docs/clasi" clasi/ tests/ .claude/ .github/ AGENTS.md README.md` returns zero hits (historical references inside `.clasi/sprints/done/**` are exempt).
- `grep -rn "todo" clasi/ tests/ .claude/ .github/ AGENTS.md README.md` returns zero references to the old CLASI artifact concept (Python `# TODO:` comments and unrelated third-party usages may remain).
- `clasi install` on a fresh target creates `.clasi/issues/` (not `docs/clasi/todo/` or `docs/clasi/issues/`).
- This source repo's `.clasi/` is populated and `clasi project-status` runs successfully.
- `<sprint>/issues/` exists in any sprint that has claimed an issue; pending issues remain at `.clasi/issues/`.
- Closing a sprint moves `<sprint>/issues/` to `.clasi/sprints/done/<sprint>/issues/` automatically.
- Single `.clasi/clasi-version` file present after install; no `.clasi-version` files in `.claude/`, `.codex/`, `.agents/`, `.github/`.
- `README.md` and the SE-overview template each contain a clearly-headed "Issues vs Tickets" paragraph.
- Full test suite passes.
- `clasi migrate` smoke-tested against `rundbat` or `dotconfig`.

## Scope

### In Scope

- All code symbol/path/file renames listed in the four source TODOs.
- Status-enum value rename `todo` → `open` (template, validators, hooks, fixtures, agent prompts).
- New `clasi migrate` subcommand.
- Self-migration of this source repo (`docs/clasi` → `.clasi`).
- Re-render of all installer-generated rule files and agent prompts.
- README + SE-overview "Issues vs Tickets" documentation.

### Out of Scope

- Touching ticket markdown bodies inside `.clasi/sprints/done/**` (historical archives — leave references intact).
- Backward-compat dual-path reads or deprecated aliases. Hard cut.
- Authoring new design content. This sprint only relocates `Project.design_dir` to point at the existing `docs/design/`.
- Rewriting `architecture-update.md` format or position in the sprint flow (Sprint B owns that).

## Test Strategy

- Unit suite must stay green throughout. Restructure fixtures that hardcode `docs/clasi/` and `status: todo` in lockstep with the production code rename.
- New unit tests for `Issue.move_to_in_progress` to verify it lands in `<sprint>/issues/`, and for `Sprint.issues_dir`/`list_issues`.
- Integration test: fresh-project install → create issue → create sprint that claims it → verify file location → close sprint → verify file at `.clasi/sprints/done/<sprint>/issues/<filename>`.
- Migration smoke test: copy of an existing CLASI-managed project, run `clasi migrate`, verify `.clasi/` populated, `.gitignore` updated, `clasi project-status` clean.

## Architecture impact

`Project` becomes the single arbiter of CLASI paths. Hook handlers, MCP tools, and installers all consult `Project.clasi_dir` rather than hardcoded strings. Issue lifecycle moves from a top-level state-folder model to a sprint-scoped model — `Issue.move_to_done` no longer moves files; the sprint's own `done/` move is the archive operation.

## Dependencies / sequencing notes

- Land before Sprint B (delta-spec): Sprint B touches `architecture-update.md` location and would conflict with path moves done here.
- Land before Sprint D (schema-driven): the schema declares paths; pinning `.clasi/` first means the schema doesn't have to encode legacy `docs/clasi/` fallbacks.
- Independent of Sprint C, E, F.

## Source TODOs to be archived as superseded by this sprint

- `move-clasi-artifact-root-from-docs-clasi-to-dot-clasi.md`
- `rename-clasi-todos-to-issues.md`
- `sprint-scoped-issues-directory.md`
- `consolidate-the-clasi-version-marker-into-clasi-clasi-version.md`
