---
status: done
sprint: '003'
tickets:
- 003-010
---

# Transcript renderer should format Write tool content readably

In the markdown transcript rendering (`_render_transcript_lines` in
`clasi/hook_handlers.py`), `Write` tool uses currently dump `file_path` and
`content` as a single JSON blob with escaped newlines, making the content
unreadable.

## Fix

When rendering a `tool_use` block for the `Write` (or `Edit`) tool:

1. Extract `file_path` and `content` from the input separately
2. Show `file_path` as a heading or bold line
3. Render `content` based on the file extension:
   - `.md` files: inline as markdown (no code fence)
   - All other files: render in a fenced code block with appropriate language tag
4. For `Edit` tool: show `old_string` and `new_string` similarly, perhaps as a
   diff-style before/after

This makes ticket descriptions, skill files, and other markdown content readable
in the log without having to parse escaped JSON.
