---
name: subagent-protocol
description: Rules for curating context when dispatching subagents — what to include, what to exclude, and examples
---

# Subagent Protocol

This instruction defines the rules for curating context when dispatching
work to subagents via the Agent tool. Proper context curation is the
single most important factor in subagent success.

## Core Principle

**Include everything the subagent needs. Exclude everything it does not.**
A subagent with too little context will guess wrong. A subagent with too
much context will lose focus. The controller's job is to find the right
balance.

## Include Rules

Always include these in the subagent's prompt:

### 1. Relevant Source Files

Read and include the content of files the subagent will modify or needs
to understand. Do not tell the subagent to "read file X" — include the
actual content so the subagent has it immediately.

- Files listed in the ticket plan's "Files to create or modify" section
- Files that define interfaces the subagent's code must conform to
- Test files the subagent should update or add to
- Configuration files that affect the subagent's work

### 2. Ticket Description and Acceptance Criteria

Include the full ticket markdown — description, acceptance criteria, and
testing section. The subagent needs to know exactly what "done" looks
like.

### 3. Ticket Plan

Include the full ticket plan — approach, design decisions, files to
modify, testing plan. This is the subagent's roadmap.

### 4. Architecture Decisions

Include only the specific architecture decisions from the sprint's
`architecture.md` that are relevant to the ticket. Do not include the
entire architecture document.

Examples of relevant decisions:
- "Templates are loaded at import time via `_load()` in `templates.py`"
- "All agent definitions use YAML frontmatter with name and description"
- "Tests use pytest with no cacheprovider plugin"

### 5. Coding Standards

Include the applicable coding standards from
`instructions/coding-standards`. For Python work, also include any
language-specific instructions.

### 6. Testing Instructions

Include the testing approach from `instructions/testing` and the
specific testing requirements from the ticket's Testing section.

### 7. Git Workflow

Include the commit message format and branching conventions from
`instructions/git-workflow` so the subagent commits correctly.

## Exclude Rules

Never include these in the subagent's prompt:

### 1. Conversation History

The controller's conversation with the stakeholder, prior subagents,
or other agents is irrelevant to the subagent's task. Including it
wastes context and can confuse the subagent with outdated information.

### 2. Other Tickets

The subagent works on one ticket. Other tickets in the sprint — even
related ones — are noise. If the subagent needs to know about a
dependency, summarize the relevant output (e.g., "Ticket 001 created
`dispatch-subagent.md` which you should reference").

### 3. Debug Logs and Error History

If a previous subagent attempt failed, do not dump the full debug
session. Instead, summarize:
- What was attempted
- What went wrong (specific error or incorrect behavior)
- What the subagent should do differently

### 4. Full Directory Listings

Do not include `ls -R` or `find` output. Instead, list the specific
files the subagent needs to know about.

### 5. Sprint-Level Planning Documents

The sprint document (`sprint.md`), use cases (`usecases.md`), and
full architecture document are planning artifacts for the controller.
Extract the relevant parts for the subagent — do not pass them whole.

### 6. Unrelated Source Files

Do not include source files that the subagent will not read or modify.
Even "for reference" files add noise if the subagent does not need them.

## Context Size Guidelines

- **Optimal**: 2,000 - 8,000 tokens of context for a focused task
- **Acceptable**: Up to 15,000 tokens for complex tasks with many files
- **Too much**: Over 20,000 tokens usually means the task should be
  split or the context needs pruning

These are guidelines, not hard limits. A task that genuinely requires
reading 10 source files will need more context than a task that modifies
one function.

## Examples

### Example 1: Dispatching a Python Implementation Subagent

**Good context curation:**

```
You are a Python developer implementing ticket #003: Add template loading.

## Task
Add a REVIEW_CHECKLIST_TEMPLATE constant to templates.py that loads
the review-checklist.md template file.

## Acceptance Criteria
- [ ] REVIEW_CHECKLIST_TEMPLATE constant added to templates.py
- [ ] Template is loadable via the templates module
- [ ] Follows existing pattern of other template constants

## Current File: templates.py
[full content of templates.py]

## Template to Load: templates/review-checklist.md
[full content of review-checklist.md]

## Pattern to Follow
Existing constants use: CONSTANT_NAME = _load("template-name")
The _load() function reads from the templates/ directory.

## Standards
- Follow PEP 8
- No trailing whitespace
- Constants in UPPER_SNAKE_CASE

## Verification
Run: uv run pytest -p no:cacheprovider --override-ini="addopts="
```

**Bad context curation (too much):**

```
Here is the full project structure...
Here are all 42 source files...
Here is the sprint document...
Here are all 4 tickets in this sprint...
Here is the conversation where we planned this sprint...
Now implement ticket #003.
```

### Example 2: Dispatching a Code Review Subagent

**Good context curation:**

```
You are a code reviewer reviewing ticket #003: Add template loading.

## Acceptance Criteria
[ticket acceptance criteria]

## Changed Files
[git diff output or file contents]

## Coding Standards
[relevant coding standards]

## Review Protocol
Phase 1: Check each acceptance criterion — pass or fail.
Phase 2: Check quality against coding standards — rank issues by severity.
Use the review-checklist template for output format.
```

### Example 3: Dispatching with Feedback (Iteration)

**Good follow-up prompt:**

```
You are continuing work on ticket #003. A previous attempt was made
but had issues:

- The REVIEW_CHECKLIST_TEMPLATE constant was added correctly
- BUT: the template file was placed in the wrong directory (root instead
  of templates/)
- Fix: Move review-checklist.md to claude_agent_skills/templates/

## Current State
[content of templates.py — showing the constant is already there]
[content of the incorrectly placed file]

## What to Do
1. Create claude_agent_skills/templates/review-checklist.md with the
   correct content
2. Remove the incorrectly placed file at the project root
3. Verify: uv run pytest
```
