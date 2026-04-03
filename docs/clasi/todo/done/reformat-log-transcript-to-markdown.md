---
status: done
---

# Reformat JSON transcript in log files to readable markdown

The subagent log files (e.g., `docs/clasi/log/sprint-NNN/NNN-programmer.md`) append
the full JSON transcript at the end. This is hard to scan. Add a human-readable
markdown rendering before the raw JSON.

## Format

Insert an `---` (hrule) just before the transcript section, then render each message
as a markdown block with these fields:

- **timestamp**
- **type** (user, assistant, tool_use, tool_result)
- **gitBranch**
- **userType**
- **cwd**
- **model**
- **content**
- **stop_reason**

### Content rendering

- **Text content**: Render inline as markdown (not in a code block).
- **Tool result content**: Render in a separate block, distinguished from text
  (e.g., with a `> Tool Result:` prefix or a fenced block).

### Raw JSON preserved

After the markdown rendering, continue to display the full transcript in a fenced
JSON block exactly as it is today. The markdown is an addition, not a replacement.

## Where to change

Find the code that writes the `## Transcript` section of subagent log files. This
is likely in the subagent stop hook (`clasi/plugin/hooks/subagent_stop.py`) or in
the agent SDK integration (`clasi/agent.py`). The transcript is currently written as
a raw JSON dump inside a fenced code block.
