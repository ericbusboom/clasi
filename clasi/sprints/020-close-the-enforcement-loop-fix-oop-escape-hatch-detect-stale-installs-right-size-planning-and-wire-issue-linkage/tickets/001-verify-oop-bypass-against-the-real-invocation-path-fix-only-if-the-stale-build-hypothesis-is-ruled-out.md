---
id: '001'
title: Verify OOP bypass against the real invocation path; fix only if the stale-build
  hypothesis is ruled out
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: oop-bypass-broken-role-guard-blocks-team-lead.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Verify OOP bypass against the real invocation path; fix only if the stale-build hypothesis is ruled out

## Description

E2E run 003 reported that `.clasi/oop` does not bypass `role-guard` for
team-lead writes. Planning-time investigation of the working tree found
`_oop_active()` (`src/clasi/hook_handlers.py:43`) already correct — checks
`.clasi/oop` then legacy `.clasi-oop`, introduced in `019-002`
(`9c5cbab`). Separately, this repo's bare `clasi` resolves to pipx build
`0.20260627.14` (measured via `clasi --version`), 18+ days stale and
predating `_oop_active()` entirely, while `uv run clasi` resolves to
`0.20260715.3` (measured via `uv run clasi --version`). Every hook in
`.claude/settings.json` invokes bare `clasi hook ...`.

**Do the verification before writing any hook_handlers.py fix.** The
working hypothesis is that issue 1 is a symptom of issue 5 (stale
install), not an independent logic bug. This ticket must prove or disprove
that before touching `_oop_active()` or `handle_role_guard`.

Do not assume ticket 002 (stale-install detection) has landed yet when
this ticket runs — it hasn't (dependency order below). Verify against
whatever the actual current bare-`clasi` resolution is at the time this
ticket executes; if 002 has already fixed the resolution, verify against
the corrected path instead and note that in the ticket's completion notes.

## Acceptance Criteria

- [x] A real, captured PreToolUse `role-guard` payload (not a hand-built
      fixture) — for a Write/Edit call with `.clasi/oop` present, no
      in-progress ticket — is exercised against the actual invocation path
      configured in `.claude/settings.json` (bare `clasi hook role-guard`,
      or `uv run clasi hook role-guard` if bare `clasi` is confirmed stale
      and ticket 002 hasn't landed yet) and is allowed.
- [x] The investigation's finding (stale-build symptom vs. genuine
      hook_handlers.py bug) is recorded in this ticket's notes with the
      versions/commands used to establish it.
- [x] If the finding confirms genuine broken logic in `_oop_active()` or
      its call sites (not just staleness), fix it and add a regression
      test. (N/A — finding was staleness-only; see notes.)
- [x] If the finding confirms staleness is the sole cause, no
      `hook_handlers.py` code change is made in this ticket — the fix
      belongs to ticket 002. This ticket still adds a regression test
      proving OOP bypass works when the correct build is invoked.
- [x] Revert-check: whatever test is added must fail when the underlying
      fix (or, in the staleness case, when pointed back at a stale build)
      is reverted/simulated — not just pass because it was already
      lenient.
- [x] No hand-built payload fixtures that bypass real hook parsing; use a
      real captured JSON payload shape as documented in
      `tests/unit/test_hook_handlers.py`'s existing `_role_guard_payload()`
      fixture pattern from sprint 019.

## Implementation Plan

**Approach**: Investigate first, fix only what the investigation shows is
actually broken.

1. Reproduce: create `.clasi/oop`, invoke the configured hook command
   (check `.claude/settings.json` for the exact invocation) with a real
   captured role-guard payload, observe allow/block.
2. Compare `clasi --version` / `which clasi` against `uv run clasi
   --version` to establish whether the invocation is hitting a stale
   build.
3. If stale: document the finding, write the regression test against the
   correct build (`uv run clasi` or a fixed bare `clasi` if ticket 002's
   scope somehow lands first), do not modify `hook_handlers.py` logic.
4. If not stale (i.e., a real bug remains even on the current build):
   diagnose and fix the actual defect in `_oop_active()` or its callers,
   with a revert-check test.

**Files likely involved**: `src/clasi/hook_handlers.py` (read/verify,
maybe fix), `tests/unit/test_hook_handlers.py` (new test).

**Testing plan**: Real payload fixture, real invocation path, revert-check
required per house standard.

**Documentation updates**: None required unless a genuine bug is found and
fixed, in which case update `oop.md` / relevant rule docs if the fix
changes documented behavior (it should not, since the doc-promised
behavior is what's being restored).

## Completion Notes

**Verdict: staleness confirmed as the sole cause. No `hook_handlers.py`
logic change was made.**

### Versions established

```
$ which clasi
/Users/eric/.local/bin/clasi   (symlink -> pipx venv, confirmed via `which -a` and `ls -la`)

$ clasi --version
clasi, version 0.20260627.14

$ uv run clasi --version
clasi, version 0.20260715.3

$ .venv/bin/clasi --version   (editable install, equivalent resolution to `uv run clasi`)
clasi, version 0.20260715.3
```

The pipx venv's *internal* module further reports a third, different
value:

```
$ /Volumes/Cache/User-Eric/.local/pipx/venvs/clasi/bin/python -c \
    "import clasi; print(clasi.__version__)"
0.20260627.12
```

So there are three different version strings in play for what a
stakeholder would call "clasi": `0.20260627.14` (pipx `--version`
resolution), `0.20260627.12` (that same install's internal
`clasi.__version__`), and `0.20260715.3` (current editable tree). This
three-way mismatch is itself worth flagging — whatever process stamped
`clasi_version: 0.20260715.2` on the E2E-003 issue was not the build that
executed the hooks; ticket 002 (stale-install detection) is the right
place to close that gap, not this ticket.

### Reproduction against the real invocation path

`.claude/settings.json` configures `PreToolUse` for `Edit|Write|MultiEdit`
as bare `clasi hook role-guard` (confirmed by reading the file directly).
Reproduced with a real nested payload
(`{"tool_name": "Write", "tool_input": {"file_path": "src/clasi/hook_handlers.py"}, "session_id": "..."}`)
piped over stdin, `cwd` = repo root, both with and without `.clasi/oop`
present:

| Build            | `.clasi/oop` absent | `.clasi/oop` present |
|------------------|----------------------|-----------------------|
| bare `clasi` (stale pipx, `0.20260627.14`) | exit **0** (should be 2 — fails OPEN) | exit 0 |
| `uv run clasi` (current, `0.20260715.3`)   | exit **2** (correctly blocks)         | exit **0** (correctly bypasses) |

`uv run clasi` behaves exactly per spec: blocks by default, bypasses with
the flag present. AC #1 is satisfied against this corrected invocation
path, per the ticket's own fallback instruction (ticket 002, stale-install
resolution, had not landed at the time this ticket ran).

### Root cause of the stale build's behavior (not fixed here — informational)

Dumped `handle_role_guard` source directly from the pipx venv
(`inspect.getsource`). It predates **both** `019-001` (nested payload
parsing) and `019-002` (unified `_oop_active()`):

- It reads `tool_input = payload if payload else {}` — the pre-019-001
  flat-shape bug. Given the real nested payload, `file_path` resolves to
  `""` regardless of `.clasi/oop`.
- Its no-path branch is `_exit_hook("role-guard", payload, 0, "no-path")`
  — allow, the pre-019-001 fail-OPEN default (current tree fails closed
  for tier 0/1, exit 2).
- It checks `Path(".clasi-oop").exists()` only — no `.clasi/oop` support
  at all, confirming `_oop_active()` (introduced in `019-002`,
  `9c5cbab`) does not exist in this build:
  `"def _oop_active" in inspect.getsource(clasi.hook_handlers)` → `False`.

Net effect: the stale build doesn't fail to bypass OOP — it fails open
unconditionally (allows every tier-0/1 write with no path resolved),
independent of whether `.clasi/oop` exists. E2E run 003's report ("OOP
does not bypass, writes were blocked") doesn't fully match this
fail-open behavior either, which reinforces that the E2E run's reported
build identity is unreliable (see version discrepancy above) — but the
current working tree's `_oop_active()` and `handle_role_guard` are
verified correct by both the pre-existing sprint-019 unit suite and the
new subprocess-level test added here. No `hook_handlers.py` change was
needed or made.

### Test added

`tests/unit/test_hook_handlers.py`, new class
`TestRoleGuardRealCliInvocationPath` (after `TestOopBypassHandlerLevel`):

- `test_current_build_blocks_without_oop_flag` — control: real nested
  payload, real `clasi hook role-guard` CLI subprocess (`.venv/bin/clasi`,
  equivalent resolution to `uv run clasi`), no `.clasi/oop` → exit 2.
- `test_current_build_bypasses_with_oop_flag` — AC #1: same, with
  `.clasi/oop` present → exit 0.
- `test_revert_check_stale_build_fails_open_regardless_of_oop_flag` —
  revert-check: same payload/harness pointed at the actual stale pipx
  binary (`/Volumes/Cache/User-Eric/.local/pipx/venvs/clasi/bin/clasi`),
  skipped if that path doesn't exist on the running machine. Asserts
  `returncode == 0` even with **no** OOP flag present — i.e. it pins down
  that the stale build fails open unconditionally, which is what makes it
  distinguishable from "correctly enforcing."

All three invoke the actual installed CLI entrypoint via `subprocess.run`
(not `handle_role_guard()` called in-process), piping a real nested
payload built from the existing `_role_guard_payload()` fixture — no
hand-built flat-shape payloads.

**Revert-check result**: confirmed manually and via the added test. Ran
`test_current_build_blocks_without_oop_flag`'s exact scenario (no OOP
flag, real nested payload) against the stale pipx binary instead of the
current build: exit code `0` instead of the expected `2` — i.e. pointing
the "correct build" control test at the stale build makes it fail, which
is the required revert-check property. `uv run pytest
tests/unit/test_hook_handlers.py -k TestRoleGuardRealCliInvocationPath`:
3 passed. Full `tests/unit/test_hook_handlers.py`: 155 passed, no
regressions.

### Flag-file cleanup

`.clasi/oop` (created for manual reproduction) and `.clasi-oop` were both
removed from the repo root at the end of the investigation. Verified
absent via `ls` before finishing (both report "No such file or
directory").
