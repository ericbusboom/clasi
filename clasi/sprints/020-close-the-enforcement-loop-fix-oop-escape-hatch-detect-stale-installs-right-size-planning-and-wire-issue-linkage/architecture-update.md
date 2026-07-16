---
sprint: "020"
status: draft
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Architecture Update -- Sprint 020: Close the enforcement loop: fix OOP escape hatch, detect stale installs, right-size planning, and wire issue linkage

This is a bugfix-and-process-quality sprint across 9 largely independent
issues. No new subsystem is introduced except one small staleness-detection
check. Kept intentionally short — this sprint exists partly *because* prior
plans were disproportionate to their scope (issue 3), and a 9-issue backlog
of mostly-independent, mostly-small fixes does not warrant a component
diagram.

## 1. Understand the Problem

Sprint 019 made the enforcement guards fail closed instead of fail open,
but left two things unverified: whether the sanctioned escape hatch
(`.clasi/oop`) actually opens under the real invocation path, and whether
the tool used to verify any of it is even running the code being tested.
Investigation during this sprint's planning established that the second
question answers the first: `_oop_active()` in the working tree
(`hook_handlers.py:43`) is already correct, but bare `clasi` — what every
hook in `.claude/settings.json` and `.mcp.json` actually invokes — resolves
to a pipx build 18+ days stale, predating `_oop_active()` entirely. The
sprint's other 7 issues are smaller, independent process-quality gaps
(issue linkage, ticket auto-linking, plan verbosity, plan-to-issue shape,
disabled MCP tools, drift-checker over-reach, version-bump noise).

## 2. Identify Responsibilities

1. **Stale-install detection** (new) — compare the running server/hook's
   source against the project tree it's meant to manage; warn or fail
   loudly on mismatch.
2. **OOP bypass verification/fix** — confirm `_oop_active()` behaves
   correctly against the real invocation path once (1) is fixed; only add
   `hook_handlers.py` logic changes if the stale-build hypothesis turns out
   wrong.
3. **Version-bump policy** — reconcile "bump signals which build is live"
   against "one bump per ticket is noise."
4. **Issue-sprint-ticket linkage** — make the existing `link_sprint_issues`
   / `add_issue_ref` / `create_ticket(issue=)` chain actually get invoked
   by planning skills.
5. **create_ticket multi-issue default** — stop auto-linking all sprint
   issues when more than one is linked and no explicit `issue=` is given.
6. **Sprint-planner plan sizing** — proportion plan length/diagram use to
   actual scope size.
7. **plan-to-issue shape** — reshape plan output into house issue format
   instead of verbatim copy.
8. **MCP process-content tool re-enablement** — restore 9 commented-out
   `@server.tool()` decorators to match already-shipped docs.
9. **detect_inconsistencies terminal-sprint skip** — stop drift-checking
   sprints in the state machine's terminal state.

Each changes for an independent reason and lives in a different module;
none of these responsibilities overlap or need to merge.

## 3. Modules Touched

### `mcp_server.py` / `init_command.py` — staleness detection (new logic)
- **Purpose**: Detect when the running CLASI build's source differs from
  the project tree it is serving.
- **Boundary**: Inside — comparing `get_version()`'s existing
  `source_path`/`metadata_version` output against the target project root
  at server/hook startup, and this repo's own `.mcp.json` pointing at the
  editable install. Outside — how a consumer project's `clasi init` picks
  its MCP command (unchanged: still bare `clasi` by default, per
  `init_command._detect_mcp_command`'s documented, still-valid rationale
  for projects without `uv`).
- **Use cases served**: SUC-002.

### `hook_handlers.py` — `_oop_active()` / `handle_role_guard` (verify, fix only if needed)
- **Purpose**: Confirm the OOP escape hatch opens under the actual
  invocation path; the existing logic (checks `.clasi/oop` then
  `.clasi-oop`) is believed correct based on planning-time code reading.
- **Boundary**: Inside — a real-payload regression test proving the
  bypass works once the stale-build variable is controlled for. Outside —
  the ticket-state gate and tier resolution, unchanged (019 already fixed
  these; not reopened here).
- **Use cases served**: SUC-001.

### `.claude/rules/git-commits.md` + version-bump call sites — policy reconciliation
- **Purpose**: State one bump policy that both keeps "which build is live"
  answerable for an editable install and stops bumping every commit.
- **Boundary**: Inside — the rule text and wherever it's enforced (skill
  docs, possibly a lighter hook). Outside — the `dotconfig version bump`
  mechanism itself (unchanged, just called less often).
- **Use cases served**: SUC-003.

### Sprint-planner / create-tickets skill docs — issue linkage invocation
- **Purpose**: Ensure `link_sprint_issues`, `create_ticket(issue=)`, and
  `add_issue_ref` are actually called at the right lifecycle points, not
  just documented as available.
- **Boundary**: Inside — skill instruction text and any missing explicit
  call-site reminders. Outside — the underlying tools themselves (already
  correct per sprint 014 and per this sprint's own issue-9 finding that
  `add_issue_ref` was wrongly blamed).
- **Use cases served**: SUC-004.

### `artifact_tools.create_ticket` — multi-issue auto-link default
- **Purpose**: Stop defaulting an omitted `issue=` to "all sprint issues"
  once a sprint has more than one linked issue.
- **Boundary**: Inside — the auto-link branch at
  `artifact_tools.py:586-589`. Outside — `add_issue_ref` (already correct,
  not touched).
- **Use cases served**: SUC-005.

### Sprint-planner — plan-size proportionality
- **Purpose**: Match plan length and diagram use to actual scope.
- **Boundary**: Inside — the sprint-planner's judgment call on when a
  Mermaid diagram / long-form section is warranted vs. when compact bullets
  suffice. Outside — the underlying architecture-authoring skill mechanics
  (unchanged).
- **Use cases served**: SUC-006.

### `plan_to_issue.py` (`plan_to_issue` / `plan_to_issue_from_text`) — issue reshaping
- **Purpose**: Produce house-format issue content instead of a verbatim
  plan copy.
- **Boundary**: Inside — the hook's block-and-handoff behavior (preferred
  fix per the issue: block, instruct the model to rewrite into issue
  format, rather than parse/template plan sections). Outside — the model's
  actual rewriting (happens in-session, not in the hook).
- **Use cases served**: SUC-007.

### `process_tools.py` — 9 re-enabled `@server.tool()` decorators
- **Purpose**: Match the MCP tool surface to what shipped docs already
  promise.
- **Boundary**: Inside — the decorator re-enablement and updated test
  expectations (`EXPECTED_PROCESS_TOOLS`, tool count). Outside — the
  discovery-reliability measurement and any installer shrink (explicitly
  deferred, separate future work per the issue's own staging).
- **Use cases served**: SUC-008.

### `status/inconsistency.py` — terminal-state skip
- **Purpose**: Stop asking a drift question that has no useful answer for
  an archived, terminal sprint.
- **Boundary**: Inside — deriving the terminal state from `sprint.yaml`
  (reusing `_load_terminal_sprint_state` from
  `tests/unit/test_sprint.py`, promoted out of the test module) and
  skipping `_check_sprint` for sprints in that state. Outside — `_check_sprint`'s
  comparison logic itself for non-terminal sprints (unchanged).
- **Use cases served**: SUC-009.

## 4. Dependency Note

No new cross-module edges beyond: `mcp_server.py`/hook entry points now
also consult `get_version()`'s existing output at startup (a read, not a
new dependency direction — `get_version` already exists precisely for
this). No diagram is included; the module list above is the full picture
and every dependency direction already existed before this sprint.

## 5. Impact on Existing Components

- Every hook invocation and MCP server start gains one cheap
  version/source comparison. Negligible cost, bounded blast radius (a
  warning, not a new gate, unless a project opts into "fail closed on
  mismatch" per the issue's proposed layer 2 — deferred to ticket
  discretion, not mandated here).
- `.claude/settings.json` / `.mcp.json` in *this* repo change to point at
  the editable install; consumer projects' `clasi init` output is
  unchanged (still bare `clasi`, still correct for the no-uv case).
- `create_ticket` callers relying on the old multi-issue auto-link
  behavior (silently linking all sprint issues) must start passing
  `issue=` explicitly — this sprint's own ticketing does so already.
- `detect_inconsistencies` output shrinks (18 fewer permanent false
  positives) with no change to genuine-drift detection.

## 6. Design Rationale

### Decision: Investigate issue 1 as a symptom of issue 5 before touching hook_handlers.py
- **Context**: Reading `_oop_active()` in the working tree shows correct
  logic already shipped in `019-002`. The e2e test that reported the OOP
  break ran against whatever `clasi hook role-guard` resolved to at the
  time, and issue 5 independently proves that resolution was 18 days
  stale.
- **Alternatives considered**: Re-derive/rewrite OOP detection logic from
  the issue's root-cause hypotheses (flag-file path mismatch, prompt-based
  detection) without first checking install staleness — rejected, would
  duplicate already-correct code and misdiagnose a working fix as broken,
  the same class of error this sprint exists to avoid repeating.
- **Why this choice**: Cheaper to verify (one `which clasi` + version
  compare) than to rewrite, and the fix — if the hypothesis holds — is
  ticket 002's staleness detection, not a second OOP implementation.
- **Consequences**: Ticket 001 must explicitly test against the real
  invocation path (bare `clasi`, or `uv run clasi` if staleness isn't yet
  fixed) rather than assuming the working-tree code is sufficient proof.

### Decision: Reconcile version-bump policy rather than just removing bumps
- **Context**: `.claude/rules/git-commits.md` requires a bump per commit
  specifically because editable installs make version the only signal for
  which code is live — the same mechanism whose absence (bare `clasi`
  resolving to pipx, not editable) is issue 5's root cause.
- **Alternatives considered**: Drop the per-commit bump rule outright —
  rejected, removes the one signal that would have caught issue 5 sooner;
  keep per-commit bumps unchanged — rejected, doesn't address the noise
  complaint at all.
- **Why this choice**: Reduce bump frequency (e.g. per-sprint or
  per-meaningful-checkpoint) while keeping the property that a session can
  always tell which code is live — the two issues are two symptoms of one
  underlying need (verifiable liveness) and should resolve together.
- **Consequences**: Ticket 003 must state the new policy precisely enough
  that `.claude/rules/git-commits.md` and actual practice cannot drift
  apart again.

## 7. Open Questions

- Exact bump cadence (per-sprint? per-ticket-batch? on `close_sprint`
  only?) is left to ticket 003's implementation judgment — the sprint plan
  fixes the *tension*, not a specific number, since the right cadence
  depends on how staleness detection (ticket 002) changes the risk profile.
- Whether stale-install detection should ever fail closed (issue 5's
  proposed layer 2) versus warn-only (layer 1, the floor) is left to
  ticket 002 to decide and justify — the issue itself frames layer 1 as
  mandatory and layer 2 as a judgment call.
- No other open questions; each issue's own proposed-fix section already
  resolved its design choice during issue authoring.

## Migration Concerns

None requiring data migration. Behavioral changes on upgrade:
- Any project's next `clasi init`/upgrade after ticket 008 sees 9 more MCP
  tools advertised.
- Any project relying on the old `create_ticket` multi-issue auto-link
  behavior must adopt explicit `issue=` (this sprint's own tickets do).
- This repo's `.mcp.json`/hook config changes to point at the editable
  install; consumer-project `clasi init` output does not change.
