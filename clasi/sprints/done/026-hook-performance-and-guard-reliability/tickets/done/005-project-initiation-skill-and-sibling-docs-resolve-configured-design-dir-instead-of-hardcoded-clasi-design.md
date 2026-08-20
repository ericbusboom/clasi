---
id: '005'
title: 'project-initiation skill and sibling docs: resolve configured design_dir instead
  of hardcoded .clasi/design/'
status: done
use-cases:
- SUC-007
depends-on:
- '001'
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

- [x] `project-initiation/SKILL.md` instructs writing the three
      initiation documents to the project's configured `design_dir`
      (resolved dynamically, e.g. via `get_status` or an MCP tool that
      reports `Project.design_dir`), not a hardcoded `.clasi/design/`
      literal.
- [x] Every sibling doc found by `grep -rl '\.clasi/design'` under
      `src/clasi/plugin/` is reviewed and updated consistently:
      `instructions/software-engineering.md`,
      `agents/sprint-planner/plan-sprint.md`,
      `agents/sprint-planner/agent.md`,
      `agents/team-lead/project-status.md`,
      `skills/sprint-roadmap/SKILL.md`, `skills/project-status/SKILL.md`,
      `skills/architecture-authoring/SKILL.md`.
- [x] `migrate_command.py`'s `.clasi/design/` references are reviewed
      individually — only literal instructional/default-path references
      are changed; legitimate migration-source-path literals (the old
      location migrate reads *from*) are left alone. Document which
      category each hit fell into in the PR/commit description.
- [x] Regression test: real captured payload, tier 1, write to a
      custom-configured `design_dir` (e.g. `docs/design`) → allowed,
      reason `artifact-dir`; tier 1, write to a source path → still
      blocked.
- [x] End-to-end scenario test: a project configured with
      `paths.design: docs/design` and no `protected_paths:` — a
      dispatched sprint-planner (tier 1) following `project-initiation`
      writes the three documents successfully, and the project's
      `initialize` transition (`overview_exists()`) recognizes them,
      advancing past `uninitialized`.

## Implementation Notes

**get_status has no design_dir field**: confirmed by inspecting
`get_status`/`build_status`/`narrow_status` (src/clasi/tools/process_tools.py,
src/clasi/status/__init__.py) — no MCP-facing field reports
`Project.design_dir`. Every instructional replacement therefore tells
the reader to resolve `paths.design` from the `paths:` map in
`.clasi/config.yaml` directly (default `docs/design/` when the file or
key is absent), rather than pointing at a nonexistent `get_status`
field.

**Files changed (plugin source, `src/clasi/plugin/`)**:
`skills/project-initiation/SKILL.md`,
`instructions/software-engineering.md` (2 literal hits, plus the
Directory Layout ASCII tree, which showed the same wrong
`.clasi/design/overview.md` default and would have self-contradicted
the fixed prose two sections above it — updated for consistency even
though it wasn't a literal grep hit),
`agents/sprint-planner/plan-sprint.md`, `agents/sprint-planner/agent.md`,
`agents/team-lead/project-status.md`, `skills/sprint-roadmap/SKILL.md`,
`skills/project-status/SKILL.md`, `skills/architecture-authoring/SKILL.md`.

**`migrate_command.py` — single hit, reviewed, left unchanged**: line 67,
`CANDIDATE_LOCATIONS["design"] = [".clasi/design", "docs/clasi/design"]`.
Per the module's own docstring ("Destinations are always resolved live
from the Project object"), this table lists legacy/alternate *source*
locations `clasi migrate` moves artifacts *from* — never a
current/target instructional path. This is exactly the "legitimate
migration-source-path literal" category the ticket calls out; no change
made.

**Installed-copy convention (checked `src/clasi/platforms/claude.py`
and the sprint 022/021 commit history, e.g. b52c63f, 248048c)**: skills
are installed as a tracked canonical copy at
`.agents/skills/<name>/SKILL.md` (git-tracked, dogfooded in this repo)
aliased via symlink at `.claude/skills/<name>/SKILL.md`
(`.claude/` is entirely gitignored). Agents have no tracked canonical
mirror — `.claude/agents/<name>/*.md` are gitignored direct copies of
`src/clasi/plugin/agents/<name>/*.md` with nothing else tracking them.
Applied accordingly: propagated the same fix into the four affected
`.agents/skills/*/SKILL.md` canonical copies
(`project-initiation`, `sprint-roadmap`, `project-status`,
`architecture-authoring` — targeted edits only, not a full
reconciliation of `architecture-authoring`'s unrelated pre-existing
drift from plugin source found while diffing) so `.claude/skills/*`
picks them up live via the symlink; also refreshed the three
gitignored `.claude/agents/*.md` copies by re-copying the fixed plugin
source over them (mirrors what `clasi init`'s installer does) purely
for this session's own live agent-definition consistency — these are
untracked and not part of the commit.

**Bonus (adjacent, not in the ticket's file list)**: `README.md:91`
carried the identical `.clasi/design/overview.md` claim in
user-facing top-level documentation. Fixed for consistency with the
rest of this pass.

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
