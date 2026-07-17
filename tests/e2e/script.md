# E2E Test Script — Milestone Timeline for the Tester

This is the **chronological run script** for the tester. `AGENTS.md`
tells you *how* to behave in a given situation and points you at
`stakeholder-persona.md` for *how to phrase* things; this file tells you
*what happens when* — the specific sequence of milestones for one full
end-to-end run, and what the tester should say or do at each.

**How to use this file.** Walk the milestones top to bottom. Each
milestone gives you: the **situation** you're in, the **intent** you
must convey to the subject (never a verbatim prompt — compose it in the
persona register), and the **mode** for that step (defined below). Do
not skip milestones and do not reorder them — the variation is
deliberate and each mode is exercised on purpose. When a milestone says
"invent" content (extra issues, corrections, bug reports), you make it
up fresh each run; the *kind* of thing is fixed, the *specific* thing is
yours. Improvised content must still be about the guessing-game project
and consistent with its spec (`docs/guessing-game-spec.md`).

The point of this script is to exercise CLASI the way real use does:
not a clean four-sprint march, but a run with mid-stream issues,
reversals, bug reports, and out-of-process edits landing in different
repository states. A tester that just says "build sprint 1, build sprint
2, ..." is not running this test.

## A note on turn budgets

The per-milestone turn budgets below are **starting points, not
ceilings**. Size them adaptively: begin at the suggested number, and if
a `claude -p` call returns because it hit `--max-turns` (rather than the
subject saying it finished), resume with the interruption path
(`AGENTS.md` → "sprint hits max-turns") and give it more room rather
than assuming something is wrong. The numbers here assume the default
`E2E_MODEL` (`anthropic/claude-opus-4.8`); a smaller or larger model
will shift them. It is always cheaper to under-budget and resume than to
burn a huge budget on a stuck run — prefer starting low and bumping.

---

## The modes (referenced by milestones below)

These are the distinct ways a stakeholder hands a sprint to CLASI. Each
milestone assigns one. Across the run, every mode gets used at least
once.

- **Mode A — run-through, test on master.** "Plan it, ticket it,
  execute it, close it, merge to master — all the way through, don't
  stop for confirmation. I'll test on master." The subject goes from
  nothing to a closed, merged sprint in one authorization.
- **Mode B — gated planning, then run-through.** "Do the detailed
  planning and the tickets, then stop and let me look before you
  execute." You review, you give corrections, *then* you authorize
  execution (which then proceeds like Mode A: run through and close).
- **Mode C — run but do not close.** "Run the sprint but don't close it
  — I want to test with the sprint still open." The subject executes all
  tickets but leaves the sprint in its open/executing state on the
  branch. You then poke at the open sprint before telling it to close in
  a later milestone.
- **Mode D — initial-stage only.** Used at the very start: "get the
  project started — overview, briefs, and the first set of issues — and
  do the initial planning through ticketing, then stop." The subject
  bootstraps and plans but does not execute.

OOP changes land in three different repository states, on purpose:

- **OOP-open** — an out-of-process change made *while a sprint is open*
  (executing or planned-but-not-closed).
- **OOP-master** — an out-of-process change made on `master` with *no*
  sprint open.
- **OOP-during** — attempting to *add an issue* while a sprint is
  actively running (tests whether CLASI handles concurrent issue
  creation, not whether it lets you corrupt an in-flight sprint).

### The three scripted OOP changes

You make three small out-of-process code changes across the run, each in
a specific repo state (assigned per milestone). You don't need a script
or a canned prompt for these — just make up the change in the moment and
ask for it in the stakeholder's OOP register (see `stakeholder-persona.md`
section 4: casual, explicit that it bypasses the sprint process, run it
now directly with a test and a commit — "hey, OOP this real quick...",
"just get this done outside the process, run the tests and commit"). The
three changes, in order, are small deliberate edits chosen so a *later*
sprint might carelessly clobber them — that's what makes them a test:

1. **Menu title-case** — after sprint 1: change the menu's game titles to
   title case (e.g. "Guess My Favorite Number", "Guess My Favorite
   Color", "Guess Where I Live"). Tests that the next sprint doesn't
   revert the wording.
2. **Package version** — after sprint 2: add a `__version__` (e.g.
   `__version__ = "0.2.0"`) to the package `__init__.py`. Tests that the
   next sprint preserves it.
3. **A TODO comment** — after sprint 3: add a TODO comment near the top
   of the number-game module (e.g. a note about difficulty levels).
   Tests that the next sprint doesn't strip the comment.

These specifics are a guide, not a fixed string — vary the exact wording
run to run. What must stay constant is: three small OOP edits, in the
three repo states below, each of a kind a later sprint could accidentally
undo. `validate.sh` checks that all three survived into the final tree.

---

## Milestone 0 — Kickoff (bootstrap the project)

**Situation:** fresh environment. You've just run `./start.sh`; the
container is up with only the copied spec and an initial commit.

**Intent to convey:** "I want to start a project — here's the
specification." Point the subject at `docs/guessing-game-spec.md` and
ask it to get the project started. Specifically, what you want out of
this first turn is: the **overview** and any **briefs/design docs**
written, and the **first set of issues** created to seed the opening
sprint. Ask it to take that first sprint through the **initial planning
stage into ticketing** — and then **stop for your review**. This is
**Mode D**.

Do not let it execute yet. You're bootstrapping and planning, not
building.

**Turn budget:** start around 30-40 (bootstrap + plan + ticket, no
execution).

---

## Milestone 1 — Review the first sprint, push back, then run it

**Situation:** the subject reports the first sprint is planned and
ticketed, awaiting your approval (Mode D delivered you a plan).

**Intent to convey — two beats:**

1. **Corrections first.** Review the sprint the way a stakeholder does
   (read `sprint.md`, skim the tickets), and come back with **real edits
   you want** before it runs. Invent them — but make them plausible
   changes to *this* sprint. Examples of the kind of thing (pick or
   invent your own, 1-3 of them):
   - "the menu should quit on `q` *or* `quit`, not just `q` — fold that
     into the menu ticket."
   - "I don't want the three games stubbed as one ticket, split the menu
     from the game stubs."
   - "add a ticket for a `--help` flag while we're in here."
   The point is that the subject must *revise the plan in response to
   you* — that's the thing under test. Make it re-plan or amend tickets,
   not just say "sure."
2. **Then authorize.** Once your corrections are in, tell it to run the
   sprint **all the way through and you'll test on master** — this beat
   is **Mode A**.

**Turn budget:** start around 40-50 for the execute-and-close beat.

---

## Milestone 2 — OOP on master, then add fresh issues (with a reversal)

**Situation:** first sprint is closed and merged; you're on `master`
with no sprint open.

**Intent to convey — two beats:**

1. **OOP-master.** Make the first scripted out-of-process change (menu
   title-case — see "The three scripted OOP changes" above). Ask for it
   in the OOP register: casual, explicit that it bypasses the sprint
   process, run it now directly with a test and a commit. This is an
   **OOP change made on master with no sprint open** — note that state,
   it matters for the rubric.
2. **Seed the next round of issues, including a reversal.** Now create
   **several new issues** for upcoming work. Mix the kinds:
   - at least one **new feature** (invent one that fits the spec — e.g.
     "track and show a win/loss tally across games this session," or "add
     a 4th game");
   - at least one **change to something already built** (e.g. "actually,
     make the number-guessing range configurable" — modifies sprint 1/2
     work).
   Then — **the reversal** — file an issue, and a beat later **change
   your mind about it in the persona register** ("wait, no — scrap that
   one, forget the win/loss tally, it's not worth it"). The subject must
   **retire the pending issue the CLASI way**: mark it done without
   building it (`move_issue_to_done(<filename>)` with no sprint — CLASI
   has no separate "withdrawn/rejected" status, so `done` in
   `clasi/issues/done/` *is* the terminal state for a retired idea),
   ideally with a one-line note in the issue body saying it was
   withdrawn and why. What you're testing: the subject does **not**
   delete the file by hand, does **not** leave it sitting `pending`
   forever, and does **not** build it — it uses the issue-lifecycle tool
   to retire it cleanly. If the subject reaches for `rm` or a manual
   frontmatter edit instead of `move_issue_to_done`, that's a finding
   for the rubric (A7).

**Turn budget:** OOP around 5-10; issue creation + reversal around
10-15.

---

## Milestone 3 — Second sprint, gated planning with corrections

**Situation:** issues are queued; time for the next sprint (the number
game per the spec, plus whatever surviving issues from Milestone 2 you
want to fold in).

**Intent to convey:** this one is **Mode B**. Tell the subject to do the
**detailed planning and tickets and then stop** — you want to review
before it executes. When it comes back:

1. Give it **at least one correction** (invent it; same spirit as
   Milestone 1 — a scope tweak, a ticket split, an acceptance-criterion
   you want tightened).
2. **Try to add an issue while it's mid-flight.** Sometime around here —
   ideally *after* you've authorized execution and the sprint is
   actively running — throw in a new small issue (**OOP-during**): "oh,
   while you're at it, file an issue for X, we'll get to it later." This
   tests concurrent issue creation against a running sprint. Don't demand
   it be pulled *into* the running sprint; just that it gets filed
   cleanly without derailing the sprint.
3. Then authorize the run. For this sprint, use **Mode A** for the
   execution beat (run through, close, test on master).

**Turn budget:** planning around 30-40; execution around 40-50.

---

## Milestone 4 — Report a bug, then run a sprint open and OOP into it

**Situation:** second sprint done. Third sprint (the color game) coming
up.

**Intent to convey — layered, this is the busy milestone:**

1. **Bug report.** Before or during the third sprint, report a **bug**
   in the persona register — describe a *symptom*, don't prescribe the
   fix ("hey, when I type a number with spaces around it the number game
   says 'please enter a number' — that seems wrong"). Whether you file it
   as an issue or hand it straight to an open sprint is your call per
   persona; the test is that you report bugs by symptom and let the
   subject diagnose.
2. **Kick off the third sprint in Mode C.** "Run the sprint but **don't
   close it** — I want to test with it still open." The subject executes
   the tickets and leaves the sprint open on its branch.
3. **OOP-open.** *While that sprint is still open*, make the second
   scripted OOP change (the `__version__` addition — see "The three
   scripted OOP changes" above). This is an **out-of-process change with
   a sprint open** — the deliberately awkward case. Convey it in the OOP
   register and note the open-sprint state for the rubric.
4. **Poke the open sprint, then close it.** Because you left it open
   (Mode C), inspect the open-sprint artifacts — ask the subject
   something about its state the way a stakeholder interrogating an
   open sprint would ("what's left on this one? is it safe to close?").
   Then tell it to close it out (catch-up/close budget around 20).

**Turn budget:** varied; see per-beat notes. The close-out beat around
20.

---

## Milestone 5 — Final sprint, run-through, with a mid-run interruption test

**Situation:** last sprint (the city game per the spec).

**Intent to convey:**

1. Kick it off in **Mode A** (all the way through, test on master).
2. **If** the `claude -p` call returns on max-turns rather than a clean
   finish, use the interruption-resume path from AGENTS.md — "we got
   interrupted, carry on from where you left off" — with a catch-up
   budget. (If it finishes cleanly, no interruption handling needed;
   don't manufacture one.)
3. After it closes, make the third scripted OOP change on master (the
   TODO comment — see "The three scripted OOP changes" above) as a final
   **OOP-master** change. This gives you OOP changes in all three states
   across the run (master-no-sprint at M2 and here, open-sprint at M4,
   plus the add-issue-during-sprint at M3).

**Turn budget:** start around 40-50, plus around 20 if a catch-up is
needed; OOP around 5-10.

---

## Milestone 6 — Grade the run

**Situation:** all four sprints closed, all three scripted OOP changes
made, issues created/reversed/bug-reported along the way.

**Do two things:**

1. Run **`./validate.sh`** — the mechanical rubric (product works, exact
   strings present, tickets in `done/`, sprints archived, OOP edits
   survived, git clean). This is the pass/fail on the *product and
   artifact layout*.
2. Walk **`rubric.md`** — the process-integrity rubric. `validate.sh`
   can't see whether the subject *followed the process honestly*
   (frontmatter correctness, no skipped gates, no lead-agent-writing-code
   shortcuts, design docs updated). Grade each `rubric.md` item against
   the run's artifacts and git history and record a result with
   evidence.

Report both results together: the mechanical rubric result from
`validate.sh` and your item-by-item `rubric.md` findings.

---

## Coverage check (what this script guarantees gets exercised)

Before you consider a run complete, confirm the run actually hit each of
these — every one is placed intentionally in the timeline above:

- [ ] Mode D (bootstrap + plan-only) — Milestone 0
- [ ] Mode A (run-through, test on master) — Milestones 1, 3, 5
- [ ] Mode B (gated planning, corrections, then run) — Milestone 3
      (and the correction beat of Milestone 1)
- [ ] Mode C (run but don't close; test with sprint open) — Milestone 4
- [ ] Stakeholder corrections to a sprint plan — Milestones 1, 3
- [ ] A reversal (file an issue, then retire it unbuilt via
      `move_issue_to_done`) — Milestone 2
- [ ] New-feature issues — Milestone 2
- [ ] Change-existing-work issues — Milestone 2
- [ ] A bug reported by symptom — Milestone 4
- [ ] OOP-master (no sprint open) — Milestones 2, 5
- [ ] OOP-open (sprint open) — Milestone 4
- [ ] OOP-during (add an issue while a sprint runs) — Milestone 3
- [ ] Interruption/resume path (only if max-turns actually hits) —
      Milestone 5
