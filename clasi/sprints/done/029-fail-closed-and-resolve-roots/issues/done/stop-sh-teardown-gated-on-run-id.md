---
status: done
type: bug
tags:
- reliability-campaign
- phase-1
- e2e
- cleanup
sprint: 029
tickets:
- 029-002
---

# stop.sh performs no teardown when it cannot resolve a run id — leaves the container and staged credentials behind

## Description

Found during the sprint-028 baseline E2E shakedown on 2026-08-20,
immediately after the mcp-2.0 crash
(`mcp-2-breaks-every-fresh-install.md`).

`start.sh` failed early — the container started but Claude Code never
came up, so the script aborted at the readiness wait, *before* it minted
the run directory. `.e2e-runs/current` therefore never existed. Running
`./tests/e2e/stop.sh` then produced:

```
ERROR: could not resolve a run id — no --run-id/positional given and
  .../tests/e2e/e2e-project/.e2e-runs/current does not exist or is empty.
  Pass --run-id <id> explicitly, or fix .e2e-runs/current, then retry.
```

and exited **without doing any teardown at all**. Left behind:

- the exited `clasi-e2e` container, and
- `tests/e2e/.creds-stage/.credentials.json` — a real copy of the host's
  Claude Code OAuth credentials, staged by `start.sh` and documented as
  "removed by ./stop.sh".

Both had to be cleaned up by hand.

## Cause

The Run-ID Handoff Contract (added by ticket 028-002) makes run-id
resolution a hard precondition for the whole script. But the run id is
only needed for the *capture* half of stop.sh (saving `docker logs` and
the subject's session directory into the run dir). The *teardown* half —
removing the container and deleting the staged credentials — has no
dependence on it.

Fail-loud-on-unresolvable-run-id is right for `run.sh`, `validate.sh`,
and `report.sh`, which have nothing to do without a run. It is wrong for
`stop.sh`, whose most important job is cleanup, and which is precisely
the script you reach for *after* something went wrong early.

Note the failure mode this creates: the worse the failure, the earlier
it happens, the less likely a run id exists — so cleanup is least
available exactly when it is most needed.

## Acceptance criteria

- [ ] `stop.sh` always performs teardown (container removal and
      `.creds-stage` deletion) regardless of whether a run id resolves.
- [ ] When no run id resolves, stop.sh skips only the capture step,
      reporting clearly that artifacts could not be saved and why — it
      does not abort.
- [ ] Credential staging is removed even when the container never
      started, and even when `docker` itself errors; a `trap`-based
      cleanup or an unconditional final step, not a happy-path line.
- [ ] Exercised by a test (or a documented manual check) that runs
      stop.sh with no `.e2e-runs/current` present and asserts the
      container and `.creds-stage` are gone afterward.
- [ ] Consider the same audit for `start.sh`'s own failure paths: its
      `cleanup()` trap currently removes `$ENV_FILE` but not
      `.creds-stage`, which is why the staged credentials survived the
      aborted run in the first place.
