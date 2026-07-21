---
status: done
---

# team-lead skips multi-sprint roadmapping, jumps straight to detail-planning sprint 1

## Description

When the stakeholder hands the team-lead a batch of open issues (e.g.
"let's go take care of these tickets"), the team-lead should look at the
actual scope of the work and decide how many sprints it takes — one, or
several. If it's several, it should roadmap the whole arc (a lightweight
pass over every sprint) before detail-planning just the first one, so
the stakeholder can see the whole picture before work starts. What
actually happens today: the team-lead always creates and fully
detail-plans exactly one sprint, then executes it, regardless of how
much work the issues actually represent.

This is not about recognizing a special phrasing from the stakeholder —
"let's go take care of these tickets" doesn't signal "multi-sprint" any
more than it signals "single-sprint." The decision is the team-lead's to
make, from the content of the issues, the same way the sprint-planner
already makes its own trivial/compact/substantial sizing judgment call.
This matches the documented real-world usage pattern in
`tests/e2e/stakeholder-persona.md` ("plan the first sprint completely,
the rest first-pass, then stop and let me look at the sprints, and then
I'll kick you off on them") and Mode D / Milestone 0 of the e2e test
script.

## Cause

- `.claude/skills/sprint-roadmap/SKILL.md`, `.claude/skills/plan-sprint/SKILL.md`
  (which already fully models the two-phase Roadmap → Detail flow), and
  the sprint-planner agent's Roadmap Mode / Detail Mode split
  (`.claude/agents/sprint-planner/agent.md` lines 46-69, 133-134) are all
  already correctly built and capable of exactly this flow.
- `.claude/agents/team-lead/agent.md`'s **"Execute Issues Through a
  Sprint"** scenario (lines 72-104) — the scenario that already matches
  "take these issues through the process" — is hard-coded to a *single*
  `create_sprint` call (step 2) followed immediately by full detail
  planning (step 4) and execution through close. It never looks at how
  much work the captured issues actually represent before committing to
  exactly one sprint. `sprint-roadmap` is invoked in exactly one other
  place in the whole file: "Project Initiation" (lines 34-47), which
  only fires when there's no `overview.md` yet — inapplicable to an
  established project with a backlog.
- Sprint creation must go through the sprint-planner, never a direct
  team-lead `create_sprint` call — see Related below.

## Proposed fix

Rework "Execute Issues Through a Sprint" in
`.claude/agents/team-lead/agent.md` to make the one-sprint-vs-many
decision itself, in place, instead of assuming one sprint. No new
top-level scenario, no stakeholder-phrasing heuristic. No changes needed
to the skills or the sprint-planner agent — both are already correct.

Revised steps for "Execute Issues Through a Sprint":

1. **Capture issues** if raw ideas are given (unchanged).
2. **Assess scope.** Read the issues in play. Decide whether they fit
   one cohesive sprint or need to be broken into an arc of several —
   the same kind of judgment call the sprint-planner already makes for
   trivial/compact/substantial sizing (related functionality, dependency
   ordering, incremental value, difficulty balancing — the existing
   `sprint-roadmap`/`plan-sprint` Phase 1 grouping criteria). This is a
   normal part of taking on the work, not a special case requiring the
   stakeholder to ask for it.
3. **Roadmap.** Dispatch the sprint-planner agent in Roadmap Mode once
   per sprint the work is grouped into — one dispatch if it's a single
   sprint, several if it's an arc. Each dispatch creates one lightweight
   `status: roadmap` sprint. Link issues to each roadmap sprint via
   `link_sprint_issues` immediately after each dispatch reports back a
   sprint id (never a direct team-lead `create_sprint` call).
4. **Detail-plan the first sprint only.** Dispatch the sprint-planner
   again (Detail Mode — it self-detects via the existing `status:
   roadmap` check) to advance only the first roadmap sprint to full
   planning (architecture, use cases, tickets). Remaining sprints in the
   arc, if any, stay in roadmap phase for now.
5. **Stakeholder review.** Present the plan: the full roadmap (all
   sprints, lightweight, if more than one) plus the first sprint's full
   detail plan. Record `record_gate_result(sprint_id, "stakeholder_approval", "passed")`
   once approved.
6. **Acquire execution lock.** Call `acquire_execution_lock(sprint_id)`
   for the first sprint.
7. **Execute tickets.** Invoke `execute-sprint` (unchanged).
8. **Validate.** Invoke `sprint-review` (unchanged).
9. **Close.** Invoke `close-sprint` (unchanged).
10. **Next sprint in the arc, if any.** When the stakeholder is ready
    for the next sprint, detail-plan it the same way step 4 did (it's
    already roadmapped — just needs Detail Mode), then repeat steps 5-9.
    A brand-new "which sprint next" conversation with the stakeholder is
    not required — the roadmap already answered that; the team-lead
    picks up the next roadmap-phase sprint in order unless told
    otherwise.

This collapses what a single sprint looks like (steps 2-3 produce
exactly one roadmap sprint, step 4 details it) with what an arc looks
like (steps 2-3 produce several) into the same flow — there's no fork to
maintain, no phrase to detect, just one scope-assessment step up front.

Only `.claude/agents/team-lead/agent.md` needs changes — "Execute Issues
Through a Sprint" gets rewritten per above (steps 2-3 replace the old
single "Create the sprint" step; step 10 is new). "Capture Ideas and
Plans" is untouched — its existing quick-capture vs. discussed-planning
fork is a separate, correct distinction and isn't part of this gap.

## Verification

- Read back the edited `agent.md` and confirm: (a) every `create_sprint`
  reference is a sprint-planner dispatch, never a direct team-lead MCP
  call, (b) the single-sprint case still reads naturally as a special
  case of the general flow (one sprint out of the scope assessment, not
  a degenerate/awkward path), (c) step 5's stop-for-review behavior
  isn't accidentally skipped when there's only one sprint.
- No code changes, so no test suite to run — this is a prose/process
  documentation fix. Validate by walking through the revised scenario
  mentally against `tests/e2e/script.md` Milestone 0 (which already
  exercises exactly this pattern) and confirming the new steps would
  produce that milestone's expected outcome (overview + first-sprint
  detail plan + lightweight roadmap for the rest, stopped for review).

## Related

- `team-lead-agent-doc-contradicts-mcp-guard-on-create-sprint.md` — the
  fix above is written consistent with that issue's "Option A"
  (dispatch-only `create_sprint` via sprint-planner), not compounding
  the same contradiction.
