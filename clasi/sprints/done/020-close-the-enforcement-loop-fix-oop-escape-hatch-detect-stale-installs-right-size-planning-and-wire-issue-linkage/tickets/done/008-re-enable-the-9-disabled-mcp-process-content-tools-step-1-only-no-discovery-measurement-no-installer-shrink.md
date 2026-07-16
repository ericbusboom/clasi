---
id: 008
title: Re-enable the 9 disabled MCP process-content tools (step 1 only; no discovery
  measurement, no installer shrink)
status: done
use-cases:
- SUC-008
depends-on:
- '002'
github-issue: ''
issue: issue-re-enable-the-mcp-process-content-tools.md
completes_issue: false
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Re-enable the 9 disabled MCP process-content tools (step 1 only; no discovery measurement, no installer shrink)

## Description

Nine content-serving MCP tools in `src/clasi/tools/process_tools.py` are
disabled (`#@server.tool()` commented out at lines 188, 198, 212, 221,
307, 339, 349, 358, 414: `list_agents`, `list_skills`, `list_instructions`,
`get_agent_definition`, `get_skill_definition`, `get_instruction`,
`list_language_instructions`, `get_language_instruction`,
`get_activity_guide`), but shipped docs (`clasi-se-process.md`,
`.claude/rules/source-code.md`, `src/clasi/AGENTS.md`,
`se-overview-template.md`) still tell agents to call them. Meanwhile
`tests/unit/test_mcp_server.py:62,144` pins the tool count to the 3 live
tools and actively fails if any of the 9 are re-enabled — docs and tests
contradict each other with no artifact recording which way is right.

**This ticket is step 1 only** of the issue's staged 3-step plan. Do not
bundle step 2 (discovery-reliability measurement — a scratch-repo trial of
whether a model reliably calls `list_skills()` when instructed via a
rule, with a real chance of a negative result) or step 3 (installer
file-count shrink, 47 to about 6, which depends entirely on step 2's
outcome). Re-enabling is low risk on its own merits regardless of what
step 2 finds — the functions are already covered by
`tests/system/test_process_tools.py`, `tests/system/test_content_smoke.py`,
and `tests/unit/test_skill_stub_loader.py`, all of which import the
undecorated functions directly and pass today.

This ticket depends on ticket 002 (stale-install detection): re-enabled
MCP-served content resolves from the installed package
(`content_path("plugin", ...)`, `mcp_server.py:52,74-81`), which inherits
the exact staleness problem ticket 002 addresses — MCP-served skills would
come from a stale build too if ticket 002 hasn't landed.

## Acceptance Criteria

- [x] All 9 `@server.tool()` decorators restored in `process_tools.py`.
- [x] `EXPECTED_PROCESS_TOOLS` (`tests/unit/test_mcp_server.py:62`) and the
      hardcoded tool count (`:144`, currently `== 36`) updated to match —
      `clasi mcp` now exposes 45 tools (36 + 9).
- [x] `get_skill_definition` resolving a `Load from:` skill is verified
      against the actual resolution path this repo now uses (post-ticket-
      002, ideally against the editable install, not a stale one) — sprint
      013 flagged the `_PACKAGE_ROOT` triple-parent coupling
      (`process_tools.py:259`) and asked for wheel-resolution proof; this
      ticket at minimum verifies resolution against whatever install path
      is now correct per ticket 002.
- [x] No discovery-reliability trial and no installer file-count change
      included in this ticket — explicitly out of scope, left for future
      tickets gated on the measurement.

## Implementation Plan

**Approach**: Uncomment the 9 decorators; update the two test-expectation
constants; run the existing (already-passing, since they test undecorated
functions directly) system tests to confirm nothing regresses once the
tools are live on the MCP surface too.

**Files likely involved**: `src/clasi/tools/process_tools.py`,
`tests/unit/test_mcp_server.py`.

**Testing plan**: `test_no_unexpected_tools` and `test_tool_count` updated
and passing; existing `tests/system/test_process_tools.py`,
`tests/system/test_content_smoke.py`, `tests/unit/test_skill_stub_loader.py`
re-run to confirm no regression now that the tools are live on the MCP
surface (not just directly importable).

**Documentation updates**: None needed — the docs already describe these
tools as live; this ticket makes reality match them, not the reverse.
