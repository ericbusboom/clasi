---
status: in-progress
sprint: '020'
tickets:
- 020-009
---

# detect_inconsistencies drift-checks terminal, archived sprints

## Description

`detect_inconsistencies` (`src/clasi/status/inconsistency.py:37`) compares
declared-vs-computed state for **every** sprint in the status dict, including
sprints that are archived under `clasi/sprints/done/` and sitting in the state
machine's terminal state.

For a terminal, archived sprint this question cannot have a useful answer.
`closed` has no outbound transitions (verified — it is the only state in
`sprint.yaml` with zero), so there is no next action to unblock, no reconciliation
to perform, and no decision anywhere that reads an archived sprint's declared
status. A drift report on such a sprint is not telling the operator their data is
wrong; it is telling them the checker asked a question that does not apply.

**Concretely today**: the 18 sprints in `clasi/sprints/done/` were archived by a
writer that wrote `status: done` — a value `sprint.yaml` never defined (fixed at
the source by ticket `019-007`). Each of those 18 is therefore reported as
permanent `state_drift`: declared `done` vs computed `closed`. Forever. Nothing
can clear it except editing history.

**Priority: low — there is no visible symptom.** Ticket `019-006` now excludes
`done/` from status-block assembly, so those 18 warnings no longer reach anyone.
This issue is filed to record the analysis, not because anything is currently
broken in a way a user can see. It should be picked up only if the drift check
grows another consumer that does not filter `done/`.

## Cause

`detect_inconsistencies` iterates `status_dict["sprints"]` unconditionally and
calls `_check_sprint` for each (`inconsistency.py:57-63`). `_check_sprint`
(`:89-104`) compares `sprint_entry["state"]` against the frontmatter's declared
`status:` and emits a `state_drift` entry on any mismatch. There is no notion of
"this sprint is finished; stop asking."

The stale data is a symptom, not the cause. Sprint `019-007` fixed the writer so
no *future* archive drifts, but every sprint archived before it still carries the
legacy value and always will.

## Proposed fix

Skip drift-checking sprints in the machine's terminal state (or, equivalently,
sprints under `sprints/done/`). Derive the terminal state from `sprint.yaml`
rather than hardcoding `closed` — `tests/unit/test_sprint.py::_load_terminal_sprint_state`
(added by `019-007`) already does exactly this and can be reused or promoted out
of the test module.

This fixes the class rather than the instances: it covers all 18 legacy sprints
and every sprint archived before `019-007` shipped, without rewriting a single
data file.

**Explicitly rejected alternative**: bulk-rewriting `status: done` → `status: closed`
across the 18 archived `sprint.md` files. This was ticket `019-007`'s original
Part B and was **cut by stakeholder decision** during execution. It rewrites
history to satisfy a checker — those sprints genuinely *were* archived with
`status: done`, and editing them makes the record assert something untrue at the
time. Do not resurrect it. Legacy `done` should be tolerated on read.

## Verification

- A sprint archived via `Sprint.archive()` with a legacy `status: done` in its
  frontmatter produces zero `state_drift` entries from `detect_inconsistencies`.
- A non-terminal sprint whose declared status genuinely disagrees with its
  computed state STILL reports drift — the fix must not silence live drift, only
  terminal-state drift. This is the assertion that matters; a skip that is too
  broad is worse than the current noise.
- The 18 archived files remain byte-for-byte unmodified on disk
  (`grep -lc "^status: done" clasi/sprints/done/*/sprint.md` still returns 18).

## Related

- `019-007` fixed the writer (`Sprint.archive()` now writes the terminal state)
  and cut the bulk-rewrite; its ticket file records the full reasoning.
- `019-006` excluded `done/` from status-block assembly, which is why this has no
  visible symptom today.
- `clasi/review/e2e-001-review.md` item 7 is where the drift was first reported.
