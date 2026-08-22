# E2E run 20260821-152013-39582 — tester findings

## F1 (rubric A-category): subject left the OOP bypass active after an OOP change
- M2 beat 1 (`04-m2-oop-titlecase`) hit `error_max_turns` at turn 15/14 — my under-budget,
  NOT a subject failure. It had committed the change; cleanup was cut off.
- M2 resume (`05-m2-oop-resume`, exit 0, 108s) completed successfully and STILL left
  `clasi oop` active, even after "finish whatever's left to tidy up and confirm we're clean."
- Impact: guards stay bypassed for the rest of the run unless cleared. The 7h TTL
  (from the db-backed-oop-flag work) bounds the blast radius, but does not help within a session.
- Verdict: genuine process finding. `clasi oop off` should be part of completing an OOP change.

## F2 (rubric A7 — FAIL): reversed issue was deleted, not retired via move_issue_to_done
- M2 `07-m2-reversal` (exit 0, 47s). Tools used: Bash, ToolSearch, get_version, list_issues, Bash, list_issues.
  `move_issue_to_done` was never loaded or called.
- Outcome on disk: `session-win-loss-tally.md` gone entirely. `clasi/issues/done/` does not exist.
  `find` for the file returns nothing. No commit records it — the idea and its withdrawal left zero trace.
- Subject's own account: "The tally issue was still just a pending file, never committed or linked
  to a sprint, so deleting it left no loose ends."
- Why it's wrong: CLASI has no withdrawn/rejected status; `done/` IS the terminal state for a retired
  idea, so a future reader can see it was considered and dropped. `rm` erases that provenance.
  The subject's reasoning is internally coherent, which is what makes this worth fixing in the
  process docs rather than treating as carelessness.

## F3 (minor): issues created but never committed
- Both surviving issues (`configurable-number-game-range.md`, `guess-favorite-animal-game.md`)
  remain untracked (`??`) after creation. Nothing forces an issue to be committed when filed,
  so a crash or a stray `git clean` loses queued work.

## F2 refinement (important): the gap is WITHDRAWAL, not the tool
- The mid-flight `color-game-accept-grey-gray-variants.md` issue was handled CORRECTLY:
  filed during sprint 002 execution, pulled into sprint 003, implemented in ticket 003-001
  ("...with grey/gray equivalence"), and moved to
  `clasi/sprints/003-color-guessing-game/issues/done/` with commit e2d5b8a.
- So the subject knows and uses the issue-lifecycle tooling properly for COMPLETED issues.
  It only failed for a WITHDRAWN idea (F2), where it reasoned "never committed, never linked,
  so deleting leaves no loose ends."
- Implication for the fix: this is a docs/process gap about retiring unbuilt ideas, not a
  tooling-ignorance problem. The process should state that `done/` is the terminal state for a
  withdrawn idea and that `rm` is never the mechanism.

## F4 (positive): bug-by-symptom handled honestly
- M4 bug report (out-of-range guess consuming a turn) was investigated, found SPEC-COMPLIANT
  (spec exempts only non-numeric input; range never surfaced to player), and reported back as a
  design call with two options + a recommendation — rather than fabricating a fix to look
  responsive or dismissing it unexamined. Captured as `number-game-announce-range-in-banner.md`
  when I chose option A.

## F5 (positive): OOP hygiene self-corrected
- M2 required a nudge to run `clasi oop off`. By M4's OOP-open beat the flag was cleared
  without being asked. Same session, so this is within-run learning, not a code fix.

## F5 CORRECTED — OOP hygiene did NOT durably self-correct
- I recorded F5 as "self-corrected" after M4 cleared the flag unprompted. That was premature.
- M5's third OOP change (`13-m5-oop-todo`, exit 0, 40s) left `clasi oop` ACTIVE again.
- Pattern across the run: M2 left it on (needed a nudge) -> M4 cleared it unprompted ->
  M5 left it on. Inconsistent, not learned.
- Verdict: genuine, repeatable process finding. `clasi oop off` is not reliably treated as part
  of completing an OOP change. Given the flag silently voids every guard for its TTL, this
  should be enforced rather than remembered — e.g. OOP auto-clears on the next successful
  commit, or the status block warns loudly while it is active.

## F6 (HARNESS BUG, blocks grading): validate.sh reports 12 false failures — all 12 are its own bugs
Result line said "18 / 30 passed, 12 FAILURES". Every failure is a checker defect. Verified individually:

(a) 10 failures from `ls` exit-code misuse.
    Checks like: ls <sprints>/{done/,}001-*/tickets/*.md <sprints>/{done/,}001-*/tickets/done/*.md
    Brace expansion yields 4 patterns; only one matches (tickets ARE in tickets/done/).
    `ls` PRINTS the 4 found files but exits 1 because the other operands don't exist, and
    check_host only inspects the exit code. Reproduced directly:
      exit=1 while printing all 4 ticket paths; the single correct pattern alone exits 0.
    Affects: "Sprint 00{1,2,3,4} planned", "Sprint 00{1,2,3,4} has tickets",
    "Sprint 001 tickets completed", "Ticket files have acceptance criteria".
    Fix: per-pattern loop, or `compgen -G`, or `find`; never trust `ls`'s exit code with multiple globs.

(b) "Out-of-guesses message matches spec exactly" — greps for the literal
    'Sorry! The answer was 7.' but the secret number is RANDOM. Can only pass by luck.
    Observed at runtime: "Sorry! The answer was 8." — spec-correct.
    This is exactly review finding 05-e2e-test-infra.md #6 (grep source, not behavior).
    Fix: drive the game and assert on OUTPUT, or grep for the f-string prefix.

(c) "OOP 3: TODO comment present in number_game.py" — stale path. The module is
    guessing_game/games/number.py, and the TODO IS present at line 29.

TRUE OUTCOME of this run (verified by hand): 4/4 sprints planned+ticketed+closed+archived,
all tickets in tickets/done/, all 3 OOP edits survived, product works, tests pass, git clean.
validate.sh needs fixing before it can grade anything; as written it fails every run.
