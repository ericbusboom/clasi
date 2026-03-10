---
status: done
sprint: '017'
---

# Inline CLASI block into CLAUDE.md instead of using @AGENTS.md

The `clasi init` command currently creates `CLAUDE.md` with just `@AGENTS.md`,
putting the CLASI process instructions in a secondary file. Agents read
CLAUDE.md first but may deprioritize AGENTS.md content since it's loaded
via indirection.

Change `init_command.py` to inline the CLASI block (with start/end markers)
directly into CLAUDE.md. Update the template (`claude-md.md`), adjust the
init logic to write/update the CLASI section in CLAUDE.md, and drop the
AGENTS.md step.
