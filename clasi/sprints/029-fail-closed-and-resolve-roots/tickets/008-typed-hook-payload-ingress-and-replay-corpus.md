---
id: 008
title: Typed hook payload ingress and replay corpus
status: open
use-cases: [SUC-008]
depends-on: []
github-issue: ''
issue: hook-payload-typed-ingress-and-replay-corpus.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Typed hook payload ingress and replay corpus

## Description

Six handlers each hand-roll their own payload extraction
(`handle_role_guard:570-576`, `_log_hook_event:341-356`,
`handle_mcp_guard:960-980`, `handle_subagent_start:1333-1335`,
`handle_subagent_stop:1401-1404`, `handle_plan_to_issue:1725`); the
file-path rule has drifted once already (the 876-event fail-open
incident). This ticket introduces one typed `HookPayload` dataclass
built once in `handle_hook`, consumed by every handler, and a
replay-test corpus of real captured payloads from sprint 028's
`.clasi/log/denied/` capture (plus a small set of temporarily-teed
allow-path fixtures) so a future harness-side shape change is caught by
a failing test instead of drifting silently a second time.

**Dogfooding note (read before starting)**: this is the highest-risk
ticket in the sprint — it touches the payload-parsing entry point of
every guard handler. Work in small, independently-testable steps (e.g.
land the `HookPayload` dataclass and `from_stdin` first with full test
coverage before migrating handlers one at a time), and run
`uv run pytest tests/unit/test_hook_handlers.py` after each step, not
just at the end. `.clasi/oop` (`clasi oop on --reason '...'`) remains
available as an escape hatch. This ticket is deliberately sequenced
right before ticket 009 (the fail-closed boundary) specifically so any
regression it introduces is still caught by this sprint's own test
suite and replay corpus while the module's crash path is still sprint
028's catch/log/re-raise-unchanged, not a hard block — **do not skip
the replay-corpus acceptance criteria to save time; they are what makes
ticket 009 safe to land after this one.**

**Scope**: `src/clasi/hook_handlers.py`, new
`tests/fixtures/hook_payloads/*.json`.

**Files to touch (verified during planning):**

- `hook_handlers.py` — new frozen `HookPayload` dataclass with
  `from_stdin(raw: str) -> HookPayload` (or `from_dict`, whichever
  composes better with the existing `read_payload()` at line 62),
  fields: `tool_name`, `tool_input`, `file_path` (the single
  nested-then-flat resolution — matching the pattern already correct
  at the existing per-handler resolution, e.g. `handle_role_guard`'s
  current `tool_input.get("file_path") or tool_input.get("path") or
  tool_input.get("new_path") or ""`), `caller_id` (+
  `caller_id_source`), `agent_type`, `transcript_path`,
  `plan_file_path`, and `missing: list[str]` — expected-but-absent
  fields, appended to the `hooks.log` line by `_exit_hook` (which
  already accepts a `decisions` list per sprint 028's ticket 005;
  extend or reuse that same mechanism rather than adding a second
  parallel logging channel).
- `handle_hook` (`hook_handlers.py:1880+`) — builds one `HookPayload`
  from the raw stdin read once, before dispatching to any handler.
- All six handlers named above — read from the shared `HookPayload`
  instead of hand-rolling their own extraction from the raw `payload:
  dict`. Preserve every existing decision exactly — this ticket changes
  *how* each handler reads its input, not what it decides.
- New `tests/fixtures/hook_payloads/*.json` — verbatim payloads
  captured from real events: at least two deny-path fixtures (from
  sprint 028's `.clasi/log/denied/*.json` capture — if that corpus is
  still thin because the E2E hasn't run much since sprint 028 landed,
  generate a small set via a temporary local capture during this ticket
  rather than blocking on it, and note that explicitly in the ticket's
  test notes) and at least one allow-path fixture per hook event type
  (captured via a temporary tee, per the issue's own suggested
  approach).
- New parametrized replay test module — reads each fixture, runs it
  through `read_payload` → the relevant handler, asserts the expected
  decision.

## Acceptance Criteria

- [ ] All six handlers consume `HookPayload`; no handler touches the
      raw dict directly
- [ ] The replay test covers every hook event type with at least one
      captured fixture, including at least two deny-path fixtures
- [ ] Deny-path assertions use real captured payloads (from sprint
      028's corpus, or a documented temporary capture if the corpus is
      still thin), not hand-written ones
- [ ] `HookPayload.missing` is populated correctly for at least one
      fixture with an absent expected field, and appears in the
      resulting `hooks.log` line
- [ ] No existing guard's allow/deny outcome changes for any payload
      already covered by `tests/unit/test_hook_handlers.py` — run the
      full existing file and confirm zero behavior regressions before
      adding new tests

## Testing

- **Existing tests to run**: `uv run pytest tests/unit/test_hook_handlers.py`
  (scoped, foreground — the module's largest test file; a regression
  here means this ticket changed guard behavior, which it must not)
- **New tests to write**: the `HookPayload.from_stdin` unit tests
  (nested-then-flat resolution, `missing` tracking); the parametrized
  replay-corpus test described above.
- **Verification command**: `uv run pytest tests/unit/test_hook_handlers.py -v`
  (scoped, foreground — do not run the full suite for this ticket)
