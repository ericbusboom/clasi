---
name: testing
description: Instructions for testing conventions, test types, design for testability, and verification strategies
---

# Testing Instructions

## Core Rule

No ticket is considered finished until tests have been written to exercise the
changes in that ticket. This is non-negotiable.

## Development Methods

Two approaches to writing tests are available. Both are valid — choose
based on what fits the work.

### Implement-Then-Test (Default)

Write the implementation first, then write tests to verify it. This is
the default approach and is appropriate for most work: configuration
changes, documentation updates, exploratory spikes, UI layout, and
simple glue code.

### Test-Driven Development (Optional)

TDD (red-green-refactor) is available via the `tdd-cycle` skill. With
TDD, you write a failing test first, then write the minimum code to make
it pass, then refactor.

**When TDD is most useful:**
- Well-defined interfaces where you know the inputs and outputs
- Bug fixes (write a test that reproduces the bug, then fix it)
- Complex logic with many edge cases
- Refactoring with confidence (lock in behavior with tests first)

**When implement-then-test is usually better:**
- Exploratory spikes where the design is unclear
- Configuration and deployment changes
- UI layout and styling
- Documentation updates

TDD is not mandatory and is not the default. The agent or stakeholder
may choose to use it when it fits. See the `tdd-cycle` skill for the
full workflow.

## Test Placement (Mandatory)

Every test file MUST go in the correct subdirectory. Never place test files
directly in `tests/`.

- **`tests/unit/`** — Tests a single module in isolation.
- **`tests/system/`** — Tests multiple modules working together.
- **`tests/dev/`** — Throwaway scripts used during development.

When creating a new test file, decide: does this test one module, or does it
exercise multiple modules interacting? That determines the directory.

## Test Types

### Unit Tests (`tests/unit/`)

Tests for individual classes, modules, or small subsystems in isolation.

- One test file per module: `tests/unit/test_<module>.py`
- Mock external dependencies so the test exercises only the unit under test.
- These should be fast and deterministic.

### System Tests (`tests/system/`)

Tests for systems or subsystems working together. These verify that
components integrate correctly and produce expected end-to-end behavior.

- May use real dependencies (databases, file systems, network) or
  controlled test fixtures.
- Slower than unit tests; run less frequently but always before merging.

### Development Tests (`tests/dev/`)

Temporary tests created during development to exercise code while building
it. These are the way you run and try out code during development.

**Rules for development tests:**
- If you need to run a program during development, create a test script in
  `tests/dev/` rather than running commands on the command line.
- Do not run ad-hoc scripts, one-liners, or heredocs on the command line to
  exercise code. Always create a test file.
- Development tests may be discarded once the feature is stable and covered
  by unit or system tests.
- Name them descriptively: `tests/dev/test_trying_<feature>.py`

## Design for Testability

Testability is a first-class design consideration. When choosing between
design options, prefer the one that is easier to test.

Guidelines:
- Create minimally connected components with clear interfaces.
- Depend on abstractions, not concrete implementations, so dependencies
  can be easily mocked or swapped.
- Components should be runnable in isolation or as separate processes.
- Avoid global state. Pass dependencies explicitly.
- Prefer pure functions where possible — they are trivially testable.
- If a component is hard to test, that is a design smell. Refactor it.

## Verification Strategies

Choose the right strategy based on complexity:

### Simple Assertions

For straightforward logic, use direct assertions:

```python
def test_add():
    assert add(2, 3) == 5
```

Check that conditions are true, values match expectations, exceptions are
raised when expected.

### Output File Comparison

For more complex behavior, dump the output to a file and check it:

1. Run the code and write its output to a file.
2. Inspect the file to verify correctness.
3. If the output is correct, copy it into a `tests/golden/` directory as the
   reference (golden file).
4. Future test runs compare current output against the golden file.

```python
def test_report_output(tmp_path):
    output_file = tmp_path / "report.txt"
    generate_report(output_file)

    golden_file = Path("tests/golden/report.txt")
    assert output_file.read_text() == golden_file.read_text()
```

When the expected output intentionally changes, update the golden file.

### Visual / Image Comparison

For applications that produce UI output or visual results:

1. Render the output to an image file.
2. Compare the image against a golden image in `tests/golden/`.
3. Use pixel-level or perceptual diff tools to detect regressions.

This is appropriate for plots, rendered documents, UI screenshots, or any
output where visual correctness matters.

## Test Organization Summary

```
tests/
├── unit/              # Isolated module/class tests
│   └── test_<module>.py
├── system/            # Integration and end-to-end tests
│   └── test_<feature>.py
├── dev/               # Throwaway development tests
│   └── test_trying_<feature>.py
└── golden/            # Reference output files for comparison
    ├── report.txt
    └── chart.png
```

## Running Tests

```bash
# Full suite
pytest

# Unit tests only
pytest tests/unit/

# System tests only
pytest tests/system/

# Development tests
pytest tests/dev/

# With coverage
pytest --cov=src

# Verbose output
pytest -v
```

## Sprint Test Strategy

Each sprint's `sprint.md` includes a **Test Strategy** section that describes
the overall testing approach for that sprint. This section should cover:

- What types of tests are needed (unit, system, dev)
- Which areas need coverage
- Any integration or system-level testing required
- Any special testing considerations (fixtures, test data, etc.)

Individual ticket plans reference the sprint test strategy and specify the
specific tests for that ticket.

## Relationship to Tickets

- Every ticket must have tests that exercise its changes.
- A ticket is not done until its tests pass.
- If a test cannot be written for a criterion, document why in the ticket.
- Acceptance criteria in tickets should map directly to test cases.
