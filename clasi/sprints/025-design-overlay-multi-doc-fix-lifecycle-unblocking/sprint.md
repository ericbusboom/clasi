---
id: '025'
title: Design-overlay multi-doc fix + lifecycle unblocking
status: roadmap
branch: sprint/025-design-overlay-multi-doc-fix-lifecycle-unblocking
worktree: false
use-cases: []
issues:
- design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md
- norecursedirs-stale-e2e-project-breaks-bare-pytest-and-close-sprint.md
- team-lead-agent-doc-contradicts-mcp-guard-on-create-sprint.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 025: Design-overlay multi-doc fix + lifecycle unblocking

## Goal

Fix the design-overlay machinery so a sprint can seed and run the full
overlay lifecycle (seed → edit → diff → validate → apply) for **every**
co-located `DESIGN.md` it touches, not just one; plus two small
non-`hook_handlers.py` correctness/staleness fixes.

## Scope

This is a roadmap-phase sprint. The three issues below are linked and
summarized here; full detail lives in the issue files themselves and is
not duplicated.

**1. Design overlay cannot seed multiple co-located DESIGN.md files per
sprint** (`design-overlay-cannot-seed-multiple-colocated-design-md-per-sprint.md`)
— PRIMARY issue, substantial. In the co-located design-doc model, every
subsystem's canonical doc is named `DESIGN.md`, but the sprint overlay
directory is flat and keys entries by basename — so a sprint touching
more than one subsystem doc can only ever overlay one of them; the rest
get edited directly on the canonical files, bypassing the seed → edit →
diff → validate → apply lifecycle entirely. `seed_sprint_design_overlay`
also hardcodes `docs/design/` as the base path, which predates
co-location. Stakeholder-decided fix: slugify overlay filenames
(hyphenated, e.g. `firm-app-DESIGN.md`) so multiple docs can coexist in
the flat overlay dir; the existing `_sources.json` manifest already
disambiguates `apply()` and `generate_diffs()` and does not need to
change. Four touchpoints identified: `seed_sprint_design_overlay`
(`artifact_tools.py`), `seed_and_commit` (`overlay.py`), the validator's
overlay check (`validator.py` — must match via the manifest rather than
basename), and skill prose (plan-sprint / architecture-authoring /
bootstrap-design — instruct overlaying every touched doc, not just one).

**2. Stale `norecursedirs` breaks bare pytest and close-sprint**
(`norecursedirs-stale-e2e-project-breaks-bare-pytest-and-close-sprint.md`)
— trivial, one-line `pyproject.toml` fix. `norecursedirs` lists the older
e2e fixture project paths but not `tests/e2e/e2e-project` (introduced by
the sprint-023 e2e-harness rework), so a bare `uv run pytest` from the
repo root tries to collect that nested standalone project's test modules
and fails with import collisions, breaking both ad-hoc test runs and
`close_sprint`'s test-suite gate.

**3. team-lead agent doc contradicts mcp-guard on create_sprint**
(`team-lead-agent-doc-contradicts-mcp-guard-on-create-sprint.md`) —
trivial, plugin-source docs sync. `.claude/agents/team-lead/agent.md`
still instructs the team-lead to call `create_sprint` directly in two
places, but the `mcp-guard` PreToolUse hook blocks tier-0 (team-lead)
calls to `mcp__clasi__create_sprint`, requiring dispatch to
sprint-planner instead. Every team-lead session that follows the
documented flow verbatim gets denied. Fix is a docs correction to match
the enforced (and correct) behavior.

### Out of scope

All `hook_handlers.py` issues — `db-backed-oop-flag`,
`get-project-upward-discovery`, `role-guard-plans-dir`,
`sprint-planner-tier-1` — are explicitly excluded from this sprint.
There is uncommitted, concurrent work in `src/clasi/hook_handlers.py` and
`tests/unit/test_hook_handlers.py` from another session; this sprint must
not touch either file to avoid colliding with that in-flight work.

Also out of scope, as unrelated to this sprint's theme:
`clasi-init-reverts-mcp-config` and `claude-cli-openrouter`.

## Deferred to detail-planning

Sizing/tiering, tickets, and the Architecture and Use Cases sections are
deferred to Phase 2 (detail-planning), pending stakeholder review of this
roadmap scope. No architecture work, ticket creation, branch creation, or
execution-lock acquisition has been done as part of this roadmap sprint.

## GitHub Issues

(GitHub issues linked to this sprint's tickets. Format: `owner/repo#N`.)

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning document is complete (sprint.md, including its
      Architecture and Use Cases sections)
- [ ] Architecture review passed (or skipped, for changes with no
      architectural impact)
- [ ] Stakeholder has approved the sprint plan

## Tickets

| # | Title | Depends On |
|---|-------|------------|

Tickets execute serially in the order listed.
