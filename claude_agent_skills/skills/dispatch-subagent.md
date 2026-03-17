---
name: dispatch-subagent
description: Controller/worker pattern for dispatching isolated subagents via the Agent tool with curated context
---

# Dispatch Subagent Skill

This skill defines how a controller agent dispatches work to an isolated
subagent via the Agent tool. The controller curates context, composes a
prompt, dispatches the subagent, reviews results, and iterates with
feedback if needed.

## Core Principle

**The controller never writes code directly.** All implementation is
delegated to subagents. The controller's job is to set the subagent up
for success by providing exactly the right context — no more, no less.

## Protocol Reference

Context curation rules are defined in `instructions/subagent-protocol`.
Always follow those rules when preparing a subagent dispatch.

## Controller/Worker Pattern

### Roles

- **Controller**: The orchestrating agent (typically project-manager or
  execute-ticket). Reads the ticket plan, curates context, dispatches
  subagents, reviews their output, and iterates.
- **Worker (subagent)**: A fresh Claude Code instance spawned via the
  Agent tool. Receives curated context, executes a focused task, and
  returns results. Has no memory of the controller's conversation.

### Why Subagents

- **Context isolation**: Each subagent starts fresh. No context bleed
  from prior tasks, debugging sessions, or unrelated tickets.
- **Focused attention**: The subagent sees only what it needs. Less
  context means higher quality work on the specific task.
- **Clean failure boundaries**: If a subagent fails, the controller
  can retry with adjusted context without corrupting its own state.

## Dispatch Lifecycle

### Step 1: Curate Context

Before dispatching, the controller gathers exactly the context the
subagent needs. Follow the include/exclude rules in
`instructions/subagent-protocol`.

Gather these artifacts:
- The ticket description and acceptance criteria
- The ticket plan (approach, files to modify, testing plan)
- The specific source files the subagent will read or modify
- Relevant architecture decisions from the sprint's `architecture.md`
- Applicable coding standards from `instructions/coding-standards`
- Testing instructions from `instructions/testing`
- Git workflow conventions from `instructions/git-workflow`

### Step 2: Compose the Prompt

Structure the prompt to the subagent as:

```
You are a {role} working on ticket #{id}: {title}.

## Task
{ticket description and acceptance criteria}

## Approach
{ticket plan — approach and key decisions}

## Files to Modify
{list of specific files with paths}

## Architecture Context
{relevant architecture decisions only}

## Standards
{coding standards and testing requirements}

## Constraints
- Implement ONLY what the ticket specifies
- Do not modify files outside the listed set
- Run tests after implementation: {verification command}
- Commit with message: {commit message format}
```

Key prompt principles:
- Be specific about what to do and what NOT to do
- Include file paths, not descriptions of where to find things
- State the verification command explicitly
- Set boundaries on scope — subagents should not explore or expand

### Step 3: Dispatch via Agent Tool

Use the Agent tool to spawn the subagent:

```
Agent(prompt=<composed prompt>, tools=[Read, Write, Edit, Bash, Grep, Glob])
```

The Agent tool creates a fresh Claude Code instance with its own
conversation context. The subagent will execute the task and return
a summary of what it did.

### Step 4: Review Results

After the subagent returns, the controller reviews:

1. **Did the subagent complete the task?** Read the subagent's summary.
2. **Are the changes correct?** Read the modified files. Check against
   acceptance criteria.
3. **Do tests pass?** Run the verification command.
4. **Are there unintended changes?** Check `git diff` for unexpected
   modifications.

### Step 5: Iterate with Feedback (if needed)

If the subagent's work is incomplete or incorrect:

1. Identify the specific issues.
2. Compose a follow-up prompt with:
   - What was done correctly (so the subagent does not undo it)
   - What needs to be fixed (specific, actionable feedback)
   - The current state of the files (read and include relevant sections)
3. Dispatch a new subagent with the corrected context.

Repeat until the work meets acceptance criteria. Limit to 3 iterations
— if the subagent cannot complete the task in 3 attempts, escalate to
the stakeholder.

## Anti-Patterns

- **Kitchen-sink context**: Dumping the entire codebase or conversation
  history into the subagent prompt. This overwhelms the subagent and
  degrades output quality.
- **Controller writes code**: The controller should never implement
  code directly. If tempted, dispatch a subagent instead.
- **Vague prompts**: Telling the subagent to "implement the ticket"
  without specifying files, approach, or constraints. Always be explicit.
- **No review**: Trusting the subagent's output blindly. Always review
  the actual file changes and run tests.
- **Infinite iteration**: Dispatching more than 3 times for the same
  task. Escalate instead.

## When to Use This Skill

- **Ticket implementation**: The primary use case. The execute-ticket
  skill dispatches a coding subagent for Step 4 (implement).
- **Code review**: Dispatch a review subagent with the changed files
  and acceptance criteria.
- **Documentation updates**: Dispatch a documentation subagent with
  the files that changed and the documentation plan.
- **Any focused task**: Whenever a task can be clearly scoped and
  the required context can be enumerated.

## When NOT to Use This Skill

- **Interactive planning**: Tasks that require back-and-forth with the
  stakeholder should stay in the controller.
- **Cross-cutting changes**: Tasks that touch many files across
  multiple subsystems may need the controller's broader context.
- **Debugging**: Root-cause analysis often requires exploring
  unpredictable paths — keep this in the controller.
