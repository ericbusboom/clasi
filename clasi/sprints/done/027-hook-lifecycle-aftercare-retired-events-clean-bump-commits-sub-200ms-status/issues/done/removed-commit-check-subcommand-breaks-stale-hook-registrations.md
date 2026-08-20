---
status: done
sprint: '027'
tickets:
- 027-001
---

# Removed `clasi hook commit-check` subcommand errors on every Bash call in sessions with stale hook registrations

## Description

Field report (2026-08-20, post sprint 026): an agent reports that a
PostToolUse hook is running `clasi hook commit-check`, which is no
longer a valid subcommand — and because the hook fires on the
`Bash` matcher, every Bash call in that session errors out.

Sprint 026 ticket 004 removed the dead commit-check hook end to end:
the registration in `plugin/hooks/hooks.json`, this repo's
`.claude/settings.json`, AND the `handle_commit_check` handler plus its
routing-table and `click.Choice` CLI entries. That last part is the
regression surface: any environment still carrying the old registration
now invokes a subcommand the CLI rejects (click usage error, non-zero
exit) on every Bash call. Affected environments:

- Claude Code sessions started before the settings change (hook config
  is snapshotted at session start), running against the upgraded clasi.
- Consumer projects whose `.claude/settings.json` was installed by a
  pre-026 `clasi init` and not re-run after upgrading clasi — every
  such project breaks on upgrade until re-init.
- Same story will apply to the removed `TaskCreated`/`TaskCompleted`
  registrations wherever they were installed.

The removal was correct (the handler had provably never worked — 0 of
2,447 logged events); the missing piece is graceful degradation for
stale registrations that outlive the code.

## Cause

`clasi hook <event>` treats an unknown event name as a hard CLI error
(`click.Choice` rejection; the dispatcher also reserves exit 1 for
unknown events). Hook registrations live in per-project settings files
and in already-running sessions, so they upgrade on a different
schedule than the CLI — a removed event name must therefore be
tolerated, not rejected.

## Proposed fix

1. Make `clasi hook` exit 0 (silent no-op, optionally a single
   deprecation line to stderr and a `retired-event` entry in hooks.log)
   for RETIRED event names (`commit-check`, `task-created`,
   `task-completed` and their alias forms) instead of erroring. Keep
   the hard error for genuinely unknown names so typos in fresh
   registrations still surface — a small retired-names allowlist, not a
   blanket catch-all.
2. Consider having `get_version()`/staleness or `clasi init --check`
   detect stale hook registrations in `.claude/settings.json` (events
   the installed CLI no longer serves) and tell the user to re-run
   `clasi init`, so the no-op path is a bridge, not a permanent silent
   state.
3. Regression test: invoke the CLI with each retired event name and a
   real payload on stdin → exit 0, no stderr noise beyond the
   deprecation line; unknown junk name → non-zero as today.

## Verification

- A session/fixture with the pre-026 `.claude/settings.json` (including
  the commit-check PostToolUse/Bash registration) runs Bash calls
  cleanly against post-fix clasi: hook exits 0, no error surfaced.
- Typo'd event name still errors.
- After `clasi init` refresh, the retired registrations are gone and
  the no-op path stops being exercised.

## Related

- Sprint 026 ticket 004 (the removal;
  clasi/sprints/done/026-hook-performance-and-guard-reliability/tickets/done/004-*.md).
- hook-overhead-status-inject-dead-hooks-and-logging.md (sprint 026,
  done) — the parent investigation that removed the dead hooks.
