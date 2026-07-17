---
id: '007'
title: 'Bootstrap skill: create/rework consolidate-architecture into bootstrap-design'
status: open
use-cases: [SUC-001, SUC-006]
depends-on: ['003', '004']
github-issue: ''
issue: persistent-per-subsystem-architecture-docs-with-sprint-update-overlays.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Bootstrap skill: create/rework consolidate-architecture into bootstrap-design

## Description

Write a new `bootstrap-design` skill (`.agents/skills/bootstrap-design/SKILL.md`)
that tells an agent how to: read the declared source roots, identify
subsystems (top-level directories under each root), derive canonical
filenames via `clasi.design.paths`, and write `docs/design/design.md`
plus one doc per subsystem plus frontmattered subsystem `README.md`
files via `clasi.design.store` — then validate via `clasi design
validate` and fix/re-validate on failure.

This skill absorbs `consolidate-architecture`'s reason for existing going
forward, per the issue's explicit instruction ("repurposes/absorbs
consolidate-architecture, whose single-doc output this design
supersedes"). `consolidate-architecture` itself is retained, unmodified,
as the mechanism for sprints still on the pre-021 single-big-document
model — do not delete it.

## Acceptance Criteria

- [ ] New skill file `.agents/skills/bootstrap-design/SKILL.md` exists
      with frontmatter (`name`, `description`) matching the format of
      existing skills (e.g. `architecture-authoring/SKILL.md`).
- [ ] Skill instructs the agent to read `Project.sources` and reject/flag
      the case where no `sources:` are declared (nothing to bootstrap).
- [ ] Skill instructs the agent to enumerate top-level directories under
      each declared source root as candidate subsystems, using judgment
      for what constitutes a "logical subsystem" (the issue leaves this
      to agent judgment, consistent with how `architecture-authoring`
      already asks for judgment in Step 2 "Identify Responsibilities").
- [ ] Skill instructs the agent to derive filenames via
      `clasi.design.paths` (not hand-slugify) and write via
      `clasi.design.store` (not hand-write frontmatter) — the whole point
      of tickets 002/003 is that this skill doesn't reimplement that
      logic in prose.
- [ ] Skill instructs the agent to run `clasi design validate` (or
      `validate_design`) after writing, and to fix and re-validate on any
      reported failure, per SUC-001's acceptance criteria.
- [ ] Skill documents how it differs from `consolidate-architecture`
      (single persistent doc set vs. one-off consolidated document) so an
      agent choosing between them (or the team-lead deciding which to
      dispatch) has a clear rule.
- [ ] `consolidate-architecture/SKILL.md` gains a short note pointing to
      `bootstrap-design` as the current mechanism for new/opted-in
      projects, without having its own existing content removed (it must
      keep working for sprints on the old model, per sprint.md's Out of
      Scope).

## Implementation Plan

**Approach**: Author prose only — no code in this ticket. Base the
skill's structure on the existing `architecture-authoring/SKILL.md` and
`consolidate-architecture/SKILL.md` files' shape and tone (both already
read during sprint planning) so the new skill feels consistent with its
siblings rather than introducing a new documentation style.

**Files to create/modify**:
- `.agents/skills/bootstrap-design/SKILL.md` (new)
- `.agents/skills/consolidate-architecture/SKILL.md` (small addition: a
  cross-reference note, not a rewrite)

**Testing plan**:
- No automated tests for skill prose itself. Verification is ticket 009
  (bootstrap run on this repo) actually following this skill and
  succeeding — treat that as this ticket's real acceptance test, executed
  as a dependent ticket.

**Documentation updates**:
- This ticket *is* documentation. No further doc updates needed beyond
  what's listed above.
