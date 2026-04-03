---
name: project-initiation
description: Bootstrap a new project from a stakeholder's specification — produces overview, specification, and use cases
---

# Project Initiation Skill

Process a written specification into structured project documents that
all other processes will reference throughout the project lifecycle.

## When to Use

At the start of a new project when the stakeholder has provided a
written specification. There are no existing `overview.md`,
`specification.md`, or `usecases.md` documents yet.

## Inputs

- A path to a written specification file from the stakeholder

## Process

1. **Read the specification** provided by the stakeholder.

2. **Produce three documents** in `docs/clasi/design/`:

   **`overview.md`** — A one-page summary of the project. An elevator
   pitch for quick context. It is additive, NOT a replacement for the
   specification.

   **`specification.md`** — The full feature specification, preserving
   ALL stakeholder detail. Exact messages, behavior rules, edge cases,
   test expectations — if the stakeholder wrote it, it MUST survive.
   Reorganize for clarity, but do not lose information. Do not summarize,
   paraphrase, or omit.

   **`usecases.md`** — Numbered use cases (UC-001, UC-002, etc.) extracted
   from the specification. Each use case has: ID, title, actor,
   preconditions, main flow, postconditions, and error flows.

3. **Create the overview** using the `create_overview` MCP tool.

## Critical Rule

**Do not lose information.** The overview adds context. The specification
preserves everything. When in doubt, include rather than omit.

## Output

Three documents in `docs/clasi/design/`: overview.md, specification.md, usecases.md.
