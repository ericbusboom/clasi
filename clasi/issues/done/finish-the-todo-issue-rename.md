---
status: done
---

# Finish the TODO → issue rename

## Context

Sprint 015 renamed the CLASI artifact concept from "TODO" to "issue." The rename was supposed to be a hard cut, no aliases. It landed roughly **70% complete** — the high-visibility surface (class names, MCP tool names, CLI subcommands, skill names, frontmatter fields on tickets) was renamed, but a lot of less-visible identifier names, docstring prose, agent instructions, and documentation still use "TODO" as the artifact noun.

An audit of the source code on master (post sprints 015–022) confirms residual references in three categories:

1. **Pragmatic aliases keeping the old MCP working.** Hook handler registry keys (`plan-to-todo`, `codex-plan-to-todo`) and CLI deprecated aliases. These exist because the currently-running MCP server is pinned at `0.20260502.2` (older code that exposes `list_todos` and `move_todo_to_done`). Once the user upgrades the pinned install, these can be removed. **Out of scope for this work** — handled separately when the pin moves.

2. **Genuine incomplete rename.** Parameter names, variable names, docstring prose, agent prose, README references, frontmatter schema examples in software-engineering.md. Not forced by backward-compat — just unfinished from sprint 015. This is what the new sprint addresses.

3. **Test artifacts.** Class and method names like `TestHandlePlanToTodo`, `test_todo_moves_to_in_progress_not_done`. Lower priority but should be cleaned up in the same sprint to avoid the cleanup being half-done twice.

## Outcome of the future sprint

After it lands:

- No production-code identifier (parameter, variable, function, class, module) contains `todo` as a name component, unless it's intentionally an alias for backward-compat with the old MCP.
- No docstring or agent-prompt prose uses "TODO" as the artifact noun.
- No documentation file (README, SE-overview, software-engineering instructions) describes the artifact as "TODO."
- Test class names and method names follow the new vocabulary.
- The `softwareware-engineering.md` schema example shows `issue:` / `completes_issue:` consistently with the actual `ticket.md` template.

## Action: capture as a CLASI TODO

The plan is to write a TODO at `docs/clasi/todo/finish-todo-to-issue-rename.md` capturing the audit findings. When picked up for sprint planning, the resulting sprint implements the cleanup.

## Locked-in scope

### In scope

**Python identifiers (production code, not tests)**

- `clasi/plan_to_issue.py`: rename `todo_dir` parameter → `issue_dir` (two functions: `plan_to_issue`, `plan_to_issue_from_text`). Update callers in `clasi/cli.py` and `clasi/hook_handlers.py`. Local `todo_dir.mkdir()` calls follow.
- `clasi/sprint.py`: rename `todo` parameter on `create_ticket` → `issue`. Rename local `sprint_todos` variable → `sprint_issues`.
- `clasi/tools/artifact_tools.py`: rename `todo` parameter on the `create_ticket` MCP-tool wrapper → `issue`. Rename local variables `completed_todos`, `moved_todos`, `unresolved_todos` → `completed_issues`, `moved_issues`, `unresolved_issues`. The `moved_todos` / `unresolved_todos` keys in the close-sprint result JSON are also renamed; this is a small public-API change but consistent with the "hard rename" policy.

**Docstring prose**

- `clasi/issue.py:15` — class docstring still says `docs/clasi/todo/`. Update to `<sprint>/issues/` or `.clasi/issues/` depending on the new model.
- `clasi/plan_to_issue.py:33` — "Copy a plan file to the TODO directory" → "issue directory."
- `clasi/hook_handlers.py:858, 863, 867, 894, 915` — five docstring/prose locations using "TODO" as the artifact noun. Replace with "issue."

**Agent prose**

- `clasi/plugin/agents/sprint-planner/plan-sprint.md:56-57` — "For each TODO claimed by this sprint…" → "For each issue claimed…"
- `clasi/plugin/agents/sprint-planner/create-tickets.md:35-36` — "Propagate TODO and GitHub issue references" — rename the CLASI-side "TODO" to "issue"; the "GitHub issue" part stays (different system).
- `clasi/plugin/agents/team-lead/agent.md:42-44` — "If TODOs exist, read them and produce impact assessments." Update to "issues."

**Documentation**

- `clasi/plugin/instructions/software-engineering.md:211-212` — frontmatter example shows `todo:` and `completes_todo:`. Update to `issue:` and `completes_issue:`.
- `clasi/plugin/instructions/software-engineering.md:229-230` — field reference table mentions `todo` and `completes_todo` and "Controls whether linked TODOs are archived." Update all three.
- `README.md:44, 117, 142, 162` — four references to old skill name (`/todo`) and old hook name (`codex-plan-to-todo`) in prose. The skill name should be `/issue`; the hook should be `codex-plan-to-issue`. Where the README documents the *deprecated alias* explicitly, mark it as deprecated rather than removing.
- `clasi/plugin/skills/se/SKILL.md:22, 25` — "Import GitHub issues as TODOs" → "as issues"; "Enter plan mode for a discussed TODO" → "issue."

**Tests**

- `tests/unit/test_hook_handlers.py` — rename test classes `TestHandlePlanToTodo`, `TestHandleCodexPlanToTodo` → `TestHandlePlanToIssue`, `TestHandleCodexPlanToIssue`. Update test method names that say `test_*_todo_*` to `test_*_issue_*`.
- `tests/unit/test_issue_tools.py:285` — `test_todo_moves_to_in_progress_not_done` → `test_issue_moves_to_in_progress_not_done`.
- `tests/unit/test_plan_to_issue.py` — audit test class/method names; rename remaining `todo` → `issue`.
- `tests/unit/test_issue_lifecycle.py` — audit and rename.

### Out of scope

- **Hook handler aliases** (`handle_plan_to_todo`, `handle_codex_plan_to_todo`) at `clasi/hook_handlers.py:890, 926`. Keep — required for backward compatibility with the pinned old MCP server. These get removed in a separate cleanup once the pinned MCP version moves.
- **CLI deprecated aliases** at `clasi/cli.py:274-276, 295-297`. Keep — already correctly labeled as deprecated.
- **Hook registry keys** `"plan-to-todo"` and `"codex-plan-to-todo"` at `clasi/hook_handlers.py:980, 982`. Keep — pinned-MCP compatibility.
- **Path strings referring to `docs/clasi/todo/`**. These remain in code only because this repo's own artifacts are still at the old path (the `.clasi/` self-migration was deferred). Once the self-migration runs, these go away naturally. Don't update them in this sprint.
- **Sprint-level rename of historical artifacts** in `docs/clasi/sprints/done/**`. Archives don't get mutated.

## Acceptance criteria for the future sprint

- `grep -rn "\\btodo\\b" clasi/ tests/ README.md` returns no hits other than:
  - Backward-compat aliases at hook_handlers.py:890, 926, 980, 982
  - CLI alias block at cli.py:274-276, 295-297
  - Path strings referring to `docs/clasi/todo/` (deferred to self-migration)
  - Generic Python `# TODO:` comments unrelated to the CLASI artifact concept
- Existing tests still pass after identifier renames.
- The `moved_todos` / `unresolved_todos` keys in `close_sprint` JSON output are now `moved_issues` / `unresolved_issues`. Callers updated (likely just tests and the team-lead agent prompt).
- README's `/todo` reference is removed or marked deprecated; new `/issue` is documented.
- software-engineering.md's frontmatter example matches the actual `ticket.md` template.

## Why this is a TODO, not a direct fix now

The original sprint 015 was supposed to do this work. A second pass to finish it deserves its own sprint because:

- The `create_sprint` tool's `todo` parameter is part of the MCP tool surface. Renaming it changes the schema the pinned MCP version doesn't see, but the *next* pinned version will. Coordinating this with the MCP-pin upgrade is sprint-shaped, not session-shaped.
- The `moved_todos` / `unresolved_todos` JSON keys are also part of the MCP tool output schema — same coordination concern.
- ~30 files touched across three packages; running the test suite per intermediate state is sprint workflow.

## Files to read for context (when planning the future sprint)

- `clasi/plan_to_issue.py` — parameter `todo_dir`
- `clasi/sprint.py:198, 209` — `todo` kwarg, `sprint_todos` local
- `clasi/tools/artifact_tools.py:450, 723, 741, 827, 845` — kwarg + locals + JSON output keys
- `clasi/hook_handlers.py:858-915, 890, 926, 980-982` — prose + aliases + registry keys
- `clasi/issue.py:15` — class docstring
- `clasi/plugin/agents/sprint-planner/plan-sprint.md`, `create-tickets.md` — agent prose
- `clasi/plugin/agents/team-lead/agent.md:42-44` — agent prose
- `clasi/plugin/instructions/software-engineering.md:211-212, 229-230` — frontmatter schema example
- `README.md:44, 117, 142, 162` — user docs
- `clasi/plugin/skills/se/SKILL.md:22, 25` — skill prose
- `tests/unit/test_hook_handlers.py`, `test_issue_tools.py:285`, `test_plan_to_issue.py`, `test_issue_lifecycle.py` — test class / method names

## Verification (when the future sprint runs)

- After all renames: full test suite green.
- `grep -rn "\\btodo\\b" clasi/ README.md` and inspect: every remaining hit should be on the out-of-scope list (aliases, path strings, generic `# TODO:`).
- Smoke: `clasi tool plan-to-issue …` still works; deprecated `clasi tool plan-to-todo …` still works with deprecation notice.
- The `close_sprint` MCP result JSON has the renamed keys (verify by close-sprinting a synthetic sprint and inspecting return value).
