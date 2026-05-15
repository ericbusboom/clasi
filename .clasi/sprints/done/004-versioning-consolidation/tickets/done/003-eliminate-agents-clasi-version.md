---
id: 004-003
title: "Eliminate .agents/.clasi-version \u2014 verify no write path remains, update\
  \ docs"
status: done
use-cases:
- SUC-003
depends-on:
- 004-001
issue:
- consolidate-clasi-version-storage.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# 004-003: Eliminate .agents/.clasi-version — verify no write path remains, update docs

## Description

`.agents/.clasi-version` is a legacy stamp file from an older installer design.
`_markers.py` already removes it opportunistically on install runs (lines 63-68).
The installer now writes `.clasi/clasi-version` instead. However, the stale-cleanup
comment on line 54-55 still names `.agents/.clasi-version` as a target — that
is correct behavior and must stay. What this ticket ensures is:

1. No production code path **writes** `.agents/.clasi-version`.
2. The stale-cleanup in `_markers.py` is verified to still cover `.agents/`.
3. Any documentation or prose that tells users to look at `.agents/.clasi-version`
   is corrected to point at `.clasi/clasi-version` or removed.

This ticket can run in parallel with ticket 002 (both depend on 001 only).

## Acceptance Criteria

- [x] `grep -rn "\.agents/\.clasi-version"` finds only the stale-cleanup removal code
      in `_markers.py` (lines 63-68) and test fixtures — no write path.
- [x] `_markers.py` stale-cleanup list (`_stale_dirs`) still includes `".agents"`.
- [x] Any prose in `docs/`, `README.md`, or agent instruction `.md` files that
      references `.agents/.clasi-version` is corrected or removed.
- [x] Full test suite passes (`pytest`).

## Implementation Plan

### Approach

This is primarily an audit-and-cleanup ticket, not a logic change.

**Step 1: Audit write paths**

Run:
```
grep -rn "\.agents/\.clasi-version\|agents.*clasi.version\|clasi-version" clasi/ tests/ docs/ README.md
```

Confirm:
- `_markers.py` lines 63-68: removal only (correct — keep).
- `_markers.py` line 54-55: docstring reference (correct — keep, it describes the cleanup behavior).
- No other location writes to `.agents/.clasi-version`.

**Step 2: Verify stale-cleanup coverage**

Read `_markers.py` lines 62-68. Confirm `".agents"` is in `_stale_dirs`. No code
change needed if it is already there.

**Step 3: Scan and fix docs**

Search for `.agents/.clasi-version` or `.agents/\.clasi-version` in:
- `docs/` tree
- `README.md`
- `clasi/plugin/` agent and skill instruction files

If any prose tells users to check `.agents/.clasi-version` for the installed
version, update to reference `.clasi/clasi-version` instead.

**Step 4: Delete any actual `.agents/.clasi-version` in this repo**

Check if `/Users/eric/proj/ai-project/clasi/.agents/.clasi-version` exists.
If so, delete it (it is a stale artifact from an old install run).

### Files That May Need Changes

- `docs/` — any file referencing `.agents/.clasi-version` (audit first)
- `README.md` — if it references `.agents/.clasi-version`
- No production Python files expected to change

### Testing Plan

1. `grep -rn "agents.*clasi-version" .` — confirm only stale-cleanup code appears.
2. `pytest` — full suite, no new failures.

### Documentation Updates

Correct any prose that references `.agents/.clasi-version` to `.clasi/clasi-version`.
