---
date: 2026-03-10
sprint: 028
category: ignored-instruction
---

## What Happened

When the stakeholder asked "what has to happen after you close this next
sprint?", I answered from memory instead of consulting the SE process
documentation. My answer was incomplete — I missed the architecture
versioning step, stakeholder confirmation, final test validation, and
the full push sequence. I only looked up the actual `close-sprint` skill
definition when the stakeholder pushed back and asked "what does the
agents file say you're supposed to do in order to understand the
process?"

## What Should Have Happened

The AGENTS.md explicitly says: "Use `/se` or call `get_se_overview()`
for full process details and MCP tool reference." When asked about the
sprint closing process, I should have immediately called
`get_skill_definition("close-sprint")` to give an accurate, complete
answer rather than guessing from incomplete memory.

## Root Cause

**Ignored instruction.** The AGENTS.md documents how to look up process
details, and the `close-sprint` skill has a 12-step procedure. I skipped
the lookup and relied on a partial mental model, which produced an
incomplete answer. This is the same pattern as previous corrections —
acting on assumptions instead of consulting the documented process.

## Proposed Fix

Before answering any question about how a process works (sprint closing,
ticket execution, requirements gathering, etc.), always call the
relevant skill definition first. The process is documented — use it.
Do not answer SE process questions from memory.
