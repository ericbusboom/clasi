---
status: pending
---

# Append Subagent Response to Dispatch Log

**Do not implement yet.**

## Problem

Dispatch log files currently record one side of the conversation: the
full prompt sent TO the subagent. When `update_dispatch_log` is called
after the subagent returns, it only writes `result` (success/fail) and
`files_modified` into the YAML frontmatter. The actual text response
from the subagent is discarded.

This means you cannot reconstruct what happened during a dispatch by
reading the log. You can see what was asked and whether it succeeded,
but not what the subagent said, what decisions it made, or what errors
it reported. For debugging, auditing, and process improvement, both
sides of the conversation need to be in the log.

## Current Behavior

1. `log_subagent_dispatch` creates the log file with frontmatter and
   appends the full prompt under `# Dispatch: parent -> child`.
2. `update_dispatch_log` calls `update_dispatch_result`, which adds
   `result` and `files_modified` to frontmatter only. The body is
   not modified.

## Proposed Solution

Add a `response` parameter to `update_dispatch_log` (and the underlying
`update_dispatch_result` in `dispatch_log.py`) that appends the
subagent's text response to the log body.

### Changes to `dispatch_log.py`

`update_dispatch_result` should:
1. Continue updating frontmatter with `result` and `files_modified` as
   it does today.
2. Accept an optional `response: str | None` parameter.
3. When `response` is provided, append a new section to the body:

```markdown
# Response: child

<response text>
```

The child agent name is already in the frontmatter and can be read
from there.

### Changes to `artifact_tools.py`

`update_dispatch_log` should:
1. Accept an optional `response: str | None` parameter.
2. Pass it through to `update_dispatch_result`.

### Caller Changes

Any agent or skill that calls `update_dispatch_log` after a subagent
returns should pass the response text. This includes the `dispatch`
skill and any direct callers in orchestration code.

## Files to Modify

```
claude_agent_skills/dispatch_log.py     (add response param, append to body)
claude_agent_skills/artifact_tools.py   (add response param, pass through)
```

## Open Questions

- Should `response` be required or optional? Making it optional
  preserves backward compatibility but means callers can silently
  forget to pass it. A deprecation warning for calls without
  `response` could help enforce adoption.
- Should very large responses be truncated? Subagent responses can be
  lengthy. A size limit (e.g., first N characters) might be practical,
  though losing content defeats the purpose.
