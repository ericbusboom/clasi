---
sprint: "012"
status: final
---
<!-- CLASI: Before changing code or making plans, review the SE process in CLAUDE.md -->

# Architecture Update — Sprint 012: State-machine path consistency

## What Changed

This sprint resolves the split between the write side and read side of CLASI artifact paths. The write side (`project.py`, `sprint.py`, MCP tools) consistently uses `.clasi/` with slugged directory names. The read side (state-machine predicates) still uses hardcoded `docs/clasi/` with bare-ID names. After this sprint, both sides derive paths from the same `Project` / `Sprint` model objects.

### Module-level changes

**`clasi/project.py` — `Project.design_dir`**
- Was: `return self._root / "docs" / "design"` (points away from `.clasi/`)
- Now: `return self.clasi_dir / "design"` (`.clasi/design/`)
- Boundary: single source of truth for the design-documents root. Every consumer of `design_dir` automatically follows the canonical location.

**`clasi/status/reader.py` — `ClasiStateReader`**
- Adds: `overview_exists() -> bool` — returns `(self._project.design_dir / "overview.md").exists()`
- No other method changes. The new method derives its path from `project.design_dir`, so changing that property propagates here automatically.

**`clasi/state_machine/context.py` — `StateReader` protocol and `NullStateReader`**
- Adds: `overview_exists() -> bool` to the `StateReader` Protocol (required for structural satisfaction).
- Adds: `overview_exists() -> bool: return False` to `NullStateReader` (safe default for tests).

**`clasi/state_machine/predicates/project.py` — overview predicates**
- `is_overview_present` / `is_overview_absent`: replace `ctx.reader.file_exists("docs/clasi/overview.md")` with `ctx.reader.overview_exists()`.
- Module docstring: remove stale reference to `docs/clasi/overview.md`.

**`clasi/state_machine/predicates/sprint.py` — sprint artifact predicates**
- `is_sprint_doc_present`, `is_architecture_present`, `is_usecases_present`, `is_close_report_present`:
  - Replace hardcoded `f"docs/clasi/sprints/{ctx.sprint_id}/..."` with `ClasiStateReader`-native path resolution (via `sprint.sprint_dir / filename`).
  - Implementation: the predicates call `ctx.reader.file_exists()` with a path derived from `project.get_sprint(sprint_id).sprint_dir`, which already performs the ID-prefix glob (`<id>-*`).
  - `usecases.md` (no hyphen) replaces `use-cases.md` in `is_usecases_present`.

**`clasi/state_machine/predicates/ticket.py` — ticket artifact predicates**
- `is_ticket_file_present`:
  - Replace hardcoded `docs/clasi/sprints/{sprint_id}/tickets/{ticket_id}.md` with resolution through `ClasiStateReader._find_ticket_path(sprint_id, ticket_id)`, which already performs the slug-aware glob.
  - The predicate can now call a new reader method `ticket_file_present(sprint_id, ticket_id) -> bool` that delegates to `_find_ticket_path`.

**`clasi/status/reader.py` — `ticket_file_present` helper** (new method)
- `ticket_file_present(sprint_id, ticket_id) -> bool` — returns `self._find_ticket_path(sprint_id, ticket_id) is not None`. Exposes the already-correct `_find_ticket_path` logic as a protocol-visible method.

**`clasi/state_machine/context.py` — `StateReader` protocol**
- Adds: `ticket_file_present(sprint_id: str, ticket_id: str) -> bool` to the Protocol.
- Adds: `ticket_file_present` stub to `NullStateReader` (returns `False`).

**Sprint vocabulary reconciliation**
- `clasi/plugin/agents/sprint-planner/dispatch-template.md.j2` line 55: `planning_docs` → `planning-docs` (hyphen, matching the DB phase string).
- `clasi/plugin/agents/sprint-planner/contract.yaml` line 58: same fix.
- `clasi/plugin/agents/sprint-planner/plan-sprint.md`: audit for any remaining `planning_docs` underscored references.
- Note: the DB (`state_db_class.py`) already accepts `planning-docs` (hyphenated) as a valid phase. The sprint state machine YAML (`schemas/state-machines/sprint.yaml`) uses a separate vocabulary (`open/planned/pre-flight/ticketed/...`) that drives `get_status` inconsistency reporting. Reconciliation target: the sprint.md frontmatter `status` field should reflect the DB phase rather than a third independent vocabulary.

**Stale doc/skill references**
- `clasi/plugin/skills/plan-sprint/SKILL.md` lines 24, 71: `docs/clasi/design/` → `.clasi/design/`.
- `docs/design/state-machines.md` lines 148-150, 166: `docs/clasi/overview.md` → `.clasi/design/overview.md`.
- `README.md` line 300: `docs/design/overview.md` → `.clasi/design/overview.md`.

**Repository self-consistency (`git mv`)**
- `docs/design/overview.md` → `.clasi/design/overview.md`
- `docs/design/specification.md` → `.clasi/design/specification.md`
- `docs/design/usecases.md` → `.clasi/design/usecases.md`
- `docs/design/state-machines.md` and `docs/design/worktree-process.md` remain in place (design documentation, not the CLASI artifact triad).

**Tests**
- `tests/unit/test_project.py:30` — assert `design_dir == tmp_path / ".clasi" / "design"`.
- `tests/unit/test_state_machine/test_predicates.py` — `TestIsOverviewPresent` / `TestIsOverviewAbsent`: switch from `file_exists=True/False` to `overview_exists=True/False`; add `reader.overview_exists.return_value = False` to `_mock_reader` defaults; add `reader.ticket_file_present.return_value = False` default.
- `tests/unit/test_status/test_reader.py` — add `test_overview_exists_true` and `test_overview_exists_false`; add `test_ticket_file_present_true` and `test_ticket_file_present_false`.
- New integration test `tests/unit/test_state_machine/test_predicate_path_agreement.py` — creates real sprint and ticket directories in `tmp_path`, constructs `ClasiStateReader`, asserts all relevant predicates return True.

## Why

The write side was migrated from `docs/clasi/` to `.clasi/` (with slugged names) in a previous sprint, but the predicate/reader layer was not updated in the same commit. This left the state machine permanently unable to see the artifacts it creates, blocking all transitions. (See issues gh-16, gh-17, gh-18, and the detailed plan in `fix-clasi-overview-path-mismatch-project-reads-as-uninitialized.md`.)

The design principle enforced here: **predicates must derive paths through the same `Project` / `Sprint` model the writers use.** Hardcoded path strings are replaced by property-chain traversal, so future path changes to the model propagate automatically to both layers.

## Impact on Existing Components

```mermaid
graph TD
    Project["Project\n(project.py)"] -->|design_dir| DesignDir[".clasi/design/"]
    ClasiStateReader["ClasiStateReader\n(status/reader.py)"] -->|_project.design_dir| Project
    ClasiStateReader -->|overview_exists()| DesignDir
    ClasiStateReader -->|ticket_file_present()| SprintModel["Sprint\n(sprint.py)"]
    SprintModel -->|sprint_dir, tickets_dir| SluggedPaths[".clasi/sprints/<id>-<slug>/"]

    StateReaderProtocol["StateReader Protocol\n(context.py)"] -.->|satisfies| ClasiStateReader
    NullStateReader["NullStateReader\n(context.py)"] -.->|satisfies| StateReaderProtocol

    ProjPredicates["predicates/project.py"] -->|overview_exists()| StateReaderProtocol
    SprintPredicates["predicates/sprint.py"] -->|file_exists() via sprint_dir| StateReaderProtocol
    TicketPredicates["predicates/ticket.py"] -->|ticket_file_present()| StateReaderProtocol
```

**Dependency direction** (correct, no cycles):
- Predicates → StateReader Protocol → ClasiStateReader → Project/Sprint model
- Project.design_dir is a leaf; nothing in the predicate layer imports it directly.

**Interface changes:**
- `StateReader` protocol gains two methods: `overview_exists()` and `ticket_file_present()`. Both `ClasiStateReader` and `NullStateReader` are updated. Any third-party `StateReader` implementation must add these two methods — a minor but necessary breaking change to the protocol.
- `Project.design_dir` property return value changes: any code that depended on `docs/design/` will now get `.clasi/design/`. The only current consumer is the reader added in this sprint.

**Sprint predicate path resolution detail:**
The sprint predicates currently call `ctx.reader.file_exists(hardcoded_path)`. After this sprint they call `ctx.reader.file_exists(relative_path)` where the relative path is computed by the reader from `self._project.get_sprint(sprint_id).sprint_dir`. This keeps predicates as pure protocol callers — the path derivation logic lives entirely in `ClasiStateReader`, not in the predicate functions.

## Migration Concerns

**`git mv` must run before `get_status` is called in the clasi repo** — after merging this sprint, running `get_status` before performing the `git mv` will show the project still as `uninitialized` (no overview at either the old or new path). The `git mv` of the design-artifact triad is a required post-merge step in this repo.

No database migration is needed — phase values in the SQLite DB are string literals and are unaffected.

No schema migration — the sprint state machine YAML is documentation/validation, not runtime-enforced; the `state_drift` inconsistency from vocabulary mismatch disappears once the sprint.md `status` field (and the planner docs that set it) align with the DB phase string `planning-docs`.

## Design Rationale

**Decision: add `overview_exists()` to the protocol rather than passing a path through `file_exists()`.**
- Context: two options — (A) fix the hardcoded path in the predicate (`file_exists(".clasi/design/overview.md")`), or (B) add a semantic method to the protocol.
- Alternatives: Option A is simpler but re-introduces a hardcoded string in the predicate layer, deferring the drift problem. It also means tests must simulate a real path rather than using a named mock.
- Why this choice: Option B keeps predicates free of path knowledge. The path derivation belongs in `ClasiStateReader` where `self._project` is available. Tests become more readable (`reader.overview_exists.return_value = True` vs. mocking `file_exists` with a specific path).
- Consequences: `StateReader` protocol grows two methods. Future sprint implementations of the protocol must add stubs.

**Decision: add `ticket_file_present()` to the protocol rather than exposing `_find_ticket_path`.**
- Context: `_find_ticket_path` already implements slug-aware ticket discovery correctly. The predicate was bypassing it entirely.
- Why this choice: wrapping `_find_ticket_path` in a protocol-visible method maintains the same encapsulation pattern as `overview_exists`. The predicate layer never needs to know about globs or frontmatter reads.

**Decision: fix sprint predicate path resolution through `reader.file_exists()` with a derived path (not a new protocol method per sprint artifact).**
- Context: sprint predicates check four distinct artifacts (`sprint.md`, `architecture-update.md`, `usecases.md`, `close-report.md`). Adding four new protocol methods would be verbose.
- Why this choice: the sprint dir is a stable concept (`Project.get_sprint(sprint_id).sprint_dir`). The reader derives the path internally and passes a relative-path string to `file_exists`. This is a smaller protocol surface than four new methods.

## Open Questions

None. All decisions above are confirmed by the stakeholder (see `fix-clasi-overview-path-mismatch-project-reads-as-uninitialized.md`).
