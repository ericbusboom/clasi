---
status: done
github-issue: ericbusboom/clasi#17
sprint: '012'
---

# initialize gate checks docs/clasi/overview.md but skill writes .clasi/design/overview.md (path inconsistency strands new projects in 'uninitialized')

> Imported from [ericbusboom/clasi#17](https://github.com/ericbusboom/clasi/issues/17)
## Summary

The project-level `initialize` transition (`uninitialized → planning`) is gated by the predicate `is_overview_present`, which checks for **`docs/clasi/overview.md`**. However, the project-initiation skill, the `software-engineering.md` instructions, and the sprint-planner agent's read scope all use **`.clasi/design/overview.md`** as the canonical location. As a result, a freshly-initiated project writes its overview to the documented path but the state machine never leaves `uninitialized`.

CLASI version: `0.20260603.3` (installed via pipx).

## The inconsistency (three different paths in one release)

1. **State machine predicate — `docs/clasi/overview.md`**
   `clasi/state_machine/predicates/project.py`:
   ```python
   @predicate("is_overview_present")
   def is_overview_present(ctx: ProjectContext) -> bool:
       """Return True iff docs/clasi/overview.md exists."""
       return ctx.reader.file_exists("docs/clasi/overview.md")
   ```
   `file_exists` resolves literally against the project root (`status/reader.py`):
   ```python
   def file_exists(self, path: str) -> bool:
       return (self._project.root / path).exists()
   ```
   And `schemas/state-machines/project.yaml` agrees:
   ```yaml
   actions:
     write_overview:
       description: Generates docs/clasi/overview.md from stakeholder input. Idempotent.
   predicates:
     is_overview_present:
       description: Returns True iff docs/clasi/overview.md exists.
   ```

2. **Documented canonical location — `.clasi/design/overview.md`**
   - `plugin/instructions/software-engineering.md`:
     > ### 1. Project Overview (`.clasi/design/overview.md`) — Recommended
   - The `project-initiation` skill instructs: "write all three documents to `.clasi/design/`".
   - `plugin/agents/sprint-planner/agent.md` read scope: `.clasi/design/overview.md`.
   - `plugin/agents/sprint-planner/plan-sprint.md` inputs: `.clasi/brief.md` or `.clasi/design/overview.md` (must exist).

3. **A third path also appears** — `Project.design_dir` in `project.py` returns `docs/design/` (not `.clasi/design/` and not `docs/clasi/`), and the dispatch template references `docs/clasi/design/overview.md`. So there are effectively three or four different overview locations referenced across the codebase.

## Steps to reproduce

1. Start a new CLASI project (state `uninitialized`).
2. Run the `project-initiation` skill — it dispatches the sprint-planner, which writes `overview.md`, `specification.md`, `usecases.md` to `.clasi/design/` (per the skill's own instructions).
3. Call `get_status` / re-check project state.

## Expected

After the overview is written to the documented location, the project transitions to `planning` and `initialize` is satisfied.

## Actual

Project remains `uninitialized`; `initialize` reports `blocked_by: [is_overview_present]` because the predicate is looking at `docs/clasi/overview.md`, which the skill never creates.

## Notes

- There is no MCP tool that performs the `write_overview` action — project state is derived purely from filesystem predicates — so an agent following the skills has no sanctioned tool to satisfy the gate; it can only create the file. The skill writes it to a path the gate doesn't check.
- Suggested fix: make the predicate and the `project-initiation` skill agree on one path. Either point `is_overview_present` at `.clasi/design/overview.md` (matches the skill + instructions + sprint-planner read scope), or update the skill/instructions to write to `docs/clasi/`. Reconciling `Project.design_dir` (`docs/design/`) and the dispatch template (`docs/clasi/design/`) in the same pass would remove the remaining ambiguity.

## Workaround used

Kept the canonical docs at `.clasi/design/` and symlinked `docs/clasi -> ../.clasi/design` so the gate file `docs/clasi/overview.md` resolves. The project then transitioned to `planning`.

---
_Filed by the CLASI team-lead during project initiation of PopComicStudio._
