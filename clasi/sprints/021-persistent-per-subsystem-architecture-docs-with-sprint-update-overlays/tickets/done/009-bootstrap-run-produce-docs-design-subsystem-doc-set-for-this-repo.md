---
id: 009
title: 'Bootstrap run: produce docs/design/ subsystem doc set for this repo'
status: done
use-cases:
- SUC-001
- SUC-003
- SUC-006
depends-on:
- '001'
- '007'
- '010'
- '011'
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: true
exception:
  thrown_by: programmer
  thrown_at: '2026-07-17T06:02:59.486343+00:00'
  attempted: "After ticket 010 landed (design_doc_slug collision fallback), re-verified\
    \ computed filenames (design/ now correctly resolves to clasi-design.md, distinct\
    \ from the reserved design.md system-doc name) and executed the full bootstrap\
    \ write: .clasi/config.yaml already had sources: [src/clasi] and design_docs:\
    \ enabled from the first pass. Ran the scratchpad script (bootstrap_docs.py),\
    \ fixing several hardcoded subsystem-doc filename references in the system doc's\
    \ prose/table that had assumed the wrong (pre-ticket-010) collision-avoidance\
    \ naming scheme, to match the actual per-subsystem slugs computed via design_doc_slug\
    \ (platforms.md, plugin.md, schemas.md, state_machine.md, status.md, templates.md,\
    \ tools.md, and clasi-design.md for the one colliding case). Wrote all 8 subsystem\
    \ design docs, all 8 subsystem READMEs, and the system doc (docs/design/design.md)\
    \ via clasi.design.store.write_design_doc/write_readme/write_system_doc exclusively,\
    \ per the bootstrap-design skill's Step 4. Confirmed via `ls docs/design/` that\
    \ no filename collision occurs between the 8 new subsystem docs (clasi-design.md,\
    \ platforms.md, plugin.md, schemas.md, state_machine.md, status.md, templates.md,\
    \ tools.md) and the 5 existing frozen initiation docs (overview.md, specification.md,\
    \ state-machines.md, usecases.md, worktree-process.md) \u2014 this is Open Question\
    \ 2's recommendation holding in practice, exactly as ticket 009's acceptance criteria\
    \ requires. Then ran `uv run clasi design validate`, which exited 1 with five\
    \ \"Orphaned design doc\" messages, one for each of the five frozen initiation\
    \ docs (overview.md, specification.md, state-machines.md, usecases.md, worktree-process.md)."
  conflict: "clasi.design.validator._check_subsystem_docs's orphan-detection check\
    \ (validator.py, the \"Orphaned docs\" block after the filename-collision check\
    \ ticket 010 just added) flags any .md file in docs/design/ whose name is not\
    \ in expected_names (the system-doc name plus every subsystem's computed slug)\
    \ as an orphan. It has no allowance whatsoever for the five frozen initiation\
    \ docs (overview.md, specification.md, state-machines.md, usecases.md, worktree-process.md)\
    \ that sprint 021's own Architecture section, Open Question 2, explicitly approved\
    \ as coexisting at the top level of docs/design/ alongside subsystem docs (\"\
    Recommendation: coexist at the top level, no subdirectory... collision is already\
    \ avoided by design.md being the one reserved top-level name\"). That recommendation\
    \ addressed filename collision, not validator recognition \u2014 nothing in tickets\
    \ 001-004's implementation ever taught the validator that these five specific\
    \ filenames (or, more generally, \"docs not derived from any subsystem slug but\
    \ not therefore invalid\") are legitimate non-orphaned content. This blocks ticket\
    \ 009's own acceptance criterion (\"clasi design validate exits 0 against the\
    \ resulting docs/design/ tree\") using only the tools tickets 001-008 already\
    \ built \u2014 there is no config flag, allowlist, or parameter anywhere in clasi.design.validator,\
    \ clasi.design.store, or Project that lets a caller mark a doc as \"known non-subsystem\
    \ content, not an orphan.\" Fixing this correctly requires editing clasi.design.validator._check_subsystem_docs's\
    \ orphan-detection logic (ticket 004's module, the same module ticket 010 already\
    \ had to touch once this sprint for the collision bug) \u2014 e.g. excluding the\
    \ five frozen initiation-doc filenames, or more generally exempting docs whose\
    \ frontmatter lacks the subsystem-doc source_paths/readme_path shape from orphan-checking.\
    \ That is out of ticket 009's scope to decide and implement unilaterally: it is\
    \ a second, independent validator defect (distinct from the collision ticket 010\
    \ already fixed) that only a real bootstrap run against a repo with pre-existing\
    \ frozen initiation docs could surface, which is exactly what ticket 009 is for."
  surface: internal
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

- [x] `.clasi/config.yaml` (this repo's own) gains `sources: [src]` and
      the doc-set opt-in recorded as enabled, using the mechanism built
      in ticket 001.
- [x] `docs/design/design.md` exists, listing every subsystem identified
      under `src/clasi/`.
- [x] Every top-level directory under `src/clasi/` identified as a
      subsystem (e.g. `tools/`, `schemas/`, `state_machine/`, `status/`,
      `platforms/`, `plugin/`, `templates/`, and top-level modules
      grouped sensibly — exact grouping is the bootstrap agent's
      judgment call per the skill) has a corresponding design doc under
      `docs/design/` and a frontmattered `README.md` in that source
      directory.
- [x] No filename collision occurs between the new subsystem docs and the
      existing initiation docs (`overview.md`, `specification.md`,
      `state-machines.md`, `usecases.md`, `worktree-process.md`) —
      confirms Open Question 2's recommendation in practice, not just in
      theory.
- [x] `clasi design validate` exits 0 against the resulting `docs/design/`
      tree.
- [x] The produced docs describe the codebase at module/subsystem level
      (purpose, boundary, use cases served) — not function signatures or
      line-by-line detail, consistent with `architecture-authoring`'s
      existing "stay at module level" quality check.

## Implementation Notes

This bootstrap run surfaced two real, distinct defects in tickets 001-008's
`clasi.design` implementation — exactly the "system-level acceptance test"
role this ticket's description says it plays. Both were escalated via
`throw_ticket_exception` rather than patched unilaterally (out of this
ticket's module scope), resolved upstream, then this run resumed.

1. **Filename collision: subsystem `design/` vs. the system doc.** With
   this repo's single source root (`src/clasi`), `design_doc_slug`'s
   single-root rule (root name omitted) computed `design.md` for the
   `design/` subsystem — identical to the reserved `SYSTEM_DOC_NAME`.
   Writing both would have silently clobbered one with the other, and the
   validator's `expected_names` set union collapsed the collision into one
   entry, so neither the "system doc present" nor "subsystem has a doc"
   check would have caught it. Resolved by ticket 010 (commit `829e314`):
   `design_doc_slug` now falls back to the root-qualified form when a
   single-root slug would equal `SYSTEM_DOC_NAME` (`design/` -> `clasi-
   design.md`), raises `DesignPathError` on a residual collision, and the
   validator now computes each subsystem's slug individually and reports
   collisions as an explicit, actionable message instead of silently
   collapsing them.
2. **Validator had no allowance for the frozen initiation docs.** Sprint
   021's own Architecture Open Question 2 explicitly approved the five
   frozen initiation docs (`overview.md`, `specification.md`, `state-
   machines.md`, `usecases.md`, `worktree-process.md`) coexisting at the
   top level of `docs/design/` alongside subsystem docs — but that
   recommendation addressed filename collision only, not validator
   recognition. `_check_subsystem_docs`'s orphan check flagged all five as
   orphaned, blocking this ticket's own "`clasi design validate` exits 0"
   acceptance criterion using only the tools 001-008 had built. Resolved
   by ticket 011 (commit `64c247f`): the orphan check now applies only to
   docs carrying the subsystem-doc frontmatter shape (`source_paths`/
   `readme_path`); frontmatter-less files are reported as non-blocking
   INFO lines instead of ERROR. Re-run after the fix:
   `uv run clasi design validate` exits 0 with five INFO lines (one per
   initiation doc).

**Subsystem grouping decision**: the mechanical enumeration
(`clasi.design.store._subsystem_dirs`) only considers directories one
level under `src/clasi/` (`design`, `platforms`, `plugin`, `schemas`,
`state_machine`, `status`, `templates`, `tools` — all eight got a design
doc + README). `src/clasi/`'s many loose top-level `.py` files (no
enclosing subdirectory) have no mechanical subsystem slot and are
described narratively in `design.md` under a `clasi-core` heading instead
of getting individual docs — flagged as an open question in `design.md`
and `clasi-design.md` for a future sprint to resolve if that loose-file
surface grows large enough to need its own maintained doc.

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
