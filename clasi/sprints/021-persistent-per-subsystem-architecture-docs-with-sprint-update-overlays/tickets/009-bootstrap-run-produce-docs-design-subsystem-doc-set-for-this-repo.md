---
id: '009'
title: 'Bootstrap run: produce docs/design/ subsystem doc set for this repo'
status: open
use-cases: [SUC-001, SUC-003, SUC-006]
depends-on: ['001', '007']
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Bootstrap run: produce docs/design/ subsystem doc set for this repo

## Description

Record this repo's own opt-in decision (`sources: [src]`, doc-set
enabled, per ticket 001's config mechanism) and run the `bootstrap-design`
skill (ticket 007) against `src/clasi/` to produce the first real
persistent design doc set for this project. This is both a deliverable
(the actual docs) and the system-level acceptance test for tickets
001-004 and 007 working together correctly end to end — the sprint's
Success Criteria explicitly requires this to happen and to pass
validation afterward.

Resolves Open Question 2 from sprint.md's Architecture section: subsystem
docs coexist at the top level of `docs/design/` alongside the existing
frozen initiation docs (`overview.md`, `specification.md`,
`state-machines.md`, `usecases.md`, `worktree-process.md`) — no
subdirectory. Implementing this ticket is also the concrete check that
this recommendation holds (no filename collisions actually occur).

## Acceptance Criteria

- [ ] `.clasi/config.yaml` (this repo's own) gains `sources: [src]` and
      the doc-set opt-in recorded as enabled, using the mechanism built
      in ticket 001.
- [ ] `docs/design/design.md` exists, listing every subsystem identified
      under `src/clasi/`.
- [ ] Every top-level directory under `src/clasi/` identified as a
      subsystem (e.g. `tools/`, `schemas/`, `state_machine/`, `status/`,
      `platforms/`, `plugin/`, `templates/`, and top-level modules
      grouped sensibly — exact grouping is the bootstrap agent's
      judgment call per the skill) has a corresponding design doc under
      `docs/design/` and a frontmattered `README.md` in that source
      directory.
- [ ] No filename collision occurs between the new subsystem docs and the
      existing initiation docs (`overview.md`, `specification.md`,
      `state-machines.md`, `usecases.md`, `worktree-process.md`) —
      confirms Open Question 2's recommendation in practice, not just in
      theory.
- [ ] `clasi design validate` exits 0 against the resulting `docs/design/`
      tree.
- [ ] The produced docs describe the codebase at module/subsystem level
      (purpose, boundary, use cases served) — not function signatures or
      line-by-line detail, consistent with `architecture-authoring`'s
      existing "stay at module level" quality check.

## Implementation Plan

**Approach**: Follow the `bootstrap-design` skill (ticket 007) exactly,
as its own first real-world exercise. Read `src/clasi/`'s top-level
structure (already partially surveyed during this sprint's own planning
research — `agent.py`, `artifact.py`, `cli.py`, `contracts.py`,
`frontmatter.py`, `hook_handlers.py`, `init_command.py`, `issue.py`,
`mcp_server.py`, `migrate_command.py`, `plan_to_issue.py`, `project.py`,
`sprint.py`, `staleness.py`, `state_db.py`/`state_db_class.py`,
`ticket.py`, `uninstall_command.py`, `versioning.py`, plus directories
`platforms/`, `plugin/`, `schemas/`, `state_machine/`, `status/`,
`templates/`, `tools/` — this ticket's own executor should re-survey
rather than trust this stale list, since 001-008 will have added
`design/`).

**Files to create/modify**:
- `.clasi/config.yaml` (add `sources:` and opt-in fields).
- `docs/design/design.md` (new).
- `docs/design/<subsystem-slug>.md` (new, one per identified subsystem).
- `src/clasi/<subsystem>/README.md` (new, one per identified subsystem
  directory).

**Testing plan**:
- `clasi design validate` (CLI) run against the live repo, must exit 0.
- Manual read-through: does each doc read as a subsystem an agent could
  usefully load before editing that part of the codebase?

**Documentation updates**:
- This ticket's output is itself the documentation deliverable — no
  further updates needed elsewhere, beyond linking `design.md` from
  wherever the project's top-level docs index (if any) already points to
  `docs/design/overview.md` and friends.
