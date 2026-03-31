---
status: pending
---

# Remove ghtodo Skill

The `/se ghtodo` skill creates GitHub issues from the CLI. We don't
use it — the workflow is GitHub → local (via `/se gh-import`), not
local → GitHub.

Remove:
- The `ghtodo` entry from the `/se` dispatch table in `SKILL.md`
- The `ghtodo.md` skill file (if separate) or the ghtodo section
  from the todo-worker agent
- The `ghtodo` entry from `get_se_overview` output
