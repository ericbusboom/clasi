---
id: '006'
title: Right-size sprint-planner's plan output for small-scope sprints
status: open
use-cases: [SUC-006]
depends-on: []
github-issue: ''
issue: sprint-planner-excessive-plans-for-simple-projects.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Right-size sprint-planner's plan output for small-scope sprints

## Description

For a trivial 3-game stdlib Python CLI, sprint-planner consistently
produces 1,300-2,300 word plans with a Mermaid diagram in every sprint.
Sprint 018's right-sizing (single-document model) reduced volume about
30% but plans remain disproportionate: each sprint adds one about-60-line
module and tests, which should cost about 300-500 words of structured
bullets, not 2,000+ words with an architecture diagram.

Note the irony this ticket must act on: the sprint-planner agent
definition and `architecture-authoring` skill are exactly what needs
updating here, and this very sprint (020) is a live example of scope that
*does* warrant a real architecture-update.md (9 modules, cross-file
concerns, dependency direction call-outs) versus a single-module addition
that does not. The fix must make that distinction operational, not flatten
every plan to one size.

## Acceptance Criteria

- [ ] The sprint-planner agent definition and/or `architecture-authoring`
      skill states a concrete proportionality rule: e.g., a sprint adding
      one module with no new cross-module dependency gets a compact
      architecture-update (no diagram, roughly 300-500 words); a sprint
      touching 3+ modules or changing dependency direction gets full
      treatment.
- [ ] The rule gives the planner enough judgment criteria to self-assess
      scope size before writing (module count, whether dependencies
      change, whether the data model changes) rather than a purely
      word-count target that could be gamed by padding or truncating.
- [ ] Verification: a scratch/example single-module sprint plan produced
      under the new guidance lands at roughly 300-500 words with no
      Mermaid diagram.
- [ ] Regression: the guidance explicitly preserves full treatment for
      genuinely architectural sprints — cite this sprint (020) or a
      similarly-scoped prior sprint (e.g. 019) as the "still gets full
      treatment" example in the updated doc.

## Implementation Plan

**Approach**: Add an explicit sizing heuristic to the
`architecture-authoring` skill (and/or the sprint-planner agent
definition's Phase 2 instructions) that the planner applies before
starting Step 4 (diagrams) of the 7-step methodology — skip diagrams and
compress prose when scope is a single module with no new dependencies.

**Files likely involved**: `.claude/skills/architecture-authoring/`
(and `src/clasi/plugin/skills/architecture-authoring/` mirror),
`.claude/agents/sprint-planner/agent.md` (and plugin mirror).

**Testing plan**: No automated test possible for plan-writing judgment;
verify via a documented example (small scratch sprint) showing the before/
after word count and diagram presence.

**Documentation updates**: `architecture-authoring` skill,
`sprint-planner` agent definition — both the primary deliverable.
