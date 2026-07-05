---
name: architecture-review
description: Review sprint architecture updates for consistency, quality, and risk
---

Evaluates a sprint's `sprint.md` Architecture section for consistency with the existing system, design quality, risks, and completeness, then issues an APPROVE, APPROVE WITH CHANGES, or REVISE verdict. Skippable for small sprints -- see below.

## Skippable for Small Sprints

This review is not mandatory for every sprint. If the sprint-planner's
effort decision (see the sprint-planner `agent.md`) classified the sprint
as trivial/small, skip this review entirely and record the gate result as
`skipped` via `record_gate_result(sprint_id, "architecture_review",
"skipped")`. Only substantial/structural sprints require the full review
below.

## Instructions

Load from: `clasi/schemas/se-process/instructions/architecture-update.md`
