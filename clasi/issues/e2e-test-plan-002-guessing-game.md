---
status: pending
type: e2e-test-plan
agent: e2e-test-runner
sprint: none
created: '2026-07-15'
run: 003
tags:
- e2e
- test-plan
- agent-instructions
---

# E2E Test Plan — Guessing Game CLI (Run 003)

**This is an e2e test agent issue, NOT a development issue.** Do not plan,
ticket, or sprint this. The e2e test runner agent reads this as its
observation checklist, runs the test, then moves this file to
`clasi/issues/done/` with `status: done`. No main-development agent should
touch this.

## Context

The first E2E run (`e2e-001-review.md`) ran 4 sprints successfully (37 tests
passing, game functional) but surfaced 8 process-quality issues. Three sprints
have shipped since then (016–019) that directly address flaws the E2E exposed
or would expose. This second run validates those fixes and checks for
regressions with the OpenRouter API backend (replacing direct Anthropic).

## What to Watch for During the Run

These are the specific observations to make while the 4 sprints execute. Each
is sourced from the last five CLASI sprints (014–019) and the e2e-001 review.

### 1. Guard Enforcement — Do Guards Actually Block Anything?

**Source:** Sprint 019 found every enforcement guard was silently failing open.
`role-guard` read `file_path` from the wrong payload level (root vs
`tool_input`), always got `""`, and always allowed. The ticket-gate and OOP
flag were also broken.

**How to observe during the run:**
- After the run, read `.clasi/log/hooks.log` from the container.
- Count `role-guard` entries: are they all `0 no-path` (the dead-gate
  signature) or do some show `2 denied` with real reasons?
- Check: do any `Write`/`Edit` operations on source files happen without an
  in-progress ticket? (If guards work, this should be blocked. If they fail
  open, it happens silently.)
- The OOP changes (3 total) should go through the bypass — verify they did
  NOT trigger guard blocks (the bypass works).

**Sprint-019 test-strategy lesson:** The fix for dead guards wasn't the code
change; it was replacing hand-built test fixtures with real captured payloads.
This E2E IS the real-payload test — it exercises guards with actual Claude
Code tool call payloads.

### 2. Planning Proportionality — Is the Sprint-Planner Still Writing Novels?

**Source:** Sprint 018 (right-sized planning) collapsed the three-document
planning model into a single `sprint.md`. The e2e-001 review documented
"multi-thousand-word plans with Mermaid diagrams for 40-line modules."

**How to observe:**
- After each sprint, check the sprint plan documents. For a project this
  small (3 simple games, stdlib only), a sprint plan should be a few
  paragraphs, not a treatise.
- Measure: word count of each sprint.md. Flag anything over ~500 words of
  planning prose for a guessing game sprint.
- Check: are there Mermaid diagrams? (Inappropriate for this project size.)

### 3. Version Bump Noise — 11 Bumps in 40 Commits?

**Source:** e2e-001 review item 3 (still pending). The first run produced
11 "chore: bump version" commits in a 40-commit history — one per ticket
plus one at close. Sprint 019 explicitly deferred this.

**How to observe:**
- After all sprints: `git log --oneline | grep -c "bump version"`
- Count total commits vs version-bump commits. Ratio should be ≤1 bump per
  sprint (≤4 bumps for 4 sprints), not 1 per ticket.

### 4. Close Report Quality — Are They Consistent?

**Source:** e2e-001 review item 4 (still untracked). The first run's close
reports were inconsistent, partly because `max-turns` exhaustion cut the close
step short.

**How to observe:**
- Check all 4 close reports exist and are non-empty.
- Do they all have the same essential sections? (Summary, what was completed,
  what was deferred, test results?)
- If a sprint hits `max-turns` without completing close, is the catch-up
  prompt needed?

### 5. OOP Bypass — Is the Flag Path Correct?

**Source:** Sprint 019 found the OOP flag was split-brain: guards checked
`.clasi-oop` (hyphen), everything else used `.clasi/oop` (slash). The e2e
tests OOP changes between sprints — does the bypass actually work?

**How to observe:**
- Before the first OOP change, verify `.clasi/oop` (or `.clasi-oop`) exists
  when the OOP `claude -p` command runs.
- Check hooks.log: OOP changes should NOT show `role-guard` blocks.
- Verify all 3 OOP changes landed correctly (validate.sh checks this).

### 6. Artifact Layout — Do Paths Match?

**Source:** Sprint 019 found generated rules had unreachable `paths:` because
CLASI's artifact layout changed (`.clasi/**` → `clasi/**`) but generators
weren't updated. Sprint 018 consolidated planning docs.

**How to observe:**
- Where do sprint artifacts actually land? `docs/clasi/sprints/` or
  `clasi/sprints/`?
- Are tickets in `tickets/done/` with acceptance criteria checked?
- Do the `validate.sh` path checks still match reality?

### 7. Transcript Security — Is the Log Directory Gitignored?

**Source:** Sprint 016 found `docs/clasi/log/` was committed with live secrets
in a downstream project.

**How to observe:**
- After the run: `docker exec clasi-e2e cat /project/.gitignore`
- Verify `docs/clasi/log/` appears in `.gitignore`.
- Check: does `git status` show log files as untracked/ignored?

### 8. Ticket Lifecycle — Do Tickets Properly Progress?

**Source:** Sprint 014 fixed issue→sprint→ticket→done linkage that never
fired because agents weren't instructed to invoke the tools.

**How to observe:**
- Each sprint should have 3+ tickets in `tickets/done/`.
- Tickets should show `status: done` with checked acceptance criteria.
- Are issues linked to sprints? (Check sprint.md frontmatter for `issues:`)

### 9. State Machine Terminology — `done` vs `closed`

**Source:** e2e-001 review item 7, resolved in sprint 019. Sprint.archive()
now writes `status: closed`.

**How to observe:**
- After the run, check sprint.md files: do they use `status: done` or
  `status: closed`?
- If `done` → the fix didn't reach the version of clasi installed in the
  container (installed from `git+https://github.com/ericbusboom/clasi.git`).

## Post-Run Verification (validate.sh)

After all 4 sprints and 3 OOP changes, `./validate.sh` checks:
- Process artifacts (overview.md, plans, tickets, close reports)
- Ticket lifecycle (3+ tickets per sprint, status: done, acceptance criteria)
- Sprint closure (4 close reports, all sprints phase: done)
- Code quality (game runs, all 3 games work, 37+ tests pass)
- Git hygiene (≥10 commits, branches per sprint, clean tree)
- OOP change resilience (3 OOP commits preserved)

## How This Issue Is Used

1. **E2E test agent reads this file** before running the test.
2. **During the run**, the agent monitors each sprint for the 12 observation
   points above.
3. **After the run**, the agent updates the frontmatter:
   ```yaml
   status: done
   ```
   and moves this file to `clasi/issues/done/e2e-test-plan-002-guessing-game.md`.
4. The agent writes a brief completion note at the bottom of this file with
   findings from the 12 observations.

## Related

- `clasi/issues/e2e-001-review.md` — first run review (8 items, partially resolved)
- `clasi/sprints/019-.../sprint.md` — enforcement guard fixes
- `clasi/sprints/018-.../sprint.md` — right-sized planning
- `clasi/sprints/016-.../sprint.md` — security and housekeeping
- `tests/e2e/AGENTS.md` — agent driving instructions for the run