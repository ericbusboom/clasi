---
id: '005'
title: 'project-initiation skill and sibling docs: resolve configured design_dir instead
  of hardcoded .clasi/design/'
status: open
use-cases: [SUC-007]
depends-on: ['001']
github-issue: ''
issue: role-guard-tier1-design-dir-and-initiation-skill-hardcoded-path.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# project-initiation skill and sibling docs: resolve configured design_dir instead of hardcoded .clasi/design/

## Description

`plugin/skills/project-initiation/SKILL.md` (lines 25, 38, 42, 48, 59)
hardcodes `.clasi/design/` as the destination for
`overview.md`/`specification.md`/`usecases.md`, but `Project.design_dir`
is configurable via `paths.design` and already *defaults* to
`docs/design/` — so the hardcoded path is wrong even for default-config
projects, not just custom ones. `overview_exists()` checks
`design_dir / "overview.md"`, so a skill-compliant write to
`.clasi/design/overview.md` leaves the `initialize` transition
permanently blocked regardless of ticket 001's tier-1 allow-list fix.
Several sibling docs make the same literal-path mistake. This ticket
fixes the instructional content to resolve the configured path instead
of naming a literal one.

**Depends on ticket 001**: this ticket's end-to-end verification (a
tier-1 sprint-planner's write actually succeeding) requires ticket 001's
tier-1 artifact-dir allow-list fix to already be in place — without it,
the write would still be blocked regardless of what the skill instructs.

## Acceptance Criteria

- [ ] `project-initiation/SKILL.md` instructs writing the three
      initiation documents to the project's configured `design_dir`
      (resolved dynamically, e.g. via `get_status` or an MCP tool that
      reports `Project.design_dir`), not a hardcoded `.clasi/design/`
      literal.
- [ ] Every sibling doc found by `grep -rl '\.clasi/design'` under
      `src/clasi/plugin/` is reviewed and updated consistently:
      `instructions/software-engineering.md`,
      `agents/sprint-planner/plan-sprint.md`,
      `agents/sprint-planner/agent.md`,
      `agents/team-lead/project-status.md`,
      `skills/sprint-roadmap/SKILL.md`, `skills/project-status/SKILL.md`,
      `skills/architecture-authoring/SKILL.md`.
- [ ] `migrate_command.py`'s `.clasi/design/` references are reviewed
      individually — only literal instructional/default-path references
      are changed; legitimate migration-source-path literals (the old
      location migrate reads *from*) are left alone. Document which
      category each hit fell into in the PR/commit description.
- [ ] Regression test: real captured payload, tier 1, write to a
      custom-configured `design_dir` (e.g. `docs/design`) → allowed,
      reason `artifact-dir`; tier 1, write to a source path → still
      blocked.
- [ ] End-to-end scenario test: a project configured with
      `paths.design: docs/design` and no `protected_paths:` — a
      dispatched sprint-planner (tier 1) following `project-initiation`
      writes the three documents successfully, and the project's
      `initialize` transition (`overview_exists()`) recognizes them,
      advancing past `uninitialized`.

## Implementation Plan

**Approach**: Replace each hardcoded `.clasi/design/` literal with
instructional text describing how to resolve the configured path (e.g.
"write to the project's configured design directory, reported by
`Project.design_dir` / surfaced via `get_status`"), matching how other
skill docs in this codebase already describe resolving configured paths
rather than naming defaults. Verify the fix by running the actual
project-initiation flow against a fixture project with a
non-default `paths.design` value.

**Files to modify**:
- `src/clasi/plugin/skills/project-initiation/SKILL.md`.
- `src/clasi/plugin/instructions/software-engineering.md`.
- `src/clasi/plugin/agents/sprint-planner/plan-sprint.md`.
- `src/clasi/plugin/agents/sprint-planner/agent.md`.
- `src/clasi/plugin/agents/team-lead/project-status.md`.
- `src/clasi/plugin/skills/sprint-roadmap/SKILL.md`.
- `src/clasi/plugin/skills/project-status/SKILL.md`.
- `src/clasi/plugin/skills/architecture-authoring/SKILL.md`.
- `src/clasi/migrate_command.py` (selective — see acceptance criteria).

**Testing plan**: An end-to-end fixture test standing up a temp project
with `paths.design: docs/design`, dispatching a tier-1-tagged write
attempt through `handle_role_guard` with a real captured
`project-initiation`-shaped payload, and asserting both the guard
allows it and `overview_exists()` sees the result. A guard-level
regression test with real captured payloads for the allow/deny pair.

**Documentation updates**: This sprint's `design/` overlay
(`plugin-DESIGN.md`) already documents this change at the module level.
