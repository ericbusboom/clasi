---
id: '007'
title: Finalize docs/design/design.md content and update team-lead/agent references
status: open
use-cases: [SUC-003]
depends-on: ['003', '006']
github-issue: ''
issue: co-locate-design-docs-as-design-md-in-source-replacing-readme.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Finalize docs/design/design.md content and update team-lead/agent references

## Description

Two parts:

**1. Finalize the design overlay.** This sprint already seeded, edited,
and diffed `clasi/sprints/022-.../design/design.md` at planning time
(via `clasi.design.overlay.seed_and_commit`/`generate_diffs`, run
directly since the session's MCP server predated the
`seed_sprint_design_overlay`/`validate_design` tools — see sprint.md's
Process Notes). That overlay copy describes the new co-located model
and updates the Subsystem Map links to `<subsystem>/DESIGN.md`. This
ticket verifies the overlay content is still accurate against what
tickets 001-006 actually built (subsystem paths, the exact link targets,
any naming detail that shifted during implementation) and updates the
overlay copy in place if implementation diverged from the plan —
re-running `generate_diffs` after any edit, per `architecture-authoring`'s
"Revising in place" convention. Do not edit the canonical
`docs/design/design.md` directly — the overlay `apply` step at sprint
close (or the equivalent library-call fallback, if the MCP server is
still stale then) is what publishes it.

**2. Update non-design-doc references.** `src/clasi/plugin/agents/
team-lead/agent.md` (lines ~133, ~151, ~227 as of planning time)
references `docs/design/design.md` existence checks and the "run
bootstrap-design to produce the initial `docs/design/` doc set"
framing. Verify: the `design.md` existence check itself is still valid
(the system doc doesn't move), but any framing suggesting subsystem
docs also live in `docs/design/` needs correcting to point at
co-located `DESIGN.md` files instead.

## Acceptance Criteria

- [ ] The sprint's overlay copy of `design.md` accurately reflects the
      as-built Subsystem Map (links to each subsystem's real
      `<subsystem>/DESIGN.md` path) — verified against ticket 003's
      actual migration output, not just the plan.
- [ ] `generate_diffs` re-run (if the overlay copy needed edits) so
      `design.diff.md` is not stale before architecture-review/
      stakeholder-review would re-read it.
- [ ] `team-lead/agent.md`'s `docs/design/` references are accurate:
      system-doc existence check preserved, subsystem-doc framing
      corrected to co-located `DESIGN.md`.
- [ ] `grep -rn "docs/design/<slug>\|docs/design/.*-design.md" src/clasi/plugin/`
      (or equivalent pattern for the old per-subsystem flat-file shape)
      returns no matches referring to a subsystem doc — only the 5
      project-level docs and `design.md` itself should still show
      `docs/design/` in that grep.

## Testing

- **Existing tests to run**: any test asserting on
  `team-lead/agent.md` content or `docs/design/design.md` structure.
- **New tests to write**: none required beyond ticket 008's end-to-end
  check; this is primarily a documentation-accuracy ticket.
- **Verification command**: `uv run clasi design validate` (confirms
  `design.md` itself still validates once applied/finalized)
