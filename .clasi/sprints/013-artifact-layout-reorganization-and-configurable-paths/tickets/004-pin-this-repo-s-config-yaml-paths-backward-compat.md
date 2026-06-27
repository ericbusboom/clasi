---
id: "004"
title: "Pin this repo's config.yaml paths (backward-compat)"
status: open
use-cases:
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

# Pin this repo's config.yaml paths (backward-compat)

## Description

After ticket 001 changes `ARTIFACT_PATH_DEFAULTS` to the new visible layout
(`clasi/issues`, `docs/architecture`, etc.), this repo's own `.clasi/` files
are still at the OLD physical locations (`.clasi/issues`, `.clasi/sprints`,
`.clasi/architecture`, `.clasi/reflections`). Without a config pin, `Project`
would resolve categories to the new defaults — directories that don't exist —
and MCP tools would see empty sprint/issue lists.

This ticket writes an explicit `paths:` block to `.clasi/config.yaml` that
points every category at its CURRENT physical location. This lets the MCP
server and all CLI commands continue to function correctly after ticket 001
lands, with zero file moves.

The config-pin is intentionally explicit (not computed) so it survives re-runs
of `clasi init`. The finale sprint will rewrite this block when files are
actually relocated.

## Acceptance Criteria

- [ ] `.clasi/config.yaml` contains a `paths:` block with these values after
      this ticket:
      ```yaml
      paths:
        issues:        .clasi/issues
        sprints:       .clasi/sprints
        reflections:   .clasi/reflections
        architecture:  .clasi/architecture
        design:        docs/design
        logs:          .clasi/log
        db:            .clasi/.clasi.db
      ```
- [ ] `Project(repo_root).issues_dir` resolves to `<root>/.clasi/issues`.
- [ ] `Project(repo_root).sprints_dir` resolves to `<root>/.clasi/sprints`.
- [ ] `Project(repo_root).architecture_dir` resolves to
      `<root>/.clasi/architecture`.
- [ ] `clasi status` on this repo still shows all sprints and tickets.
- [ ] MCP `list_sprints()` still returns the active sprint(s).
- [ ] `uv run pytest` passes.

## Implementation Plan

### Files to Modify

- `.clasi/config.yaml` — add/merge the `paths:` block.

### Implementation Steps

This ticket is a one-file data change; no code changes.

1. Read `.clasi/config.yaml` (currently contains only `process: se`).

2. Write the updated config:
   ```yaml
   process: se
   paths:
     issues:        .clasi/issues
     sprints:       .clasi/sprints
     reflections:   .clasi/reflections
     architecture:  .clasi/architecture
     design:        docs/design
     logs:          .clasi/log
     db:            .clasi/.clasi.db
   ```

3. After writing, run `clasi status` to confirm sprint resolution is intact.

4. Run `uv run pytest` to confirm no regressions.

### Testing Plan

No new automated tests. Verification is:
- `clasi status` output before vs. after — sprint list must be identical.
- `uv run pytest` green.

This ticket MUST be committed in the same PR as ticket 001 (or immediately
after it in the same branch execution), so the default-change and the pin
land atomically.
