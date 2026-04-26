---
id: '007'
title: Update README for corrected Codex install footprint
status: todo
use-cases:
  - SUC-003
  - SUC-004
  - SUC-007
depends-on:
  - '006'
github-issue: ''
todo: ''
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Update README for corrected Codex install footprint

## Description

After tickets 001–006 land, the Codex install footprint is materially different from what
was shipped in sprint 010. The README should accurately describe what `clasi install
--codex` writes, the hook firing limitation, and the sub-agent capability.

## Acceptance Criteria

- [ ] README Codex install section lists all emitted files:
      `.codex/config.toml`, `.codex/hooks.json`, `.codex/agents/*.toml`,
      `AGENTS.md` (root), `docs/clasi/AGENTS.md`, `clasi/AGENTS.md`,
      `.agents/skills/*/SKILL.md`.
- [ ] README documents the repo-local hooks.json firing limitation
      (openai/codex#17532) with the workaround (manual copy to `~/.codex/hooks.json`).
- [ ] README mentions the three installed sub-agents (team-lead, sprint-planner,
      programmer) and where their TOML files live.
- [ ] README does not reference the old flat hooks.json format.
- [ ] `uv run pytest` passes (README changes do not break tests).

## Implementation Plan

### Approach

Find the Codex install section in `README.md` (or `docs/README.md` — confirm the actual
path first by reading the repo root). Update it to:

1. Replace or extend the "files written" list to include `.codex/agents/*.toml` and the
   two nested `AGENTS.md` files.
2. Add a note about the Stop hook firing behavior:
   > **Note**: As of April 2026, Codex fires hooks.json Stop hooks only from
   > `~/.codex/hooks.json`, not from repo-local `.codex/hooks.json` (openai/codex#17532).
   > To enable plan-to-todo capture, copy `.codex/hooks.json` to `~/.codex/hooks.json`
   > after install.
3. Add a brief paragraph about sub-agents:
   > CLASI installs three Codex sub-agent definitions under `.codex/agents/`: `team-lead`,
   > `sprint-planner`, and `programmer`. These map to the CLASI SE process roles and can
   > be invoked as Codex sub-agents.

### Files to Modify

- `README.md` (confirm path) — Codex install section only.

### Testing Plan

1. Read README diff to ensure no broken Markdown.
2. `uv run pytest` — full suite regression (no tests read README content).

### Documentation Updates

This ticket IS the documentation update. No code changes.
