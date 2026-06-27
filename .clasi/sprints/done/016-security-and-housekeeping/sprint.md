---
id: '016'
title: Security and housekeeping
status: done
branch: sprint/016-security-and-housekeeping
use-cases: []
issues:
- gh-15-clasi-must-gitignore-docs-clasi-log-transcripts-contain-live-secrets.md
- plan-document-the-empty-argument-tool-call-bug.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 016: Security and housekeeping

## Goals

Address a confirmed security incident (live secrets in committed transcript files) and
document a confirmed harness bug (empty-argument tool calls dropping all parameters).

## Problem

### Security (PRIORITY — flag for stakeholder)

CLASI writes conversation transcripts to `docs/clasi/log/` but does not add that
directory to the project's `.gitignore`. These transcripts capture raw tool results,
including the contents of `.env` / dotconfig files, and routinely contain live secrets.

A real incident occurred: in a downstream project (`league-infrastructure/student-accounts`),
a version-bump commit accidentally staged 237 untracked `docs/clasi/log/*.md` files. Two
contained live secrets (Google OAuth Client ID + Client Secret, Anthropic API key + Admin
API key). The push was stopped only by GitHub Push Protection.

**Stakeholder flag:** the security item (gh-15) may warrant pulling forward ahead of
013/014 given the confirmed incident and ongoing exposure risk. Sprint 016 is ordered last
per the team-lead's grouping; surface this to the stakeholder before execution planning.

### Documentation

There is a confirmed bug in Claude Code (VS Code extension and possibly other harnesses)
where if any argument in a tool call is empty or null, all arguments are silently dropped
and the tool receives `input_value={}`. This caused repeated sprint-closure failures
(sprints 007, 010, 011) with `sprint_id: Field required, input_value={}`. The full
picture and mitigation needs a prominent, always-loaded rule file.

The `plan-document-the-empty-argument-tool-call-bug.md` issue confirms that NONE-sentinel
stripping is NOT yet implemented in the MCP server — the rule file must document both the
mitigation convention (use `"NONE"` sentinel) and the required code change in
`clasi/mcp_server.py` to actually strip it.

## Solution

### A. Security: gitignore the log directory

- Add `docs/clasi/log/` to the clasi repo's own `.gitignore` immediately.
- When CLASI initializes a project or first writes to `docs/clasi/log/`, idempotently
  ensure `.gitignore` contains the rule (append only if absent).
- Detail planning should decide the right insertion point (project-initiation skill, log
  writer, or both).

### B. Documentation and sentinel stripping: empty-argument bug

- Create `.claude/rules/tool-call-empty-args.md` with `paths: ["**"]` so it loads in
  every agent session.
- Add preprocessing to `clasi/mcp_server.py` `_logged_call_tool` wrapper: strip `"NONE"`
  sentinel values from `Optional[str]` parameters before dispatching, treating them as
  absent.
- Document the ToolSearch-first requirement as part of the same rule file.

Note: skill/agent doc edits target `clasi/plugin/...`; `.claude/` and `.agents/` copies
are installer-generated.

## Success Criteria

- `docs/clasi/log/` is in the clasi repo's `.gitignore`.
- A project initialized by CLASI has `docs/clasi/log/` gitignored before the first
  transcript is written.
- `.claude/rules/tool-call-empty-args.md` exists with `paths: ["**"]` and accurately
  documents the bug, NONE-sentinel mitigation, and ToolSearch-first requirement.
- Passing `"NONE"` for an `Optional[str]` MCP parameter results in the server receiving
  `None` (not the string `"NONE"`).
- `pytest -q` green.

## Scope

### In Scope

- `.gitignore` (clasi repo root) — add `docs/clasi/log/` rule
- CLASI project-initiation / log-writing code — idempotent gitignore insertion
- `clasi/mcp_server.py` — NONE-sentinel stripping in `_logged_call_tool`
- `.claude/rules/tool-call-empty-args.md` — new always-loaded rule file

### Out of Scope

- Redacting secret patterns from transcript content (noted as optional hardening; defer)
- Log directory path change (keep `docs/clasi/log/` as-is; just gitignore it)

## Dependencies

After sprint 012 (for phase gates). However, the security item (A) is independent of
012's path fixes — if the stakeholder decides to pull gh-15 forward, it can run before
012 closes.

## Issues Addressed

- `gh-15-clasi-must-gitignore-docs-clasi-log-transcripts-contain-live-secrets.md` (SECURITY)
- `plan-document-the-empty-argument-tool-call-bug.md`

## Architecture Notes

The NONE-sentinel stripping is a single central intercept in `_logged_call_tool` — one
change covers all tools, no per-tool changes needed. The gitignore insertion is best
placed at the earliest possible point in project initialization so the ignore rule
precedes the first log write.

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Ensure log-dir gitignore on runtime hook_handlers mkdir | — |
| 002 | Add NONE-sentinel stripping unit tests to test_mcp_server | — |
| 003 | Create tool-call-empty-args rule file in plugin/rules | 002 |

Tickets execute serially in the order listed.
