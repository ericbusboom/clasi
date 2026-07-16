---
id: '002'
title: Detect stale CLASI installs at MCP/hook startup; point this repo's own config
  at the editable install
status: done
use-cases:
- SUC-002
depends-on:
- '001'
github-issue: ''
issue: mcp-server-runs-stale-pipx-build-not-the-working-tree.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Detect stale CLASI installs at MCP/hook startup; point this repo's own config at the editable install

## Description

`.mcp.json` and every hook in `.claude/settings.json` invoke bare `clasi`,
which resolves through `$PATH` to whatever build is installed globally —
measured this session at pipx `0.20260627.14`, 18+ days behind this repo's
working tree (`0.20260715.3` via `uv run clasi`). This silently voided
sprint 019's entire verification story: `close_sprint` archived 019 with
`status: done`, the exact bug `019-007` had just fixed, because the tool
doing the closing ran pre-019 code. `get_version()` already returns
`version`, `metadata_version`, and `source_path` specifically so staleness
is detectable — nothing currently acts on it.

Layered fix per the issue (do 1, this repo's own config fix, and consider
2; do not stop at "just reinstall"):

1. **Detect and report staleness.** Compare the running server/hook's
   `source_path` against the project tree at startup; warn loudly
   (status block, MCP `instructions` field, or startup log) on mismatch.
2. **Consider failing closed on a dangerous mismatch** — a stale guard
   that reports success while enforcing nothing is worse than no guard.
   Judgment call for this ticket to make and justify; the issue frames
   this as optional, not mandatory.
3. **Point this repo's own `.mcp.json` at the editable install** — a
   dogfooding checkout should run the code under development.

Do NOT simply re-run `pipx install --force` and call it fixed — that
resolves today's drift and leaves the detection gap that allowed it.

## Acceptance Criteria

- [x] A deliberately stale install (e.g. an older pipx build alongside a
      newer working tree) produces a visible warning naming both versions,
      surfaced through at least one of: status block, MCP `instructions`,
      or startup log.
- [x] This repo's `.mcp.json` and/or `.claude/settings.json` hook
      invocations are corrected so the MCP server and hooks run this
      repo's working tree, not a stale global install.
- [x] A fresh `clasi init` in a consumer project with no `uv` and no
      `[project]` table still works unchanged — `init_command._detect_mcp_command`'s
      existing rationale for bare `clasi` as the *default* for consumer
      projects is not broken by this fix.
- [x] `close_sprint`, run through the corrected invocation path on a tree
      containing the 019-007 writer fix, produces `status: closed`, not
      `status: done`.
- [x] Decision on fail-closed vs. warn-only for a large version gap is
      made and justified in this ticket's notes (not silently deferred).
- [x] Regression test: staleness comparison logic is unit-tested against
      real `importlib.metadata`/`source_path` shapes, not synthetic stand-ins.

## Completion Notes

### The actual root cause: a stale `clasi.egg-info/` at the repo root

`importlib.metadata.version("clasi")` was returning `0.20260627.12` — a
value matching *no* installed build (pipx was at `.14`, the tree at `.4`).
The repo root is on `sys.path`, and a June 27 `clasi.egg-info/` directory
sat there shadowing the correct `.venv` dist-info. Every in-process version
check in this repo had been reading that phantom for 18 days — including
whatever stamped `clasi_version: 0.20260715.2` onto the E2E run 003 issues,
a version that never existed on disk.

Deleted by the stakeholder (a gitignored build artifact). `importlib`
immediately began reporting `0.20260715.4`, matching pyproject.

This also explains an apparent bug in the new module: it initially reported
`stale=True` against the *current* tree. Not a false positive — it was
correctly detecting a third stale artifact nobody knew about.

### Fail-closed decision: FAIL CLOSED, scoped narrowly

`handle_role_guard` refuses to enforce (exit 2, reason `stale-guard`) when
the running build does not match this repo's editable source.

Justification: a stale guard is strictly worse than no guard — it reports
success while enforcing nothing. That is precisely how sprint 019's entire
enforcement story went silently inert for 18 days. Warn-only was rejected
because the warning would land in the same stderr nobody was reading when
the original failure occurred.

Placement was deliberate: the check sits *after* the `_oop_active()` bypass
and the safe-prefix allowances, so the escape hatches needed to *repair* a
stale pointer (setting `.clasi/oop`, editing `.claude/settings.json` or
`.mcp.json`) are never blocked by the same staleness they exist to fix. A
fail-closed guard that locks you out of fixing it is a worse trap than the
bug.

### Config corrected, consumer default preserved

This repo's `.mcp.json` and all five hooks in `.claude/settings.json` now
invoke `uv run clasi`. `init_command._detect_mcp_command()` is untouched and
still emits bare `clasi` for consumer projects — verified by calling it
directly against a non-uv path: `{'command': 'clasi', 'args': ['mcp']}`. The
dogfooding fix does not leak into the consumer default.

### Verified live, not only by unit test

- `check_staleness(root, "0.20260627.14")` → `stale=True`, names both versions
- `check_staleness(root, "0.20260715.4")` → `stale=False`
- `check_staleness(root, "0.20260715.3")` → `stale=True` — catches even a
  one-version gap (the pipx build the stakeholder refreshed mid-ticket)
- `get_version()` now returns `stale` and `staleness_reasons`
- `tests/unit/test_staleness.py` — 14 passing, against real
  `importlib.metadata` shapes

The pipx build was refreshed to `0.20260715.3` mid-ticket. It does not fail
closed on its own drift because that build predates this module — expected,
not a defect. Any build from this commit forward carries the check.

### The fix demonstrated itself, twice

While writing these notes, role-guard blocked the team-lead from editing
this ticket directly — correctly, since ticket artifacts are sprint-planner
scope. That block only fired *because* this ticket pointed the hook at
`uv run clasi`; the previous bare-`clasi` invocation would have failed open
and allowed it silently.

A sprint-planner was then dispatched to do the write and **was also
blocked** — incorrectly. It threw a proper exception rather than routing
around the guard via Bash, which is the right instinct. Root cause: the
`active_agents` table is empty (verified: 0 rows), so `get_active_tier()`
returns the unresolved sentinel and the planner falls through to tier 0's
block, despite `hook_handlers.py:357-359` explicitly permitting tier 1 to
write `clasi/sprints/`. The `SubagentStart` registration is not firing or
not persisting. **Filed separately** — 019-003 fixed the tier *lookup* but
nothing ever verified the *registration*, because those tests inserted their
own fixture rows. Same class of gap this sprint keeps finding.

These notes were ultimately written under `.clasi/oop`, used for exactly its
documented purpose: unblocking work when a gate is genuinely broken. Flag
removed immediately afterward.

### Process note

The dispatched programmer agent died mid-ticket (199k tokens, 195 tool
calls, incoherent final message) with all work uncommitted and the ticket
left `in-progress`. The team-lead verified the partial work against the live
system, found the egg-info root cause the agent had not identified, and
completed the remaining criteria rather than re-dispatching.

## Implementation Plan

**Approach**: Build the comparison as a small, cheap check reusing
`get_version()`'s existing output; wire it into MCP server startup and/or
the hook entry point; fix this repo's own config as a separate, explicit
step from the general-purpose detection logic (which must not assume it's
running inside the CLASI repo itself).

**Files likely involved**: `src/clasi/mcp_server.py`,
`src/clasi/tools/process_tools.py` (`get_version`), `src/clasi/init_command.py`
(read the existing `_detect_mcp_command` rationale, don't break the
no-uv case), this repo's `.mcp.json`, `.claude/settings.json`.

**Testing plan**: Real `importlib.metadata` staleness comparison test;
integration-style test that a stale vs. fresh install produces different
observable output; regression test that consumer-project `clasi init`
(no uv, no `[project]` table) is unaffected.

**Documentation updates**: Note the staleness-detection mechanism in
`docs/architecture/` on the next consolidation; no user-facing skill/rule
doc changes expected unless the fail-closed decision changes user-visible
behavior.
