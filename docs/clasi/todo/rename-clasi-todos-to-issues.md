---
status: pending
---

# Rename CLASI TODOs to issues

Rename the CLASI "TODO" concept to "issue" — the user-facing name for any proposed change to the system (covers TODOs, bugs, enhancements, tasks). The new term aligns with GitHub Issues. Tickets remain unchanged and continue to mean "steps that implement a change within a sprint."

Documentation must make this distinction explicit: an **issue** is a proposed change to the system; a **ticket** is a step in implementing one.

## Decisions already locked in (do not re-ask)

1. **Directory rename**: `docs/clasi/todo/` → `docs/clasi/issues/` (with `in-progress/` and `done/` subdirs preserved). The on-disk migration of existing CLASI projects is **not** part of this work — it will be folded into the separate planned initiative that moves `docs/clasi/` → `.clasi/`. This sprint changes the code/templates/docs to use the new directory name; the umbrella `.clasi/` migration handles moving real artifacts.

2. **Public API**: hard rename, no deprecated aliases.
   - MCP tools: `list_todos` → `list_issues`, `move_todo_to_done` → `move_issue_to_done`
   - CLI: `clasi tool plan-to-todo` → `clasi tool plan-to-issue`, `--todo-dir` → `--issues-dir`
   - Skill: `/todo` → `/issue`
   - Hook handler keys: `plan-to-todo`, `codex-plan-to-todo` → `plan-to-issue`, `codex-plan-to-issue`

3. **Ticket frontmatter rename**:
   - `todo:` → `issue:` (links a ticket to its source issue file)
   - `completes_todo:` → `completes_issue:` (and any per-filename mapping form)
   - Old tickets in `done/` sprints keep their old field names — those archives are not mutated.

4. **Status enum collision fix**: tickets currently have `status: todo` meaning "not yet started." Rename that status value to `status: open` (matches GitHub-issue terminology). The full enum becomes `open / in-progress / done`. Update template, validation, hook handlers, every test fixture, and any agent prompt that mentions the old value.

## Surface area to update (from a fresh code map; treat as starting checklist, not exhaustive)

**Python source — symbols and modules**
- Rename `clasi/todo.py` → `clasi/issue.py`; class `Todo` → `Issue`; all instance methods (`move_to_in_progress`, `move_to_done`, `add_ticket_ref`) keep their names.
- `clasi/plan_to_todo.py` → `clasi/plan_to_issue.py`; functions `plan_to_todo` and `plan_to_todo_from_text` → `plan_to_issue` / `plan_to_issue_from_text`.
- `clasi/project.py`: `todo_dir` → `issues_dir`; `get_todo` → `get_issue`; `list_todos` → `list_issues`. Internal path: `docs/clasi/todo/` → `docs/clasi/issues/`.
- `clasi/ticket.py`: `todo_ref` property → `issue_ref`; `completes_todo_for(filename)` → `completes_issue_for(filename)`; reads of frontmatter keys updated.

**MCP tools** — `clasi/tools/artifact_tools.py`
- `list_todos()` → `list_issues()`
- `move_todo_to_done()` → `move_issue_to_done()`

**Skills**
- `clasi/plugin/skills/todo/` → `clasi/plugin/skills/issue/`; SKILL.md `name: todo` → `name: issue`; description updated to "Create an issue file…"
- `clasi/plugin/skills/gh-import/SKILL.md` description: "Import GitHub issues as CLASI TODOs" → "Import GitHub issues as CLASI issues" (the term collision is fine; the skill's behavior is unchanged).

**CLI** — `clasi/cli.py`
- `@tool.command("plan-to-todo")` → `"plan-to-issue"`
- `--todo-dir` option → `--issues-dir`, default `"docs/clasi/issues"`

**Hook handlers** — `clasi/hook_handlers.py`
- `handle_codex_plan_to_todo` / `handle_plan_to_todo` → `handle_codex_plan_to_issue` / `handle_plan_to_issue`
- Hook registry keys `plan-to-todo`, `codex-plan-to-todo` → `plan-to-issue`, `codex-plan-to-issue`
- Path constants `Path("docs/clasi/todo")` → `Path("docs/clasi/issues")` everywhere they appear.

**Platform installers** — `clasi/platforms/codex.py`
- `_build_todo_dir_content()` → `_build_issues_dir_content()`
- File written: `docs/clasi/todo/AGENTS.md` → `docs/clasi/issues/AGENTS.md`
- `clasi/platforms/copilot.py`: glob `docs/clasi/todo/**` → `docs/clasi/issues/**`
- `clasi/platforms/claude.py`: same glob update.

**Templates** — `clasi/templates/`
- `ticket.md`: `status: todo` → `status: open`; `todo: ""` → `issue: ""`; `completes_todo` → `completes_issue` (block comment updated to match).
- Any other template referencing old terms.

**Init command** — `clasi/init_command.py`
- Creates `docs/clasi/issues/` (with `in-progress/` and `done/` subdirs) instead of `todo`.

**Rules and instructions**
- `.claude/rules/todo-dir.md` → `.claude/rules/issues-dir.md` (path glob updated, body retitled). Also installer-side templates that generate this file.
- `.claude/rules/clasi-artifacts.md`: term updates.
- `.github/instructions/todo-dir.instructions.md` → `issues-dir.instructions.md`.
- `.github/instructions/clasi-artifacts.instructions.md`: term updates.

**Agent prompts** — `.claude/agents/team-lead/`, `.claude/agents/sprint-planner/`
- Every reference to "TODO" as the artifact name → "issue."
- Every reference to `status: todo` → `status: open`.

**SE-overview, project doc**
- `clasi/se-overview-template.md`, `README.md`, `clasi/plugin/instructions/software-engineering.md`: explain the **issue vs ticket** distinction explicitly:
  > **Issue** — a proposed change to the system (a TODO, bug, enhancement, or task). Lives in `docs/clasi/issues/`.
  > **Ticket** — a step within a sprint that implements an issue (or part of one). Lives in `docs/clasi/sprints/<sprint>/tickets/`.

**Tests**
- Rename test files: `test_todo.py` → `test_issue.py`, `test_todo_lifecycle.py` → `test_issue_lifecycle.py`, `test_todo_tools.py` → `test_issue_tools.py`, `test_plan_to_todo.py` → `test_plan_to_issue.py`.
- Update `test_hook_handlers.py`, `test_platform_codex.py`, `test_init_command.py`, `test_sprint.py`, `test_ticket.py`, `test_agent.py`, `tests/system/test_artifact_tools.py` for new symbol/path names.
- Update fixtures that hardcode `status: todo`, `docs/clasi/todo/`, `todo:` / `completes_todo:` frontmatter.

## Not in scope

- **Migrating real `docs/clasi/todo/` content in existing CLASI projects** — the `.clasi/` umbrella migration owns this.
- **Backward-compat shims, deprecation warnings, dual reads** — hard rename per the locked-in decision.

## Acceptance criteria

- `grep -rn "todo" clasi/ tests/ .claude/ .agents/ docs/ AGENTS.md README.md` returns zero references to the old CLASI artifact concept (Python `# TODO:` comments and unrelated third-party usages may remain — flag them in review).
- All MCP tools, CLI subcommands, and skills work under their new names.
- `clasi install` on a fresh target creates `docs/clasi/issues/` (not `todo/`).
- Full test suite passes.
- `README.md` and the SE-overview template each contain a clearly-headed "Issues vs Tickets" paragraph.
