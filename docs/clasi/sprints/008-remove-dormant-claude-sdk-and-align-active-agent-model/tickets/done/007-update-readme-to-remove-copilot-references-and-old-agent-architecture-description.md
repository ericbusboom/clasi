---
id: "007"
title: "Update README to remove Copilot references and old agent architecture description"
status: done
use-cases: ["SUC-004"]
depends-on: ["005"]
github-issue: ""
todo: ""
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update README to remove Copilot references and old agent architecture description

## Description

`README.md` contains two stale areas:

1. **Copilot mirroring**: The opening description says "gives Claude Code (and GitHub
   Copilot)..." and the setup table includes a `.github/copilot/instructions/` row
   described as "Mirror of the SE process rule for GitHub Copilot." This is not a current
   feature and misleads users.

2. **Old agent architecture**: Any prose or diagram listing the old agent hierarchy
   (`project-manager`, `sprint-executor`, `ad-hoc-executor`, `code-monkey`,
   `code-reviewer`, `architect`, `technical-lead`) should be updated to reflect the
   current 3-agent model or replaced with a link to `docs/design/overview.md` (the
   authoritative architecture reference).

## Acceptance Criteria

- [x] README opening description no longer mentions GitHub Copilot as a supported tool.
- [x] The `.github/copilot/instructions/` row is removed from any setup table.
- [x] No Mermaid diagram or prose in README names old agent roles as active agents.
- [x] README accurately describes CLASI with `team-lead`, `sprint-planner`, and `programmer`, or defers to `docs/design/overview.md` for architecture detail.
- [x] `uv run pytest` passes after the README-only change.

## Implementation Plan

### Approach

1. Read `README.md` in full.
2. Edit the opening paragraph — remove the Copilot parenthetical `(and GitHub Copilot)`.
3. Remove or update the setup table row for `.github/copilot/instructions/`.
4. Scan for any agent architecture Mermaid diagram or prose listing old agents. If present:
   - Replace with a brief 3-agent description (`team-lead` → `sprint-planner`/`programmer`), or
   - Remove and add: "See `docs/design/overview.md` for the full agent architecture."
5. Confirm no other Copilot or old-agent references remain.

### Files to Create / Modify

- **Edit**: `README.md`

### Testing Plan

- `uv run pytest` — passes (no code changed).
- `grep -n "Copilot\|copilot\|code-monkey\|sprint-executor\|ad-hoc-executor\|technical-lead\|project-manager\|code-reviewer" README.md` — no remaining matches (or only clearly archival/historical).

### Documentation Updates

README is itself the documentation being updated. No other files need changes.
