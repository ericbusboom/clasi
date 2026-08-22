---
status: pending
type: task
tags:
- process-docs
- issue-lifecycle
- e2e-finding
---

# Retiring a withdrawn idea must use move_issue_to_done — say so, because the reasoning against it is plausible

## Description

Found by the full multi-sprint E2E run `20260821-152013-39582` (2026-08-21),
rubric item A7. The stakeholder filed an issue and then changed their mind
("scrap that win/loss tally"). The subject **deleted the file with `rm`** and
never loaded `move_issue_to_done`.

Result on disk: the issue was gone entirely. `clasi/issues/done/` did not
exist. `find` returned nothing. No commit recorded it. **The idea and its
withdrawal left zero trace.**

## The important part: the subject's reasoning was coherent

> "The tally issue was still just a pending file, never committed or linked to
> a sprint, so deleting it left no loose ends."

That is a defensible inference. It is also wrong, and the wrongness is not
obvious from anything the process currently says.

And the same subject, in the same run, handled a *completed* issue perfectly:
the mid-flight `color-game-accept-grey-gray-variants.md` was filed during
sprint 002's execution, pulled into sprint 003, implemented, moved to
`clasi/sprints/003-color-guessing-game/issues/done/`, and committed (e2d5b8a).

So this is **not** tooling ignorance. The subject knows the lifecycle tools and
uses them correctly for work that got built. The gap is specifically about
retiring an idea that will **never** be built, and nothing in the process
states that `done/` is the terminal state for that case too.

## Why `rm` is the wrong answer

CLASI has no `withdrawn` or `rejected` status by design — `done/` is the
terminal state for a retired idea. Keeping the file records that the idea was
considered and dropped, and ideally why. Deleting it means a future reader
re-proposes the same thing with no way to know it was already declined. The
provenance is the whole point.

## Acceptance criteria

- [ ] The process states, in one canonical place, that a withdrawn idea is
      retired via `move_issue_to_done` with a one-line note saying it was
      withdrawn and why — and that `rm` / manual frontmatter edits are never
      the mechanism.
- [ ] The statement explicitly addresses the plausible counter-argument
      ("it was never committed or linked, so deleting is clean"), because an
      agent that has not been told otherwise will reach that conclusion.
- [ ] The team-lead agent definition's issue-lifecycle section covers the
      withdrawal case, not only completion.
- [ ] Consider whether `move_issue_to_done` should accept an optional reason
      that it writes into the issue body, so the note isn't a separate manual
      step that can be skipped.
