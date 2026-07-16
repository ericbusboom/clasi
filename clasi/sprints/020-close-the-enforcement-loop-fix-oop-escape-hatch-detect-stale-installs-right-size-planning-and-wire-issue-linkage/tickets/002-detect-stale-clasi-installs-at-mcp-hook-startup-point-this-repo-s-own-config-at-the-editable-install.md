---
id: '002'
title: Detect stale CLASI installs at MCP/hook startup; point this repo's own config
  at the editable install
status: open
use-cases: [SUC-002]
depends-on: ['001']
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

- [ ] A deliberately stale install (e.g. an older pipx build alongside a
      newer working tree) produces a visible warning naming both versions,
      surfaced through at least one of: status block, MCP `instructions`,
      or startup log.
- [ ] This repo's `.mcp.json` and/or `.claude/settings.json` hook
      invocations are corrected so the MCP server and hooks run this
      repo's working tree, not a stale global install.
- [ ] A fresh `clasi init` in a consumer project with no `uv` and no
      `[project]` table still works unchanged — `init_command._detect_mcp_command`'s
      existing rationale for bare `clasi` as the *default* for consumer
      projects is not broken by this fix.
- [ ] `close_sprint`, run through the corrected invocation path on a tree
      containing the 019-007 writer fix, produces `status: closed`, not
      `status: done`.
- [ ] Decision on fail-closed vs. warn-only for a large version gap is
      made and justified in this ticket's notes (not silently deferred).
- [ ] Regression test: staleness comparison logic is unit-tested against
      real `importlib.metadata`/`source_path` shapes, not synthetic stand-ins.

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
