---
status: approved
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Sprint 003 Use Cases

## SUC-001: Production identifiers use issue vocabulary
Parent: (none — cross-cutting vocabulary)

- **Actor**: Developer reading or maintaining production Python code
- **Preconditions**: The codebase contains Python parameters and variables named with the old `todo` vocabulary (`todo_dir`, `todo`, `sprint_todos`, `completed_todos`, `moved_todos`, `unresolved_todos`)
- **Main Flow**:
  1. Developer opens any file in `clasi/` and reads function signatures or local variables
  2. Every identifier related to the CLASI artifact concept reads `issue` (not `todo`)
  3. Callers in `cli.py` and `hook_handlers.py` pass the renamed keyword arguments
- **Postconditions**: No production-code identifier contains `todo` as a name component except intentional backward-compat aliases
- **Acceptance Criteria**:
  - [ ] `plan_to_issue` and `plan_to_issue_from_text` parameters renamed from `todo_dir` to `issue_dir`
  - [ ] `Sprint.create_ticket` parameter renamed from `todo` to `issue`; local `sprint_todos` → `sprint_issues`
  - [ ] `artifact_tools.create_ticket` wrapper parameter and locals renamed (`completed_todos` → `completed_issues`, `moved_todos` → `moved_issues`, `unresolved_todos` → `unresolved_issues`)
  - [ ] JSON output keys `moved_todos` / `unresolved_todos` in `close_sprint` renamed to `moved_issues` / `unresolved_issues`
  - [ ] All callers updated to pass renamed keyword arguments

## SUC-002: Docstring prose uses issue vocabulary
Parent: (none)

- **Actor**: Developer reading docstrings or IDE hover text
- **Preconditions**: Several docstrings in `clasi/` describe the artifact as "TODO"
- **Main Flow**:
  1. Developer hovers over a function or class in their IDE
  2. The docstring text reads "issue" wherever it refers to the CLASI artifact concept
- **Postconditions**: No docstring in scope files uses "TODO" as the artifact noun
- **Acceptance Criteria**:
  - [ ] `Issue` class docstring (`issue.py:15`) updated from `docs/clasi/todo/` reference
  - [ ] `plan_to_issue` docstring (`plan_to_issue.py:33`) updated from "TODO directory" to "issue directory"
  - [ ] Five docstring / prose locations in `hook_handlers.py` (lines 858, 863, 867, 894, 915) updated to use "issue"

## SUC-003: Agent instruction prose uses issue vocabulary
Parent: (none)

- **Actor**: Agent reading its own instructions at runtime
- **Preconditions**: Agent `.md` instruction files contain "TODO" as the artifact noun
- **Main Flow**:
  1. Sprint-planner or team-lead agent loads its instruction file
  2. Prose refers to "issue" consistently when describing CLASI artifacts
- **Postconditions**: No agent instruction file uses "TODO" as the artifact noun in scope lines
- **Acceptance Criteria**:
  - [ ] `plan-sprint.md:56-57` updated from "For each TODO claimed" to "For each issue claimed"
  - [ ] `create-tickets.md:44-46` updated from "Propagate TODO and GitHub issue references" / "set the ticket's `todo` frontmatter field to the TODO filename"
  - [ ] `agent.md:42-44` updated from "If TODOs exist, read them" to "If issues exist"

## SUC-004: Documentation uses issue vocabulary
Parent: (none)

- **Actor**: User reading README or the SE process instructions
- **Preconditions**: `README.md` and `software-engineering.md` reference old skill names, hook names, and frontmatter field names
- **Main Flow**:
  1. User reads documentation to understand the CLASI workflow
  2. All skill references show `/issue`, all hook references show `codex-plan-to-issue`, all frontmatter examples show `issue:` / `completes_issue:`
- **Postconditions**: Documentation is consistent with the live vocabulary; deprecated references are marked deprecated
- **Acceptance Criteria**:
  - [ ] `software-engineering.md:211-212` frontmatter example updated to `issue:` and `completes_issue:`
  - [ ] `software-engineering.md:229-230` field reference table updated (`todo` → `issue`, `completes_todo` → `completes_issue`, description prose updated)
  - [ ] `README.md:44, 117, 142, 162` updated (`/todo` → `/issue`, `codex-plan-to-todo` → `codex-plan-to-issue`; deprecated aliases marked as deprecated)
  - [ ] `se/SKILL.md:22, 25` updated from "Import GitHub issues as TODOs" and "plan mode for a discussed TODO"

## SUC-005: Test names use issue vocabulary
Parent: (none)

- **Actor**: Developer running or reading the test suite
- **Preconditions**: Test class names, method names, and fixture names use the old `todo` vocabulary
- **Main Flow**:
  1. Developer runs or reads unit tests
  2. Test class and method names follow the `issue` vocabulary
- **Postconditions**: No test class or method name uses `todo` as a name component in the audit scope
- **Acceptance Criteria**:
  - [ ] `test_hook_handlers.py`: `TestHandlePlanToTodo` → `TestHandlePlanToIssue`, `TestHandleCodexPlanToTodo` → `TestHandleCodexPlanToIssue`, `TestHandleHookCodexPlanToTodo` → `TestHandleHookCodexPlanToIssue`; `test_*_todo_*` method names updated
  - [ ] `test_issue_tools.py:285`: `test_todo_moves_to_in_progress_not_done` → `test_issue_moves_to_in_progress_not_done`
  - [ ] `test_plan_to_issue.py`: audit and rename remaining `todo` class/method names
  - [ ] `test_issue_lifecycle.py`: audit and rename all `todo`-named test methods

## SUC-006: Grep audit confirms only allowed residuals remain
Parent: (none)

- **Actor**: Developer running the acceptance grep
- **Preconditions**: All rename tickets have been completed
- **Main Flow**:
  1. Developer runs `grep -rn "\btodo\b" clasi/ tests/ README.md`
  2. Every hit is inspected
  3. Every remaining hit belongs to the out-of-scope list (backward-compat aliases, path strings, generic `# TODO:` comments)
- **Postconditions**: The codebase passes the audit with no unallowed residuals
- **Acceptance Criteria**:
  - [ ] Grep returns no hits outside the allowed set
  - [ ] Allowed residuals confirmed: `hook_handlers.py:890, 926, 980, 982`; `cli.py:274-276, 295-297`; path strings referencing `docs/clasi/todo/`; generic `# TODO:` programmer comments
  - [ ] Full test suite passes after all renames
