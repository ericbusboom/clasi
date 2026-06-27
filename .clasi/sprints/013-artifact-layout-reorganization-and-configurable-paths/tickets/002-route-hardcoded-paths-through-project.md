---
id: "002"
title: "Route hardcoded paths through Project"
status: open
use-cases:
- SUC-001
- SUC-003
depends-on:
- "001"
github-issue: ""
issue: ""
# completes_issue: Controls whether linked issues are archived when this ticket
# is moved to done. Default: true (archive when all referencing tickets are done).
# Set to false (scalar) to suppress archival for ALL linked issues on this ticket.
# Set to a mapping {filename.md: false} to suppress archival per issue filename.
# Use false for tickets that partially address a multi-sprint umbrella issue.
completes_issue: true
# exception: Written by a lower agent when it cannot proceed (see architecture §exception-protocol).
# exception:
#   thrown_by: "programmer"          # "programmer" | "sprint-planner"
#   thrown_at: "2026-05-07T14:23:00Z"
#   attempted: |
#     Description of what was attempted before giving up.
#   conflict: "architecture-update.md §3 — reason the agent is blocked"
#   surface: "internal"              # "user-visible" | "internal"
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Route hardcoded paths through Project

## Description

After ticket 001 adds `Project.db_path`, `architecture_dir`, `log_dir`, and
`reflections_dir`, this ticket removes all remaining raw path constructions
outside `Project` that bypass those properties.

Specific callsites to fix:

- `clasi/sprint.py:501` — `project.clasi_dir / "architecture"` becomes
  `project.architecture_dir`.
- `clasi/tools/artifact_tools.py:237` — same fix.
- `clasi/tools/artifact_tools.py:1476` — `project.clasi_dir / ".clasi.db"`
  becomes `project.db_path`.
- `clasi/hook_handlers.py` (~8 occurrences) — `get_project().clasi_dir /
  ".clasi.db"` becomes `get_project().db_path`; any `base / "log"` construction
  becomes `get_project().log_dir`.

Also fixes the overview-presence bug: `ClasiStateReader.overview_exists()` in
`clasi/status/reader.py:93` already uses `self._project.design_dir /
"overview.md"`, so once `design_dir` is config-driven (ticket 001), the bug is
fixed automatically. Verify this during implementation.

## Acceptance Criteria

- [ ] `clasi/sprint.py` — no raw `clasi_dir / "architecture"` expression;
      uses `project.architecture_dir`.
- [ ] `clasi/tools/artifact_tools.py` — no raw `clasi_dir / "architecture"` or
      `clasi_dir / ".clasi.db"`; uses `project.architecture_dir` and
      `project.db_path`.
- [ ] `clasi/hook_handlers.py` — no raw `clasi_dir / ".clasi.db"` expressions;
      uses `get_project().db_path`. Any `log_dir` construction uses
      `get_project().log_dir`.
- [ ] `grep -rn "clasi_dir / \".clasi.db\"\|clasi_dir / \"architecture\"\|clasi_dir / \"log\""
      clasi/` returns no results (excluding `project.py` itself and comments).
- [ ] `uv run pytest` passes (all existing tests green).
- [ ] `ClasiStateReader.overview_exists()` returns `True` on this repo (design_dir
      now resolves to `docs/design` via config pin from ticket 004 — verify
      manually after that ticket lands, or write a unit test with a scratch
      project that has `docs/design/overview.md`).

## Implementation Plan

### Files to Modify

- `clasi/sprint.py` — line ~501
- `clasi/tools/artifact_tools.py` — lines ~237 and ~1476
- `clasi/hook_handlers.py` — ~8 occurrences

### Implementation Steps

1. Open each file; replace each raw path construction with the appropriate
   `Project` property call.
2. Run `grep -rn 'clasi_dir / "\.clasi\.db"\|clasi_dir / "architecture"\|clasi_dir / "log"' clasi/`
   to confirm no stragglers.
3. Run `uv run pytest` to confirm green.

### Testing Plan

- Existing tests cover `sprint.close()` and the hook handlers; no new tests
  needed for this mechanical substitution.
- If any `clasi_dir / "reflections"` callsites were found during ticket 001's
  grep, fix them here and add a targeted test that confirms `reflections_dir`
  is used.
- Run: `uv run pytest -x`
