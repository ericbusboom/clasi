---
status: pending
type: bug
tags:
- reliability-campaign
- phase-1
- state-db
- enforcement
sprint: 029
---

# State DB: reads stop creating databases; short busy timeout

## Description

Every StateDB method calls `init()` first, which runs the full
`executescript(_SCHEMA)` — a write transaction — even for pure reads, and
connections use the default 5-second busy timeout. Two failure modes, from
the reliability review (00-review.md C2 second half; 01-state-layer.md
finding 5; 03-hooks-guards.md F4):

1. A hook fired with the wrong cwd auto-creates a phantom, empty
   `.clasi/.clasi.db` at that path — OOP off, lock invisible, tier unset —
   so guards silently resolve against a database that answers everything
   with defaults. Stray DB files then seed future confusion.
2. Under parallel agents, the per-read write transactions contend; the 5s
   busy wait can consume role-guard's entire 5s harness timeout, which
   kills the hook, which is an allow.

## Acceptance criteria

- Read methods return "absent"/defaults when the DB file does not exist,
  without creating it; schema creation happens only in `clasi init` and
  write paths.
- `sqlite3.connect` uses `timeout=1` (or similar short value) on hook paths.
- `init()` runs at most once per StateDB instance.
- A test asserts that a read against a nonexistent path creates no file.
