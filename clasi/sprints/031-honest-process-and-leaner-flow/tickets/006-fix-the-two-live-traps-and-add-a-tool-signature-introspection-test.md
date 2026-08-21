---
id: '006'
title: Fix the two live traps and add a tool-signature introspection test
status: open
use-cases:
- SUC-006
depends-on: []
github-issue: ''
issue: one-canonical-text-per-process-topic.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Fix the two live traps and add a tool-signature introspection test

## Description

Two shipped instructions currently route an agent that follows them
literally into machinery that does not exist — verified against the
current code during planning, not assumed:

- `_get_definition`'s `rglob` fallback in `tools/process_tools.py` (the
  bottom of the file, `matches = list(directory.rglob(f"{name}.md"))`)
  is the **one** lookup path in this file that does not already exclude
  `agents/old/` — `_list_agents_recursive` and `_find_agent_dir` both
  already skip `"old" in ... .parts` (confirmed by reading all three).
  A lookup for a nonexistent skill/agent silently resolves into
  `plugin/agents/old/sprint-executor/execute-ticket.md` instead of
  failing.
- `.claude/rules/source-code.md` — loaded on every source edit — tells
  agents to "follow the execute-ticket skill" and call
  `get_skill_definition("execute-ticket")`. No skill by that name exists
  under `plugin/skills/` (confirmed: `find` returns nothing); the only
  file named `execute-ticket.md` anywhere in the tree is the retired one
  above. The canonical source is `platforms/_rules.py` (confirmed by
  reading it — the rule's prose lives there, `.claude/rules/
  source-code.md` is a generated copy).
- `plugin/skills/dispatch-subagent/SKILL.md` says "you MUST call
  `log_subagent_dispatch`... If unavailable or fails, STOP." That tool
  does not exist anywhere in `src/clasi` (confirmed by grep across the
  whole package during planning).

## Acceptance Criteria

- [ ] `_get_definition`'s `rglob` fallback excludes any match under
      `agents/old/`, matching the exclusion `_list_agents_recursive`/
      `_find_agent_dir` already apply.
- [ ] A lookup for a nonexistent skill or agent name raises a clear,
      named "not found" error — a test asserts this rather than
      asserting the absence of a specific silent-resolution outcome.
- [ ] `platforms/_rules.py`'s `source-code.md` body no longer references
      "the execute-ticket skill" — it points at the programmer agent
      definition instead (via `get_agent_definition("programmer")` or
      an equivalent pointer, whichever this codebase's existing
      convention for cross-referencing an agent from a rule uses).
- [ ] `plugin/skills/dispatch-subagent/SKILL.md` no longer mandates
      `log_subagent_dispatch` or references any other tool absent from
      the current MCP tool surface — rewritten to describe what
      dispatch logging (if any) this package actually does, or the
      logging-mandate language is dropped entirely if none exists.
- [ ] A new test introspects the live MCP tool signatures (via
      `inspect.signature` or the MCP server's own tool registry) for at
      least the tools named in the review's contradiction table
      (`move_ticket_to_done`, `reconcile_worktrees`) and asserts no doc
      this ticket touches states a signature that disagrees with the
      introspected one.

## Implementation Plan

**Approach**: three independent, narrow fixes plus one test. No
dependency on any other ticket in this sprint — this is deliberately the
narrower, code-adjacent half of the canonical-text issue (ticket 007 is
the larger prose-consolidation half, sequenced after 002/003/006 since
it must describe their post-fix reality).

**Files to modify**:
- `src/clasi/tools/process_tools.py` — `_get_definition`'s fallback
- `src/clasi/platforms/_rules.py` — `source-code.md`'s body
- `src/clasi/plugin/skills/dispatch-subagent/SKILL.md`
- New test file for tool-signature introspection

**Do not modify**: `_list_agents_recursive`/`_find_agent_dir` (already
correct); `software-engineering.md`/`team-lead/agent.md`/`sprint-plan.md`
(ticket 007's scope).

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is a hard block, not a silent allow.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or any mechanism that
  avoids the tool the guard is watching. Reporting a block is a
  successful outcome of this ticket, not a failure.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/system/test_process_tools.py -v`
- **New tests to write**: nonexistent-skill/agent lookup raises loudly;
  tool-signature introspection test.
- **Verification command**: the existing-tests command above plus the
  new test file, scoped to this ticket's modules.
