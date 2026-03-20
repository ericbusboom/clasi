---
status: pending
---

# Enforce Dispatch Template Usage

**Do not implement yet.**

## Problem

Sprint 024 created dispatch templates and placed them in agent
directories. The agent definitions tell agents to use them. But the e2e
test shows that dispatches are still ad-hoc prompts -- the agent
composes whatever it wants and sends it, ignoring the templates entirely.

This is the same compliance failure pattern documented in
`fix-agent-process-engagement.md`: instructional controls ("you should
use the template") do not work because nothing mechanically forces the
agent to load or follow the template. The template exists, the agent is
told to use it, and it doesn't. Adding more words to AGENTS.md will not
fix this.

## Root Cause

There is no mechanical forcing function. The dispatch template is a
passive file that the agent must voluntarily retrieve and fill in. In
practice, agents skip the retrieval step because composing an ad-hoc
prompt is faster and produces something that looks correct. The dispatch
log accepts the call regardless of whether a template was used.

## Proposed Solution

### 1. MCP tool: `get_dispatch_template(target_agent)`

Add an MCP tool that returns the dispatch template text for a given
agent. The dispatching agent calls this tool, receives the template with
UPPERCASE placeholders, fills them in, and uses the result as the
dispatch prompt.

This creates a mechanical step in the workflow -- the agent calls a tool
and gets back text it must use, rather than being told to go read a file
it can ignore.

### 2. `log_subagent_dispatch` requires `template_used`

For dispatches to agents that have defined templates, the
`log_subagent_dispatch` tool should require a `template_used` field and
reject the call if it is missing. This makes the dispatch log the
enforcement point: the agent cannot log the dispatch (which it is
already required to do) without also declaring it used the template.

The tool should:
- Accept `template_used: <template-name>` as a parameter
- Reject with an error if the target agent has a template but
  `template_used` is not provided
- Allow `template_used` to be omitted for agents without templates

### 3. E2E verification

The e2e verify script should check dispatch log frontmatter for the
`template_used` field. For dispatches to templated agents, the field
must be present. Its absence is a verification failure.

## Why This Should Work

The pattern that works in CLASI is tool-mediated enforcement -- the
agent must call an MCP tool, and the tool enforces constraints. The
pattern that fails is instructional enforcement -- the agent is told
to do something and it doesn't.

This proposal follows the working pattern:
- `get_dispatch_template` makes the template available via tool call
  (mechanical retrieval instead of voluntary file read)
- `log_subagent_dispatch` rejects non-compliant dispatches (mechanical
  enforcement instead of instructional "you should")
- E2E verification catches any remaining gaps (audit instead of trust)

## Files to Create or Modify

```
claude_agent_skills/mcp_server.py           (add get_dispatch_template tool)
claude_agent_skills/dispatch_log.py          (add template_used enforcement)
tests/e2e/verify.py                          (check template_used in dispatch logs)
```

## Related

- `done/agent-dispatch-templates-with-role-and-field-conventions.md` --
  the original TODO that created the templates. This TODO addresses the
  fact that creating them was not sufficient.
- `fix-agent-process-engagement.md` -- documents the general pattern of
  instructional controls failing. This is a specific instance.
