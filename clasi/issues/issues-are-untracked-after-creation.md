---
status: pending
type: bug
tags:
- issue-lifecycle
- e2e-finding
- minor
---

# Filed issues sit untracked in git, so queued work is one `git clean` from gone

## Description

Found by the full multi-sprint E2E run `20260821-152013-39582` (2026-08-21).
After the subject created three issues at the stakeholder's request, `git
status` showed:

```
?? clasi/issues/configurable-number-game-range.md
?? clasi/issues/guess-favorite-animal-game.md
```

Nothing commits an issue when it is filed. The backlog therefore lives only in
the working tree until some later, unrelated commit happens to sweep it up.

## Why it is worth fixing despite being minor

- A `git clean -fd`, a branch switch, or a lost container deletes queued work
  with no record it ever existed.
- It interacts badly with the withdrawal defect
  ([[retiring-a-withdrawn-idea-must-use-move-issue-to-done]]): in this run the
  withdrawn issue was created and deleted while never tracked, so there is no
  git history of the idea at all — not even a deletion commit to point at.
- The campaign's own team-lead hit the mirror of this repeatedly, committing
  planning artifacts explicitly after each step precisely because nothing else
  did.

## Acceptance criteria

- [ ] A newly filed issue is committed as part of filing it, or the `issue`
      skill instructs the filer to commit it and says why.
- [ ] Whichever mechanism is chosen also covers issues created by the
      plan-to-issue hook, not only the `issue` skill.
- [ ] The commit message convention makes filed issues easy to find in history.
