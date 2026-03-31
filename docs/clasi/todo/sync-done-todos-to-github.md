---
status: pending
---

# Sync Done TODOs Back to GitHub Issues

When a TODO with a `source:` URL pointing to a GitHub issue moves to
`todo/done/`, we should close the corresponding GitHub issue.

Proposed approach:
- New `/se sync` command (or add to close-sprint flow)
- Walk `todo/done/`, find items with `source: https://github.com/.../issues/NNN`
- Call `gh issue close NNN` for each
- Optionally add a comment on the issue linking to the sprint that
  resolved it

This keeps GitHub in sync without making it the primary source of
truth.
