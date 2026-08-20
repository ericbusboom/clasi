# CLASI Reliability Review

2026-08-20 · six subsystem review passes over the working tree at 0.20260820.1

Why a change in one place keeps breaking something unrelated — and the sequenced
campaign to fix it, validated by an instrumented E2E.

Companion documents in this directory hold the six full subsystem reports with
complete file:line evidence:

- [01-state-layer.md](01-state-layer.md) — DB, state machine, sprint/ticket/issue objects
- [02-mcp-tools.md](02-mcp-tools.md) — MCP server and tools layer
- [03-hooks-guards.md](03-hooks-guards.md) — hooks, guards, status package
- [04-cli-install-platforms.md](04-cli-install-platforms.md) — CLI, init/migrate/uninstall, platforms, clasr
- [05-e2e-test-infra.md](05-e2e-test-infra.md) — E2E harness and test suite
- [06-process-flow.md](06-process-flow.md) — process definitions, skills, ceremony cost

## Verdict

**The "weird unrelated bug" pattern is structural, not bad luck.** Six review
passes over about 23,500 source lines converged on the same small set of root
causes: process state kept in four disagreeing vocabularies with no single
writer, enforcement that silently allows on any internal error, pervasive trust
in the process's working directory, and shipped instructions that mandate
machinery which no longer exists. Every one of the bugs hit lately — the held
lock after a failed close, the OOP flag that "wasn't set," the planner blocked
mid-sprint, the init that reverts this repo's own `.mcp.json` — is a direct
instance of one of these causes.

The good news: the fixes are small relative to the codebase. The five
highest-leverage changes total well under 200 lines, roughly 1,700 lines of
dead machinery can simply be deleted, and the leaner sprint flow cuts ceremony
by more than half without giving up the two safety properties that matter (the
stakeholder approves the plan; tests gate the close).

| Findings | Critical | Major | Fail-open paths | Doc/code conflicts | Deletable lines |
|---|---|---|---|---|---|
| 96 | 14 | 36 | 18 | about 20 | about 1,700 |

## Part 1 — The diagnosis: six root causes

Individually, most findings look like ordinary bugs. Read together, they are
six patterns repeated across every subsystem. Fixing instances one at a time is
why the bugs keep coming back; the campaign in Part 5 attacks the patterns.

### RC-1 · Sprint state has four vocabularies and no single writer

A sprint's stage lives in the SQLite DB (`roadmap`…`done`), the frontmatter
`status:` field (`roadmap`/`planning-docs`/`closed`), the computed state
machine (`open`/`planned`/`ticketed`/…), and the directory location (`sprints/`
vs `done/`) — and the `list_sprints` docs advertise a fifth set
(`planning`/`active`/`done`) that nothing ever writes. These stores are updated
by separate, non-transactional writes, so any failure between them produces
permanent disagreement. The drift detector compares two vocabularies that are
**disjoint by construction**, so it flags every healthy sprint and its real
signal drowns. Ticket state is split the same way: moving a ticket to `done/`
and writing `status: done` are two operations no single code path performs
together.

Evidence: state review findings 2, 4, 6, 8, 10, 14 · `inconsistency.py:243`,
`state_db_class.py:55`, `predicates/project.py:76` (queries phase `"ticketed"`,
which no writer produces — visible right now: every session's status block
shows `enter-sprint` permanently blocked by `is_any_sprint_ticketed`).

### RC-2 · Failure is silent — guards fail open, tools fail half-done

The Claude Code harness only blocks a tool call on hook exit code 2; a crash,
timeout, or spawn failure is an **allow**. CLASI's guards have no top-level
exception boundary, so every unanticipated bug in a guard is an unlogged
allow — and `hooks.log` proves the class is real: 876 events from the weeks
when role-guard ran fail-open with nobody noticing. Meanwhile the tools layer
swallows its own failures: `close_sprint` wraps its DB update and version bump
in `except: pass`, so a failed close can archive the sprint directory while the
DB keeps the old phase **and the execution lock** — the exact "tool is useless
until I hand-edit it" lockup. Broad `except Exception` blocks that return safe
defaults appear in over twenty places across the state readers, guards, and
tools.

Evidence: hooks review F1–F5 plus the 18-row fail-open inventory · MCP review
F1, F2, F10 · state review findings 1, 11, 13 · `hook_handlers.py:1800`,
`artifact_tools.py:1259`.

### RC-3 · Everything trusts the current working directory

`get_project()` is literally `Project(Path.cwd())` with no upward search for
`.clasi/`. A hook fired from a subdirectory resolves every path against the
wrong root — and because every DB **read** auto-creates a fresh schema'd
database at whatever path it's handed, the wrong root gets a phantom DB where
the OOP flag is off, the lock is invisible, and the agent tier is unset: guards
fail open with benign-looking logs. The same trust in cwd runs through the
tools layer: most git subprocesses run with no `cwd=`, relative artifact paths
resolve against the server process's directory, and `clasi status` requires
being at the root while `clasi oop` walks upward. This one assumption is the
confirmed root cause of the OOP-flag incident and the prime suspect for several
"works at root, breaks from anywhere else" bugs.

Evidence: hooks review F2, inventory #4 · state review finding 5 · MCP review
F3, F4 · CLI review F15, F17 · issue `get-project-has-no-upward-root-discovery`.

### RC-4 · The docs and the code enforce two different processes

The phase machine requires stakeholder approval **before** tickets exist; every
agent definition and skill says tickets come first — so the planner is
hard-blocked mid-dispatch every sprint (the sprint-026 incident), costing a
third planner dispatch that exists only to work around the contradiction.
Process text lives in up to four diverging copies per topic (skill, schema
instruction, agent-local copy, `software-engineering.md` — whose largest file
describes a retired seven-agent process). Tool signatures in the docs don't
match the code (`move_ticket_to_done`, `reconcile_worktrees`). The
state-machine YAMLs that feed `clasi status` reference a gate that
`record_gate` rejects, an artifact nothing writes, and a phase string nothing
produces.

Evidence: process review — 20-row contradiction table, findings 1–4 · state
review findings 4, 6 · issue
`sprint-phase-gate-order-contradicts-plan-sprint-skill-docs`.

### RC-5 · Dead machinery is still wired into live instructions

Roughly 550 of `worktree.py`'s 1,035 lines implement a parallel-execution path
that has never run, has no MCP surface, and was deliberately abandoned — yet
`execution.md` still spends about 175 lines telling agents to drive it. The
`dispatch-subagent` skill says "you MUST call `log_subagent_dispatch`… if
unavailable, STOP" — the tool no longer exists. The rule loaded on **every
source edit** points at an "execute-ticket" skill that resolves, via a
directory-scan fallback, into `agents/old/` and a retired process that mandates
per-ticket full test runs. Dead code that stays referenced isn't inert — it's a
standing supply of mysterious mid-sprint blocks.

Evidence: CLI review F5 and deletion table · hooks review F11 · process review
findings 2, 9 · `process_tools.py:120` rglob fallback.

### RC-6 · Decisions and runs leave no evidence

When a guard blocks or allows, the log records **what** but not **why** — and
on the failure paths, nothing at all (guard crashes bypass logging entirely;
the plan-to-issue hook has written zero log lines in 3,021 events). The E2E
leaves rich in-container logs, but the subject's actual sessions die with the
container, validation output isn't persisted, and there's no per-phase timing
anywhere. This is why debugging a broken sprint run means archaeology instead
of reading a report — and it's the gap the instrumentation phase closes first,
so every later fix in the campaign can be verified instead of trusted.

Evidence: hooks review recommendation 3 · E2E review findings 2, 3 and the
8-item instrumentation plan · state review finding 3 (status recovers state by
regexing an exception's message text).

## Part 2 — Critical findings

The fourteen findings rated critical (or high, for infrastructure) across the
six passes. Each is independently worth fixing this month; file:line references
are in the subsystem reports.

| # | Root cause | Finding | Failure it produces |
|---|---|---|---|
| C1 | RC-2 | Guards have no exception boundary; any crash is a silent allow (`hook_handlers.py:1800`) | A refactor bug turns enforcement off invisibly; 876-event historical precedent |
| C2 | RC-3 | `get_project()` has no upward root discovery; DB reads auto-create phantom databases | Guards fail open from any subdirectory; stray `.clasi.db` files seed later confusion |
| C3 | RC-2 | `close_sprint` swallows DB/lock update failures (`except: pass`) | Archived sprint keeps the execution lock; next sprint can't start until hand-repair |
| C4 | RC-2 | `close_sprint` re-runs the version bump on retry and ignores git return codes | Double version tags; tags on wrong commits; merge fails on dirty tree, cause hidden |
| C5 | RC-2 | `close_sprint` self-repair mutates tickets/issues/phases **before** the test gate, no rollback | Failed close leaves the repo in a state that never existed; no `unclose_sprint` |
| C6 | RC-3 | Most git subprocesses in the tools layer run with no `cwd=` | Merge/tag/prune can target whatever repo the server process sits in |
| C7 | RC-1 | Four sprint-stage vocabularies; drift detector compares two disjoint ones | Every healthy sprint flagged; real drift invisible; status queries return empty |
| C8 | RC-1 | State-machine invariants unsatisfiable (`sprint_review` gate unrecordable; `"ticketed"` phase never written; ambiguous-state is the normal path, recovered by parsing exception text) | `clasi status` reports against a fictional process; predicates permanently False |
| C9 | RC-4 | Phase machine gates ticketing on stakeholder approval; all docs say the reverse | Planner hard-blocked every sprint; a whole extra dispatch as workaround |
| C10 | RC-5 | Mandatory instructions reference dead machinery (`log_subagent_dispatch` with STOP wording; execute-ticket resolving into `agents/old/`) | By-the-book agents dead-end or follow the retired process |
| C11 | RC-2 | `clasi init` unconditionally rewrites the `.mcp.json` server entry | This repo silently reconnects to the stale PATH build after every init/migrate |
| C12 | RC-2 | `clasi uninstall` deletes the whole CLAUDE.md; init clobbers user hooks in settings.json | Consumer repos lose their own content on uninstall/reinstall |
| C13 | RC-6 | E2E default auth path is dead (OpenRouter model gate) and the CLI is unpinned; readiness check is tmux-only | Full runs impossible on the default path; failures found 20 minutes in |
| C14 | RC-6 | Subject sessions and validation results aren't captured; deny payloads never recorded | A failed E2E run has no replayable evidence — the campaign can't measure itself |

## Part 3 — Per-subsystem highlights

Full detail in the companion reports; the load-bearing points per subsystem:

### State layer ([01](01-state-layer.md)) — 5 critical · 9 major · 6 minor

Beyond C2/C3/C7/C8: gate predicates accept a **failed** review (`is not None`)
while `advance_phase` requires passed/skipped — two gate semantics for one row.
`move_ticket_to_done` never writes `status: done` despite the YAML contract
saying it does. Frontmatter parsing is not line-anchored and writes are not
atomic — a crash corrupts the file and `list_sprints` then silently drops the
sprint. A corrupt `config.yaml` silently becomes `{}`, rerouting the db path,
protected paths, and design opt-in to defaults. Ticket globs match `*-plan.md`
companions, corrupting `all_tickets_done`.

The missing test with the highest payoff: one integration test driving a sprint
through the **real** writers (create → detail → gates → tickets → close),
asserting DB phase, frontmatter status, and machine state agree at every step.
It would have caught six findings; today's tests stub readers that echo
whatever the predicate asks for, making vocabulary drift structurally
undetectable.

### MCP server and tools ([02](02-mcp-tools.md)) — 3 critical · 9 major · 9 minor

Beyond C3–C6: a three-way inconsistent error contract across the 34 tools
(raise vs `{"error"}` in a success shape vs `close_sprint`'s own format; and
`list_tickets` returns `[]` for a typo'd sprint id). The NONE-sentinel
stripping is installed by monkey-patching three private MCP-library internals —
a library upgrade silently disables it, and `test_command="NONE"` then becomes
a literal command whose failure **silently skips the close test gate**. Bare
`git commit -m` sweeps whatever the user had staged into CLASI's chore commits.
`get_use_case_coverage` (a query tool) renames a directory as a side effect. No
caching in `Artifact`: `get_sprint_status` parses sprint.md five times and
every ticket three times.

Decomposition target (after the fixes, so the move is mechanical):
`tools/_common.py` (root-anchored paths, `run_git`, uniform envelope plus
sentinel decorator), then sprint/ticket/issue/close/review/github tool modules,
with close-sprint orchestration promoted to a resumable step-runner in
`clasi/close.py` that reads the recovery state it already writes. Roughly
400–500 of the 3,192 lines are duplication that disappears in the move.

### Hooks and guards ([03](03-hooks-guards.md)) — 2 critical · 6 major · 5 minor · 18-row fail-open inventory

Ten paths fail **open** (crash = allow; cwd mismatch = allow-everything; DB
contention silently skips tier-2's only gate; any garbage tier string allows;
Bash writes bypass the guard entirely), five fail closed (the friction bursts),
plus a destructive fallback: on payload drift, the plan-to-issue hook
**deletes the newest file in `~/.claude/plans`** on a guess, and logs nothing.
Every default DB read runs schema creation (a write transaction) with a 5s busy
timeout — under parallel agents this can eat role-guard's whole 5s budget,
which means killed, which means allow. The 2-hour agent-tier TTL is keyed on
start time, so a long ticket loses its tier mid-run and every write blocks as
tier 0, unexplained.

Latency verdict: status-inject is about 220–260 ms per prompt, role-guard about
60–110 ms per edit — already near target; the remaining cost is real work, not
process spawn. **A persistent daemon is not justified** — it would reintroduce
the stale-runtime failure class this repo has been burned by twice. The
dangerous number is the tail (DB contention → timeout → fail open), which the
reads-don't-write fix removes.

### CLI, install, platforms, clasr ([04](04-cli-install-platforms.md)) — 2 critical · 7 major · 11 minor

Beyond C11/C12: the four destructive installer behaviors share one root
cause — installers overwrite instead of merge/compare. Two complete
platform-adapter stacks exist (`clasi/platforms` 2,531 lines; `clasr/` 2,432
lines) with incompatible marker formats and uninstall models; nothing in clasi
imports clasr, and every platform fix is currently a two-tree change. Staleness
detection cannot see same-version drift (the exact gap in the memory notes) — a
12-line mtime-vs-import-time check closes it. About 550 lines of `worktree.py`
are an unreachable parallel-execution lifecycle that `execution.md` still
documents as live.

### E2E harness and test suite ([05](05-e2e-test-infra.md)) — 2 high · 5 medium · 4 low

The E2E is genuinely good — a stakeholder-persona-driven Claude session
exercising the full SE process in Docker, with 29 mechanical checks plus a
graded rubric — and its repo hygiene is already correct. What it lacks is
capture: subject sessions die with the container, validate output isn't
persisted, and a fail-open guard produces the same "no violations" evidence as
a healthy run. Separately, `-m 'not slow'` is dead config — zero slow marks
exist, so every pytest run is the full suite (about 2,850 tests, 6–10 min) with
coverage welded into `addopts`.

Instrumentation plan (ordered): (1) `run.sh` wrapper writing every subject
exchange to `.e2e-runs/<id>/` as stream-json; (2) preflight probe in start.sh;
(3) per-call durations plus an `mcp-calls.jsonl` trace in the server; (4) a
`phase_transitions` history table; (5) full-payload capture on every guard
denial (builds the real-payload test corpus); (6) container log and session-dir
collection in stop.sh; (7) a single assembled `run-report.md` per run; (8) the
coverage harness already specced in the existing issue. Plus six scripted
scenarios for failure modes the E2E can't currently see: fail-open guards,
stale server, subagent stall, MCP-down stop rule, tag push to a real bare
remote, OOP file-vs-DB semantics.

### Process flow and ceremony ([06](06-process-flow.md)) — 2 critical · 3 high · 4 medium

Measured cost of a 3-ticket sprint under the enforced path: **6 subagent
dispatches** (one exists purely to work around the gate-order contradiction),
**35–40 MCP calls**, **3 full test-suite runs** (the docs themselves claim two
is the total), 2 human stops, and 6–7 agent-driven phase/gate calls that are
pure bookkeeping. Guard friction is measured, not anecdotal: 68% of hard blocks
arrive in retry bursts, and the OOP escape hatch carries more traffic than the
gates block. The close-recovery machinery (`recovery_state`,
`clear_sprint_recovery`, guard bypasses during recovery) is the one engineered
failure path in the whole system — and no process document mentions it.

## Part 4 — Where the time goes

Speed turned out to be mostly a process problem, not a code problem. The hooks
are already near their latency targets, and the biggest wins are structural:

- **Sprint ceremony**: three planner dispatches and three full-suite runs per
  sprint where one of each suffices. At 6–10 minutes per suite run and a
  cold-context planner dispatch each time, this dominates sprint wall-clock.
- **Developer loop**: every pytest invocation runs all tests with coverage
  because the fast/slow split was never activated. A sub-minute default loop is
  one marking pass away.
- **Tool internals**: repeated frontmatter parsing — fixed by an mtime cache
  and a per-call index, no behavior change.
- **Not worth doing**: a hook daemon. The remaining latency is real work, and a
  resident process reintroduces the stale-runtime bug class.

| | Today | Leaner flow (proposed) |
|---|---|---|
| Subagent dispatches | 6 | 4 (1 planner + 3 programmers) |
| MCP calls | 35–40 | about 15 |
| Full test-suite runs | 3 | 1, at close |
| Human stops | 2–3 | 1–2 |
| Agent phase/gate calls | 6–7 | 0 — phases derive from tool events |

The leaner flow keeps both safety properties: the stakeholder approves the plan
(now with its tickets, matching what the docs always claimed), and tests still
gate the close. It requires the gate-order fix (approval gates the **lock**,
not ticketing) and the tier-0 relaxation already decided on 2026-08-19.

## Part 5 — The fix campaign

Sequenced for the intended working style: a worktree branch, validated
continuously against the instrumented E2E. Instrumentation comes first
precisely so every later phase can be **measured** — before/after run reports
instead of vibes. Phases 1–2 are deliberately small and high-leverage; deletion
and decomposition come last, when the ground is stable.

### Phase 0 — See clearly: unblock and instrument the E2E

Goal: a full E2E run completes and leaves a self-contained run report.

- Pin `@anthropic-ai/claude-code` in the Dockerfile; add the preflight probe;
  default to subscription auth until the OpenRouter gate is solved.
- `run.sh` wrapper plus `.e2e-runs/<id>/` capture of every subject exchange;
  container-log and session collection in stop.sh.
- MCP call trace with durations (`mcp-calls.jsonl`); phase-transition history
  table; guard decision-trail tokens in hooks.log; full-payload capture on
  every denial.
- `report.sh` assembling the single run report (validate output, milestone
  durations, slowest calls, deny histogram, empty-args signatures).

Validation: one complete baseline run on current master — the "before"
measurement for everything that follows; its denial-payload corpus feeds
Phase 1's tests.

### Phase 1 — Fail closed, resolve roots

Goal: no guard failure is ever a silent allow; nothing depends on cwd. Under
200 lines total.

- Exception boundary in `handle_hook`: guard crash → exit 2 plus a
  `guard-crash` log line (about 10 lines).
- `get_project()` walks upward via `_find_project_root`; DB reads stop creating
  databases; SQLite `timeout=1`.
- One `run_git(args, cwd=project.root)` helper for the whole tools layer plus
  sprint.py; commits use explicit pathspecs.
- Atomic frontmatter writes; root-anchored artifact path resolution; mtime
  source-drift signal in `check_staleness` (about 12 lines).
- Replay-test the captured payload corpus; assert the deny paths with real
  payloads.

Validation: E2E guard-probe scenario — malformed payload denies rather than
allows; subdirectory-cwd scenario passes; stale-server scenario trips the new
drift signal.

### Phase 2 — One truth for state; a close that can't wedge

Goal: sprint stage has one vocabulary and one writer; a failed close is
resumable, never a lockup.

- Single stage vocabulary (the DB phase list); frontmatter derived at write
  time by one `set_sprint_stage()`; delete the other vocabularies and fix the
  drift detector to compare like with like.
- Transactional `force_close` (phase=done plus lock release in one step), loud
  on failure; close reads its own recovery state to skip completed steps — no
  repeated version bumps, no re-run tests, repairs applied only after the test
  gate.
- Fix the impossible predicates (`"ticketed"`, `sprint_review`, gate-result
  semantics); define most-advanced-match-wins and delete the exception-text
  parser.
- `update_ticket_status("done")` performs the done-move; uniform `{"ok": …}`
  tool envelope with owned NONE-sentinel stripping.
- The writer-to-reader integration test: real writers, real DB, three-way
  agreement asserted at every lifecycle step.

Validation: E2E close-failure scenario — kill tests mid-close, re-run, assert
single tag, released lock, resumed steps. Run report shows zero self-repairs on
the happy path.

### Phase 3 — Honest process, leaner flow

Goal: docs, gates, and enforcement describe the same process; a small sprint
costs 4 dispatches and 1 suite run.

- Gate-order fix: `stakeholder_approval` gates the execution lock; delete the
  stakeholder-review phase; phases become event-derived (agents never call
  `advance_sprint_phase`).
- Ship the decided tier-0 relaxation (team-lead may `create_sprint` and write
  sprint files; `create_ticket` stays planner-owned); verify tier wiring with a
  real-dispatch test.
- One canonical text per topic: exclude `agents/old/` from definition lookup;
  fix or retire dispatch-subagent and source-code.md's execute-ticket pointer;
  rewrite `software-engineering.md` to the 3-agent reality; sync installed vs
  plugin team-lead.
- One full-suite run, owned by close; sprint-review interprets
  `review_sprint_pre_close`; document the close-recovery contract.

Validation: full E2E run under the new flow — run report shows the
dispatch/call/suite-run counts hit the leaner-flow targets, with zero
blocked-call retry bursts.

### Phase 4 — Delete and decompose

Goal: the codebase shrinks to what actually runs; the 3,192-line file becomes
eight small modules.

- Delete the worktree parallel-path lifecycle (about 1,700 lines with tests and
  the execution.md sections); dead versioning surface; dispatch_log (or
  reinstate it properly); debug scaffolding in mcp_server.
- Installer fixes as one small sprint: preserve existing `.mcp.json` entries,
  marker-based CLAUDE.md uninstall, per-event hook merge, shared
  canonical-skill writer.
- Split `artifact_tools.py` per the decomposition map (close orchestration and
  issue-sweep dedup first — those are the moves that make future bugs
  findable).
- mtime frontmatter cache plus sprint index (the speed fix).
- Execute the clasi/clasr decision from Part 6.

Validation: full E2E run green; coverage report from the run confirms the
deleted code was never exercised.

### Phase 5 — A test suite you'll actually run

Goal: sub-minute default loop; the E2E as the acceptance backstop.

- Activate the fast/slow split (mark real-FS/git/subprocess tiers); unweld
  coverage from `addopts`; add `just test` / `just test-all`.
- Developer-driven pruning of the duplicated tiers, using E2E coverage data as
  evidence (per the existing issue — the stakeholder drives every removal
  decision).
- Delete the empty test dirs; relocate the clasr demo fixtures.

Validation: timed — default loop under 60 s; full gate unchanged in coverage.

## Part 6 — Decisions needed

Everything above proceeds on defaults except these — each changes scope
materially:

1. **The clasi/clasr fork.** Two full platform stacks, zero shared code.
   Options: (a) freeze clasr now and archive it out of the repo (fastest, loses
   the manifest-based uninstall model), or (b) port `clasi init` onto clasr's
   manifest engine (better end state, but clasr's Codex output is broken and
   needs work first). Recommendation: (a) freeze-and-archive now, revisit (b)
   only if multi-platform becomes real.
2. **Codex/Copilot adapters.** 1,126 source plus 1,762 test lines, never
   dogfooded, carrying live bugs. Keep, or archive to a branch until there's a
   consumer? Recommendation: archive.
3. **The E2E auth path.** Accept subscription auth as the supported path (and
   drop the OpenRouter redirect goal), or invest in solving the CLI model-gate?
   Recommendation: subscription now; the OpenRouter issue stays parked in
   `later/`.
4. **Worktree parallel execution.** The deletion assumes it stays retired. If
   it might come back someday, archive rather than delete — but the docs get
   cut now either way.
5. **Scope of the first worktree branch.** Recommendation: Phases 0–2 as the
   first arc (instrumentation plus the two reliability phases), pausing for
   stakeholder review before the process changes in Phase 3.

---

Synthesized from six parallel review passes. Cross-review claims (gate names,
phase strings, dead tools) were independently confirmed by at least two passes
before inclusion.
