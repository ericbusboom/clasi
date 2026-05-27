---
id: '001'
title: Add Philosophy section to README
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: add-philosophy-section-to-readme.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Add Philosophy section to README

## Description

Insert a `## Philosophy` section into `README.md` immediately after the
opening introduction paragraph and before the `## Installation` heading.
The section should contain the Le Guin quote from *The Wave in the Mind*
(2004) and one or two framing sentences.

The opening introduction ends after the paragraph that begins "An MCP
server that gives Claude Code a structured software engineering process..."
The new section goes between that paragraph and the `## Installation` heading.

Suggested quote (from *The Wave in the Mind*, 2004):

> "It is good to have an end to journey toward; but it is the journey that matters, in the end."

## Acceptance Criteria

- [x] `README.md` contains a `## Philosophy` heading.
- [x] The section appears after the introduction paragraph and before `## Installation`.
- [x] The Le Guin quote is present as a block-quote.
- [x] The quote is attributed to Ursula K. Le Guin and *The Wave in the Mind* (2004).
- [x] One or two framing sentences accompany the quote.
- [x] No other content in `README.md` is modified.

## Implementation Plan

### Approach

Open `README.md`, locate the end of the introduction (before `## Installation`),
and insert the new section.

### Files to Modify

- `/Volumes/Proj/proj/ai-projects/clasi/README.md` — insert the Philosophy section.

### Implementation Steps

1. Read `README.md` to confirm the exact boundary between the introduction and `## Installation`.
2. Insert the following block immediately before the `## Installation` heading:

```markdown
## Philosophy

> "It is good to have an end to journey toward; but it is the journey that matters, in the end."
>
> — Ursula K. Le Guin, *The Wave in the Mind* (2004)

CLASI is built on the belief that a reliable process is what makes
good outcomes repeatable. The journey — planning, reviewing, iterating —
is the work.
```

3. Verify placement and that no surrounding content was disturbed.

### Testing Plan

Visual inspection only. No automated tests are needed for a
documentation-only change.

### Documentation Updates

This ticket is itself the documentation change. No other docs to update.
