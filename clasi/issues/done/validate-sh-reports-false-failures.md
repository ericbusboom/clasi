---
status: done
type: bug
tags:
- e2e
- test-harness
- p1
---

# validate.sh reports 12 false failures — every one is a checker bug, so it fails every run

## Description

Found by the full multi-sprint E2E run `20260821-152013-39582`
(2026-08-21, 1h 26m 45s, four sprints). `validate.sh` reported:

```
Results: 18 / 30 passed
Status:  12 FAILURES
```

**All twelve are defects in `validate.sh` itself.** Verified by hand against
the run's artifacts: 4/4 sprints planned, ticketed, closed and archived; all
tickets in `tickets/done/`; all three OOP edits survived; product works; tests
pass; git clean.

As written the script fails every run regardless of subject quality. That is
worse than having no checker — it manufactures 12 lines of noise that would
mask a genuine regression, and it makes the rubric's Category-D result
meaningless.

## Three distinct bugs

### (a) `ls` exit-code misuse — 10 of the 12 failures

The ticket/sprint checks look like:

```sh
ls "$P"/clasi/sprints/{done/,}001-*/tickets/*.md \
   "$P"/clasi/sprints/{done/,}001-*/tickets/done/*.md 2>/dev/null
```

Brace expansion produces four patterns. Exactly one matches, because tickets
legitimately live in `tickets/done/` after a sprint closes. `ls` **prints all
four found ticket files and then exits 1**, because its other operands don't
exist — and `check_host` only inspects the exit code.

Reproduced directly:

```
$ bash -c "ls .../{done/,}001-*/tickets/*.md .../{done/,}001-*/tickets/done/*.md 2>/dev/null"
<prints all 4 ticket paths>
exit=1
$ bash -c "ls .../done/001-*/tickets/done/*.md"   # the one correct pattern alone
exit=0
```

Affected checks: `Sprint 00{1,2,3,4} planned`, `Sprint 00{1,2,3,4} has
tickets`, `Sprint 001 tickets completed`, `Ticket files have acceptance
criteria`.

Fix: never rely on `ls`'s exit status with multiple globs. Use a per-pattern
loop, `compgen -G`, or `find ... -print -quit`.

### (b) Hardcoded random value in an exact-string check

```sh
grep -rq 'Sorry! The answer was 7.' "$P/guessing_game/"
```

The secret number is **random**. This check can only pass by coincidence. The
source contains an f-string, and the runtime output for this run was
`Sorry! The answer was 8.` — spec-correct.

This is precisely the defect the earlier review recorded as
`docs/reviews/2026-08-reliability/05-e2e-test-infra.md` finding 6: exact-string
checks grep *source* rather than asserting *behavior*.

Fix: drive the game via stdin and assert on its output (as the menu checks
already do), or match the f-string prefix.

### (c) Stale module path

```sh
# OOP 3: TODO comment present in number_game.py
```

The module is `guessing_game/games/number.py`. The TODO **is** present, at
line 29. The check looks in a file that has never existed under that name.

## Acceptance criteria

- [ ] A run whose artifacts are actually correct reports zero failures.
      Re-run against the preserved `20260821-152013-39582` project tree, which
      is known-good by hand inspection, and require 30/30.
- [ ] No check depends on `ls`'s exit code with multiple glob operands.
- [ ] No check greps for a value that varies at runtime; behavioral strings are
      asserted against program output.
- [ ] Module/file paths referenced by checks are verified to exist, ideally by
      deriving them rather than hardcoding.
- [ ] A deliberately broken tree still FAILS — after fixing, confirm the script
      can still detect a real problem (e.g. hide a ticket, revert an OOP edit)
      so the fix isn't "make everything pass".
