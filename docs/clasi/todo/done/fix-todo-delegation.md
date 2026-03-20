---
status: done
sprint: '024'
tickets:
- '006'
---

# Fix TODO Delegation: Team Lead Should Pass Raw Stakeholder Input

## Problem

The current TODO creation process has the team lead doing the
todo-worker's job. The team lead receives stakeholder input, rewrites
it into a structured TODO with frontmatter, title, sections, and
formatting, and then hands the finished artifact to the todo-worker
agent — or bypasses the agent entirely.

This is wrong. The team lead is doing the work that the todo-worker
exists to do. The todo-worker agent's purpose is to take raw,
unstructured stakeholder input and turn it into a properly formatted
TODO file with correct frontmatter, clear problem descriptions, and
actionable proposals.

## Desired Behavior

1. **Stakeholder says something** — unstructured, conversational,
   possibly rambling. This is the raw input.
2. **Team lead dispatches to todo-worker** — passes the stakeholder's
   raw words verbatim (or near-verbatim) as input. The team lead
   does NOT restructure, reformat, or pre-digest the content.
3. **Todo-worker does the formatting** — the todo-worker agent
   receives the raw text, interprets it, and produces the proper
   TODO file with correct YAML frontmatter (`status: pending`),
   a clear title, problem/solution sections, and any other structure
   the TODO format requires.

## Changes Needed

1. **Team-lead agent definition** — Update the team-lead's
   instructions to state: when creating a TODO, pass the
   stakeholder's raw words to the todo-worker agent. Do not
   pre-format or pre-structure the content. The dispatch message
   should contain the stakeholder's original text, not a rewritten
   version.

2. **Todo-worker agent definition** — Confirm the todo-worker's
   instructions make clear that it receives raw stakeholder input
   and is responsible for all structuring, formatting, and
   frontmatter generation.

3. **Dispatch protocol** — The team lead's dispatch to the
   todo-worker should look like: "Create a TODO from this
   stakeholder input: [raw text]" — not "Create a TODO with
   this title, this problem, this solution."
