---
id: "003"
title: "Update execute-ticket, testing, and SE instructions"
status: done
use-cases: [SUC-003]
depends-on: ["001", "002"]
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update execute-ticket, testing, and SE instructions

## Description

Update three existing instruction/skill files to reference the new
tdd-cycle and systematic-debugging skills created in tickets 001 and 002.
These are cross-reference updates — the new skills exist as standalone
files, and these changes wire them into the existing process at the
appropriate points.

### 1. Update `claude_agent_skills/skills/execute-ticket.md`

- In step 4 (Implement), add a note that the **tdd-cycle** skill is
  available as an optional approach. The agent or stakeholder may choose
  to use TDD for the implementation phase. This is not the default —
  it is an option. Phrasing should be something like: "If TDD is
  appropriate for this ticket (well-defined interfaces, complex logic),
  consider using the `tdd-cycle` skill for the implementation phase."
- In the Error Recovery section under "Test failures", add a reference
  to the **systematic-debugging** skill. When simple diagnosis does not
  resolve a test failure, the agent should invoke the debugging skill
  rather than making rapid speculative changes. Add the trigger
  conditions: invoke after two consecutive failed fix attempts, or when
  a previously passing test breaks.

### 2. Update `claude_agent_skills/instructions/testing.md`

- Add a new section (e.g., "## Development Methods") between "Core Rule"
  and "Test Placement" that references TDD as an available method.
  Explain that TDD (red-green-refactor) is available via the `tdd-cycle`
  skill and is most useful for well-defined interfaces and complex logic.
  The implement-then-test approach remains valid and is the default.
  Include brief guidance on when each approach is most appropriate.

### 3. Update `claude_agent_skills/instructions/software-engineering.md`

- In the Skills section, add `tdd-cycle` and `systematic-debugging` to
  the "Supporting skills used during ticket execution" list.
- In the Error Recovery section under "Test failures", add a reference
  to the systematic-debugging skill as the structured approach when
  simple diagnosis fails.

**Reference**: The implementer should read the Superpowers skill files
at `github.com/obra/superpowers` (`tdd.md` and `systematic-debugging.md`)
to understand the intent and conventions before making these updates.

## Acceptance Criteria

- [x] `execute-ticket.md` step 4 references tdd-cycle as an optional
      approach for implementation
- [x] `execute-ticket.md` Error Recovery references systematic-debugging
      with trigger conditions
- [x] `testing.md` includes a section referencing TDD as an available
      development method (not default, not mandatory)
- [x] `testing.md` includes guidance on when TDD vs implement-then-test
      is most appropriate
- [x] `software-engineering.md` Skills section lists tdd-cycle and
      systematic-debugging as supporting skills
- [x] `software-engineering.md` Error Recovery references
      systematic-debugging skill
- [x] All three files remain internally consistent (no contradictions)
- [x] TDD is consistently presented as optional across all files
- [x] All existing tests still pass

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_process_tools.py`
  (full suite to verify no regressions from content changes)
- **New tests to write**: None (content-only markdown changes to existing
  files; no new behavior to test)
- **Verification command**: `uv run pytest tests/unit/test_process_tools.py`
