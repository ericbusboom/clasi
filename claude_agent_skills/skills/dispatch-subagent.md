---
name: dispatch-subagent
description: Controller/worker pattern for dispatching isolated subagents via the Agent tool with curated context, directory scope, and dispatch logging
---

# Dispatch Subagent Skill

This skill defines the controller/worker dispatch pattern. The
controller curates context, declares a directory scope, logs the full
dispatch prompt, and sends a fresh subagent to do the work.

## Process

### 1. Determine task scope

Identify:
- Which agent to dispatch (by tier and role)
- What directory the subagent may write to (`scope_directory`)
- What files and instructions the subagent needs

### 2. Curate context

Select only the files and instructions relevant to the task. Follow
`instructions/subagent-protocol` for include/exclude rules.

**Include:**
- Ticket description and acceptance criteria (if executing a ticket)
- Ticket plan (approach, files to modify)
- Content of source files the subagent will read or modify
- Relevant architecture decisions
- Applicable coding standards and testing instructions

**For raw-text delegation** (e.g., TODO creation, sprint planning):
- Pass the stakeholder's raw words verbatim
- Provide file references (TODO paths, overview path) instead of
  pre-digested content
- Let the subordinate agent make structuring decisions

**Exclude:**
- Controller's conversation history
- Other tickets in the sprint
- Debug logs from prior attempts
- Full directory listings
- Sprint-level planning documents (unless the task is planning)

### 3. Compose the prompt

Include in the subagent prompt:
- The curated context
- The scope constraint: "You may only create or modify files under
  `<scope_directory>`. You may read files from any location."
- The specific task and acceptance criteria
- Instructions for how to report results

### 4. Log the dispatch

Before sending the prompt, write the full prompt to a log file using
`dispatch_log.log_dispatch()`. This creates an audit trail with:
- YAML frontmatter: timestamp, parent agent, child agent, scope,
  sprint, ticket
- Body: the complete prompt text

### 5. Dispatch

Send the subagent via the Agent tool with the composed prompt.

### 6. Review results

When the subagent returns:
- Read the output
- Update the dispatch log with the result using
  `dispatch_log.update_dispatch_result()`
- Check that the work meets the task requirements
- If issues found, compose a new prompt with feedback and re-dispatch
  (max 2 retries, then escalate to the controller's parent)

## Notes

- The controller never writes code directly — all implementation is
  delegated to subagents.
- Each subagent starts with fresh context. It does not inherit the
  controller's conversation.
- Scope enforcement is prompt-level + rule-level. Path-scoped rules
  reinforce the constraint when the subagent accesses files.
