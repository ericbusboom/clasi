---
id: '005'
title: Uniform MCP tool envelope
status: done
use-cases:
- SUC-005
depends-on:
- '004'
github-issue: ''
issue: uniform-mcp-tool-envelope.md
completes_issue: true
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Uniform MCP tool envelope

## ⚠ Read this before touching any code

**The `"NONE"`-sentinel stripping this ticket relocates is currently the
only thing standing between an agent's empty-optional-argument workaround
and a literal `"NONE"` string landing in frontmatter or a shell command.**
The Claude Code harness bug this sentinel exists for is real and
currently active (see `.claude/rules/tool-call-empty-args.md`): if any
tool call argument is empty or null, the harness silently drops *all*
arguments. Agents route around this by passing the literal string
`"NONE"` for an omitted optional parameter, and today's
`mcp_server.py`-level monkey-patch strips it back to `None` before any
tool function sees it. **Do not disable, weaken, or leave a gap in this
mechanism while relocating it.** The acceptance criteria below exist
specifically to prove the new location works before the old one is
removed — do not remove the old monkey-patch until the new decorator is
tested and applied to every tool.

**This ticket's decorator is the prerequisite for a future `mcp` 2.x
migration — but that migration is explicitly OUT OF SCOPE here.** Sprint
029 capped `mcp` at `>=1.0,<2.0` specifically because `mcp` 2.x deletes
`mcp.server.fastmcp` and the private internals the current monkey-patches
tap (`_tool_manager.call_tool`, `JSONRPCMessage.model_validate_json`) —
under 2.x those patches would silently stop installing, and the
NONE-sentinel mitigation would silently stop working (fail-open, not a
crash). `@clasi_tool` removes that dependency on private `mcp`-library
internals, which is *why* it's a prerequisite — but do not attempt the
2.x migration itself in this ticket. It is tracked separately at
`clasi/issues/migrate-to-mcp-2-x-api.md`. If you find yourself touching
`pyproject.toml`'s `mcp` version pin, stop — that is not this ticket.

## Description

The 34 artifact MCP tools have a three-way inconsistent error contract
(raise / `{"error": ...}` inside a success shape / `close_sprint`'s own
third format), and the NONE-sentinel mitigation is installed by
monkey-patching three private `mcp`-library internals inside
`mcp_server.py`'s `run()` (`_tool_manager.call_tool`,
`_mcp_server.instructions`, `JSONRPCMessage.model_validate_json` — see
`mcp_server.py:301-334`). This ticket adds a `@clasi_tool` decorator that
owns sentinel-stripping, the result envelope, and the per-call
`mcp-calls.jsonl` trace, and applies it to every tool function. See
`sprint.md`'s Architecture M5 and its Design Rationale entry on why
`gitutil.run_git` deliberately stays out of the new module.

**Verified evidence** (checked during planning):
- `_strip_none_sentinel` (`mcp_server.py:23-33`) and `_write_call_trace`
  (`mcp_server.py:36-79`) are already self-contained, plain-value
  functions — `_write_call_trace`'s own docstring says it was written
  this way specifically "so a later sprint (030...) can lift this helper
  into the decorator without rewriting it." Reuse them; do not rewrite
  their logic from scratch.
- `_build_logged_call_tool`/`_logged_call_tool`
  (`mcp_server.py:82-127`) is what the new decorator's call-interception
  behavior replaces — read it before designing `@clasi_tool`'s dispatch
  path, it already does most of what the decorator needs to do, just at
  the wrong layer (patched onto the library's tool manager instead of
  applied per-function).
- `list_tickets` (`tools/artifact_tools.py`) returns `[]` for an unknown
  `sprint_id` today — a silent-looking success, not an error.
- The documented test-skip mechanism, `test_command=""`, is unreachable
  through the empty-args harness bug this same sentinel mitigation exists
  for; `"NONE"` maps to `None` (the default `uv run pytest`), not to
  "skip."

## Acceptance Criteria

- [x] New `tools/_common.py` holds `@clasi_tool` (composed as
      `@server.tool()` over `@clasi_tool` over the tool function, so
      FastMCP's schema introspection still sees the original signature)
      and `resolve_artifact_path` (relocated from `artifact_tools.py` —
      already root-anchored since sprint 029, a pure move with no
      behavior change).
- [x] `@clasi_tool` strips the `"NONE"` sentinel per-call using the
      relocated `_strip_none_sentinel` logic, in code this package owns —
      no monkey-patch over any `mcp`-library private attribute.
- [x] `@clasi_tool` converts a domain exception (`ValueError`,
      `FileNotFoundError`, and the artifact model's own exception types)
      into one `{"ok": false, "error": {...}}` result shape. A
      successful call's shape is documented in this ticket's
      implementation notes (nested under a key vs. merged alongside
      existing fields — sprint.md's Open Question 5 leaves this
      genuinely open; pick one, document it in `tools/_common.py`'s own
      docstring, and apply it uniformly to all 34 tools — consistency
      across tools matters more than which specific shape is chosen).
      See **Implementation Notes** below for the shape actually chosen
      and why.
- [x] `@clasi_tool` appends the per-call `mcp-calls.jsonl` trace, reusing
      `_write_call_trace`'s existing logic (moved, not rewritten).
- [x] Every `@server.tool()` function in `artifact_tools.py`,
      `process_tools.py`, and `design_tools.py` also carries
      `@clasi_tool` — no tool is left on the old contract.
- [x] `mcp_server.py`'s `_tool_manager.call_tool` monkey-patch and its
      NONE-stripping/call-logging behavior are removed **only after**
      confirming every tool carries `@clasi_tool` and its unit tests
      pass. The separate raw-RPC diagnostic tap
      (`JSONRPCMessage.model_validate_json`, `mcp_server.py:301-323`) is
      **not** touched by this ticket — it is unrelated debug scaffolding
      for a closed investigation, flagged for a future cleanup pass, not
      part of the NONE-sentinel/call-logging mechanism this ticket
      replaces.
- [x] Sentinel stripping is exercised by unit tests that call
      `@clasi_tool`-wrapped functions directly — not only reachable
      through a live server round-trip, unlike today.
- [x] `list_tickets` on an unknown `sprint_id` returns the new error
      envelope, not `[]`.
- [x] `close_sprint` accepts `test_command="SKIP"` as an explicit,
      documented sentinel and actually skips the test step when passed —
      replacing the unreachable `test_command=""` mechanism. Document
      this in `close_sprint`'s own docstring (per `tools-DESIGN.md`'s
      existing constraint that a tool's docstring is the literal contract
      agents depend on).

## Implementation Notes

**Envelope shape decision (Open Question 5):** resolved as *nested for
failure only* — success passes the wrapped function's own return value
through completely unchanged; only a caught domain exception produces
the envelope, as `{"ok": false, "error": {"type": ..., "message": ...}}`.
This directly matches SUC-005's own Main Flow step 3 ("On success, the
tool returns its normal result") and the reliability review's F15 fix
description ("converts domain exceptions to a single `{"ok": false,
"error": {...}}` shape" — nothing there wraps success).

Two concrete findings during implementation drove this over wrapping
success too:

1. **Merging is unsafe in general.** `validate_design` already returns
   `{"ok": <did validation pass>, "messages": [...], "info": [...]}`.
   Merging an envelope-level `"ok": true` on top the moment the *call*
   succeeds would silently overwrite that domain-level `"ok"` (did
   *validation* pass), masking a real validation failure — exactly the
   silent-failure class this ticket exists to eliminate.
2. **Nesting success uniformly is prohibitively invasive.** A repo-wide
   scan while implementing this ticket found upwards of 350
   `json.loads(<tool call>)` call sites across 28 test files asserting
   directly on today's un-enveloped success shape. Renesting every
   tool's success payload would mean rewriting that entire surface for a
   change with no entry in this ticket's own `Files to modify` list.

Full reasoning is in `tools/_common.py`'s own module docstring (point 2),
per the acceptance criterion above. The postcondition SUC-005 actually
needs — an agent checks one shape to learn a call failed — holds either
way: `{"ok": false, "error": {...}}` present means failure; its absence
means success and the payload is whatever that tool has always returned.

**Collateral test fixes.** Converting exceptions to envelopes changes
behavior for every tool in the pre-existing "raises `ValueError`" bucket
(F15's own list): tests asserting `pytest.raises(ValueError/
FileNotFoundError)` around a call to one of those tools no longer see an
exception, so they were rewritten to assert on the returned envelope
instead. Found via a repo-wide static scan (not by running the full
suite) cross-referencing every `pytest.raises` block against the 47
`@clasi_tool`-decorated names, in: `tests/unit/test_artifact_tools.py`,
`tests/system/test_artifact_tools.py`, `tests/system/test_process_tools.py`
(this ticket's required run list), plus `tests/unit/test_frontmatter_tools.py`
and `tests/unit/test_issue_tools.py` (outside the required list, but
directly broken by this change and fixed as due diligence). The
`test_command="SKIP"` rename also required updating the only two other
call sites using the old `test_command=""` mechanism:
`tests/system/test_version_bump_cadence.py` and
`tests/system/test_design_overlay_lifecycle.py`. All five extra files
were run directly (not the full suite) and pass.

## Implementation Plan

**Approach**: build and unit-test `@clasi_tool` in isolation first
(against synthetic tool functions, not the real 34), apply it to a small
subset and verify via the test suite, then apply it to the remaining
tools mechanically, then remove the old monkey-patch last. This ticket
depends on 004 because `close_sprint`'s final shape (the thin wrapper
over `close.SprintCloser`, and the new `test_command="SKIP"` sentinel) is
what gets wrapped — implementing this ticket before 004 would mean
wrapping a `close_sprint` that's about to be substantially rewritten
underneath the decorator.

**Files to modify**:
- `src/clasi/tools/_common.py` (new) — `@clasi_tool`, relocated
  `resolve_artifact_path`
- `src/clasi/mcp_server.py` — remove the `_tool_manager.call_tool`
  monkey-patch and its NONE-stripping/trace logic (relocated, not
  duplicated); leave the raw-RPC diagnostic tap untouched
- `src/clasi/tools/artifact_tools.py` — apply `@clasi_tool` to every
  tool; `close_sprint` gains `test_command="SKIP"`; `resolve_artifact_path`
  import updated to the new location
- `src/clasi/tools/process_tools.py` — apply `@clasi_tool` to every tool
- `src/clasi/tools/design_tools.py` — apply `@clasi_tool` to
  `validate_design`

**Do not modify**: `gitutil.py` (deliberately excluded from
`tools/_common.py` — see Design Rationale in `sprint.md`), any
`state_machine/`/`sprint.py`/`ticket.py` logic (tickets 001-004, already
landed), `pyproject.toml`'s `mcp` version pin (see the warning above).

## Process Notes (read before starting)

- **Guards are fail-closed as of sprint 029/009.** A crash inside
  role-guard or mcp-guard is now a hard block, not a silent allow.
- **Editing ticket files under this locked sprint's `tickets/` tree is
  allowed for tier-2 agents as of sprint 029/010.** Check-boxes-then-flip
  or flip-then-check-boxes both work.
- **If a guard blocks you, STOP and report it.** Do not route around a
  block with a Bash heredoc, `sed`, redirection, or any mechanism that
  avoids the tool the guard is watching. Reporting a block is a
  successful outcome of this ticket, not a failure — the stakeholder
  raised this explicitly for this sprint.

## Testing

- **Existing tests to run**:
  `uv run pytest tests/unit/test_mcp_server.py tests/unit/test_artifact_tools.py tests/system/test_artifact_tools.py tests/system/test_process_tools.py -v`
- **New tests to write**: `@clasi_tool` unit tests (sentinel stripping,
  exception-to-envelope conversion, trace-write) against synthetic
  functions; an `envelope`-shape consistency test asserting all 34 tools
  return the same shape's `"ok"` key on both success and failure;
  `list_tickets`-on-unknown-sprint-id error-envelope test;
  `close_sprint(test_command="SKIP")` actually-skips-tests test.
- **Verification command**: the existing-tests command above, scoped to
  this ticket's modules — not the full suite.
