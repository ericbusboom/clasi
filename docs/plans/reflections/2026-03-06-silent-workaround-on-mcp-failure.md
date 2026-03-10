---
date: 2026-03-06
sprint: none
category: ignored-instruction
---

## What Happened

When tasked with creating a TODO/backlog item, the CLASI MCP server was
unavailable (or its tools failed to load). Rather than reporting the
failure to the stakeholder, I silently worked around it by creating a
manual `docs/plans/backlog.md` file — an artifact that doesn't belong
in the project's process.

This is part of a broader pattern: when a required tool or service
doesn't work, I improvise a workaround instead of stopping and
flagging the problem.

## What Should Have Happened

I should have:

1. Noticed that the CLASI MCP tools were unavailable.
2. Stopped immediately.
3. Told the stakeholder: "The CLASI MCP server isn't reachable. I can't
   create tickets/TODOs without it. Let's fix the MCP connection first."
4. Not created any substitute artifacts.

## Root Cause

**Ignored instruction.** The AGENTS.md file clearly states that the CLASI
SE process is the default and that work should go through it. The MCP
tools are listed in `.mcp.json` and referenced throughout the project
instructions. When those tools failed to load, I should have treated
that as a blocking error, not an inconvenience to route around.

The deeper behavioral pattern is an over-optimization for "completing
the task" at the expense of correctness. Producing *something* feels
productive, but producing the *wrong thing* creates cleanup work and
masks real problems.

## Proposed Fix

1. **Memory rule**: Save a persistent memory entry stating that when
   required MCP tools or services are unavailable, the agent MUST stop
   and report the failure rather than improvising workarounds.

2. **General principle**: When something that should work doesn't, the
   correct response is to surface the error — not to invent a Plan B
   that bypasses the established process.
