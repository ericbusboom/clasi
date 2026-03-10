---
name: elicit-requirements
description: Runs the requirements elicitation workflow to produce a project overview from a stakeholder narrative
---

# Elicit Requirements Skill

This skill runs the requirements elicitation workflow to produce a project
overview from a stakeholder narrative.

## Agent Used

**requirements-analyst**

## Inputs

- A stakeholder narrative describing the project (provided by the user or
  project-manager)

## Process

1. **Accept narrative**: Take the initial project description or
   conversation about what the project should do.
2. **Ask clarifying questions**: Ask about stakeholders, problem,
   components, requirements, constraints, success criteria, and out of scope.
3. **Write overview**: Produce `docs/plans/overview.md` using the
   `create_overview` MCP tool. The overview is a single lightweight document
   covering project name, problem statement, target users, key constraints,
   high-level requirements, technology stack, sprint roadmap, and out of
   scope. When illustrating system structure, data flow, or component
   relationships, prefer Mermaid diagrams over ASCII art.
4. **Verify completeness**: Every section of the overview should be filled
   in. High-level requirements should be testable. Sprint roadmap should
   sketch out the first few sprints.

## Output

- `docs/plans/overview.md` (created or updated)

## Notes

For existing projects that already have separate `brief.md`, `usecases.md`,
and `technical-plan.md` files, those files remain valid. The overview
document is the recommended approach for new projects.
