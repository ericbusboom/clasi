---
id: "001"
title: "Create tdd-cycle skill definition"
status: done
use-cases: [SUC-001]
depends-on: []
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Create tdd-cycle skill definition

## Description

Create a new skill file `claude_agent_skills/skills/tdd-cycle.md` that
defines the red-green-refactor workflow as an **optional** development
methodology. TDD is not the default and is not mandatory — it is an
available option that agents or stakeholders can invoke when appropriate.

The skill must define the complete TDD cycle:

1. **Red** — Write a failing test that describes the desired behavior.
2. **Confirm red** — Run the test and confirm it fails. Record the
   specific failure message. This step is mandatory within the cycle —
   "if you didn't watch it fail first, you don't know it works."
3. **Green** — Write the minimum production code to make the test pass.
4. **Confirm green** — Run the test and confirm it passes.
5. **Refactor** — Clean up the code while keeping tests green.
6. **Commit** — Commit at the green state.

The skill must also include:

- **When-to-use guidance**: TDD is most useful for well-defined
  interfaces, complex logic, and code where correctness is critical.
  Implement-then-test is fine for configuration changes, documentation
  updates, exploratory spikes, and UI layout work.
- **Unexpected pass handling**: If a test passes when it should fail
  (step 2), the test is wrong or the feature already exists. The agent
  must investigate before proceeding — do not just continue to the
  green phase.
- **Integration with ticket workflow**: The skill is invoked during the
  implementation phase of execute-ticket. It does not replace the
  existing test requirements — tests are still required regardless of
  whether TDD was used.

**Reference**: The implementer should read the Superpowers TDD skill
file at `github.com/obra/superpowers` (`tdd.md`) for implementation
details, edge cases, and phrasing conventions before writing this skill.

## Acceptance Criteria

- [x] Skill file exists at `claude_agent_skills/skills/tdd-cycle.md`
- [x] Frontmatter includes `name: tdd-cycle` and a description
- [x] Complete red-green-refactor cycle is defined with all six steps
- [x] Each step is a discrete action the agent must perform and report on
- [x] Includes when-to-use guidance (TDD vs implement-then-test)
- [x] TDD is presented as optional, not mandatory or default
- [x] Includes unexpected-pass handling (test passes when it should fail)
- [x] Includes guidance on recording failure messages before writing code
- [x] All existing tests still pass

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_process_tools.py`
  (skill listing — new skill should appear in list)
- **New tests to write**: None (content-only markdown change; skill
  listing is tested by existing test infrastructure)
- **Verification command**: `uv run pytest tests/unit/test_process_tools.py`
