---
id: '003'
title: Finish TODO to Issue Rename
status: planning-docs
branch: sprint/003-finish-todo-to-issue-rename
use-cases: []
issues:
- finish-the-todo-issue-rename.md
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 003: Finish TODO to Issue Rename

## Goal

Complete the mechanical rename of the CLASI artifact concept from "TODO" to "issue" that sprint 015 left roughly 70% finished. The high-visibility surface (class names, MCP tool names, CLI subcommands, frontmatter field names on tickets) was already renamed. This sprint addresses the remaining less-visible identifiers: Python parameter and variable names in production code, docstring prose, agent instruction prose, README references, test class and method names, and the frontmatter schema example in software-engineering.md. The backward-compatibility aliases that exist to support the pinned old MCP server are explicitly preserved untouched.

## Issues in scope

- `issues/finish-the-todo-issue-rename.md` — rename residual `todo`-based Python identifiers, docstring prose, agent prose, documentation references, and test names; preserve all backward-compat aliases; verify with `grep` and the full test suite.

## Out of scope

The following are explicitly excluded to preserve backward compatibility with the pinned MCP server version and to avoid collateral migration work:

- **Hook handler aliases** (`handle_plan_to_todo`, `handle_codex_plan_to_todo`) in `clasi/hook_handlers.py:890, 926` — required for the pinned old MCP server; removed when the pin moves.
- **CLI deprecated aliases** in `clasi/cli.py:274-276, 295-297` — already labeled deprecated; stay until the pin moves.
- **Hook registry keys** `"plan-to-todo"` and `"codex-plan-to-todo"` in `clasi/hook_handlers.py:980, 982` — pinned-MCP compatibility.
- **Path strings referring to `docs/clasi/todo/`** — deferred to the self-migration sprint; don't update these here.
- **Historical sprint archives** in `docs/clasi/sprints/done/**` — archives are never mutated.
- The `create_sprint` tool's `todo` parameter rename — this is an MCP tool schema change coordinated with the MCP-pin upgrade, not this sprint.
- Note: the `moved_todos`/`unresolved_todos` JSON keys in `close_sprint` output **are** renamed in this sprint (to `moved_issues`/`unresolved_issues`) — they are produced by the current source, not the pinned binary.

## Notes / open questions

None. The issue contains a detailed file-by-file audit with exact line numbers for every change needed. The backward-compat boundary is well defined.

## Tickets

| # | Title | Depends On |
|---|-------|------------|
| 001 | Rename production-code identifiers from todo to issue | — |
| 002 | Rename docstring prose from todo to issue | 001 |
| 003 | Rename agent instruction prose from todo to issue | 002 |
| 004 | Rename documentation references from todo to issue | 003 |
| 005 | Rename test class and method names from todo to issue | 001 |
| 006 | Grep verification — confirm only allowed todo residuals remain | 001, 002, 003, 004, 005 |

Tickets execute serially in the order listed.
