---
status: done
type: bug
tags:
- e2e
- regression
---

# E2E entrypoint refuses to init because start.sh's own scaffolding makes /project non-empty

## Description

Found running the end-to-end validation after sprint 033 closed
(2026-08-21). The container starts, then immediately exits:

```
ERROR: /project is non-empty and E2E_RESUME is not set.
  Refusing to run 'clasi init' over existing state.
```

`start.sh` genuinely did wipe the project directory — its own log line
confirms it. But between the wipe and the container's emptiness check, it
creates its own scaffolding there:

```
tests/e2e/e2e-project/
  .e2e-coverage/     # created by the coverage harness (ticket 032-007)
  .gitignore         # written when the run dir is minted (ticket 032-002)
```

`entrypoint.sh`'s guard sees two entries, concludes a prior run's state is
present, and refuses.

## Cause

The emptiness check treats ANY content as "existing project state." That
was true when the only things in `/project` were what `clasi init` and the
subject agent produced. It stopped being true once the harness began
placing its own files there — `.gitignore` in sprint 032 ticket 002, and
`.e2e-coverage/` in ticket 032-007.

Neither ticket was wrong in isolation. The guard's assumption silently
expired underneath them, which is why nothing caught it until a real
full run: ticket 032-007's programmer verified the harness mechanically
with short container invocations and stated plainly that end-to-end
behavior awaited a genuine run.

## Fix

`entrypoint.sh`'s emptiness check must ignore harness-managed entries and
consider only genuine project state. The harness-owned set is currently
`.e2e-coverage/`, `.e2e-runs/`, and `.gitignore`.

Prefer an explicit allowlist over "ignore all dotfiles" — the subject
project legitimately creates `.clasi/`, `.claude/`, `.agents/`, and
`.git/`, and those absolutely SHOULD trip the guard on a non-resume run.
The guard's value is refusing to `clasi init` over a real prior run; that
must survive the fix.

## Acceptance criteria

- [x] A fresh `./start.sh` succeeds with `.e2e-coverage/` and
      `.gitignore` present after the wipe.
- [x] The guard still refuses when genuine project state is present — a
      `/project` containing `.clasi/` or `guessing_game/` on a non-resume
      run must still abort.
- [x] The harness-owned entry list lives in one place, so adding a future
      harness file does not silently re-break this.
- [x] `--resume` behavior is unchanged.

## Resolution

Fixed in `tests/e2e/entrypoint.sh` (commit `fix(e2e): stop entrypoint.sh
guard tripping on the harness's own scaffolding`). Added a
`HARNESS_OWNED_ENTRIES` allowlist (`.e2e-coverage`, `.e2e-runs`,
`.gitignore`) declared once near the top of the script; the emptiness
check builds `find ... ! -name ...` exclusions from that array instead
of hardcoding names inline. Verified mechanically (not a full E2E run)
by running the real, edited `entrypoint.sh` inside a container with
`clasi`/`git`/`tmux` stubbed out, against four `/project` scenarios:
empty (matches the live repro — entrypoint.sh's own
`.e2e-coverage/`+`.gitignore` creation no longer trips the guard), the
full harness-owned set pre-populated, genuine `.clasi/` present
(refused, exit 1), genuine `guessing_game/` present (refused, exit 1),
and `--resume` with genuine state plus `E2E_RESUME=1` (skips the check
entirely, unchanged). `shellcheck tests/e2e/entrypoint.sh` is clean.
