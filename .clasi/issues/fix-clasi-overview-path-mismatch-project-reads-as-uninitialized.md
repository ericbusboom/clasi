---
status: pending
---

# Fix CLASI overview path mismatch (project reads as uninitialized)

## Context

A downstream agent reported that CLASI projects read as `uninitialized` even
after `project-initiation` runs. Root cause: the `is_overview_present` /
`is_overview_absent` predicates hardcode `docs/clasi/overview.md`, but
initiation writes the overview to `.clasi/design/overview.md`. The two paths
never match, so the `uninitialized → planning` transition is permanently
blocked.

The hardcoded literal is stale — it dates to sprint 005
([commit 2b21ca6](clasi/state_machine/predicates/project.py)) and was never
updated when sprint 015 ([commit 0cd35cd](clasi/project.py#L46-L49)) moved
design docs. Investigation found **four** competing conventions across the
codebase (`.clasi/design/`, `docs/design/`, `docs/clasi/`, `docs/clasi/design/`),
none of which agree with the predicate.

**Decisions (confirmed with stakeholder):**
1. Canonical home for design docs = **`.clasi/design/`** (already the dominant
   convention in README, `project-initiation`, `project-status`,
   `sprint-roadmap`, `architecture-authoring`, `sprint-planner`).
2. Predicates must **derive the path from `Project.design_dir`** (single source
   of truth) rather than a hardcoded string, so this drift cannot recur.

**Outcome:** initiation, the predicates, `Project.design_dir`, and the docs all
agree on `.clasi/design/`; a freshly-initiated project transitions to
`planning` correctly, and the clasi repo itself initializes cleanly.

## Key facts established

- `ClasiStateReader.file_exists(path)` resolves `project.root / path`
  ([reader.py:73-81](clasi/status/reader.py#L73-L81)) and holds the `Project`
  via `self._project` — so the reader can derive the canonical path.
- `Project.design_dir` is referenced nowhere else in code (only its own
  definition), so changing it is low-risk.
- Skills are triplicated; **`clasi/plugin/skills/` is the source of truth** —
  `.claude/skills/` and `.agents/skills/` are installer-generated copies
  ([claude.py](clasi/platforms/claude.py#L237) / [codex.py](clasi/platforms/codex.py#L212)).
  Only edit the `clasi/plugin/` copies.

## Changes

### 1. Single source of truth for the design dir — `clasi/project.py`
Change `design_dir` ([project.py:46-49](clasi/project.py#L46-L49)) to:
```python
@property
def design_dir(self) -> Path:
    """.clasi/design/ — overview, specification, usecases."""
    return self.clasi_dir / "design"
```

### 2. New reader method `overview_exists()` (derives from `design_dir`)
- Add to the `StateReader` protocol
  ([context.py:35](clasi/state_machine/context.py#L35) area):
  `def overview_exists(self) -> bool: ...`
- Implement in `ClasiStateReader` ([reader.py](clasi/status/reader.py)):
  ```python
  def overview_exists(self) -> bool:
      """True iff the project overview exists at the canonical design path."""
      return (self._project.design_dir / "overview.md").exists()
  ```
- Add to `NullStateReader` ([context.py:150](clasi/state_machine/context.py#L150)
  area): `def overview_exists(self) -> bool: return False`

### 3. Predicates derive via the reader — `clasi/state_machine/predicates/project.py`
Replace the hardcoded literals ([lines 27-36](clasi/state_machine/predicates/project.py#L27-L36)):
```python
@predicate("is_overview_absent")
def is_overview_absent(ctx: ProjectContext) -> bool:
    """Return True iff the project overview is absent."""
    return not ctx.reader.overview_exists()

@predicate("is_overview_present")
def is_overview_present(ctx: ProjectContext) -> bool:
    """Return True iff the project overview exists."""
    return ctx.reader.overview_exists()
```
Also fix the stale module docstring reference (`docs/clasi/overview.md`,
[line 13](clasi/state_machine/predicates/project.py#L13)).

### 4. Align the straggler docs/skills on `.clasi/design/`
- `clasi/plugin/skills/plan-sprint/SKILL.md` — `docs/clasi/design/` → `.clasi/design/` (lines 24, 71).
- `docs/design/state-machines.md` — predicate/action descriptions
  (lines 148-150, 166) `docs/clasi/overview.md` → `.clasi/design/overview.md`
  (this is the reconciliation the doc's line 86 anticipates).
- `README.md:300` — `docs/design/overview.md` → `.clasi/design/overview.md`.
- *Out of scope (note only):* legacy `clasi/schemas/se-process/schema.yaml`
  and archived `clasi/plugin/agents/old/*`; the separate
  `worktree-process.md` reference in `execute-sprint`.

### 5. Make the clasi repo self-consistent
`git mv` the artifact triad so the repo initializes under the new predicate:
- `docs/design/overview.md` → `.clasi/design/overview.md`
- `docs/design/specification.md` → `.clasi/design/specification.md`
- `docs/design/usecases.md` → `.clasi/design/usecases.md`

Leave `docs/design/state-machines.md` and `docs/design/worktree-process.md` in
place — they are design documentation, not the CLASI artifact triad.

### 6. Tests
- `tests/unit/test_project.py:30` — assert `design_dir == tmp_path / ".clasi" / "design"`.
- `tests/unit/test_state_machine/test_predicates.py` (lines 122-147) — switch
  the four overview cases from `file_exists=True/False` to
  `overview_exists=True/False`; add `reader.overview_exists.return_value = False`
  to `_mock_reader` defaults ([line ~109](tests/unit/test_state_machine/test_predicates.py#L84-L109)).
- `tests/unit/test_status/test_reader.py` — add a test for the new
  `overview_exists()` (true when `.clasi/design/overview.md` exists, false
  otherwise). Existing generic `file_exists` test (lines 134-136) can stay.

## Process

This is a small, well-scoped bugfix to CLASI's own source. Recommended path:
run it **out-of-process** (create `.clasi/oop` via the `oop` skill) rather than
spinning up a full sprint/ticket, since the bug currently blocks normal
initialization anyway. (Alternative: a one-ticket sprint if you'd rather keep
it in-process.)

## Verification

1. `pytest tests/unit/test_state_machine/test_predicates.py tests/unit/test_project.py tests/unit/test_status/test_reader.py` — green.
2. Full suite: `pytest` — no regressions.
3. End-to-end: in a scratch dir, create `.clasi/design/overview.md`, then call
   the MCP `get_status()` — project state should be `planning` (was
   `uninitialized`).
4. In the clasi repo itself (after the `git mv`), `get_status()` should no
   longer report `uninitialized` due to a missing overview.
5. After committing, `dotconfig version bump` per repo rules.
