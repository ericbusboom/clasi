---
id: '003'
title: 'Reconcile version-bump policy: fewer bumps without losing live-build signal'
status: done
use-cases:
- SUC-003
depends-on:
- '002'
github-issue: ''
issue: version-bump-noise-one-per-ticket-not-per-sprint.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Reconcile version-bump policy: fewer bumps without losing live-build signal

## Description

E2E run 003 showed 11 version-bump commits in 36 total (about one per
ticket) — noise with no release value. But `.claude/rules/git-commits.md`
requires a bump per commit specifically because tools are installed
editable and version is how a session tells which code is live. Sprint 019
explicitly deferred reconciling these two positions rather than just
deleting the bumps.

This ticket depends on ticket 002 (stale-install detection) landing first:
once staleness is detected and surfaced automatically, the version bump's
job as a manual "is this live" signal is partially subsumed by an
automatic check, which changes how much bump frequency is actually still
load-bearing. Do not reconcile the policy before reading ticket 002's
actual outcome.

Pick and justify a concrete cadence (e.g., once per sprint, once per
ticket batch, only before `close_sprint` — which already bumps + tags).
The chosen cadence must still let a session answer "is my running build
current" without relying solely on git log inspection, given ticket 002's
detection now exists as a backstop.

## Acceptance Criteria

- [x] `.claude/rules/git-commits.md` states one concrete, unambiguous bump
      cadence that is not "every commit."
- [x] The reconciliation explicitly explains why the new cadence still
      satisfies the editable-install "which code is live" need, referencing
      ticket 002's staleness detection as a complementary (not replacement)
      mechanism.
- [x] A test or documented dry-run on a 3+//-ticket sprint shows at most
      1-2 bump commits for the whole sprint, not one per ticket.
- [x] `close_sprint`'s own bump+tag behavior is explicitly reconciled with
      the new cadence (no double-bumping, no gap where neither the new
      cadence nor close_sprint covers a scenario).

## Completion Notes

### Cadence chosen: once per sprint, at `close_sprint` — not per ticket, not per commit

`.claude/rules/git-commits.md` (generated from `GIT_COMMITS_BODY` in
`src/clasi/platforms/_rules.py`, the single source of truth per the
ticket's own instruction — fixed there, not hand-patched in the generated
file) now states: no manual `dotconfig version bump` during ticket work on
a sprint branch. `close_sprint` already bumps and tags exactly once per
sprint, gated by the existing `version_trigger` setting (default
`every_change`, evaluated only at `sprint_close` via
`should_version(trigger, "sprint_close")` — this mechanism already existed
in `versioning.py` and was already respected by both `_close_sprint_full`
and `_close_sprint_legacy`; nothing new needed there). The only carve-out
is OOP (non-sprint, direct-to-master) work, which still bumps once per OOP
commit, because there is no `close_sprint` event to anchor to and OOP is
scoped to small, infrequent changes that don't reproduce the noise
pattern.

Rejected "once per ticket": produces 3 bumps for a 3-ticket sprint, still
exceeding the ticket's own "at most 1-2 for the whole sprint" target.
Rejected pure "every commit" (status quo): measured at 11 bumps in 36
commits (about one per ticket) in the source issue — no release value.

### Why this still answers "is my running build current"

The bump's old job as a manual live-build signal is not simply dropped —
it is superseded by ticket 002's automatic, continuous check. Every
`get_version()` call and every role-guard/mcp-guard hook invocation runs
`clasi.staleness.check_staleness()`, comparing the running build's
`source_path`/`metadata_version` against the project's actual source, and
**fails closed** (`stale-guard`, exit 2) the instant they diverge — not
just at commit boundaries chosen by a human/agent remembering to run
`dotconfig version bump`. That fires far more often (every guarded tool
call) and more reliably (automatic, not memory-dependent) than a
per-commit bump ever did. The bump remains useful as a once-per-sprint
release-style marker; the load-bearing "which code is live" job moved to
the automatic check. This is documented explicitly in both
`GIT_COMMITS_BODY` (`src/clasi/platforms/_rules.py`) and
`instructions/git-workflow.md`
(`src/clasi/plugin/instructions/git-workflow.md`), referencing ticket
002's mechanism by name as complementary, not a replacement being papered
over.

### close_sprint reconciliation — no double-bump, no gap

Read `_close_sprint_full` and `_close_sprint_legacy` in
`src/clasi/tools/artifact_tools.py` directly (not assumed). Both are
mutually exclusive paths (branch_name present vs. absent) and each has
exactly one bump call site, gated by the same `should_version` check —
structurally impossible to double-bump from `close_sprint` itself. With
per-ticket/per-commit manual bumps removed from sprint work, `close_sprint`
is now the *only* bump site for sprint work, closing the gap the old
policy created (a manual bump could previously land right before
`close_sprint`'s own bump, producing back-to-back version increments with
no commit in between). Non-sprint work (Option B feature branches with no
sprint) is covered by `dotconfig version bump --tag` before merge,
documented in `instructions/git-workflow.md`; OOP work is covered by its
own per-commit bump. No scenario in `git-workflow.md`'s branch strategies
is left without a bump mechanism.

### Test: real dry-run, not mocked

`tests/system/test_version_bump_cadence.py` drives a real git repo through
`create_sprint` -> 3 tickets -> 3 real ticket commits with zero manual
bumps -> the real `close_sprint` MCP tool (real precondition self-repair,
real `git rebase` + `--no-ff` merge, real `compute_next_version`/
`update_version_file`/`git commit`/`git tag`) and asserts exactly 1 bump
commit exists in the whole history (`<= 2` per the ticket's own
tolerance), plus exactly one version tag (no double-bump). Manually
verified the test's assertion is discriminating: re-running the identical
scenario with the *old* per-ticket bump reinserted (a throwaway script,
not committed) produced 4 bump commits and would fail `bump_commits == 1`
— confirming this test would have caught the regression the issue
reported, not just exercised the happy path.

### Consistency check

`instructions/git-workflow.md`'s Version Bumping section was rewritten to
match (no contradiction with the rule): sprint work bumps only at
`close_sprint`; non-sprint feature branches bump once before merge; OOP
bumps per commit. The programmer agent's own workflow step 9
(`src/clasi/plugin/agents/programmer/agent.md`) — which is the literal
mechanism that produced the "roughly one bump per ticket" pattern in the
issue's evidence — was updated to match: no manual bump for sprint
tickets, OOP exception preserved. `.claude/agents/programmer/agent.md` and
`.claude/rules/git-commits.md` (this session's locally
generated/installed copies) were also synced for immediate
self-consistency, but per the ticket's own instruction the durable fix
lives in the generator (`_rules.py`) and the plugin source (`agent.md`) —
both tracked files; `.claude/` is gitignored in this repo and regenerates
from those sources on `clasi init`.

Full suite: 2552 passed (2551 baseline + 1 new test), 0 failures.

### Process note

Editing this ticket's frontmatter/acceptance-criteria required a brief,
narrowly-scoped `.clasi/oop` override: the `active_agents`
dispatch-registration gap ticket 002 already documented (`is_
programmer_dispatched` never resolves true for this dispatched session)
blocked role-guard from recognizing this ticket as legitimately
in-progress even while genuinely doing the work. Same known gap, not a
new one. Flag removed immediately after this write.

## Implementation Plan

**Approach**: Read ticket 002's actual delivered mechanism first. Then
rewrite `.claude/rules/git-commits.md`'s bump instruction to a specific,
lower-frequency cadence, and update whatever mechanism currently prompts
per-commit bumps (rule text, and/or a hook if one enforces it) to match.

**Files likely involved**: `.claude/rules/git-commits.md`, any
version-bump-related hook or skill instruction (`instructions/git-workflow`
per the rule's own cross-reference).

**Testing plan**: Dry-run or scripted check across a multi-ticket test
sprint's git log; assert bump-commit count matches the new policy.

**Documentation updates**: `.claude/rules/git-commits.md` is the primary
deliverable; check `instructions/git-workflow` for consistency.
