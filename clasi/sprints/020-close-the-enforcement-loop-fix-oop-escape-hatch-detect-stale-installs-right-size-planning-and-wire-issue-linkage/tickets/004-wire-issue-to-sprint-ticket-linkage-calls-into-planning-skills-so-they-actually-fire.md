---
id: '004'
title: Wire issue-to-sprint/ticket linkage calls into planning skills so they actually
  fire
status: open
use-cases: [SUC-004]
depends-on: []
github-issue: ''
issue: issue-linkage-never-fires-all-sprints-empty.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Wire issue-to-sprint/ticket linkage calls into planning skills so they actually fire

## Description

Sprint 014 built the full issue→sprint→ticket→done lifecycle
(`link_sprint_issues`, `create_ticket(issue=)`, `add_issue_ref`,
`move_issue_to_done`) and added instructions to `sprint-roadmap`,
`plan-sprint`, `create-tickets`, `team-lead`, and `close-sprint` skill
docs. E2E run 003 shows all 4 sprints with `issues: []` regardless —
agents never invoke the tools despite the docs. This sprint's own planning
(sprint 020 itself) explicitly called `link_sprint_issues` for all 9
issues up front and passed `issue=` per ticket, proving the tools work
when actually invoked; the gap is that agents aren't reliably prompted to
invoke them at the right moment, not that the mechanism is broken.

Investigate why the existing instructions don't fire agent behavior: is
the instruction buried, worded as optional, or missing from the actual
call sequence an agent follows? Strengthen whatever's weakest — this is a
prompting/skill-doc problem, not a new tool to build.

## Acceptance Criteria

- [ ] Read `sprint-roadmap`, `plan-sprint`, `create-tickets` skill docs and
      identify concretely why the existing instructions (added in sprint
      014) don't reliably trigger `link_sprint_issues`/`issue=` calls —
      cite the specific weak instruction, not a guess.
- [ ] Strengthen the identified gap (e.g., make the call a numbered,
      required step rather than a mentioned option; add it earlier in the
      workflow where it's harder to skip).
- [ ] A test sprint created end-to-end (roadmap → detail → tickets) with
      2+ real issues linked at the start shows non-empty `issues:` in
      `sprint.md` frontmatter and correct per-ticket `issue:` fields,
      driven by following the actual skill doc instructions as written
      (not hand-invoking the MCP tools out of band).
- [ ] No regression to sprint 020's own linkage (this sprint is itself a
      correctly-linked example — don't break it).

## Implementation Plan

**Approach**: This is a documentation/prompting fix, not a code fix.
Read the current skill docs end to end, find where the instruction is
weak (missing "you must," buried in a long list, not tied to a concrete
tool call), and make it concrete and hard to skip — mirroring how sprint
020's own planning (this sprint) already demonstrates the tools working
when called deliberately.

**Files likely involved**: `.claude/skills/sprint-roadmap/`,
`.claude/skills/plan-sprint/`, `.claude/skills/create-tickets/`, possibly
`.claude/agents/team-lead/agent.md` and `.claude/agents/sprint-planner/agent.md`
(and their `plugin/` mirrors — check `src/clasi/plugin/skills/` and
`src/clasi/plugin/agents/` for the shipped copies that need the same fix).

**Testing plan**: Scripted or manual end-to-end sprint creation exercising
the actual skill instructions; assert linkage fields are populated.

**Documentation updates**: The skill docs themselves are the fix.
