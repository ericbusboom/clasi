---
id: '004'
title: Tighten role guard for tier-0 source writes
status: done
use-cases:
- SUC-003
depends-on: []
github-issue: ''
todo: role-guard-block-team-lead-source-writes.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Tighten role guard for tier-0 source writes

## Description

The reflection `2026-04-03-team-lead-wrote-code-directly.md` documents a case
where the team-lead wrote Python source code directly. The `handle_role_guard()`
function in `hook_handlers.py` is the enforcement point.

Reading the current code: source code files (e.g., `clasi/cli.py`) do not
match any allowed prefix (`docs/clasi/`, `.claude/`, `CLAUDE.md`, `AGENTS.md`)
and fall through to the final block section — which should already block them.
The likely failure mode is tier detection: `CLASI_AGENT_TIER` may not have
been set in the team-lead interactive session at the time of the incident,
causing the DB fallback to return an unexpected result or skip the block.

This ticket:
1. Investigates and confirms the exact failure mode by tracing the logic.
2. Tightens the guard if a logic gap is found.
3. Adds explicit tests covering the blocked and allowed paths so future
   regressions are caught immediately.

## Acceptance Criteria

- [x] `handle_role_guard` with tier-0 (env var unset, no DB) blocks writes to
  `clasi/cli.py` — exits 2
- [x] `handle_role_guard` with tier-0 blocks writes to `pyproject.toml` — exits 2
- [x] `handle_role_guard` with tier-0 allows writes to `docs/clasi/todo/my-todo.md`
  — exits 0
- [x] `handle_role_guard` with tier-0 allows writes to `.claude/settings.json`
  — exits 0
- [x] `handle_role_guard` with tier-0 allows writes to `CLAUDE.md` — exits 0
- [x] `handle_role_guard` with tier-2 allows writes to `clasi/cli.py` — exits 0
- [x] `handle_role_guard` with OOP bypass (`.clasi-oop` present) allows any
  path — exits 0
- [x] All existing tests pass (`uv run pytest`)

## Implementation Plan

### Approach

Trace the code path for a tier-0 write to `clasi/cli.py` with
`CLASI_AGENT_TIER` unset and no DB file to confirm whether a logic gap exists.

Expected trace:
1. `agent_tier = ""` (env unset)
2. DB fallback skipped (no DB file)
3. Tier-2 check: False
4. OOP check: `.clasi-oop` absent → continue
5. Recovery: no DB → continue
6. Safe prefixes: `clasi/cli.py` doesn't match → continue
7. Team-lead check: `agent_tier in ("", "0")` is True; `file_path.startswith("docs/clasi/")` is False → skip (does NOT exit 0 here)
8. Sprint-planner check: False
9. Block: exits 2

If this trace is correct, the guard already works and the incident was caused
by something external (hook not configured, binary not on PATH, etc.). In that
case, the fix is purely additive tests that confirm the guard behavior.

If a gap is found (e.g., step 7 exits 0 for non-docs paths due to a bug in the
condition), fix the condition and document it.

### Files to Modify

**`clasi/hook_handlers.py`** — `handle_role_guard()`:
- After investigation, apply the minimum necessary fix.
- If the logic is already correct, add a comment block explaining the
  allowed/blocked matrix for future readers.
- If a gap is found, tighten the condition with a comment referencing this
  sprint.

### Testing Plan

- **New tests** in `tests/test_hook_handlers.py`:
  - `test_role_guard_blocks_source_file_tier0`: payload `{"file_path": "clasi/cli.py"}`,
    env `CLASI_AGENT_TIER=""`, no DB → assert `SystemExit(2)`.
  - `test_role_guard_blocks_toml_tier0`: payload `{"file_path": "pyproject.toml"}` → `SystemExit(2)`.
  - `test_role_guard_allows_docs_clasi_tier0`: payload `{"file_path": "docs/clasi/todo/x.md"}` → `SystemExit(0)`.
  - `test_role_guard_allows_claude_settings_tier0`: payload `{"file_path": ".claude/settings.json"}` → `SystemExit(0)`.
  - `test_role_guard_allows_claude_md_tier0`: payload `{"file_path": "CLAUDE.md"}` → `SystemExit(0)`.
  - `test_role_guard_allows_tier2_source_file`: env `CLASI_AGENT_TIER="2"`,
    payload `{"file_path": "clasi/cli.py"}` → `SystemExit(0)`.
  - `test_role_guard_oop_bypass`: create `.clasi-oop` temp file → `SystemExit(0)`
    for any path.
- Use `pytest.raises(SystemExit)` and check `.code` for 0 or 2.
- Mock `sys.stdin` to return `{}` (or pass payload directly if the test helper
  supports it).
- **Existing tests**: `uv run pytest` — all must pass.

### Documentation Updates

Add inline comments in `handle_role_guard()` listing the allowed/blocked matrix
for team-lead (tier 0). No external documentation changes.
