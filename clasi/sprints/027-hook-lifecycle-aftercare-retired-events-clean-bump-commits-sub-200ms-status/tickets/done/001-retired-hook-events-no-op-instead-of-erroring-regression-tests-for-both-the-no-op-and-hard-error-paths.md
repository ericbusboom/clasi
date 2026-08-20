---
id: '001'
title: Retired hook events no-op instead of erroring; regression tests for both the
  no-op and hard-error paths
status: done
use-cases:
- SUC-001
depends-on: []
github-issue: ''
issue: removed-commit-check-subcommand-breaks-stale-hook-registrations.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Retired hook events no-op instead of erroring; regression tests for both the no-op and hard-error paths

## Description

Sprint 026 (ticket 004) removed the `commit-check`, `TaskCreated`, and
`TaskCompleted` hook registrations end to end: the entries in
`plugin/hooks/hooks.json`, and the `handle_commit_check` /
`handle_task_created` / `handle_task_completed` handler functions plus
their `_ROUTING_TABLE` and CLI `click.Choice` entries. That removal was
correct — `commit-check` alone taxed every `Bash` call about 90ms for a
handler that had never fired in 2,447 logged hook events. But hook
registrations are snapshotted at session start (or baked into a
consumer project's `.claude/settings.json` by a pre-026 `clasi init`
that hasn't been re-run) and upgrade on a different schedule than the
CLI. A field report the day after 026 closed confirms the regression:
an agent's PostToolUse hook still names `clasi hook commit-check`, and
because it fires on the `Bash` matcher, every `Bash` call in that
session now errors — `clasi hook` treats any name outside its routing
table as a hard `exit 1` (and, one layer up, `cli.py`'s `click.Choice`
argument rejects the name before `handle_hook` even runs).

This ticket makes retired event names degrade gracefully — no-op with
exit 0 instead of erroring — while keeping the hard error for any name
that is genuinely unrecognized, so a typo in a brand-new hook
registration still surfaces loudly. See this sprint's `sprint.md`
(Architecture, Design Rationale) for why a small named allowlist was
chosen over a blanket "tolerate any unknown name" catch-all.

**Key source locations verified during sprint planning** (read
directly against current source — start here, don't re-derive):

- `src/clasi/cli.py`, lines 456-472: the `hook` command's `event`
  argument is declared `click.Choice([...])` listing only the nine
  currently-live event names (`role-guard`, `subagent-start`,
  `subagent-stop`, `mcp-guard`, `plan-to-issue`, `plan-to-todo`,
  `codex-plan-to-issue`, `codex-plan-to-todo`, `status-inject`). A
  retired name (e.g. `commit-check`) is rejected by click itself as a
  usage error **before** `handle_hook` (imported lazily inside the
  command body at line 496) ever runs. This argument has to widen to
  admit retired names — either by adding them to the `Choice` list, or
  by moving the argument off `click.Choice` onto a plain validated
  string — or the fix below can never be reached.
- `src/clasi/hook_handlers.py`, lines 1777-1802: `handle_hook(event)`,
  the dispatcher. Its `_ROUTING_TABLE` dict (lines 1785-1795) maps live
  event names to handler functions; `handler = _ROUTING_TABLE.get(event)`
  followed by `if handler is None: ... sys.exit(1)` (lines 1797-1800) is
  where the current hard error happens for anything not in the table.
  This is where the retired-event allowlist check belongs — checked
  after the live-table lookup misses, before falling through to the
  `exit(1)` path.
- `hooks.log` writing: see `_log_hook_event` in the same module (fixed
  in sprint 026 ticket 004 to read `file_path` from
  `payload["tool_input"]` with a dated timestamp) for the existing
  logging convention to extend with a `retired-event` entry.

## Acceptance Criteria

Per the issue's own Verification section:

- [x] `clasi hook` exits 0 for each retired event name — `commit-check`,
      `task-created`, `task-completed` — and their documented alias
      forms (`TaskCreated`/`TaskCompleted` were the removed
      registrations' actual event names; confirm the exact casing/form
      `hooks.json` used pre-026 via git history if needed), given a
      real captured payload on stdin (not a synthetic empty payload).
- [x] Each no-op prints exactly one deprecation line to stderr — no
      other stderr noise.
- [x] Each no-op writes a `retired-event`-tagged entry to `hooks.log`,
      distinguishable from normal dispatch lines (dated timestamp, per
      026's existing format).
- [x] A genuinely unknown/typo'd event name (not in the live routing
      table and not in the retired-event allowlist) still exits
      non-zero, unchanged from current behavior.
- [x] A session/fixture carrying a pre-026 `.claude/settings.json`
      (including the `commit-check` PostToolUse/Bash registration) runs
      `Bash` calls cleanly against the post-fix `clasi`: the hook exits
      0, no error surfaced to the calling tool.
- [x] `cli.py`'s `hook` command argument no longer rejects a retired
      name at the click-parsing layer — verify with a direct CLI
      invocation (`clasi hook commit-check < payload`), not just a unit
      test against `handle_hook` in isolation.
- [x] After a `clasi init` refresh in a fixture project, the retired
      registrations are absent from the freshly-installed
      `.claude/settings.json`, confirming the no-op path is a bridge
      state, not a permanent one (existing `clasi init` behavior from
      026 ticket 004 — this criterion is a regression check, not new
      work).
- [x] (If implemented — see sprint.md Open Questions for whether this
      fits this ticket's budget) A stale-hook-registration detection
      nudge in `clasi init --check` or the existing staleness check
      recommends re-running `clasi init` when installed
      `.claude/settings.json` still names retired events. If deferred,
      note that explicitly in this ticket's Implementation Notes rather
      than silently dropping it. **Deferred — see Implementation Notes
      below.**

## Testing

- **Existing tests to run**: `tests/unit/test_hook_handlers.py` (the
  dispatcher and routing-table tests), any CLI-level test module
  covering `clasi hook` (`tests/unit/test_cli.py` or similar — confirm
  exact path via the codebase before editing). Run these scoped test
  modules only, foreground, per the programmer agent's test discipline
  — do not run the full suite or background a test run during this
  ticket.
- **New tests to write**:
  - CLI-level invocation test per retired event name, with a real
    captured payload on stdin, asserting exit code 0, a single
    deprecation line on stderr, and no other stderr output.
  - A test for a genuinely unknown event name asserting exit code
    non-zero, unchanged output shape from before this ticket.
  - A `hooks.log` assertion test confirming the `retired-event` entry
    format for at least one retired name.
  - A regression test that `cli.py`'s `hook` command accepts a retired
    name as a valid argument (no click usage-error exit) — this is the
    layer most likely to be missed if only `handle_hook` is tested in
    isolation.
- **Verification command**: run the specific new/modified test modules
  directly (e.g. `uv run pytest tests/unit/test_hook_handlers.py -k
  retired`), not the full suite.

## Implementation Notes

**Exact retired names confirmed via git history**: `git show
046db36^:src/clasi/plugin/hooks/hooks.json` (the last commit before
026/004 removed them) shows the actual `clasi hook <event>` CLI
argument values used pre-026 were `commit-check`, `task-created`, and
`task-completed` — all lowercase-hyphenated. `TaskCreated`/
`TaskCompleted` are the *Claude Code hook event type* names (the JSON
keys under `"hooks"`, alongside `PreToolUse`/`PostToolUse`/etc.), not
CLI-argument alias forms — the CLI argument dispatched from both was
always the lowercase-hyphen form. So there are exactly three retired
CLI event names, no additional alias forms at the CLI layer:
`_RETIRED_EVENTS = frozenset({"commit-check", "task-created",
"task-completed"})` in `hook_handlers.py`.

**Approach**: `cli.py`'s `hook` command's `click.Choice` list gained
the three retired names (kept as a `click.Choice`, not moved to a plain
string — this means click itself still hard-rejects any name outside
the combined live+retired list, so a genuinely new typo keeps failing
loudly at the earliest possible layer). `hook_handlers.handle_hook`
gained the `_RETIRED_EVENTS` allowlist check between the routing-table
miss and the existing `sys.exit(1)` fallback: a retired name prints one
deprecation line to stderr (naming the event and recommending `clasi
init`) and calls the existing `_exit_hook(event, payload, 0,
"retired-evt")` helper — reusing 026/004's own `_log_hook_event` "exit
+ log" pattern rather than adding a parallel logging path. The
`hooks.log` reason-code column carries `retired-evt` (11 chars, fits
this module's existing 12-char reason-code convention — e.g.
`tier-allowed`, `oop-bypass` — without truncation), and the event_type
column carries the actual retired event name (e.g. `commit-check`).
Together those two columns make a retired-event line distinguishable
from any live dispatch line by grep alone, since no live event now
shares either value.

**Stale-hook-registration detection nudge — deferred, not implemented**
(sprint.md Open Questions explicitly frames this as ticket-time-decided
and offers "split into its own follow-up issue" as a valid outcome).
Decision: defer to a follow-up issue rather than fold into this ticket.
Reasoning: the no-op allowlist above is the load-bearing fix (it's what
stops sessions/installs from erroring today) and is already a
substantial, well-scoped change on its own; a staleness-check or `clasi
init --check` extension is additive UX on top of an already-safe
no-op, not a correctness requirement, and doing it well (deciding
whether it lives in `staleness.py`'s `check_staleness()`, which already
runs on effectively every hook call per this repo's own git-commits
rule doc, or a new `clasi init --check` subcommand that doesn't exist
yet) is a separate design decision worth its own ticket rather than a
rushed addition here. No code changes were made toward it in this
ticket; `clasi init --check` does not exist as of this ticket.
