# CLASI Improvement Recommendations: Lessons from the Superpowers Plugin

**Source:** github.com/obra/superpowers (v5.0.4)
**Date:** March 2026

---

## Overview

This document describes seven capabilities from the Superpowers plugin that would strengthen CLASI. Each recommendation includes what Superpowers does, why it matters, and a concrete implementation path for CLASI. The intent is for CLASI to analyze this document and generate the corresponding skills, instructions, and infrastructure changes.

Items are ordered by estimated impact. Priorities reflect both the size of the capability gap and the effort required to close it.

## Summary

| # | Recommendation | Priority | Type |
|---|---|---|---|
| 1 | Subagent Dispatch Protocol | High | New skill + instruction |
| 2 | TDD as Process Driver | High | New skill, modify execute-ticket |
| 3 | Systematic Debugging | High | New skill |
| 4 | Session-Start Hook | Medium | Infrastructure (bash hook) |
| 5 | Parallel Execution via Worktrees | Medium | New skill + instruction |
| 6 | Two-Stage Verification | Medium | Modify code-reviewer agent |
| 7 | Commit Discipline Tied to Test State | Low | Modify git-workflow instruction |

---

## 1. Subagent Dispatch Protocol

**Priority: High**

### Rationale

CLASI defines agent roles (architect, code-reviewer, etc.) as personas the same Claude instance adopts. This means context bleeds between roles, there is no true isolation, and no parallelism. A real subagent dispatch protocol would spawn fresh Claude Code subagents via the Task tool, each with curated context and a specific mandate. This is the single largest architectural difference between CLASI and Superpowers.

### What Superpowers Does

Superpowers has a dedicated `subagent-driven-development` skill that defines a controller/worker pattern. The controller (parent agent) never writes code directly. For each task, it:

1. Curates exactly what context the subagent receives — only relevant files, specs, and constraints, with no inherited session history.
2. Dispatches a fresh subagent via the Task tool with a precise mandate.
3. Reviews results in two passes after the subagent completes (spec compliance first, then code quality).
4. Iterates if needed by dispatching again with feedback.

The key design choice is context curation: giving each subagent only what it needs prevents confusion from accumulated session state and keeps token usage efficient.

### Recommended Implementation for CLASI

Create a new skill (`skills/dispatch-subagent.md`) and a new instruction (`instructions/subagent-protocol.md`).

The **skill** should define the controller workflow: determine task scope, select relevant context files, compose the subagent prompt, dispatch via Task tool, review results.

The **instruction** should define rules for context curation:

- **Include:** relevant source files, the ticket description, acceptance criteria, architecture decisions that affect the task, applicable coding standards and testing instructions.
- **Exclude:** unrelated conversation history, other tickets, debugging logs from prior attempts, full project file listings.

Additional changes:

- The **project-manager agent** definition should be updated to use `dispatch-subagent` as its primary execution method when working on tickets.
- The **execute-ticket skill** should be modified to dispatch a coding subagent rather than switching personas inline.
- The **code-reviewer agent** should receive subagent output for review rather than reviewing its own session's context.

### Files to Create or Modify

```
skills/dispatch-subagent.md          (new skill)
instructions/subagent-protocol.md    (new instruction)
agents/project-manager.md            (modify to use dispatch)
skills/execute-ticket.md             (modify execution step)
```

---

## 2. TDD as Process Driver

**Priority: High**

### Rationale

CLASI requires tests as a completion gate: no ticket is done until tests exist and pass. But this allows an implement-first, test-after workflow where tests become retroactive verification rather than design tools. TDD inverts this: write the test first, watch it fail, then write the minimal code to make it pass. This catches interface design problems before implementation begins — if you can't write a clean test, your interface is wrong, and you find out before writing the implementation.

### What Superpowers Does

Superpowers makes TDD its central engineering discipline with a dedicated skill. The cycle is strict and explicitly ordered:

1. Write a failing test that describes the desired behavior.
2. Run it and confirm it fails. This step is mandatory — the skill explicitly states: "if you didn't watch it fail first, you don't know it works."
3. Write the minimum code to make the test pass.
4. Run the test and confirm it passes.
5. Refactor while keeping tests green.
6. Commit at the green state.

Each step is a discrete action the agent must perform and report on. The skill also addresses edge cases: what to do when a test passes unexpectedly (your test is wrong or the feature already exists), when to write integration vs. unit tests, and how to handle tests for non-deterministic behavior.

### Recommended Implementation for CLASI

Create a new skill (`skills/tdd-cycle.md`) that defines the red-green-refactor workflow as a mandatory sequence within ticket execution.

The skill should require:

1. Writing a failing test before any production code.
2. Running the test and confirming failure, with the specific failure message recorded.
3. Writing minimal production code.
4. Running the test and confirming passage.
5. Refactoring with tests green.
6. Committing at the green state.

Modify `execute-ticket.md` to invoke this skill during the implementation phase instead of the current implement-then-test approach.

Update the testing instruction (`instructions/testing.md`) to reference TDD as the default development method, while preserving the existing test placement rules (`tests/unit/`, `tests/system/`, `tests/dev/`).

Add guidance for when TDD is not practical — exploratory spikes, UI layout work, configuration changes — and what the fallback process is in those cases. The fallback should still require tests before the ticket is done; the difference is whether tests are written first or after.

### Files to Create or Modify

```
skills/tdd-cycle.md                  (new skill)
skills/execute-ticket.md             (modify implementation phase)
instructions/testing.md              (update to reference TDD)
```

---

## 3. Systematic Debugging Skill

**Priority: High**

### Rationale

CLASI has coding standards that address error handling (fail fast, specific exceptions, don't swallow errors) but no structured workflow for when things go wrong during development. Without a debugging protocol, agent behavior when tests fail or code breaks is ad hoc: agents tend to make rapid speculative changes, often making things worse. A systematic debugging skill forces structured diagnosis before any fix attempts.

### What Superpowers Does

Superpowers defines a four-phase debugging protocol:

**Phase 1 — Evidence Gathering:** Collect all error messages, stack traces, logs, and recent changes. Reproduce the issue reliably. Identify the exact input that triggers the failure.

**Phase 2 — Pattern Analysis:** Compare working vs. broken states. Identify what changed. Narrow the scope to the smallest possible reproduction case.

**Phase 3 — Hypothesis Testing:** Form a specific hypothesis about the root cause. Design a test that would confirm or refute it. Run the test. If refuted, form a new hypothesis.

**Phase 4 — Root Cause Fix:** Fix the actual root cause, not symptoms. Verify the fix resolves the original issue. Verify no regressions were introduced.

The protocol caps fix attempts at three before requiring architectural reassessment. This is the mechanism that prevents an agent from thrashing indefinitely on speculative patches.

### Recommended Implementation for CLASI

Create a new skill (`skills/systematic-debugging.md`) that defines the four-phase protocol.

The skill should be invoked automatically when:

- A test that was passing starts failing.
- An implementation attempt fails its acceptance criteria.
- The agent has made two consecutive failed attempts to fix something.

The skill should require the agent to write down (in a temporary debug log or in the ticket plan) the evidence collected, hypotheses formed, and test results for each hypothesis. This creates an audit trail and prevents the agent from repeating the same failed approach.

The three-attempt cap should be enforced: after three failed fix attempts, the agent must stop, document what was tried, and either escalate to the stakeholder or propose an architectural change.

Add a reference to this skill in `execute-ticket.md` so that agents know to invoke it when implementation hits problems rather than entering an ad hoc fix loop.

### Files to Create or Modify

```
skills/systematic-debugging.md       (new skill)
skills/execute-ticket.md             (add reference to debugging skill)
instructions/software-engineering.md (add debugging protocol reference)
```

---

## 4. Session-Start Hook for Mandatory Loading

**Priority: Medium**

### Rationale

CLASI relies on a prose directive in CLAUDE.md that says the agent MUST call `get_se_overview()` before doing any work. This is a request, not an enforcement mechanism. The agent can forget, skip it, or get distracted by the user's prompt before loading the process. A session-start hook runs automatically before the agent sees any user input, guaranteeing the process is loaded every time.

### What Superpowers Does

Superpowers uses a bash hook at `.claude/hooks/session-start.sh` that automatically injects the meta-skill (`using-superpowers`) at the start of every session. The hook runs before the agent processes any user message. The meta-skill then teaches the agent how to find and invoke all other skills. This two-step pattern — hook loads meta-skill, meta-skill teaches skill discovery — means the agent always starts with full awareness of available capabilities without relying on a prose directive.

### Recommended Implementation for CLASI

Create a session-start hook at `.claude/hooks/session-start.sh`. The hook should output a message that triggers the agent to call `get_se_overview()`, or directly invoke the MCP tool if the hook mechanism supports it.

The hook should be created during `clasi init` alongside the other initialization artifacts (`.mcp.json`, `CLAUDE.md`, etc.).

The CLAUDE.md directive should remain as a backup (belt and suspenders), but the hook becomes the primary loading mechanism.

Implementation note: verify the hook mechanism is available in the target Claude Code version, as hooks may be a newer feature. If hooks are not available, document this as a future improvement and keep the CLAUDE.md directive as the sole mechanism.

```bash
#!/bin/bash
# .claude/hooks/session-start.sh
# Automatically load CLASI SE process at session start
echo "CLASI: Loading software engineering process..."
echo "MANDATORY: Call get_se_overview() now to load the SE process."
```

### Files to Create or Modify

```
.claude/hooks/session-start.sh       (new hook, created by clasi init)
claude_agent_skills/init_command.py   (modify to create hook during init)
AGENTS.md                             (keep directive as backup)
```

---

## 5. Parallel Execution via Worktrees

**Priority: Medium**

### Rationale

CLASI's execution lock prevents more than one sprint from being in the executing phase at a time. This is a deliberate safety measure, but it also serializes all work. For sprints with multiple independent tickets (no shared files, no dependency between them), parallel execution would significantly increase throughput. Git worktrees provide the isolation mechanism: each subagent works in its own worktree, on its own branch, with no risk of merge conflicts during development.

### What Superpowers Does

Superpowers has two complementary skills: `dispatching-parallel-agents` for running multiple subagents concurrently, and `using-git-worktrees` for creating isolated workspaces. The combination works as follows: the controller agent identifies which tasks are independent (no overlapping files), creates a worktree per task, dispatches a subagent into each worktree, waits for all to complete, reviews results, and merges worktree branches back. The worktree skill includes rules for cleanup (remove worktrees after merge) and conflict resolution (if worktrees touched the same file unexpectedly, resolve manually before merging).

### Recommended Implementation for CLASI

Create a new skill (`skills/parallel-execution.md`) and a new instruction (`instructions/worktree-protocol.md`).

The **skill** should define the workflow: analyze sprint tickets for independence (no overlapping file modifications), create worktrees, dispatch subagents (using the `dispatch-subagent` skill from recommendation 1), collect results, review, and merge.

The **instruction** should define worktree management rules: naming convention (`worktree-ticket-NNN`), cleanup after merge, conflict resolution procedure.

The execution lock in `state_db.py` should remain for sprint-level serialization, but a new mechanism should allow ticket-level parallelism within a single sprint. This recommendation depends on recommendation 1 (subagent dispatch) being implemented first.

The parallel skill should be optional and invoked explicitly by the stakeholder or project-manager when appropriate — not as the default execution mode. Sequential execution remains the safe default.

### Files to Create or Modify

```
skills/parallel-execution.md         (new skill)
instructions/worktree-protocol.md    (new instruction)
skills/execute-ticket.md             (add note about parallel option)
agents/project-manager.md            (add parallel dispatch guidance)
```

---

## 6. Two-Stage Verification Protocol

**Priority: Medium**

### Rationale

CLASI has a code-reviewer agent, but the review criteria are not structured into distinct passes. Code can be well-written but wrong (doesn't meet the spec), or correct but poorly structured (meets the spec but is unmaintainable). Separating correctness from quality as distinct review passes ensures both dimensions are evaluated and neither gets skipped when context is long or the agent is rushing to close a ticket.

### What Superpowers Does

Superpowers defines a two-stage review in its subagent protocol:

**Stage 1 — Spec Compliance:** Does the implementation satisfy every acceptance criterion in the ticket? Are all required behaviors present? Are edge cases handled? Does it match the architectural decisions? This is a binary pass/fail against the spec.

**Stage 2 — Code Quality:** Is the code maintainable? Are names clear? Is there unnecessary complexity? Are there performance concerns? Does it follow project conventions? This pass produces improvement suggestions that may or may not block merge.

The two stages run sequentially, and Stage 1 failure short-circuits — there's no point reviewing the quality of incorrect code.

### Recommended Implementation for CLASI

Modify the code-reviewer agent definition (`agents/code-reviewer.md`) to define two explicit review phases:

**Phase 1 — Correctness:** Review against the ticket's acceptance criteria and the sprint architecture. Output: pass/fail with specific criteria that failed.

**Phase 2 — Quality:** Review against coding standards, architectural quality guidelines, and project conventions. Output: list of issues ranked by severity.

Phase 1 failure blocks the ticket from moving to done. Phase 2 issues above a severity threshold also block.

Create a review checklist template (`templates/review-checklist.md`) that the code-reviewer fills in for each review, stored alongside the ticket (e.g., `NNN-slug-review.md`). This makes reviews auditable and gives the coding agent specific items to address rather than vague feedback.

### Files to Create or Modify

```
agents/code-reviewer.md              (modify to define two phases)
templates/review-checklist.md        (new template)
skills/execute-ticket.md             (reference review protocol)
```

---

## 7. Commit Discipline Tied to Test State

**Priority: Low**

### Rationale

CLASI has conventional commit formatting rules but doesn't specify when to commit relative to test outcomes. This means the git history may contain commits where tests are broken, making bisection unreliable and rollbacks risky. Tying commit points to known-good test states makes the history a reliable recovery mechanism.

### What Superpowers Does

Superpowers mandates committing at specific points in the TDD cycle: after tests go green (the implementation commit), and after refactoring with tests still green (the refactor commit). Each commit in the history represents a state where all tests pass. The skill explicitly prohibits committing code that has failing tests unless the commit message documents it as work-in-progress on a feature branch.

### Recommended Implementation for CLASI

Update the git workflow instruction (`instructions/git-workflow.md`) to add commit timing rules:

1. Always run tests before committing.
2. Do not commit if tests fail, unless on a feature branch with a `WIP:` prefix in the commit message.
3. After a TDD green phase, commit immediately before refactoring.
4. After refactoring, run tests again and commit the refactor separately.

This pairs naturally with recommendation 2 (TDD as process driver). The commit message convention should include a test-state indicator: all commits on the sprint branch should have passing tests, and any exception must be explicitly noted.

Modify the `close-sprint` skill to verify that all tests pass on the sprint branch before allowing merge to main.

### Files to Create or Modify

```
instructions/git-workflow.md         (modify commit timing rules)
skills/close-sprint.md               (add test verification gate)
skills/tdd-cycle.md                  (reference commit points)
```

---

## Recommended Implementation Order

These recommendations have dependencies. The suggested implementation order accounts for those dependencies while delivering value incrementally.

**Sprint 1:** Recommendations 2 and 3 — TDD cycle skill and systematic debugging skill. These are standalone skills with no infrastructure dependencies. They can be created as new markdown files and integrated into execute-ticket immediately. They deliver the highest immediate value by changing how code gets written and how problems get solved.

**Sprint 2:** Recommendation 7 — Commit discipline tied to test state. This is a small modification to `git-workflow.md` that pairs with the TDD skill from Sprint 1. Low effort, completes the TDD integration.

**Sprint 3:** Recommendation 4 — Session-start hook. This requires modifying `init_command.py` and testing the hook mechanism. Medium effort, but it eliminates the most common process-loading failure mode.

**Sprint 4:** Recommendations 1 and 6 — Subagent dispatch protocol and two-stage verification. These are connected: the dispatch protocol defines how subagents are spawned, and two-stage verification defines how their output is reviewed. Implement together for a coherent workflow.

**Sprint 5:** Recommendation 5 — Parallel execution via worktrees. This depends on subagent dispatch (Sprint 4) and should be implemented last as an optimization layer on top of the working dispatch system.

---

## Notes for CLASI Self-Analysis

When CLASI processes this document, each recommendation should be evaluated against the existing skill and instruction inventory. Some recommendations may partially overlap with existing content. Where overlap exists, the existing content should be extended rather than replaced.

The key additions are: new skills (`dispatch-subagent`, `tdd-cycle`, `systematic-debugging`, `parallel-execution`), modified skills (`execute-ticket`, `close-sprint`), modified agents (`project-manager`, `code-reviewer`), modified instructions (`testing`, `git-workflow`, `software-engineering`), new infrastructure (session-start hook), and a new template (`review-checklist`).

The Superpowers repository is at `github.com/obra/superpowers`. The specific skill files most worth reading in detail are: `subagent-driven-development.md`, `tdd.md`, `systematic-debugging.md`, `dispatching-parallel-agents.md`, `using-git-worktrees.md`, and `receiving-code-review.md`. These contain implementation details and edge-case handling that should inform the CLASI versions.
