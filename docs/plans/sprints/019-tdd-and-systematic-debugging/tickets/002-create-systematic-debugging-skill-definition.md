---
id: "002"
title: "Create systematic-debugging skill definition"
status: done
use-cases: [SUC-002]
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create systematic-debugging skill definition

## Description

Create a new skill file `claude_agent_skills/skills/systematic-debugging.md`
that defines a structured four-phase debugging protocol. This replaces
ad hoc fix attempts with a disciplined approach that prevents agents from
thrashing on speculative patches.

The skill must define four phases:

**Phase 1 — Evidence Gathering:**
Collect all error messages, stack traces, logs, and recent changes.
Reproduce the issue reliably. Identify the exact input that triggers
the failure.

**Phase 2 — Pattern Analysis:**
Compare working vs. broken states. Identify what changed. Narrow the
scope to the smallest possible reproduction case.

**Phase 3 — Hypothesis Testing:**
Form a specific hypothesis about the root cause. Design a test that
would confirm or refute it. Run the test. If refuted, form a new
hypothesis.

**Phase 4 — Root Cause Fix:**
Fix the actual root cause, not symptoms. Verify the fix resolves the
original issue. Verify no regressions were introduced.

The skill must also include:

- **Three-attempt cap**: After three failed fix attempts, the agent must
  stop, document what was tried, and either escalate to the stakeholder
  or propose an architectural change. This prevents indefinite thrashing.
- **Escalation procedure**: When the cap is reached, the agent documents
  evidence collected, hypotheses tested, and results for each attempt.
  Then presents this to the stakeholder with a recommendation.
- **Audit trail requirement**: The agent must write down (in the ticket
  plan or a debug note) the evidence collected, hypotheses formed, and
  test results for each hypothesis. This prevents repeating the same
  failed approach.
- **Trigger conditions**: The skill should be invoked when:
  - A test that was passing starts failing
  - An implementation attempt fails its acceptance criteria
  - The agent has made two consecutive failed attempts to fix something

**Reference**: The implementer should read the Superpowers systematic
debugging skill file at `github.com/obra/superpowers`
(`systematic-debugging.md`) for implementation details, edge cases, and
phrasing conventions before writing this skill.

## Acceptance Criteria

- [x] Skill file exists at `claude_agent_skills/skills/systematic-debugging.md`
- [x] Frontmatter includes `name: systematic-debugging` and a description
- [x] All four phases are defined with clear instructions for each
- [x] Three-attempt cap is specified with explicit enforcement language
- [x] Escalation procedure is defined (what to document, how to present)
- [x] Audit trail requirement is defined (what to record and where)
- [x] Trigger conditions are listed (when the skill should be invoked)
- [x] All existing tests still pass

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_process_tools.py`
  (skill listing — new skill should appear in list)
- **New tests to write**: None (content-only markdown change; skill
  listing is tested by existing test infrastructure)
- **Verification command**: `uv run pytest tests/unit/test_process_tools.py`
