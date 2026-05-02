---
name: release-notes
description: Generate release notes from commits since the last tag.
---

# release-notes

Read `git log <last-tag>..HEAD --oneline`, group commits by type
(feat/fix/chore/refactor/test/docs), and write a Markdown summary
suitable for a GitHub release page. Lead with the most user-visible
changes; relegate internal refactors to a "Maintenance" section.
