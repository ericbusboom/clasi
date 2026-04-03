---
status: pending
---

# Role guard should block team-lead from writing source code files

From reflection 2026-04-03-team-lead-wrote-code-directly.md: the team-lead wrote
Python source code directly instead of dispatching to a programmer. The role_guard
hook exists but did not block this.

Investigate and fix the role_guard hook so that the team-lead session (tier 0)
cannot Write or Edit files outside of `docs/clasi/` and `.claude/`. Source code
files (`.py`, `.toml`, `.yaml`, test files, etc.) should be blocked for the
team-lead, making the "never write code directly" rule structurally enforced
rather than relying on agent discipline.
