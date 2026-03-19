---
id: "005"
title: "Update dispatch-subagent with scope and logging"
status: todo
use-cases: [SUC-002]
depends-on: ["003", "006"]
---

# Update dispatch-subagent with scope and logging

## Description

Update the `dispatch-subagent` skill and `subagent-protocol` instruction
to include directory scope and dispatch logging.

### dispatch-subagent skill changes

- Add `scope_directory` parameter to the dispatch prompt template
- Add logging step: after composing the prompt, write the full prompt
  to the appropriate log file before dispatching

### subagent-protocol instruction changes

- New "Directory Scope" section:
  - Always specify scope_directory when dispatching
  - Subagents may read from anywhere, write only within scope
  - If task requires writing outside scope, return a request to
    controller for expanded scope

### Logging integration

- Before each dispatch, write a log file with YAML frontmatter
  (timestamp, parent, child, scope, ticket, sprint) and full prompt
  text as body
- After dispatch returns, update the frontmatter with result and
  files_modified
- Route to correct log path per pc-architecture logging rules

## Acceptance Criteria

- [ ] dispatch-subagent skill includes scope_directory in prompt
- [ ] subagent-protocol has Directory Scope section
- [ ] Full prompt logged to file before dispatch
- [ ] Result appended to log after dispatch
- [ ] Log routing follows sprint/ticket/adhoc rules

## Testing

- **Verification command**: `uv run pytest`
