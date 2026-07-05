---
status: done
sprint: 018
tickets:
- 018-001
- 018-006
- 018-007
- 018-008
- 018-009
- 018-010
- 018-011
---

# Plan: Re-enable Git-Worktree-Based Parallel Ticket Execution in CLASI

## Context

The stakeholder wants two related capabilities back in CLASI:

1. **Specify that a sprint gets completed on worktrees** — independent tickets
   within a sprint run in parallel git worktrees instead of strictly serially.
2. **Keep planning the next sprint while one executes** — the team-lead should
   continue planning sprint N+1 while sprint N runs.

Worktrees were built once (sprint 023, 2026-03-17), disabled as "unreliable"
(commit `d7f0941`, 2026-05-02), then formally **re-designed but not
implemented** (sprint 022): a 514-line spec at
[worktree-process.md](docs/design/worktree-process.md) and a fully-stubbed API
module at [worktree.py](src/clasi/worktree.py) whose docstrings are the
implementation contract. This plan **implements that existing design** with
stakeholder-directed adaptations (per-sprint opt-in flag; plan-file file lists;
aggressive continuous cleanup).

**The reason worktrees were dropped last time: accumulation.** Unused worktrees
piled up until the pile itself became the problem — deferring cleanup to sprint
close was too late. The single most important design principle here is therefore
**aggressive, continuous cleanup so the pile never forms.** Cleanup is a
first-class pillar of this plan, not a close-time afterthought (see the Cleanup
Discipline section).

**Confirmed scope decisions:**
- **Unit of parallelism = per-ticket** (implement `worktree-process.md` as
  designed): independent tickets within ONE sprint run in parallel worktrees,
  each on its own `ticket/*` branch, merged back to the sprint branch.
- **Concurrency = plan-ahead only.** Keep the global execution-lock singleton —
  only one sprint executes at a time. Requirement #2 is already largely
  unblocked: research confirmed **no planning MCP tool enforces the
  project-level gates** (`create_sprint`, `detail_sprint`, `create_ticket`,
  `advance_sprint_phase` up to `ticketed`, `record_gate_result` all check only
  the sprint's OWN phase). The single hard interlock is the execution lock at
  `ticketing → executing`. So planning N+1 while N executes works today; this
  plan does **not** relax the lock and adds no concurrent-sprint execution.
- **Opt-in = per-sprint frontmatter flag** `worktree: true` in `sprint.md`,
  **not** the spec's repo-wide sentinel file `docs/clasi/.parallel-exec-enabled`.
  This is a deliberate deviation from spec §1/§2.4 — adapt those to read the
  frontmatter flag. Controller falls back to serial when the flag is absent/false.
- **File footprint source = the ticket plan file.** `check_independence` parses
  the `## Files to create or modify` heading in each ticket's `NNN-slug-plan.md`.
  No change to the ticketing process. (The spec's `files_to_create`
  frontmatter keys / `### Files to create` headings don't exist in current
  templates — this is why the parser must target the plan file.)
- **Cleanup = conservative on failed *branches*, aggressive on *worktrees*.**
  Never sweep failed/conflicted work without analysis and preservation — but the
  worktree *directory* is always resolved-then-cleaned, never left as dead weight
  (retain only the branch). And **never start a new worktree while unresolved old
  ones exist** — accumulation is a blocking condition. Full rules in the Cleanup
  Discipline section.

## Approach

Implement the 8 stub functions in `worktree.py` plus a new `reconcile_worktrees`
reaper, add a per-sprint opt-in flag, rewrite the serial-only execution
instruction into a flag-gated parallel path with serial fallback, replace the
stub tests with behavioral tests, and make cleanup a continuous, aggressive
discipline (preflight sweep + per-creation gate + close-time safety net). The
global execution lock and all lifecycle predicates are untouched.

### Concurrency invariant (must hold in all controller prose)

Parallelism is **intra-sprint, intra-group only.** The execution lock stays a
singleton (`state_db_class.py` `WHERE id = 1`, re-entrant per sprint). Only the
programmer *implementation* work runs concurrently (concurrent background Agent
calls). All controller git ops — `create_worktree`, `validate_worktree`,
`merge_ticket_branch`, `cleanup_worktree` — run **sequentially** on the
controller, because merging checks out the sprint branch in the single main
working tree (one HEAD).

## Cleanup Discipline (the core of this plan)

Accumulation is what killed worktrees before, so cleanup is designed as three
distinct behaviors, none of which defer to "later":

1. **Success → immediate teardown.** On a successful ticket merge, the worktree
   directory AND branch are removed *right then* (`cleanup_worktree(keep_branch=
   False)`), before the controller moves to the next ticket. Nothing lingers.

2. **Failure/conflict → resolved-then-cleaned, conservative on the branch.** A
   failed or conflicted worktree is never silently swept: it triggers analysis
   (recover work / escalate / abandon). But the worktree *directory* does not
   survive as dead weight — once the decision is made, the directory is removed
   (`cleanup_worktree(keep_branch=True)`) and only the *branch* is preserved for
   human inspection. Conservative on the work, aggressive on the dead directory.

3. **Standing reaper — preflight sweep + per-creation gate.** A `reconcile_
   worktrees(repo_root, sprint_dir)` reaper reconciles `.worktree-audit.json`
   against live `git worktree list` output. It runs at **three trigger points**:
   - **Session/execution start** — sweep before any sprint work begins.
   - **Before creating ANY new worktree** — the per-creation gate. If unresolved
     stale worktrees exist, the controller STOPS and resolves+cleans them before
     creating new ones. **Accumulation is a blocking condition, not a
     background annoyance.**
   - **Sprint close** — the final safety net (Chunk 7).

   **Resolution autonomy = auto-classify, clean safe, escalate the rest:**
   | Classification | Signal | Reaper action |
   |---|---|---|
   | merged-not-cleaned | audit `merged`, branch merged into sprint | remove dir + branch |
   | clean-but-abandoned | clean tree, no uncommitted work, not `in-progress` | remove dir, keep branch |
   | ambiguous | uncommitted/failed work, audit `failed`/`conflict`/`in_progress` | **escalate** with summary; do not remove |

   The reaper reports a one-line summary of what it cleaned and what it escalated
   at every trigger, so the pile's state is always visible.

## Work chunks (dependency-ordered; become CLASI tickets)

Critical path: **Chunk 1 → Chunk 3** (atomic pair) **→ Chunk 4 → Chunk 5**.
Chunks 2, 6, 7 hang off that spine and parallelize with each other.

### Chunk 1 — Implement `worktree.py` ([src/clasi/worktree.py](src/clasi/worktree.py))
Implement all 8 stub functions to their docstring contracts, **plus a new
`reconcile_worktrees(repo_root, sprint_dir) -> dict` reaper** (the standing
cleanup engine; not in the current stub set — add it). Order within:
audit pair → `check_independence` → git functions → `reconcile_worktrees` (it
composes `read_audit_record` + `git worktree list --porcelain` +
`cleanup_worktree`). All use
`subprocess.run([...], cwd=..., capture_output=True, text=True)` + returncode
checks, matching the `sprint.py` git-op style. Details in the section below.

### Chunk 2 — Opt-in flag ([src/clasi/sprint.py](src/clasi/sprint.py), [src/clasi/templates/sprint.md](src/clasi/templates/sprint.md))
- Add a `Sprint.worktree` property after `.status` (line 77), matching the
  existing accessor pattern:
  `return bool(self.sprint_doc.frontmatter.get("worktree", False))`.
- Add `worktree: false` to the `sprint.md` template frontmatter. Existing
  sprints without the field fall back to `False` (backward compatible).
- Surface the flag in `get_sprint_status` output (it already reads sprint
  frontmatter) so the controller decides with one MCP call it already makes.
- **Do NOT** add the flag to the state machine / predicates — it's an
  execution-strategy toggle, not a lifecycle gate. No new setter MCP tool;
  set via editing `sprint.md` at plan time (or existing
  `write_artifact_frontmatter`).

### Chunk 3 — Behavioral tests (replace [tests/clasi/test_worktree_stubs.py](tests/clasi/test_worktree_stubs.py))
Delete the `NotImplementedError` smoke tests, add `tests/clasi/test_worktree.py`.
Lands atomically with Chunk 1 (the stub assertions break the instant Chunk 1
lands). Real temp-git-repo fixtures for git functions; pure/fast cases for
`check_independence` and the audit pair. Details in Testing section.

### Chunk 4 — Rewrite execution instruction ([src/clasi/schemas/se-process/instructions/execution.md](src/clasi/schemas/se-process/instructions/execution.md))
Depends on Chunks 1 + 2. Replace the strictly-serial mandate (lines 7-12, 56-58)
with mode selection: read `worktree` flag → parallel path (gated) or serial path
(the current process, preserved verbatim as fallback). Update
[execute-sprint/SKILL.md](src/clasi/plugin/skills/execute-sprint/SKILL.md)
description line to reflect parallel-when-opted-in. Outline below.

### Chunk 5 — Wire the reaper into the controller (execution.md prose, depends on Chunk 1)
Make `reconcile_worktrees` the standing cleanup engine at its three trigger
points (see Cleanup Discipline): (a) session/execution start sweep, (b) the
per-creation gate that blocks new worktrees while unresolved ones exist, and (c)
the escalation prose for ambiguous cases (recover / abandon / inspect — never
auto-resume ambiguous work). This is controller prose in `execution.md` plus the
recovery step for orphaned worktrees / abandoned `ticket/<sprint>-*` branches
(spec §10/§12). This chunk is what actually prevents accumulation, so it's on the
critical path (after Chunk 4), not optional.

### Chunk 6 — MCP surface for the reaper (optional but recommended, depends on Chunk 1)
Add a thin read/act MCP tool (e.g. `reconcile_worktrees(sprint_id)`) wrapping the
`worktree.reconcile_worktrees` function, so the reaper is invocable on demand
from any session (not only inside execute-sprint) — the practical way to "keep an
eye on it" without a daemon. Returns the cleaned/escalated summary. Read-only
classification + safe auto-clean; ambiguous cases returned for the caller to act on.

### Chunk 7 — Close-sprint safety net ([src/clasi/tools/artifact_tools.py](src/clasi/tools/artifact_tools.py))
The final backstop. Extend `_prune_sprint_worktrees` ([artifact_tools.py:1155](src/clasi/tools/artifact_tools.py#L1155))
— which today matches only `refs/heads/<sprint-branch>` — to also match
`refs/heads/ticket/<sprint-id>-*` (or route it through `reconcile_worktrees` for
one code path). Per the confirmed decision: remove the orphaned worktree
*directories*, delete branches only if the audit marks them `merged`/`cleaned_up`,
and **retain** `failed`/`conflict` branches, reporting them in the close result.
Update the mock `side_effect` sequences in
[tests/system/test_artifact_tools.py](tests/system/test_artifact_tools.py)
(e.g. `test_full_lifecycle_success` ~line 739-753, which already mocks
`git worktree list --porcelain`).

## Per-function notes for `worktree.py`

- **`write_audit_record(sprint_dir, event)`** — path `sprint_dir/.worktree-audit.json`.
  Read-modify-write: load or seed `{"sprint_id": None, "worktrees": []}`, merge
  `event` into the entry matching `ticket_id` else append. **Atomic write**:
  write `.worktree-audit.json.tmp`, then `os.replace(tmp, final)`. Validate
  `event` has `ticket_id` + `state`, else `ValueError`.
- **`read_audit_record(sprint_dir)`** — absent file → default dict (no raise);
  else `json.loads` (let `JSONDecodeError` propagate).
- **`check_independence(tickets)`** — the algorithm (spec §3), highest-risk:
  - **File-set extraction** priority: (a) `files_to_create`/`files_to_modify`
    frontmatter if present; (b) **parse the plan file's `## Files to create or
    modify` heading** (accept `##`/`###` and the `Files to create`/`Files to
    modify` spellings) — collect list items until the next equal/higher heading;
    (c) neither → sentinel "unknown" = dependent on all.
  - **Normalize paths** to repo-relative POSIX and strip a leading `src/` so
    `src/clasi/foo.py` == `clasi/foo.py` (real footgun — dedicated regression test).
  - **Dependence**: A,B dependent if source-file sets overlap OR derived
    `test_<stem>.py` basenames overlap OR either set is the "unknown" sentinel.
  - **Grouping**: connected components over the dependence graph = serial
    groups; order groups by topological sort of aggregated `depends-on`,
    tie-break min ticket id ascending. Return `list[list[str]]`.
- **`create_worktree(repo_root, sprint_id, ticket_id)`** — path
  `(repo_root/".."/f"worktree-{sprint_id}-{ticket_id}").resolve()`. Use
  `git worktree add --detach <path> HEAD` (detached, since the sprint branch is
  already checked out in the main tree — git refuses the same branch in two
  worktrees). Return resolved abs `Path`.
- **`create_ticket_branch(worktree_path, ...slug)`** — `git checkout -b
  ticket/<sprint>-<ticket>-<slug>` with `cwd=worktree_path`. Controller derives
  slug via existing `templates.slugify(title)[:40]`.
- **`validate_worktree(worktree_path, ticket_path)` → bool** — three checks, all
  must pass: (1) test command (default `uv run pytest`, **make it a parameter**
  like `close_sprint`'s `test_command` so tests inject a fast stub) returncode 0;
  (2) `git status --porcelain` empty; (3) ticket frontmatter `status == "done"`
  (reuse `clasi.artifact` / `read_frontmatter`). Return bool, never raise.
- **`merge_ticket_branch(repo_root, sprint_branch, ticket_branch)`** — 2nd-highest
  risk. Checkout `sprint_branch` in `repo_root`; try `git merge --ff-only`; if
  ff not possible (branch advanced, not conflict) fall to `git merge --no-ff
  -m "Merge <ticket_branch>"`. Detect conflict via `git diff --name-only
  --diff-filter=U` non-empty (same technique as `sprint.py:359-368`) → `git
  merge --abort` + **raise `MergeConflictError`** (reuse the class at
  [sprint.py:10-19](src/clasi/sprint.py#L10)) carrying conflicted files. **No
  rebase.** The *controller* writes the `conflict` audit state on catching
  (function stays pure git+raise; §4 assigns audit writes to the controller —
  note this docstring reconciliation in the ticket).
- **`cleanup_worktree(repo_root, worktree_path, ticket_branch, keep_branch=False)`**
  — `git worktree remove --force <path>`; if not `keep_branch`, `git branch -d`
  (safe delete; never `-D`). Idempotent on already-removed worktree.
- **`reconcile_worktrees(repo_root, sprint_dir) -> dict`** (NEW — the reaper).
  Reconcile intent vs reality: read `.worktree-audit.json` (`read_audit_record`)
  and `git worktree list --porcelain`; for every worktree on a
  `ticket/<sprint>-*` branch, classify per the Cleanup Discipline table
  (merged-not-cleaned / clean-but-abandoned / ambiguous) using audit state +
  `git status --porcelain` in the worktree + merge-status vs the sprint branch.
  Auto-`cleanup_worktree` the two safe classes (updating audit to `cleaned_up`),
  collect ambiguous ones untouched. Also flag audit entries with no live
  worktree (already gone) and live worktrees with no audit entry (rogue).
  Return `{"cleaned": [...], "escalated": [...], "rogue": [...]}`. Pure of any
  prompting — the *controller* decides what to do with `escalated`. Idempotent;
  safe to call repeatedly (that's the point).

## execution.md rewrite outline

1. **Header** — parallel worktree execution when `worktree: true`, else serial.
   Remove the "strictly serial / no worktrees / no branching" language.
2. **§0 Mode selection** — read `worktree` frontmatter → serial path (existing
   §1–§5 preserved verbatim as fallback) or parallel path.
3. **Preflight sweep** — call `reconcile_worktrees` at execution start. Report
   what it cleaned; if it returns any `escalated` entries, resolve them (recover
   / abandon / inspect — never auto-resume ambiguous work) **before** starting
   new work. This is the first accumulation guard.
4. **Parallel preconditions** (adapts spec §2, flag replaces sentinel): phase
   `executing`; lock held by this sprint (re-entrant, singleton preserved); no
   tickets `in-progress`; `worktree: true`; sweep clean (step 3).
   Any failure → serial fallback for affected tickets.
5. **Grouping** — read open tickets + plan files; `check_independence` → ordered
   groups. Groups run serially; tickets within a group in parallel.
6. **Per-group loop**:
   - **Per-creation gate**: before creating this group's worktrees, call
     `reconcile_worktrees` again. If unresolved worktrees remain, STOP and
     resolve+clean them first — never create on top of a pile.
   - create worktree + ticket branch + audit + set `in-progress` per ticket →
     dispatch programmer agents **concurrently** into their worktree dirs → wait
     for all in group → per ticket **sequentially**: `validate_worktree` (retry
     re-dispatch up to 3, else audit `failed` + `cleanup_worktree(keep_branch=
     True)` + escalate) → `merge_ticket_branch` (on `MergeConflictError`: audit
     `conflict`, retain worktree, escalate; on success: audit `merged`,
     `move_ticket_to_done`, **`cleanup_worktree(keep_branch=False)` immediately**,
     audit `cleaned_up`). Advance to the next group only when the current group
     is fully merged/cleaned or explicitly escalated.
7. **Serial fallback** — entire current §3 preserved; also used when independence
   yields all-singleton groups.
8. **Close** — invoke `close-sprint`, whose safety net (Chunk 7) is the final
   reconcile pass.

## Verification

- **Unit** (`tests/clasi/test_worktree.py`): audit pair (create/merge/append,
  atomic no-`.tmp`-leftover, `ValueError` on missing key, absent→default,
  malformed→`JSONDecodeError`); `check_independence` table (overlap, disjoint,
  shared-test-module, missing-info→dependent, each heading spelling, `src/`
  normalization regression, `depends-on` group ordering); real-git fixture
  driving `create_worktree`/`create_ticket_branch`/`validate_worktree`/
  `merge_ticket_branch` (ff / --no-ff / conflict-abort-leaves-clean-tree) /
  `cleanup_worktree` (keep True/False). Inject a fast `test_command`.
- **Unit — the reaper** (`reconcile_worktrees`): real-git fixture with worktrees
  in each class — merged-not-cleaned → dir+branch removed; clean-but-abandoned →
  dir removed, branch kept; ambiguous (dirty tree / `failed` audit) → untouched +
  returned in `escalated`; audit entry with no live worktree → `rogue`/reconciled;
  live worktree with no audit entry → `rogue`. Assert idempotency (second call is
  a no-op) and that no `ticket/*` worktree survives a call unless it was
  escalated. This is the accumulation-prevention test — treat it as high-value.
- **Unit** (`tests/unit/test_sprint.py`): `Sprint.worktree` default `False`,
  and `True`/`False` when set.
- **System** (`tests/system/test_artifact_tools.py`): update close-sprint mock
  sequences to include an orphaned `ticket/<sprint>-*` worktree; assert it's
  pruned and appears in `worktrees_pruned`, and that a `failed`-audit branch is
  retained + reported.
- **End-to-end**: run `uv run pytest` (full suite green). Then drive a real
  opt-in sprint: create a sprint with `worktree: true` and 2 file-disjoint
  tickets, execute, and confirm two `../worktree-<sprint>-*` dirs are created and
  each is torn down **immediately on its merge** (not at close), leaving zero
  worktree dirs mid-sprint after the last merge. Then simulate accumulation:
  manually leave a stale `ticket/*` worktree, start another sprint, and confirm
  the preflight sweep + per-creation gate refuse to proceed until it's resolved.
  Confirm a `worktree: false` sprint still runs the serial path (no worktree dirs).
- Follow the CLASI process itself: this work should be planned as a sprint with
  the chunks above as tickets (the source-code gate requires an in-progress
  ticket).

## Risks

1. **[HIGH → mitigated] File-list source.** If `check_independence` can't find
   file lists, every ticket is "dependent on all" and the feature silently runs
   fully serial. Mitigation: parser targets the plan file's `## Files to create
   or modify` heading (confirmed decision) and accepts heading-spelling variants.
2. **[HIGH] Accumulation is the historical failure mode.** This is *why*
   worktrees were dropped. Mitigation is the whole Cleanup Discipline: immediate
   success teardown, resolved-then-cleaned failures, and the `reconcile_worktrees`
   reaper at three trigger points with a hard per-creation gate. The reaper's
   classification must err toward *escalate* (never auto-delete uncommitted/failed
   work) while still removing every dead directory — getting that boundary right
   is the crux; over-aggressive deletion loses work, under-aggressive rebuilds the
   pile.
3. **[MED] Lock must stay singleton.** Do not relax `execution_locks` to allow
   concurrent sprints. Parallelism is intra-sprint/intra-group only; execution.md
   must state this invariant.
4. **[MED] Single-HEAD merge serialization.** Controller merges ticket branches
   one at a time (merging checks out the sprint branch in the one main tree),
   even though implementation was concurrent.
5. **[LOW] Path normalization** false-independence footgun — covered by a
   regression test.
6. **[LOW] Docstring reconciliation** — `merge_ticket_branch` docstring says it
   writes the conflict audit state, but has no `sprint_dir`; controller owns the
   write. Note in the ticket.

## Spec open questions (confirmed)
- **Q1** keep the stub module — yes, implement in place.
- **Q2** audit format sprint-local `.worktree-audit.json` — keep (archives with sprint).
- **Q3** independence via static extraction — acceptable for v1; computed
  `git diff` pass is a documented follow-on.
