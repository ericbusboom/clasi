---
id: 018
title: GitHub Issue Sync
status: done
branch: sprint/018-github-issue-sync
use-cases:
- SUC-001
- SUC-002
- SUC-003
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 018: GitHub Issue Sync

## Goals

Enable bidirectional GitHub issue integration: import issues from GitHub
repos as CLASI TODOs, carry issue references through the TODO-to-ticket
lifecycle, and automatically close linked GitHub issues when a sprint is
closed.

## Problem

Language models using CLASI-managed projects create GitHub issues to
communicate problems. Currently there is no way to pull those issues into
the CLASI SE process. The `ghtodo` skill creates issues outbound, but
nothing handles inbound sync. Without this, issue reporters get no
feedback (issues stay open), and the development process has no
connection to the issue tracker.

## Solution

Three-part approach:

1. **Import skill** (`gh-import`) — Uses `gh` CLI to list open issues
   from a target repo, presents them to the user with a bulk-import gate
   (>5 issues triggers confirmation), and creates CLASI TODO files with
   a `github-issue` frontmatter field.

2. **Reference propagation** — The `github-issue` field flows from TODO
   to ticket (carried forward when a ticket is created from a TODO). The
   sprint doc gains a `## GitHub Issues` section listing all linked
   issues for the sprint.

3. **Auto-close on sprint close** — The `close-sprint` skill adds a step
   that reads the sprint doc's GitHub Issues section and closes each
   linked issue via `gh issue close`.

## Success Criteria

- Agent can import GitHub issues as TODOs with `github-issue` references
- Importing >5 issues pauses and asks the user to confirm or filter
- `gh` access is verified before attempting operations
- Issue reference is preserved through TODO -> ticket -> sprint doc
- Closing a sprint closes all linked GitHub issues
- All new code has unit tests

## Scope

### In Scope

- New `gh-import` skill definition
- New MCP tools: `list_github_issues`, `close_github_issue`
- `github-issue` frontmatter field on TODOs and tickets
- `## GitHub Issues` section in sprint doc template
- Update `close-sprint` skill with GitHub issue closing step
- `gh` CLI access verification helper
- Unit tests for all new MCP tools

### Out of Scope

- Two-way sync (updating issue state from ticket status changes mid-sprint)
- GitHub webhooks or push-based notifications
- Issue assignment or label management beyond import
- Modifying the `ghtodo` or `report` skills
- Supporting non-GitHub issue trackers

## Test Strategy

Unit tests for:
- `list_github_issues` — mock `gh` subprocess calls, test filtering,
  test access error handling
- `close_github_issue` — mock `gh` subprocess calls, test success/failure
- `_check_gh_access` — mock `gh` subprocess, test success/failure paths
- GitHub issue reference parsing and propagation

System tests:
- None (would require live GitHub access)

## Architecture Notes

All new GitHub operations use `gh` CLI as the primary method (not the
GitHub REST API). This aligns with the stakeholder requirement that users
set up `gh` for repo access. The existing `_get_github_token` / API
approach remains for `create_github_issue` but is not extended.

The `github-issue` field uses the format `owner/repo#number` (e.g.,
`ericbusboom/claude-agent-skills#42`). This is unambiguous across repos.

## Definition of Ready

Before tickets can be created, all of the following must be true:

- [ ] Sprint planning documents are complete (sprint.md, use cases, architecture)
- [ ] Architecture review passed
- [ ] Stakeholder has approved the sprint plan

## Tickets

1. **#001 — gh CLI helpers and list_github_issues MCP tool** (SUC-001)
   `_check_gh_access` helper + `list_github_issues` MCP tool in artifact_tools.py
2. **#002 — close_github_issue MCP tool** (SUC-003, depends: #001)
   `close_github_issue` MCP tool wrapping `gh issue close`
3. **#003 — Template updates for github-issue field** (SUC-002)
   Add `github-issue` field to ticket template, `## GitHub Issues` section to sprint template
4. **#004 — gh-import skill definition** (SUC-001, depends: #001)
   New skill file + update `/se` dispatcher
5. **#005 — Update close-sprint and create-tickets skills** (SUC-002/003, depends: #002, #003)
   Add issue-closing step to close-sprint, propagation instructions to create-tickets
